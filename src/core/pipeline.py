"""
Core Pipeline Engine for Post Project Manager.
Manages project creation, folder scaffolding, Nuke script generation,
metadata synchronization, and non-destructive project updates.
"""

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .nuke_generator import generate_nuke_script


DEFAULT_TEMPLATE_PATH = Path(__file__).resolve().parent.parent.parent / "templates" / "default_template.json"


class PipelineManager:
    def __init__(self, template_path: Optional[Path] = None):
        self.template_path = Path(template_path) if template_path else DEFAULT_TEMPLATE_PATH
        self.template = self.load_template()

    def load_template(self) -> Dict[str, Any]:
        """Loads the template JSON file from disk, or provides defaults if missing."""
        if self.template_path.exists():
            try:
                with open(self.template_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"Warning: Failed to load template from {self.template_path}: {e}")
        return self._get_fallback_template()

    def save_template(self, template_data: Dict[str, Any]) -> bool:
        """Saves template JSON to disk."""
        try:
            self.template_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.template_path, "w", encoding="utf-8") as f:
                json.dump(template_data, f, indent=2, ensure_ascii=False)
            self.template = template_data
            return True
        except Exception as e:
            print(f"Error saving template: {e}")
            return False

    def scan_projects(self, root_dir: Path) -> List[Dict[str, Any]]:
        """Scans root_dir for project folders and extracts metadata."""
        projects = []
        if not root_dir.exists() or not root_dir.is_dir():
            return projects

        for item in sorted(root_dir.iterdir()):
            if item.is_dir() and not item.name.startswith((".", "_")):
                meta_file = item / "_pipeline" / "project_meta.json"
                if meta_file.exists():
                    try:
                        with open(meta_file, "r", encoding="utf-8") as f:
                            meta = json.load(f)
                        seq_count = len(meta.get("sequences", {}))
                        shot_count = sum(len(shots) for shots in meta.get("sequences", {}).values())
                        projects.append({
                            "name": item.name,
                            "path": str(item),
                            "is_registered": True,
                            "created_at": meta.get("created_at", "Unknown"),
                            "active_modules": meta.get("active_modules", []),
                            "settings": meta.get("project_settings", {}),
                            "sequences_count": seq_count,
                            "shots_count": shot_count,
                            "meta": meta
                        })
                    except Exception:
                        projects.append({
                            "name": item.name,
                            "path": str(item),
                            "is_registered": True,
                            "error": "Corrupted project_meta.json",
                            "active_modules": [],
                            "sequences_count": 0,
                            "shots_count": 0
                        })
                else:
                    # Unregistered folder
                    projects.append({
                        "name": item.name,
                        "path": str(item),
                        "is_registered": False,
                        "active_modules": [],
                        "sequences_count": 0,
                        "shots_count": 0
                    })
        return projects

    def build_project_tree_preview(
        self,
        project_code: str,
        active_modules: List[str],
        sequences: Dict[str, List[str]]
    ) -> List[str]:
        """
        Generates a flat list of relative directory paths that will be created.
        Used by the UI for the dynamic Live Tree Preview.
        """
        paths = []

        # Core folders
        for folder in self.template.get("core_folders", []):
            paths.append(folder)

        # Pipeline folder
        paths.append("_pipeline")

        # Active Module root folders
        modules = self.template.get("modules", {})
        for mod_id in active_modules:
            mod_data = modules.get(mod_id, {})
            for r_folder in mod_data.get("root_folders", []):
                resolved_folder = r_folder.replace("{project}", project_code.lower())
                paths.append(resolved_folder)

        # Sequences and shots
        shot_core = self.template.get("shot_core", [])
        for seq_name, shot_list in sequences.items():
            paths.append(f"sequences/{seq_name}/_shared")
            for shot_name in shot_list:
                shot_base = f"sequences/{seq_name}/{shot_name}"
                for s_core in shot_core:
                    paths.append(f"{shot_base}/{s_core}")

                for mod_id in active_modules:
                    mod_data = modules.get(mod_id, {})
                    for s_folder in mod_data.get("shot_folders", []):
                        paths.append(f"{shot_base}/{s_folder}")

        return sorted(list(set(paths)))

    def create_project(
        self,
        root_dir: Path,
        project_code: str,
        active_modules: List[str],
        sequences: Dict[str, List[str]],
        project_settings: Dict[str, Any]
    ) -> Tuple[bool, str]:
        """
        Executes the full project creation:
        - Creates directory tree
        - Ingest safety README
        - Generates starter .nk scripts for comp
        - Writes _pipeline/project_meta.json
        """
        project_code = project_code.strip()
        if not project_code:
            return False, "Project code cannot be empty."

        project_path = root_dir / project_code
        if project_path.exists():
            return False, f"Directory '{project_code}' already exists at destination."

        try:
            # 1. Build list of directories
            rel_dirs = self.build_project_tree_preview(project_code, active_modules, sequences)

            # 2. Create all directories on disk
            for rel in rel_dirs:
                (project_path / rel).mkdir(parents=True, exist_ok=True)

            # 3. Create incoming README
            readme_ingest = project_path / "incoming" / "README_INGEST.txt"
            readme_ingest.write_text(
                "==========================================================\n"
                "INCOMING RECEPTION FOLDER (READ-ONLY / INMUTABLE)\n"
                "==========================================================\n"
                "RULES:\n"
                "1. All footage, briefs, audio, and client assets placed here are strictly read-only.\n"
                "2. Never edit, rename, move, or work directly on files inside this directory.\n"
                "3. Ingest or copy elements to editorial/ or sequences/ before processing.\n",
                encoding="utf-8"
            )

            # 4. Generate Starter Nuke Scripts if comp is active
            if "comp" in active_modules:
                fps = float(project_settings.get("fps", 24.0))
                res_str = project_settings.get("resolution", "1920x1080")
                try:
                    w_str, h_str = res_str.split("x")
                    width, height = int(w_str), int(h_str)
                except Exception:
                    width, height = 1920, 1080

                format_name = project_settings.get("resolution_name", "HD_1080")
                color_mgmt = project_settings.get("color_management", "OCIO")
                ocio_config = project_settings.get("ocio_config", "aces_1.2")
                working_space = project_settings.get("working_space", "ACES - ACEScg")
                frame_start = int(project_settings.get("frame_start", 1001))
                frame_end = int(project_settings.get("frame_end", 1100))

                for seq_name, shot_list in sequences.items():
                    for shot_name in shot_list:
                        full_shot_id = shot_name if shot_name.startswith(f"{seq_name}_") else f"{seq_name}_{shot_name}"
                        nk_content = generate_nuke_script(
                            project_code=project_code.lower(),
                            sequence=seq_name,
                            shot=shot_name,
                            fps=fps,
                            width=width,
                            height=height,
                            format_name=format_name,
                            color_management=color_mgmt,
                            ocio_config=ocio_config,
                            working_space=working_space,
                            frame_start=frame_start,
                            frame_end=frame_end
                        )
                        nk_path = project_path / "sequences" / seq_name / shot_name / "comp" / "scripts" / f"{project_code.lower()}_{full_shot_id}_comp_v001.nk"
                        nk_path.parent.mkdir(parents=True, exist_ok=True)
                        nk_path.write_text(nk_content, encoding="utf-8")

            # 5. Write metadata
            meta = {
                "project_code": project_code,
                "created_at": datetime.now().isoformat(),
                "last_modified": datetime.now().isoformat(),
                "active_modules": active_modules,
                "project_settings": project_settings,
                "sequences": sequences
            }
            meta_path = project_path / "_pipeline" / "project_meta.json"
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(meta, f, indent=2, ensure_ascii=False)

            return True, f"Project '{project_code}' successfully created!"

        except Exception as e:
            return False, f"Failed to create project: {e}"

    def update_project(
        self,
        project_path: Path,
        active_modules: List[str],
        sequences: Dict[str, List[str]],
        project_settings: Dict[str, Any]
    ) -> Tuple[bool, str]:
        """
        Non-destructive update:
        - Backs up existing project_meta.json
        - Adds missing module folders
        - Adds missing sequences/shots and generates any missing Nuke scripts
        - Never deletes existing files or folders
        """
        meta_file = project_path / "_pipeline" / "project_meta.json"
        if not meta_file.exists():
            return False, "Project metadata file (_pipeline/project_meta.json) not found."

        try:
            # 1. Backup old metadata
            history_dir = project_path / "_pipeline" / "history"
            history_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_meta = history_dir / f"project_meta_{timestamp}.json"
            shutil.copy2(meta_file, backup_meta)

            project_code = project_path.name

            # 2. Build preview of all required directories
            required_dirs = self.build_project_tree_preview(project_code, active_modules, sequences)
            created_dirs_count = 0
            for rel in required_dirs:
                target = project_path / rel
                if not target.exists():
                    target.mkdir(parents=True, exist_ok=True)
                    created_dirs_count += 1

            # 3. Generate missing Nuke scripts if comp is enabled
            if "comp" in active_modules:
                fps = float(project_settings.get("fps", 24.0))
                res_str = project_settings.get("resolution", "1920x1080")
                try:
                    w_str, h_str = res_str.split("x")
                    width, height = int(w_str), int(h_str)
                except Exception:
                    width, height = 1920, 1080

                format_name = project_settings.get("resolution_name", "HD_1080")
                color_mgmt = project_settings.get("color_management", "OCIO")
                ocio_config = project_settings.get("ocio_config", "aces_1.2")
                working_space = project_settings.get("working_space", "ACES - ACEScg")
                frame_start = int(project_settings.get("frame_start", 1001))
                frame_end = int(project_settings.get("frame_end", 1100))

                for seq_name, shot_list in sequences.items():
                    for shot_name in shot_list:
                        full_shot_id = shot_name if shot_name.startswith(f"{seq_name}_") else f"{seq_name}_{shot_name}"
                        nk_path = project_path / "sequences" / seq_name / shot_name / "comp" / "scripts" / f"{project_code.lower()}_{full_shot_id}_comp_v001.nk"
                        if not nk_path.exists():
                            nk_content = generate_nuke_script(
                                project_code=project_code.lower(),
                                sequence=seq_name,
                                shot=shot_name,
                                fps=fps,
                                width=width,
                                height=height,
                                format_name=format_name,
                                color_management=color_mgmt,
                                ocio_config=ocio_config,
                                working_space=working_space,
                                frame_start=frame_start,
                                frame_end=frame_end
                            )
                            nk_path.parent.mkdir(parents=True, exist_ok=True)
                            nk_path.write_text(nk_content, encoding="utf-8")

            # 4. Save updated metadata
            meta = {
                "project_code": project_code,
                "created_at": datetime.now().isoformat(),
                "last_modified": datetime.now().isoformat(),
                "active_modules": active_modules,
                "project_settings": project_settings,
                "sequences": sequences
            }
            with open(meta_file, "w", encoding="utf-8") as f:
                json.dump(meta, f, indent=2, ensure_ascii=False)

            return True, f"Project updated successfully ({created_dirs_count} new directories created). Backup saved to history."

        except Exception as e:
            return False, f"Error updating project: {e}"

    def _get_fallback_template(self) -> Dict[str, Any]:
        """Provides default structure in case template file is deleted."""
        return {
            "version": "1.0.0",
            "project_settings_default": {
                "fps": 24.0,
                "resolution": "1920x1080",
                "resolution_name": "HD_1080",
                "color_management": "OCIO",
                "ocio_config": "aces_1.2",
                "working_space": "ACES - ACEScg",
                "frame_start": 1001,
                "frame_end": 1100
            },
            "core_folders": [
                "incoming",
                "editorial/project_files",
                "editorial/conforms",
                "editorial/offline_refs",
                "editorial/audio",
                "assets/color",
                "assets/fonts",
                "assets/graphics",
                "assets/references"
            ],
            "shot_core": [
                "plates/v001/proxies",
                "renders/hires/v001",
                "renders/review"
            ],
            "modules": {
                "comp": {
                    "id": "comp",
                    "name": "Compositing",
                    "enabled_by_default": true,
                    "root_folders": [],
                    "shot_folders": ["comp/scripts", "comp/precomps"]
                },
                "ai": {
                    "id": "ai",
                    "name": "Artificial Intelligence",
                    "enabled_by_default": false,
                    "root_folders": ["ai_lab/prompts", "ai_lab/references", "ai_lab/models"],
                    "shot_folders": ["ai/references", "ai/outputs/v001"]
                },
                "3d_dcc": {
                    "id": "3d_dcc",
                    "name": "3D Traditional (Blender / Maya / Houdini)",
                    "enabled_by_default": false,
                    "root_folders": ["assets/3d/models", "assets/3d/textures", "assets/3d/hdri"],
                    "shot_folders": ["3d/scenes", "3d/tracking", "3d/caches"]
                },
                "unreal": {
                    "id": "unreal",
                    "name": "Unreal Engine",
                    "enabled_by_default": false,
                    "root_folders": [
                        "unreal_projects/{project}_unreal/Config",
                        "unreal_projects/{project}_unreal/Content/environments",
                        "unreal_projects/{project}_unreal/Content/characters",
                        "unreal_projects/{project}_unreal/Content/fx",
                        "unreal_projects/{project}_unreal/Content/cinematics"
                    ],
                    "shot_folders": []
                }
            }
        }
