"""
Delivery Manager for Post Project Manager.
Manages delivery folder scaffolding, file copying, and delivery logging.
"""

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple


class DeliveryManager:
    @staticmethod
    def check_delivery_files(
        project_dir: Path,
        deliveries: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Verifies presence of review and hires render files on disk for each delivery item.
        Returns a list of dicts with status for each item:
        {
            "seq_name": seq,
            "shot_name": shot,
            "version": ver,
            "has_review": bool,
            "has_hires": bool,
            "review_file": Optional[str],
            "hires_count": int,
            "missing": List[str]  # e.g. ["review", "hires"], ["hires"], or []
        }
        """
        results = []
        for item in deliveries:
            seq = item["seq_name"]
            shot = item["shot_name"]
            ver = item["version"]
            copy_hires = item.get("copy_hires", True)
            copy_review = item.get("copy_review", True)

            shot_src = project_dir / "sequences" / seq / shot

            # 1. Check Review Video
            found_review_file: Optional[Path] = None
            if copy_review:
                v_rev_dir = shot_src / "renders" / ver / "review"
                if v_rev_dir.exists() and v_rev_dir.is_dir():
                    for f in v_rev_dir.glob("*"):
                        if f.is_file() and f.suffix.lower() in [".mp4", ".mov", ".mkv"]:
                            found_review_file = f
                            break

                if not found_review_file:
                    legacy_rev_dir = shot_src / "renders" / "review"
                    if legacy_rev_dir.exists() and legacy_rev_dir.is_dir():
                        for f in legacy_rev_dir.glob(f"*{ver}*"):
                            if f.is_file() and f.suffix.lower() in [".mp4", ".mov", ".mkv"]:
                                found_review_file = f
                                break

            # 2. Check High-Res Render
            hires_count = 0
            if copy_hires:
                hires_src_dir = shot_src / "renders" / ver / "hires"
                if not hires_src_dir.exists() or not hires_src_dir.is_dir():
                    hires_src_dir = shot_src / "renders" / "hires" / ver

                if hires_src_dir.exists() and hires_src_dir.is_dir():
                    hires_count = sum(1 for f in hires_src_dir.glob("*") if f.is_file() and not f.name.startswith("."))

            has_review = found_review_file is not None
            has_hires = hires_count > 0

            missing = []
            if copy_review and not has_review:
                missing.append("review")
            if copy_hires and not has_hires:
                missing.append("hires")

            results.append({
                "seq_name": seq,
                "shot_name": shot,
                "version": ver,
                "has_review": has_review,
                "has_hires": has_hires,
                "review_file": str(found_review_file) if found_review_file else None,
                "hires_count": hires_count,
                "missing": missing
            })
        return results

    @staticmethod
    def get_missing_delivery_shots(delivery_path: Path, sequences: Dict[str, List[str]]) -> List[Tuple[str, str]]:
        """
        Checks which sequence/shot combinations from the project are not yet
        scaffolded in the delivery directory.
        Returns a list of (seq_name, shot_name) tuples.
        """
        if not delivery_path.exists():
            return []
        missing = []
        for seq_name, shot_list in sequences.items():
            for shot_name in shot_list:
                shot_deliv = delivery_path / seq_name / shot_name
                if not shot_deliv.exists():
                    missing.append((seq_name, shot_name))
        return missing

    @staticmethod
    def setup_delivery_folder(
        delivery_path: Path,
        sequences: Dict[str, List[str]],
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> Tuple[bool, str]:
        """
        Creates or updates the client delivery root directory and scaffolds
        all project sequences and shots inside it with versioned structures.
        """
        try:
            delivery_path.mkdir(parents=True, exist_ok=True)
            total = sum(len(shots) for shots in sequences.values())
            count = 0
            for seq_name, shot_list in sequences.items():
                for shot_name in shot_list:
                    if progress_callback:
                        progress_callback(count, total, f"Scaffolding {seq_name}/{shot_name}...")
                    shot_delivery_dir = delivery_path / seq_name / shot_name / "v001"
                    (shot_delivery_dir / "review").mkdir(parents=True, exist_ok=True)
                    (shot_delivery_dir / "hires").mkdir(parents=True, exist_ok=True)
                    count += 1

            if progress_callback:
                progress_callback(total, total, "Delivery folder setup complete.")

            # Place a guide file
            info_file = delivery_path / "README_DELIVERY.txt"
            info_file.write_text(
                "==========================================================\n"
                "CLIENT DELIVERY HUB\n"
                "==========================================================\n"
                f"Generated by Post Project Manager at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                "Approved shots are synced here into version folders (v001, v002...)\n"
                "with high-resolution master frames (/hires) and lightweight review proxies (/review).\n",
                encoding="utf-8"
            )

            return True, f"Delivery folder initialized with {count} shot directories."
        except Exception as e:
            return False, f"Failed to setup delivery folder: {e}"

    @staticmethod
    def execute_delivery(
        project_dir: Path,
        delivery_root: Path,
        deliveries: List[Dict[str, Any]],
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> Tuple[bool, str, List[str]]:
        """
        Transfers selected shot versions to the delivery destination.
        Each item in deliveries is:
        {
            "seq_name": "sq010",
            "shot_name": "sq010_sh010",
            "version": "v002",
            "copy_hires": True,
            "copy_review": True
        }
        Destination structure: [delivery_root]/[seq]/[shot]/[version]/[review|hires]
        """
        if not delivery_root.exists():
            return False, f"Delivery folder '{delivery_root}' does not exist.", []

        transferred_files = []
        total_items = len(deliveries)

        try:
            for idx, item in enumerate(deliveries):
                seq = item["seq_name"]
                shot = item["shot_name"]
                ver = item["version"]
                copy_hires = item.get("copy_hires", True)
                copy_review = item.get("copy_review", True)

                if progress_callback:
                    progress_callback(idx, total_items, f"Delivering {seq}/{shot} ({ver})...")

                shot_src = project_dir / "sequences" / seq / shot
                # Destination versioned folder: [delivery_root]/[seq]/[shot]/[version]
                shot_dst_ver = delivery_root / seq / shot / ver
                shot_dst_ver.mkdir(parents=True, exist_ok=True)

                # 1. Copy Review Video
                if copy_review:
                    # Check renders/[version]/review first, then legacy renders/review
                    review_candidates = []
                    v_rev_dir = shot_src / "renders" / ver / "review"
                    if v_rev_dir.exists() and v_rev_dir.is_dir():
                        review_candidates.extend(v_rev_dir.glob("*"))

                    legacy_rev_dir = shot_src / "renders" / "review"
                    if legacy_rev_dir.exists() and legacy_rev_dir.is_dir():
                        review_candidates.extend(legacy_rev_dir.glob(f"*{ver}*"))

                    for f in review_candidates:
                        if f.is_file() and f.suffix.lower() in [".mp4", ".mov", ".mkv"]:
                            dst_review_dir = shot_dst_ver / "review"
                            dst_review_dir.mkdir(parents=True, exist_ok=True)
                            dst_file = dst_review_dir / f.name
                            shutil.copy2(f, dst_file)
                            transferred_files.append(str(dst_file))
                            break  # Delivered primary review video

                # 2. Copy High-Res Render
                if copy_hires:
                    # Check renders/[version]/hires first, then legacy renders/hires/[version]
                    hires_src_dir = shot_src / "renders" / ver / "hires"
                    if not hires_src_dir.exists() or not hires_src_dir.is_dir():
                        hires_src_dir = shot_src / "renders" / "hires" / ver

                    if hires_src_dir.exists() and hires_src_dir.is_dir():
                        dst_hires_dir = shot_dst_ver / "hires"
                        dst_hires_dir.mkdir(parents=True, exist_ok=True)
                        for frame in hires_src_dir.glob("*"):
                            if frame.is_file():
                                dst_frame = dst_hires_dir / frame.name
                                shutil.copy2(frame, dst_frame)
                                transferred_files.append(str(dst_frame))

            # Final progress update
            if progress_callback:
                progress_callback(total_items, total_items, "Delivery transfer completed.")

            # Log delivery history
            pipeline_dir = project_dir / "_pipeline"
            pipeline_dir.mkdir(parents=True, exist_ok=True)
            log_file = pipeline_dir / "delivery_log.json"

            history = []
            if log_file.exists():
                try:
                    with open(log_file, "r", encoding="utf-8") as f:
                        history = json.load(f)
                except Exception:
                    history = []

            history.append({
                "timestamp": datetime.now().isoformat(),
                "delivery_root": str(delivery_root),
                "total_items": len(deliveries),
                "files_count": len(transferred_files),
                "deliveries": deliveries
            })

            with open(log_file, "w", encoding="utf-8") as f:
                json.dump(history, f, indent=2, ensure_ascii=False)

            return True, f"Successfully delivered {len(deliveries)} shots ({len(transferred_files)} files copied).", transferred_files

        except Exception as e:
            return False, f"Delivery execution failed: {e}", transferred_files
