# Post Project Manager (Portable Desktop App)

> **Modular Project Scaffolding & Pipeline Manager for Post-Production (VFX, 3D DCC, Unreal Engine, Compo & AI)**  
> **Author:** Cristian Fieiras  
> **Version:** 1.0.0  

---

## 🚀 Overview

**Post Project Manager** is a standalone, lightweight, and portable desktop tool designed for post-production studios, VFX facilities, and freelancers. It automates studio directory scaffolding, standardizes project naming conventions, generates starter Nuke compositing scripts with dynamic relative paths, and provides non-destructive project updates.

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
   - Automatically places an inmutability reminder (`README_INGEST.txt`) inside `incoming/`.

---

## 📁 Repository Structure

```text
tools/project_manager/
├── .github/
│   └── workflows/
│       └── build_release.yml     # Automated GitHub CI/CD workflow to build .exe releases
├── templates/
│   └── default_template.json     # Editable studio schema / manual
├── src/
│   ├── core/
│   │   ├── pipeline.py           # Project engine, folder builder & safe updater
│   │   └── nuke_generator.py     # Production .nk script generator
│   ├── ui/
│   │   ├── main_window.py        # Project explorer and main GUI
│   │   ├── create_dialog.py      # Project wizard with Live Tree Preview
│   │   ├── template_dialog.py    # Schema & template JSON editor
│   │   └── theme.py              # VFX dark theme stylesheet
│   └── main.py                   # Application entry point
├── build_portable.bat            # Local one-click PyInstaller compiler
├── run_app.bat                   # Quick launcher for local testing
├── requirements.txt              # PySide6 & pyinstaller dependencies
└── README.md
```

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
   git tag v1.0.0
   git push origin v1.0.0
   ```
3. GitHub Actions will automatically:
   - Spin up a clean Windows machine.
   - Compile `PostProjectManager.exe` with PyInstaller.
   - Bundle it into `PostProjectManager_portable_windows.zip`.
   - Create a public **GitHub Release** with the zip file attached ready for download!
