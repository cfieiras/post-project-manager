"""
Shot Scanner Module for Post Project Manager.
Analyzes directory structure to detect conformed plates, comp scripts,
review renders, high-res renders, version synchronization, and thumbnails.
"""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from .nuke_generator import conform_nuke_script_write_paths


class ShotScanner:
    @staticmethod
    def extract_version(filename: str) -> Optional[int]:
        """Extracts version number like v1, v01, v001, v002 from a filename or folder name."""
        match = re.search(r"[vV](\d+)", filename)
        if match:
            return int(match.group(1))
        return None

    @classmethod
    def scan_shot(cls, project_dir: Path, seq_name: str, shot_name: str) -> Dict[str, Any]:
        """
        Scans a single shot folder and gathers its current production state:
        - All Nuke script versions & their exact paths
        - Available review render versions & files (supporting renders/[version]/review and renders/review)
        - Available high-res render versions (supporting renders/[version]/hires and renders/hires/[version])
        - Sync status between script and render
        """
        shot_dir = project_dir / "sequences" / seq_name / shot_name
        data = {
            "seq_name": seq_name,
            "shot_name": shot_name,
            "shot_dir": str(shot_dir),
            "exists_on_disk": shot_dir.exists(),
            "latest_script_version": None,
            "latest_script_path": None,
            "all_script_versions": [],
            "all_script_files": {},     # { "v001": path_v001, "v002": path_v002 }
            "latest_review_version": None,
            "latest_review_path": None,
            "all_review_versions": {},  # { "v001": path, "v002": path }
            "latest_hires_version": None,
            "all_hires_versions": [],   # ["v001", "v002"]
            "is_outdated": False,
            "sync_message": "No work detected",
            "has_plate": False
        }

        if not shot_dir.exists():
            return data

        # 1. Check Plates
        plates_dir = shot_dir / "plates"
        if plates_dir.exists():
            for p_ver in sorted(plates_dir.glob("v*")):
                if p_ver.is_dir():
                    frames = list(p_ver.glob("*.exr")) + list(p_ver.glob("*.dpx")) + list(p_ver.glob("*.png"))
                    if frames:
                        data["has_plate"] = True
                        break

        # 2. Scan Comp Scripts
        scripts_dir = shot_dir / "comp" / "scripts"
        if scripts_dir.exists():
            nk_files = list(scripts_dir.glob("*.nk"))
            versions_found = []
            for nk in nk_files:
                # Automatically conform Write nodes to dynamic script-matching paths
                conform_nuke_script_write_paths(nk)
                ver = cls.extract_version(nk.name)
                if ver is not None:
                    versions_found.append((ver, nk))
            if versions_found:
                # Sort numerically by version number
                versions_found.sort(key=lambda x: x[0])
                for v_num, nk_path in versions_found:
                    v_str = f"v{v_num:03d}"
                    if v_str not in data["all_script_versions"]:
                        data["all_script_versions"].append(v_str)
                    data["all_script_files"][v_str] = str(nk_path)

                highest_ver, highest_path = versions_found[-1]
                data["latest_script_version"] = f"v{highest_ver:03d}"
                data["latest_script_path"] = str(highest_path)

        # 3. Scan Review Renders
        # Check both:
        # A) Modern versioned: renders/v001/review/*.{mp4,mov,mkv}
        # B) Legacy flat: renders/review/*.{mp4,mov,mkv}
        renders_dir = shot_dir / "renders"
        review_found = []

        if renders_dir.exists():
            # A) Search inside version subfolders (renders/v*/review)
            for v_dir in sorted(renders_dir.glob("v*")):
                if v_dir.is_dir():
                    v_num = cls.extract_version(v_dir.name)
                    v_review_dir = v_dir / "review"
                    if v_review_dir.exists() and v_review_dir.is_dir():
                        v_files = (
                            list(v_review_dir.glob("*.mp4")) +
                            list(v_review_dir.glob("*.mov")) +
                            list(v_review_dir.glob("*.mkv"))
                        )
                        for rf in v_files:
                            file_ver = cls.extract_version(rf.name) or v_num
                            if file_ver is not None:
                                ver_str = f"v{file_ver:03d}"
                                review_found.append((file_ver, ver_str, rf))
                                data["all_review_versions"][ver_str] = str(rf)

            # B) Search in legacy renders/review/
            legacy_review_dir = renders_dir / "review"
            if legacy_review_dir.exists() and legacy_review_dir.is_dir():
                legacy_files = (
                    list(legacy_review_dir.glob("*.mp4")) +
                    list(legacy_review_dir.glob("*.mov")) +
                    list(legacy_review_dir.glob("*.mkv"))
                )
                for rf in legacy_files:
                    ver = cls.extract_version(rf.name)
                    if ver is not None:
                        ver_str = f"v{ver:03d}"
                        if ver_str not in data["all_review_versions"]:
                            review_found.append((ver, ver_str, rf))
                            data["all_review_versions"][ver_str] = str(rf)

        if review_found:
            review_found.sort(key=lambda x: x[0])
            _, highest_review_ver, highest_review_path = review_found[-1]
            data["latest_review_version"] = highest_review_ver
            data["latest_review_path"] = str(highest_review_path)

        # 4. Scan High-Res Renders
        # Check both:
        # A) Modern versioned: renders/v001/hires/*.{exr,dpx,mov}
        # B) Legacy: renders/hires/v001/*.{exr,dpx,mov}
        hires_versions = []
        if renders_dir.exists():
            # A) Check renders/v*/hires
            for v_dir in sorted(renders_dir.glob("v*")):
                if v_dir.is_dir():
                    v_hires_dir = v_dir / "hires"
                    if v_hires_dir.exists() and v_hires_dir.is_dir():
                        frames = (
                            list(v_hires_dir.glob("*.exr")) +
                            list(v_hires_dir.glob("*.dpx")) +
                            list(v_hires_dir.glob("*.mov"))
                        )
                        if frames and v_dir.name not in hires_versions:
                            hires_versions.append(v_dir.name)

            # B) Check legacy renders/hires/v*
            legacy_hires_dir = renders_dir / "hires"
            if legacy_hires_dir.exists() and legacy_hires_dir.is_dir():
                for v_folder in sorted(legacy_hires_dir.glob("v*")):
                    if v_folder.is_dir():
                        frames = (
                            list(v_folder.glob("*.exr")) +
                            list(v_folder.glob("*.dpx")) +
                            list(v_folder.glob("*.mov"))
                        )
                        if frames and v_folder.name not in hires_versions:
                            hires_versions.append(v_folder.name)

        # Sort hires versions numerically
        hires_versions.sort(key=lambda x: cls.extract_version(x) or 0)
        data["all_hires_versions"] = hires_versions
        if hires_versions:
            data["latest_hires_version"] = hires_versions[-1]

        # 5. Determine Sync Status
        script_v = data["latest_script_version"]
        review_v = data["latest_review_version"]

        if script_v and review_v:
            s_num = int(script_v.replace("v", ""))
            r_num = int(review_v.replace("v", ""))
            if s_num > r_num:
                data["is_outdated"] = True
                data["sync_message"] = f"⚠️ Script Ahead ({script_v} > {review_v})"
            elif s_num == r_num:
                data["is_outdated"] = False
                data["sync_message"] = f"✔ Up to Date ({review_v})"
            else:
                data["is_outdated"] = False
                data["sync_message"] = f"✔ Render Ahead ({review_v})"
        elif script_v and not review_v:
            data["is_outdated"] = True
            data["sync_message"] = f"⚠️ Unrendered ({script_v})"
        elif not script_v and review_v:
            data["is_outdated"] = False
            data["sync_message"] = f"✔ Render ({review_v})"
        else:
            data["sync_message"] = "No Work"

        return data

    @classmethod
    def scan_all_shots(cls, project_dir: Path, sequences: Dict[str, List[str]]) -> List[Dict[str, Any]]:
        """Scans all sequences and shots in the project."""
        all_shots = []
        for seq_name, shots in sequences.items():
            for shot_name in shots:
                shot_data = cls.scan_shot(project_dir, seq_name, shot_name)
                all_shots.append(shot_data)
        return all_shots
