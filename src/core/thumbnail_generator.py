"""
Thumbnail Generator & Cache Manager for Post Project Manager.
Extracts poster frames from review video files using OpenCV or generates
procedural film slate placeholder cards with play overlays.
"""

from pathlib import Path
from typing import Any, Dict, Optional

from PySide6.QtCore import Qt, QRect
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen, QPixmap

try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False


class ThumbnailManager:
    @classmethod
    def get_thumbnail(
        cls,
        project_dir: Path,
        shot: Dict[str, Any],
        width: int = 120,
        height: int = 68
    ) -> QPixmap:
        """
        Returns a cached or extracted QPixmap thumbnail for a shot.
        """
        review_path_str = shot.get("latest_review_path")
        review_ver = shot.get("latest_review_version", "none")
        shot_name = shot.get("shot_name", "shot")

        cache_dir = project_dir / "_pipeline" / ".thumbnails"
        cache_dir.mkdir(parents=True, exist_ok=True)
        cached_file = cache_dir / f"{shot_name}_{review_ver}.jpg"

        # 1. Return from disk cache if exists
        if cached_file.exists():
            pix = QPixmap(str(cached_file))
            if not pix.isNull():
                return cls._overlay_play_icon(pix.scaled(width, height, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation), width, height, review_ver)

        # 2. Extract from review video using cv2
        if review_path_str and HAS_CV2 and Path(review_path_str).exists():
            try:
                cap = cv2.VideoCapture(str(review_path_str))
                # Grab frame at 25% of duration or frame 0
                total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                target_frame = min(max(0, total_frames // 4), 100)
                cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame)
                success, frame = cap.read()
                cap.release()

                if success and frame is not None:
                    # Convert BGR to RGB
                    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    h, w, ch = frame_rgb.shape
                    qimg = QImage(frame_rgb.data, w, h, ch * w, QImage.Format_RGB888)
                    pix = QPixmap.fromImage(qimg)

                    # Save to cache
                    pix.save(str(cached_file), "JPG", 85)

                    scaled = pix.scaled(width, height, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                    return cls._overlay_play_icon(scaled, width, height, review_ver)
            except Exception as e:
                print(f"Warning: Failed to extract frame from {review_path_str}: {e}")

        # 3. Procedural Film Slate Placeholder
        return cls._create_placeholder(shot_name, width, height)

    @classmethod
    def _overlay_play_icon(cls, base_pixmap: QPixmap, width: int, height: int, version: str) -> QPixmap:
        """Adds a play icon overlay and version tag in the corner of the thumbnail."""
        result = QPixmap(width, height)
        result.fill(Qt.transparent)

        painter = QPainter(result)
        painter.setRenderHint(QPainter.Antialiasing)

        # Draw cropped base image
        target_rect = QRect(0, 0, width, height)
        src_x = max(0, (base_pixmap.width() - width) // 2)
        src_y = max(0, (base_pixmap.height() - height) // 2)
        painter.drawPixmap(target_rect, base_pixmap, QRect(src_x, src_y, width, height))

        # Dark overlay on hover or subtle bottom bar
        painter.fillRect(QRect(0, height - 18, width, 18), QColor(0, 0, 0, 160))

        # Version tag
        painter.setPen(QColor("#4da6ff"))
        font = QFont("Segoe UI", 8, QFont.Bold)
        painter.setFont(font)
        painter.drawText(QRect(6, height - 17, width - 12, 16), Qt.AlignLeft | Qt.AlignVCenter, version)

        # Center Play Icon circle
        center_x, center_y = width // 2, (height - 10) // 2
        painter.setBrush(QColor(0, 0, 0, 140))
        painter.setPen(QColor(255, 255, 255, 180))
        painter.drawEllipse(center_x - 12, center_y - 12, 24, 24)

        # Play Triangle
        painter.setBrush(QColor(255, 255, 255, 220))
        painter.setPen(Qt.NoPen)
        from PySide6.QtGui import QPolygonF
        from PySide6.QtCore import QPointF
        triangle = QPolygonF([
            QPointF(center_x - 3, center_y - 6),
            QPointF(center_x - 3, center_y + 6),
            QPointF(center_x + 6, center_y)
        ])
        painter.drawPolygon(triangle)

        painter.end()
        return result

    @classmethod
    def _create_placeholder(cls, shot_name: str, width: int, height: int) -> QPixmap:
        """Creates a modern dark slate placeholder when no review video exists."""
        pix = QPixmap(width, height)
        pix.fill(QColor("#1b1b1f"))

        painter = QPainter(pix)
        painter.setRenderHint(QPainter.Antialiasing)

        # Subtle border
        painter.setPen(QPen(QColor("#33333d"), 1))
        painter.drawRect(0, 0, width - 1, height - 1)

        # Film slate icon / text
        painter.setPen(QColor("#60606a"))
        font_icon = QFont("Segoe UI", 12)
        painter.setFont(font_icon)
        painter.drawText(QRect(0, 12, width, 22), Qt.AlignCenter, "🎞️")

        font_text = QFont("Segoe UI", 8)
        painter.setFont(font_text)
        painter.setPen(QColor("#80808a"))
        painter.drawText(QRect(0, 38, width, 16), Qt.AlignCenter, "No Review")

        painter.end()
        return pix
