"""
Nuke Script Generator for Post Project Manager.
Generates fully valid, production-ready .nk scripts with configured Root settings,
Read node pointing to plates, and dual Write nodes (Hires EXR and Review MOV)
with dynamic TCL script-matching versioning and postage stamps enabled.
"""

import re
from pathlib import Path


def conform_nuke_script_write_paths(nk_path: Path) -> bool:
    """
    Inspects an existing .nk script and ensures its Write_HIRES and Write_REVIEW nodes
    use dynamic script-matching TCL expressions so rendering v002, v003, etc.
    never overwrites v001. Returns True if file was conformed and modified.
    """
    if not nk_path.exists() or nk_path.suffix.lower() != ".nk":
        return False

    try:
        content = nk_path.read_text(encoding="utf-8")
    except Exception:
        return False

    version_tcl = (
        r"\[expr \{[llength \[regexp -inline \{v\[0-9]+\} \[file tail \[value root.name]]]] > 0 ? "
        r"\[lindex \[regexp -inline \{v\[0-9]+\} \[file tail \[value root.name]]] 0] : \"v001\"\}]"
    )
    dynamic_hires = (
        rf'file "\[file dirname \[value root.name]]/../../renders/{version_tcl}/hires/'
        r'\[file rootname \[file tail \[value root.name]]].%04d.exr"'
    )
    dynamic_review = (
        rf'file "\[file dirname \[value root.name]]/../../renders/{version_tcl}/review/'
        r'\[file rootname \[file tail \[value root.name]]].mov"'
    )

    modified = False

    # Check each Write node block in Nuke script (accounting for nested braces in knob values)
    def fix_write_node(match):
        nonlocal modified
        block = match.group(0)
        if "name Write_HIRES" in block:
            # Check if file knob is not already using dynamic expression
            if "[file rootname" not in block or "renders/hires/v" in block or "_v001." in block:
                block = re.sub(r'file\s+"[^"]+"', dynamic_hires, block)
                modified = True
            if "postage_stamp true" not in block:
                block = block.rstrip().rstrip("}") + " postage_stamp true\n}"
                modified = True
        elif "name Write_REVIEW" in block:
            if "[file rootname" not in block or "_v001.mov" in block or "_v001.mp4" in block or "renders/review/" in block:
                # Retain mp4 extension if original used mp4
                if ".mp4" in block:
                    dyn_rev_mp4 = dynamic_review.replace(".mov", ".mp4")
                    block = re.sub(r'file\s+"[^"]+"', dyn_rev_mp4, block)
                else:
                    block = re.sub(r'file\s+"[^"]+"', dynamic_review, block)
                modified = True
            if "postage_stamp true" not in block:
                block = block.rstrip().rstrip("}") + " postage_stamp true\n}"
                modified = True
        return block

    new_content = re.sub(r'(\n|^)Write\s*\{.*?\n\}', fix_write_node, content, flags=re.DOTALL)

    if modified and new_content != content:
        try:
            nk_path.write_text(new_content, encoding="utf-8")
            return True
        except Exception as e:
            print(f"Warning: Failed to save conformed script {nk_path}: {e}")
    return False


def generate_nuke_script(
    project_code: str,
    sequence: str,
    shot: str,
    fps: float = 24.0,
    width: int = 1920,
    height: int = 1080,
    format_name: str = "HD_1080",
    color_management: str = "OCIO",
    ocio_config: str = "aces_1.2",
    working_space: str = "ACES - ACEScg",
    frame_start: int = 1001,
    frame_end: int = 1100,
    review_resolution: str = "Same as Project",
    review_format: str = "mov",
    review_codec: str = "Apple ProRes 422"
) -> str:
    """
    Returns the string contents of a production-ready Nuke (.nk) script.
    Uses dynamic [file dirname [value root.name]] and [file rootname [file tail [value root.name]]]
    relative expressions so the script dynamically matches script filename and versioning:
    - Renders are stored under renders/[version]/hires and renders/[version]/review
    - Configurable review resolution, format (MOV/MP4), and codec (ProRes / H.264).
    """
    # Avoid duplicate sequence prefix if shot already contains it (e.g. sq010_sh010)
    if shot.startswith(f"{sequence}_"):
        full_shot_id = shot
    else:
        full_shot_id = f"{sequence}_{shot}"

    script_name = f"{project_code}_{full_shot_id}_comp_v001.nk"
    plate_filename = f"{full_shot_id}_plate_v001.####.exr"

    # Color space configurations based on selected color management
    if color_management.upper() == "OCIO":
        color_root_block = f""" colorManagement OCIO
 OCIO_config {ocio_config}
 customOCIOConfigPath ""
 defaultLUT aces
 workingSpaceLUT "{working_space}"
 monitorLut "sRGB (ACES)"
 int8Lut "Utility - Texture - sRGB"
 int16Lut "Utility - Texture - sRGB"
 logLut "Input - Generic - Curve - LogC"
 floatLut "ACES - ACES2065-1" """
        read_colorspace = "Input - Generic - Curve - Rec.709" if "aces" in ocio_config.lower() else "default"
        hires_colorspace = working_space
        review_colorspace = "Output - Rec.709" if "aces" in ocio_config.lower() else "sRGB"
    else:
        color_root_block = """ colorManagement Nuke
 defaultLUT nuke
 workingSpaceLUT linear
 monitorLut sRGB
 int8Lut sRGB
 int16Lut sRGB
 logLut Cineon
 floatLut linear """
        read_colorspace = "default"
        hires_colorspace = "linear"
        review_colorspace = "sRGB"

    # Review Format & Codec Settings
    rev_fmt_clean = review_format.lower().strip()
    rev_ext = "mp4" if "mp4" in rev_fmt_clean else "mov"

    if rev_ext == "mp4":
        review_write_knobs = f""" file_type mp4
 colorspace "{review_colorspace}" """
    elif "proxy" in review_codec.lower():
        review_write_knobs = f""" file_type mov
 mov64_codec "Apple ProRes 422 Proxy"
 colorspace "{review_colorspace}" """
    elif "h.264" in review_codec.lower() or "h264" in review_codec.lower():
        review_write_knobs = f""" file_type mov
 mov64_codec "H.264"
 colorspace "{review_colorspace}" """
    else:
        review_write_knobs = f""" file_type mov
 mov64_codec "Apple ProRes 422"
 colorspace "{review_colorspace}" """

    # Reformat node for Review if resolution differs
    needs_reformat = False
    reformat_block = ""
    reformat_w, reformat_h = width, height
    if "half" in review_resolution.lower() or "540" in review_resolution:
        needs_reformat = True
        reformat_w, reformat_h = width // 2, height // 2
    elif "720" in review_resolution:
        needs_reformat = True
        reformat_w, reformat_h = 1280, 720
    elif "1080" in review_resolution and (width != 1920 or height != 1080):
        needs_reformat = True
        reformat_w, reformat_h = 1920, 1080

    if needs_reformat:
        reformat_block = f"""push $N_MAIN_BRANCH
Reformat {{
 inputs 1
 name Reformat_REVIEW
 format "{reformat_w} {reformat_h} 0 0 {reformat_w} {reformat_h} 1 Review_Res"
 resize width
 center true
 xpos 110
 ypos 100
}}
"""
        push_review_branch = ""
    else:
        push_review_branch = "push $N_MAIN_BRANCH"

    # TCL version extraction expression with v001 fallback
    version_tcl = (
        r"\[expr \{[llength \[regexp -inline \{v\[0-9]+\} \[file tail \[value root.name]]]] > 0 ? "
        r"\[lindex \[regexp -inline \{v\[0-9]+\} \[file tail \[value root.name]]] 0] : \"v001\"\}]"
    )

    content = f"""#! C:/Program Files/Nuke/nuke -nx
version 15.0 v1
Root {{
 inputs 0
 name "{script_name}"
 frame {frame_start}
 first_frame {frame_start}
 last_frame {frame_end}
 fps {fps}
 format "{width} {height} 0 0 {width} {height} 1 {format_name}"
 proxy_type scale
{color_root_block}
}}
BackdropNode {{
 inputs 0
 name Backdrop_INPUTS
 tile_color 0x243b24ff
 gl_color 0x243b24ff
 label "<center><font size=\\"6\\"><b>INPUT PLATES</b></font><br><font size=\\"3\\" color=\\"#81c784\\">Conform Ingest / Source Footage</font></center>"
 note_font_size 20
 note_font_color 0xffffffff
 xpos -120
 ypos -220
 bdwidth 360
 bdheight 240
 z_order -1
}}
Read {{
 inputs 0
 file_type exr
 file "\\[file dirname \\[value root.name]]/../../plates/v001/{plate_filename}"
 format "{width} {height} 0 0 {width} {height} 1 {format_name}"
 first {frame_start}
 last {frame_end}
 origfirst {frame_start}
 origlast {frame_end}
 origset true
 colorspace "{read_colorspace}"
 name Read_PLATE
 postage_stamp true
 xpos 10
 ypos -120
}}
Dot {{
 inputs 1
 name Dot_PIPE
 label "  <font color=\\"#90caf9\\">MAIN_PIPE</font>"
 note_font_size 12
 xpos 44
 ypos 20
}}
set N_MAIN_BRANCH [stack 0]
BackdropNode {{
 inputs 0
 name Backdrop_OUTPUTS
 tile_color 0x162c44ff
 gl_color 0x162c44ff
 label "<center><font size=\\"6\\"><b>OUTPUT RENDERS</b></font><br><font size=\\"3\\" color=\\"#64b5f6\\">Hires Master EXR & Review Daily Deliveries</font></center>"
 note_font_size 20
 note_font_color 0xffffffff
 xpos -160
 ypos 70
 bdwidth 440
 bdheight 290
 z_order -1
}}
Write {{
 inputs 1
 file "\\[file dirname \\[value root.name]]/../../renders/{version_tcl}/hires/\\[file rootname \\[file tail \\[value root.name]]].%04d.exr"
 file_type exr
 datatype "16 bit half"
 compression "Zip (1 scanline)"
 first {frame_start}
 last {frame_end}
 checkHashOnRead false
 colorspace "{hires_colorspace}"
 version 1
 name Write_HIRES
 tile_color 0xbf5d00ff
 note_font_color 0xffffffff
 postage_stamp true
 selected true
 xpos -90
 ypos 180
}}
{reformat_block}{push_review_branch}
Write {{
 inputs 1
 file "\\[file dirname \\[value root.name]]/../../renders/{version_tcl}/review/\\[file rootname \\[file tail \\[value root.name]]].{rev_ext}"
{review_write_knobs}
 first {frame_start}
 last {frame_end}
 checkHashOnRead false
 version 1
 name Write_REVIEW
 tile_color 0x007887ff
 note_font_color 0xffffffff
 postage_stamp true
 selected false
 xpos 110
 ypos 180
}}
"""
    return content
