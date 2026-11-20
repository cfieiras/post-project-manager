"""
Shot Scanner Module for Post Project Manager.
Analyzes directory structure to detect conformed plates, comp scripts,
review renders, high-res renders, version synchronization, and thumbnails.
"""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional


class ShotScanner:
    @staticmethod
    def extract_version(filename: str) -> Optional[int]:
        """Extracts version number like v001, v002 from a filename or folder name."""
        match = re.search(r"[vV](\d{3,4})", filename)
        if match:
            return int(match.group(1))
        return None

    @classmethod
    def scan_shot(cls, project_dir: Path, seq_name: str, shot_name: str) -> Dict[str, Any]:
        """
        Scans a single shot folder and gathers its current production state:
        - Latest Nuke script version
        - Available review render versions & files
        - Available high-res render versions
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
                ver = cls.extract_version(nk.name)
                if ver is not None:
                    versions_found.append((ver, nk))
            if versions_found:
                versions_found.sort(key=lambda x: x[0])
                highest_ver, highest_path = versions_found[-1]
                data["latest_script_version"] = f"v{highest_ver:03d}"
                data["latest_script_path"] = str(highest_path)
                data["all_script_versions"] = [f"v{v:03d}" for v, _ in versions_found]

        # 3. Scan Review Renders
        review_dir = shot_dir / "renders" / "review"
        if review_dir.exists():
            review_files = (
                list(review_dir.glob("*.mp4")) +
                list(review_dir.glob("*.mov")) +
                list(review_dir.glob("*.mkv"))
            )
            review_found = []
            for rf in review_files:
                ver = cls.extract_version(rf.name)
                if ver is not None:
                    ver_str = f"v{ver:03d}"
                    review_found.append((ver, ver_str, rf))
                    data["all_review_versions"][ver_str] = str(rf)

            if review_found:
                review_found.sort(key=lambda x: x[0])
                _, highest_review_ver, highest_review_path = review_found[-1]
                data["latest_review_version"] = highest_review_ver
                data["latest_review_path"] = str(highest_review_path)

        # 4. Scan High-Res Renders
        hires_dir = shot_dir / "renders" / "hires"
        if hires_dir.exists():
            hires_versions = []
            for v_folder in sorted(hires_dir.glob("v*")):
                if v_folder.is_dir():
                    frames = (
                        list(v_folder.glob("*.exr")) +
                        list(v_folder.glob("*.dpx")) +
                        list(v_folder.glob("*.mov"))
                    )
                    if frames:
                        hires_versions.append(v_folder.name)
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
