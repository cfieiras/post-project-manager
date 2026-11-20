"""
Nuke Script Generator for Post Project Manager.
Generates fully valid, production-ready .nk scripts with configured Root settings,
Read node pointing to plates, and dual Write nodes (Hires EXR and Review MOV).
"""

from pathlib import Path


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
    frame_end: int = 1100
) -> str:
    """
    Returns the string contents of a production-ready Nuke (.nk) script.
    Uses dynamic [file dirname [value root.name]] relative paths so the script
    is completely portable across drives, OSs, and workstations.
    """
    
    # Avoid duplicate sequence prefix if shot already contains it (e.g. sq010_sh010)
    if shot.startswith(f"{sequence}_"):
        full_shot_id = shot
    else:
        full_shot_id = f"{sequence}_{shot}"

    script_name = f"{project_code}_{full_shot_id}_comp_v001.nk"
    plate_filename = f"{full_shot_id}_plate_v001.####.exr"
    hires_render_filename = f"{project_code}_{full_shot_id}_comp_v001.####.exr"
    review_render_filename = f"{project_code}_{full_shot_id}_comp_v001.mov"

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
 tile_color 0x388e3cff
 label "<center><b>INPUT PLATES</b></center>"
 note_font_size 24
 xpos -60
 ypos -200
 bdwidth 300
 bdheight 250
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
 xpos 40
 ypos -120
}}
Dot {{
 inputs 1
 name Dot_MAIN
 xpos 74
 ypos 0
}}
set N_STACK_BRANCH [stack 0]
BackdropNode {{
 inputs 0
 name Backdrop_OUTPUTS
 tile_color 0x1976d2ff
 label "<center><b>DELIVERY RENDERS</b></center>"
 note_font_size 24
 xpos -80
 ypos 60
 bdwidth 340
 bdheight 240
}}
Write {{
 inputs 1
 file "\\[file dirname \\[value root.name]]/../../renders/hires/v001/{hires_render_filename}"
 file_type exr
 datatype "16 bit half"
 compression "Zip (1 scanline)"
 first {frame_start}
 last {frame_end}
 checkHashOnRead false
 colorspace "{hires_colorspace}"
 version 1
 name Write_HIRES
 selected true
 xpos -40
 ypos 140
}}
push $N_STACK_BRANCH
Write {{
 inputs 1
 file "\\[file dirname \\[value root.name]]/../../renders/review/{review_render_filename}"
 file_type mov
 mov64_codec "Apple ProRes 422"
 colorspace "{review_colorspace}"
 first {frame_start}
 last {frame_end}
 checkHashOnRead false
 version 1
 name Write_REVIEW
 selected false
 xpos 120
 ypos 140
}}
"""
    return content
