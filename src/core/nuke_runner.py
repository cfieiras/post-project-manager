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


def find_nuke_executable() -> Optional[str]:
    """Finds installed Nuke executable on the host system."""
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

    def __init__(self, parent=None):
        super().__init__(parent)
        self.nuke_exe = find_nuke_executable()
        self.process: Optional[QProcess] = None
        self.queue: List[dict] = []
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
        if not self.nuke_exe or not Path(self.nuke_exe).exists():
            self.batch_finished.emit(False, "Nuke executable not found on this machine.")
            return

        if not jobs:
            self.batch_finished.emit(False, "Render queue is empty.")
            return

        self.queue = jobs
        self.current_idx = 0
        self.total_jobs = len(jobs)
        self.is_cancelled = False
        self._run_next_job()

    def _run_next_job(self):
        if self.is_cancelled:
            self.batch_finished.emit(False, "Render cancelled by user.")
            return

        if self.current_idx >= self.total_jobs:
            self.batch_finished.emit(True, f"All {self.total_jobs} shots rendered successfully!")
            return

        job = self.queue[self.current_idx]
        shot_name = job["shot_name"]
        script_path = job["script_path"]
        write_node = job.get("write_node")
        frame_range = job.get("frame_range", "1001,1100")

        self.progress_changed.emit(self.current_idx + 1, self.total_jobs, shot_name)
        self.output_received.emit(f"\n--- [Rendering {self.current_idx + 1}/{self.total_jobs}] {shot_name} ---")

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
        if exit_code != 0:
            self.output_received.emit(f"Warning: Shot completed with exit code {exit_code}")
        self.current_idx += 1
        self._run_next_job()

    def cancel(self):
        self.is_cancelled = True
        if self.process and self.process.state() == QProcess.Running:
            self.process.kill()
