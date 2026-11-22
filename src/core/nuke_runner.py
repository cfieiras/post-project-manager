"""
Nuke CLI Headless Render Engine.
Executes batch and individual shot renders in background threads without blocking UI.
"""

import glob
import os
import subprocess
import sys
from pathlib import Path
from typing import List, Optional
from PySide6.QtCore import QObject, QProcess, Signal

from .nuke_generator import conform_nuke_script_write_paths


def find_nuke_executable() -> Optional[str]:
    """Finds installed Nuke executable on the host system or from configured DCC settings."""
    try:
        from .config_manager import get_dcc_paths
        configured = get_dcc_paths().get("nuke")
        if configured and Path(configured).exists():
            return configured
    except Exception:
        pass

    if sys.platform == "win32":
        search_paths = [
            r"C:\Program Files\Nuke*",
            r"C:\Program Files\Foundry\Nuke*"
        ]
        for sp in search_paths:
            for folder in sorted(glob.glob(sp), reverse=True):
                for pattern in ["Nuke*.exe", "nuke.exe"]:
                    for match in glob.glob(os.path.join(folder, pattern)):
                        lower = match.lower()
                        if "uninstall" not in lower and "crash" not in lower and "helper" not in lower:
                            return match
    elif sys.platform == "darwin":
        matches = sorted(glob.glob("/Applications/Nuke*.app/Contents/MacOS/Nuke*"), reverse=True)
        if matches:
            return matches[0]
    else:
        # Linux
        matches = sorted(glob.glob("/usr/local/Nuke*/Nuke*"), reverse=True)
        if matches:
            return matches[0]
    return None


class NukeBatchRunner(QObject):
    """Asynchronous background runner for Nuke headless batch rendering."""
    progress_changed = Signal(int, int, str)  # current, total, shot_name
    output_received = Signal(str)             # log output line
    batch_finished = Signal(bool, str)        # success, message
    job_finished = Signal(int, str, bool, int) # current_idx, shot_name, success, exit_code

    def __init__(self, parent=None):
        super().__init__(parent)
        self.nuke_exe = find_nuke_executable()
        self.process: Optional[QProcess] = None
        self.queue: List[dict] = []
        self.failed_jobs: List[dict] = []
        self.current_idx = 0
        self.total_jobs = 0
        self.is_cancelled = False

    def start_batch(self, jobs: List[dict]):
        """
        Jobs list format:
        [
            {
                "shot_name": "sq010_sh010",
                "script_path": "path/to/script.nk",
                "write_node": "Write_REVIEW", # or "Write_HIRES" or None (all)
                "frame_range": "1001,1100"
            }
        ]
        """
        # Refresh executable check
        self.nuke_exe = find_nuke_executable()
        if not self.nuke_exe or not Path(self.nuke_exe).exists():
            err_msg = (
                f"Nuke executable not found on this machine.\n"
                f"Please configure your Nuke path in Settings -> DCC Executables."
            )
            self.output_received.emit(f"❌ {err_msg}")
            self.batch_finished.emit(False, err_msg)
            return

        if not jobs:
            self.batch_finished.emit(False, "Render queue is empty. No scripts to execute.")
            return

        self.queue = jobs
        self.failed_jobs = []
        self.current_idx = 0
        self.total_jobs = len(jobs)
        self.is_cancelled = False
        self._run_next_job()

    def _run_next_job(self):
        if self.is_cancelled:
            self.batch_finished.emit(False, "Render cancelled by user.")
            return

        if self.current_idx >= self.total_jobs:
            if self.failed_jobs:
                failed_names = ", ".join([j["shot_name"] for j in self.failed_jobs])
                self.batch_finished.emit(
                    False,
                    f"Batch render finished with {len(self.failed_jobs)} error(s):\n{failed_names}"
                )
            else:
                self.batch_finished.emit(True, f"All {self.total_jobs} shots rendered successfully!")
            return

        job = self.queue[self.current_idx]
        shot_name = job["shot_name"]
        script_path = job["script_path"]
        write_node = job.get("write_node")
        frame_range = job.get("frame_range", "1001,1100")

        self.progress_changed.emit(self.current_idx + 1, self.total_jobs, shot_name)
        self.output_received.emit(f"\n--- [Rendering {self.current_idx + 1}/{self.total_jobs}] {shot_name} ---")

        # Check if script exists
        if not Path(script_path).exists():
            err_msg = f"Script file not found: {script_path}"
            self.output_received.emit(f"❌ Error: {err_msg}")
            self.failed_jobs.append({"shot_name": shot_name, "error": err_msg})
            self.job_finished.emit(self.current_idx + 1, shot_name, False, -1)
            self.current_idx += 1
            self._run_next_job()
            return

        # Automatically conform Write nodes to match the exact script version and basename
        conform_nuke_script_write_paths(Path(script_path))

        # Build Nuke CLI arguments
        args = ["-x"]
        if write_node:
            args.extend(["-X", write_node])
        args.append(script_path)
        if frame_range:
            args.append(frame_range)

        self.process = QProcess(self)
        self.process.readyReadStandardOutput.connect(self._on_stdout)
        self.process.readyReadStandardError.connect(self._on_stderr)
        self.process.finished.connect(self._on_job_finished)

        self.output_received.emit(f"Executing: {self.nuke_exe} {' '.join(args)}")
        self.process.start(self.nuke_exe, args)

    def _on_stdout(self):
        if self.process:
            data = self.process.readAllStandardOutput().data().decode("utf-8", errors="replace")
            self.output_received.emit(data)

    def _on_stderr(self):
        if self.process:
            data = self.process.readAllStandardError().data().decode("utf-8", errors="replace")
            self.output_received.emit(data)

    def _on_job_finished(self, exit_code, exit_status):
        job = self.queue[self.current_idx] if self.current_idx < len(self.queue) else {"shot_name": "Job"}
        shot_name = job.get("shot_name", "Job")

        if exit_code != 0:
            err = f"Failed with exit code {exit_code}"
            self.output_received.emit(f"❌ Error: {shot_name} {err}")
            self.failed_jobs.append({"shot_name": shot_name, "error": err})
            self.job_finished.emit(self.current_idx + 1, shot_name, False, exit_code)
        else:
            self.output_received.emit(f"✔ Done: {shot_name} completed successfully.")
            self.job_finished.emit(self.current_idx + 1, shot_name, True, 0)

        self.current_idx += 1
        self._run_next_job()

    def is_running(self) -> bool:
        """Returns True if a render process is currently executing."""
        return self.process is not None and self.process.state() != QProcess.NotRunning

    def append_jobs(self, new_jobs: List[dict]):
        """Dynamically enqueues new jobs to the sequential batch queue."""
        if not new_jobs:
            return
        if not self.is_running():
            self.start_batch(new_jobs)
        else:
            self.queue.extend(new_jobs)
            self.total_jobs = len(self.queue)
            self.output_received.emit(
                f"\n--- [Queue Updated] Enqueued {len(new_jobs)} additional shot(s). Sequential queue: {self.total_jobs} total ---"
            )

    def cancel(self):
        self.is_cancelled = True
        if self.process and self.process.state() == QProcess.Running:
            self.process.kill()
