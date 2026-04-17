from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Optional

from PyQt5.QtCore import Qt, QMimeData, pyqtSignal
from PyQt5.QtGui import QDragEnterEvent, QDragLeaveEvent, QDropEvent
from PyQt5.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from qfluentwidgets import BodyLabel, CaptionLabel, PrimaryPushButton, SwitchButton, StrongBodyLabel, SubtitleLabel

from ReviewInterface.dubbingedit_app.core.project_importer import import_project_folder
from ReviewInterface.dubbingedit_app.services.playback_controller import PlaybackController

if TYPE_CHECKING:
    pass


def _fmt_clock(ms: int) -> str:
    ms = max(0, int(ms))
    total_seconds = ms // 1000
    milliseconds = ms % 1000
    h = total_seconds // 3600
    m = (total_seconds % 3600) // 60
    s = total_seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}.{milliseconds:03d}"


class VideoPanel(QWidget):
    project_imported = pyqtSignal(object)

    def __init__(self, controller: PlaybackController, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._controller = controller
        self._is_drag_over = False

        from PyQt5.QtMultimediaWidgets import QVideoWidget

        self.video_widget = QVideoWidget(self)
        self.video_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.video_widget.setStyleSheet("""
            QVideoWidget {
                background-color: rgba(0, 0, 0, 0.8);
                border: 1px solid rgba(0, 0, 0, 0.2);
                border-radius: 8px;
                padding: 4px;
            }
        """)
        self._controller.video_player.setVideoOutput(self.video_widget)

        self._play_btn = PrimaryPushButton("播放", self)
        self._play_btn.clicked.connect(self._on_play_clicked)

        self._time_label = BodyLabel("00:00:00.000 / 00:00:00.000", self)

        self._bgm_switch = SwitchButton(self)
        self._vocal_switch = SwitchButton(self)
        self._dub_switch = SwitchButton(self)

        self._bgm_label = CaptionLabel("BGM", self)
        self._vocal_label = CaptionLabel("原人声", self)
        self._dub_label = CaptionLabel("配音人声", self)

        self._bgm_switch.setChecked(True)
        self._vocal_switch.setChecked(False)
        self._dub_switch.setChecked(True)

        self._bgm_switch.checkedChanged.connect(self._on_bgm)
        self._vocal_switch.checkedChanged.connect(self._on_vocal)
        self._dub_switch.checkedChanged.connect(self._on_dub)

        self._controller.video_player.durationChanged.connect(self._refresh_time)
        self._controller.video_player.positionChanged.connect(self._refresh_time)
        self._controller.video_player.stateChanged.connect(self._on_state)

        bar = QHBoxLayout()
        bar.addWidget(self._play_btn, 0, Qt.AlignLeft)
        bar.addWidget(self._time_label, 0, Qt.AlignLeft)
        bar.addStretch(1)
        bar.addWidget(self._bgm_label)
        bar.addWidget(self._bgm_switch)
        bar.addSpacing(12)
        bar.addWidget(self._vocal_label)
        bar.addWidget(self._vocal_switch)
        bar.addSpacing(12)
        bar.addWidget(self._dub_label)
        bar.addWidget(self._dub_switch)

        title = SubtitleLabel("视频预览", self)
        root = QVBoxLayout(self)
        root.addWidget(title)
        root.addWidget(self.video_widget, 1)
        root.addLayout(bar)

        self.setMinimumWidth(400)
        self._apply_track_availability(False, False)
        self.setAcceptDrops(True)
        # self._update_border_style(True)
        # self._set_drag_overlay(True)

    def _on_play_clicked(self) -> None:
        self._controller.toggle_play()

    def _on_state(self, state) -> None:
        from PyQt5.QtMultimedia import QMediaPlayer

        if state == QMediaPlayer.PlayingState:
            self._play_btn.setText("暂停")
        else:
            self._play_btn.setText("播放")

    def _refresh_time(self, *_args) -> None:
        cur = _fmt_clock(self._controller.position_ms())
        total = _fmt_clock(self._controller.duration_ms())
        self._time_label.setText(f"{cur} / {total}")

    def _on_bgm(self, checked: bool) -> None:
        self._controller.set_bgm_enabled(checked)

    def _on_vocal(self, checked: bool) -> None:
        self._controller.set_vocal_enabled(checked)

    def _on_dub(self, checked: bool) -> None:
        self._controller.set_dub_enabled(checked)

    def reset_default_switches(self) -> None:
        self._bgm_switch.setChecked(True)
        self._vocal_switch.setChecked(False)
        self._dub_switch.setChecked(True)

    def _apply_track_availability(self, has_bgm: bool, has_vocal: bool) -> None:
        # self._bgm_switch.setEnabled(has_bgm)
        # self._vocal_switch.setEnabled(has_vocal)
        self._bgm_label.setEnabled(has_bgm)
        self._vocal_label.setEnabled(has_vocal)
        tip_bgm = "" if has_bgm else "未找到 *background* 文件"
        tip_vc = "" if has_vocal else "未找到 *vocal* 文件"
        # self._bgm_switch.setToolTip(tip_bgm)
        self._bgm_label.setToolTip(tip_bgm)
        self._vocal_switch.setToolTip(tip_vc)
        self._vocal_label.setToolTip(tip_vc)

    def bind_paths(self, has_bgm: bool, has_vocal: bool) -> None:
        self._update_border_style(False)
        self._set_drag_overlay_init(False)
        self._apply_track_availability(has_bgm, has_vocal)
        self._controller.apply_track_mutes()
        self._auto_play_when_loaded()


    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls and urls[0].isLocalFile():
                event.acceptProposedAction()
                self._is_drag_over = True
                self._update_border_style(True)
                self._set_drag_overlay(True)

    def dragLeaveEvent(self, event: QDragLeaveEvent) -> None:
        self._is_drag_over = False
        self._update_border_style(False)
        self._set_drag_overlay(False)

    def dropEvent(self, event: QDropEvent) -> None:
        self._is_drag_over = False
        self._update_border_style(False)
        self._set_drag_overlay(False)

        urls = event.mimeData().urls()
        if not urls or not urls[0].isLocalFile():
            return

        path = urls[0].toLocalFile()
        result = import_project_folder(path)
        # if result.ok and result.paths:
        self.project_imported.emit(result)

    def _update_border_style(self, highlight: bool) -> None:
        if highlight:
            self.setStyleSheet("""
                VideoPanel {
                    border: 3px dashed #0078D4;
                    border-radius: 4px;
                    background-color: rgba(0, 120, 212, 0.05);
                }
            """)
        else:
            self.setStyleSheet("")

    def _auto_play_when_loaded(self) -> None:
        from PyQt5.QtMultimedia import QMediaPlayer

        def on_media_status_changed(status: QMediaPlayer.MediaStatus) -> None:
            if status == QMediaPlayer.LoadedMedia:
                self._controller.video_player.mediaStatusChanged.disconnect(on_media_status_changed)
                self._controller.play()

        self._controller.video_player.mediaStatusChanged.connect(on_media_status_changed)

    def _set_drag_overlay(self, show: bool) -> None:
        self._set_drag_overlay_init(False)
        if show:
            if hasattr(self, '_drag_overlay'):
                self._drag_overlay.deleteLater()

            from PyQt5.QtWidgets import QFrame
            from PyQt5.QtCore import Qt
            from PyQt5.QtGui import QFont

            self._drag_overlay = QFrame(self)
            self._drag_overlay.setStyleSheet("""
                QFrame {
                    background-color: rgba(0, 120, 212, 0.3);
                    border-radius: 8px;
                }
            """)
            self._drag_overlay.setGeometry(0, 0, self.width(), self.height())

            overlay_layout = QVBoxLayout(self._drag_overlay)
            overlay_layout.setAlignment(Qt.AlignCenter)

            from qfluentwidgets import StrongBodyLabel
            icon_label = StrongBodyLabel("📁", self._drag_overlay)
            icon_label.setAlignment(Qt.AlignCenter)
            icon_label.setStyleSheet("font-size: 48px;")

            text_label = StrongBodyLabel("拖拽项目文件夹到此处导入", self._drag_overlay)
            text_label.setAlignment(Qt.AlignCenter)
            text_label.setStyleSheet("font-size: 16px; color: white;")

            hint_label = StrongBodyLabel("支持包含 video/background/vocal/subtitle 文件的项目文件夹", self._drag_overlay)
            hint_label.setAlignment(Qt.AlignCenter)
            hint_label.setStyleSheet("font-size: 12px; color: rgba(255, 255, 255, 0.8);")

            overlay_layout.addWidget(icon_label)
            overlay_layout.addSpacing(10)
            overlay_layout.addWidget(text_label)
            overlay_layout.addSpacing(5)
            overlay_layout.addWidget(hint_label)

            self._drag_overlay.raise_()
            self._drag_overlay.show()
        else:
            if hasattr(self, '_drag_overlay'):
                self._drag_overlay.hide()
                self._drag_overlay.deleteLater()
                delattr(self, '_drag_overlay')


    def _set_drag_overlay_init(self, show: bool) -> None:
        print("set_drag_overlay_init", show)
        if show:
            if hasattr(self, '_drag_overlay'):
                self._drag_overlay.deleteLater()

            from PyQt5.QtWidgets import QFrame
            from PyQt5.QtCore import Qt

            self._drag_overlay = QFrame(self)
            self._drag_overlay.setObjectName("drag_overlay")
            self._drag_overlay.setStyleSheet("""
                 QFrame{
                    background-color: rgba(255, 255, 255, 0.3);
                    border-radius: 8px;
                }
            """)
            self._drag_overlay.setGeometry(0, 0, self.width(), self.height())

            overlay_layout = QVBoxLayout(self._drag_overlay)
            overlay_layout.setAlignment(Qt.AlignCenter)

            from qfluentwidgets import StrongBodyLabel
            icon_label = StrongBodyLabel("📁", self._drag_overlay)
            icon_label.setAlignment(Qt.AlignCenter)
            icon_label.setStyleSheet("font-size: 48px;")

            text_label = StrongBodyLabel("拖拽项目文件夹到此处导入", self._drag_overlay)
            text_label.setAlignment(Qt.AlignCenter)
            text_label.setStyleSheet("font-size: 16px; color: black;")

            hint_label = StrongBodyLabel("支持包含 video/background/vocal/subtitle 文件的项目文件夹", self._drag_overlay)
            hint_label.setAlignment(Qt.AlignCenter)
            hint_label.setStyleSheet("font-size: 12px; ")

            overlay_layout.addWidget(icon_label)
            overlay_layout.addSpacing(10)
            overlay_layout.addWidget(text_label)
            overlay_layout.addSpacing(5)
            overlay_layout.addWidget(hint_label)

            self._drag_overlay.raise_()
            self._drag_overlay.show()
        else:
            if hasattr(self, '_drag_overlay'):
                self._drag_overlay.hide()
                self._drag_overlay.deleteLater()
                delattr(self, '_drag_overlay')