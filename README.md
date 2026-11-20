# Post Project Manager (Portable Desktop App)

> **Modular Project Scaffolding & Pipeline Manager for Post-Production (VFX, 3D DCC, Unreal Engine, Compo & AI)**  
> **Author:** Cristian Fieiras  
> **Version:** 1.0.1  

---

## 🚀 Overview

**Post Project Manager** is a standalone, lightweight, and portable desktop tool designed for post-production studios, VFX facilities, and freelancers. It automates studio directory scaffolding, standardizes project naming conventions, generates starter Nuke compositing scripts with dynamic relative paths, and provides non-destructive project updates.

---

## 📂 Standard Directory Tree Specification (Full Hybrid Tree)

Below is the complete project directory tree generated when all modules are activated (**Core Base + Compositing + 3D DCC + Unreal Engine + AI Lab**):

```text
[PROJECT_CODE]/
│
├── incoming/                                  # Raw unedited footage, briefs & on-set data (Read-Only)
│   ├── 2026-11-20_client_brief/
│   ├── 2026-11-21_set_cam_a/
│   ├── 2026-11-22_audio_stems/
│   └── README_INGEST.txt                      # Immutability warning & guidelines
│
├── editorial/                                 # Editorial department hub
│   ├── project_files/                         # NLE projects (Premiere .prproj, Resolve .drp, FCP)
│   ├── conforms/                              # XML, EDL, AAF exchange files
│   ├── offline_refs/                          # Reference cut videos with TC & Shot ID burn-in
│   └── audio/                                 # Mix stems, scratch tracks, VO, temp music
│
├── assets/                                    # Shared project-wide assets
│   ├── color/                                 # OCIO configs, CDLs, project LUTs (.cube)
│   ├── fonts/                                 # Approved typography
│   ├── graphics/                              # Logos, vector assets, UI design elements
│   ├── references/                            # Moodboards, styleframes, color palettes
│   └── 3d/                                    # Shared 3D assets (3D DCC Module)
│       ├── models/                            # Shared props, characters, vehicles (.blend, .usd)
│       ├── textures/                          # Shared UDIM texture sets, PBR maps
│       └── hdri/                              # Environment lighting maps (.exr, .hdr)
│
├── unreal_projects/                           # Centralized Unreal projects (Unreal Module)
│   └── [PROJECT_CODE]_unreal/
│       ├── Config/
│       ├── Content/
│       │   ├── environments/                  # Master levels and environment geometry
│       │   ├── characters/                    # Skeletal meshes, animations, control rigs
│       │   ├── fx/                            # Niagara systems, post-process materials
│       │   └── cinematics/                    # Level Sequences mapped to post sequences/shots
│       │       └── sq010/
│       │           ├── sq010_master_seq
│       │           ├── sq010_sh010_seq
│       │           └── sq010_sh020_seq
│       └── [PROJECT_CODE]_unreal.uproject
│
├── ai_lab/                                    # Central AI lab & models (AI Module)
│   ├── prompts/                               # Master prompt sheets, negative prompts, seed logs
│   ├── references/                            # Style transfer targets, character consistency sets
│   └── models/                                # Custom trained LoRAs, embeddings, checkpoints
│
├── _pipeline/                                 # Pipeline metadata & version history
│   ├── project_meta.json                      # Current project configuration & module state
│   └── history/                               # Automatic backups prior to any modifications
│
└── sequences/                                 # Sequence and shot breakdown
    └── sq010/
        ├── _shared/                           # Assets shared only across this sequence
        └── sq010_sh010/
            ├── plates/                        # Conformed source plates (Strictly Versioned)
            │   ├── v001/                      # Initial plate delivery with head/tail handles
            │   │   └── proxies/               # Lightweight proxy for fast playback
            │   └── v002/                      # Editorial re-conform / slip / regrade version
            │       └── proxies/
            │
            ├── comp/                          # Compositing (Comp Module)
            │   ├── scripts/                   # Working scripts (.nk, .aep, .comp)
            │   │   └── prj_sq010_sh010_comp_v001.nk  # Auto-generated Nuke script
            │   └── precomps/                  # Intermediate caches, roto renders, cleanplates
            │
            ├── 3d/                            # Shot-specific 3D (3D DCC Module)
            │   ├── scenes/                    # Shot working files (.blend, .ma, .hip, .c4d)
            │   ├── tracking/                  # Matchmove cameras, survey points (.abc, .fbx)
            │   └── caches/                    # Shot-specific Alembic, USD or VDB caches
            │
            ├── ai/                            # Shot-specific AI (AI Module)
            │   ├── references/                # Shot prompts, input frames, inpaint masks
            │   └── outputs/                   # Downloaded/generated passes from AI platforms
            │       ├── v001/                  # Raw generation batch / initial variations
            │       └── v002/                  # Refined selects & upscaled passes
            │
            └── renders/                       # Output renders of the shot
                ├── hires/                     # Master delivery passes (EXR, ProRes 4444)
                │   ├── v001/
                │   └── v002/
                └── review/                    # Internal review files (MP4 H.264 with burn-in)
                    ├── sq010_sh010_v001.mp4
                    └── sq010_sh010_v002.mp4
```

---

## ✨ Key Features

1. **100% Portable (Zero-Install):**
   - Runs as a standalone `.exe` without requiring Python, admin privileges, or registry modifications.
   - Saves settings in a local `config.json` next to the executable.
2. **Modular Architecture:**
   - Every project starts with a lean **Core Base** (`incoming/`, `editorial/`, `sequences/`, `assets/`).
   - Add specialized modules on demand: **Compositing**, **AI Lab**, **3D Traditional (Blender/Maya)**, and **Unreal Engine**.
3. **Live Interactive Tree Preview:**
   - Visualizes the complete folder hierarchy dynamically as you select modules and type sequence/shot names before touching the disk.
4. **Automated Nuke Script Scaffolding (`.nk`):**
   - When Compositing is enabled, generates production-ready `.nk` scripts for every shot.
   - Configures Nuke Root settings (`fps`, `resolution`, `colorManagement`, `OCIO_config`, `working_space`, `frame_start`, `frame_end`).
   - Inserts `Read_PLATE` pointing to conformed plates, and dual write nodes: `Write_HIRES` (16-bit half EXR) and `Write_REVIEW` (ProRes/H.264 MOV).
   - Uses relative Nuke expressions (`[file dirname [value root.name]]/../../`) ensuring scripts open anywhere across drives, workstations, and NAS storage without broken links.
5. **Non-Destructive Project Modification:**
   - Safely add new shots, sequences, or modules to existing projects.
   - Automatically archives previous metadata into `_pipeline/history/project_meta_{timestamp}.json`.
   - Never deletes existing files or work.
6. **In-App Manual & Template Editor:**
   - Studio leads can edit `pipeline_template.json` directly from the UI with built-in JSON syntax validation.
7. **Incoming Safety:**
   - Automatically places an immutability reminder (`README_INGEST.txt`) inside `incoming/`.

---

## 🛠️ How to Run Locally

### Prerequisites
- Python 3.9+ installed.

### Steps
1. Double-click `run_app.bat` (or run in terminal):
   ```bash
   pip install -r requirements.txt
   python src/main.py
   ```

---

## 📦 How to Build the Standalone Portable Executable (`.exe`)

Simply double-click **`build_portable.bat`**.

This executes PyInstaller with optimized flags and generates:
```text
dist/PostProjectManager.exe
```
This `.exe` can be copied to a USB drive, NAS, or another PC and runs independently with zero installations.

---

## 🌐 GitHub Release Automation (CI/CD)

This repository includes a GitHub Actions workflow (`.github/workflows/build_release.yml`).

### To publish a new release:
1. Push your code to your GitHub repository.
2. Create and push a version tag:
   ```bash
   git tag v1.0.2
   git push origin v1.0.2
   ```
3. GitHub Actions will automatically compile `PostProjectManager.exe` and publish the release with the standalone executable attached.
