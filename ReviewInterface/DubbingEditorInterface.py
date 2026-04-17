from __future__ import annotations

import sys
from typing import Any, Optional

from PyQt5.QtCore import Qt, QUrl, QPropertyAnimation, QEasingCurve
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtWidgets import QFileDialog, QHBoxLayout, QSplitter, QVBoxLayout, QWidget, QApplication, QDesktopWidget, \
    QWIDGETSIZE_MAX, QSizePolicy, QFrame, QDialog

from qfluentwidgets import (
    FluentIcon,
    FluentWindow,
    InfoBar,
    InfoBarPosition,
    MessageBox,
    NavigationItemPosition,
    PrimaryPushButton,
    Theme,
    setTheme, Slider, HyperlinkButton, Dialog,
)

from ReviewInterface.dubbingedit_app.core.project_importer import import_project_folder
from ReviewInterface.dubbingedit_app.core.subtitle_io import write_merged_subtitle
from ReviewInterface.dubbingedit_app.core.subtitle_parser import parse_subtitle_uncertain, timecode_to_ms, \
    ms_to_timecode
from ReviewInterface.dubbingedit_app.core.workspace_paths import WorkspacePaths
from ReviewInterface.dubbingedit_app.services.playback_controller import PlaybackController
from ReviewInterface.dubbingedit_app.services.submit_worker import FunctionWorker
from ReviewInterface.dubbingedit_app.ui.edit_panel import EditPanel
from ReviewInterface.dubbingedit_app.ui.subtitle_list import SubtitleListPanel
from ReviewInterface.dubbingedit_app.ui.video_panel import VideoPanel
from ReviewInterface.dubbingedit_app.utils.audio_edit import apply_speed_to_segment

import subprocess
import os
import shutil
import time


class DubbingEditorInterface(FluentWindow):
    def __init__(self) -> None:
        super().__init__()
        setTheme(Theme.LIGHT)
        # self.setWindowTitle("配音编辑界面")
        self.resize(1400, 840)

        # 设置最小窗口大小，允许用户调整大小
        # self.setMinimumSize(1200, 800)
        # self.setMaximumSize(QWIDGETSIZE_MAX, QWIDGETSIZE_MAX)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self._paths: Optional[WorkspacePaths] = None
        self._subtitles: list[dict[str, Any]] = []
        self._roles: list[str] = []
        self._worker: Optional[FunctionWorker] = None
        self._busy_dialog: Optional[QDialog] = None

        self._controller = PlaybackController(self)

        self._center = QFrame()
        self._center.setObjectName("editorCenter")
        self._center.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.addSubInterface(self._center, FluentIcon.MUSIC, "配音编辑", NavigationItemPosition.TOP)

        self._video_panel = VideoPanel(self._controller, self._center)
        self._video_panel.project_imported.connect(self._on_project_imported)

        self._subtitle_panel = SubtitleListPanel(self._center)
        self._edit_panel = EditPanel(self._center)
        self._edit_panel.pause.connect(self._controller.pause)

        self._split = QSplitter(Qt.Horizontal, self._center)
        self._split.setHandleWidth(6)
        self._split.setChildrenCollapsible(False)
        self._split.addWidget(self._video_panel)
        self._split.addWidget(self._subtitle_panel)
        self._split.setStretchFactor(0, 3)
        self._split.setStretchFactor(1, 4)
        self._split.setSizes([520, 720])

        self._progress_slider = Slider(Qt.Horizontal, self._center)
        self._progress_slider.setRange(0, 100000)
        self._progress_slider.setValue(0)
        self._progress_slider.setEnabled(False)
        self._is_slider_dragging = False
        self._progress_slider.sliderPressed.connect(self._on_slider_pressed)
        self._progress_slider.sliderReleased.connect(self._on_slider_released)
        self._progress_slider.valueChanged.connect(self._on_slider_value_changed)

        layout = QVBoxLayout(self._center)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        slider_container = QWidget(self._center)
        slider_container_layout = QVBoxLayout(slider_container)
        slider_container_layout.setContentsMargins(12, 8, 12, 8)
        slider_container_layout.addWidget(self._progress_slider)


        main_content = QWidget(self._center)
        main_content_layout = QVBoxLayout(main_content)
        main_content_layout.setContentsMargins(12, 0, 12, 12)
        main_content_layout.setSpacing(0)


        self._import_btn = PrimaryPushButton("导入项目", self)
        self._import_btn.clicked.connect(self._on_import_project)

        self._save_btn = PrimaryPushButton("保存", self)
        self._save_btn.clicked.connect(self._on_save_video)
        self._save_btn.setEnabled(False)

        self._help_btn = PrimaryPushButton("使用说明", self)
        self._help_btn.clicked.connect(self._on_help_clicked)

        # 创建可点击的标题按钮
        # self._title_btn = QPushButton("配音编辑界面", self)
        self._title_btn = HyperlinkButton()
        self._title_btn.setText("配音编辑界面")
        self._title_btn.clicked.connect(self._on_title_clicked)

        self.titleBar.hBoxLayout.insertWidget(0, self._import_btn, 0, Qt.AlignLeft)
        self.titleBar.hBoxLayout.insertWidget(1, self._save_btn, 0, Qt.AlignLeft)
        self.titleBar.hBoxLayout.insertWidget(2, self._help_btn, 0, Qt.AlignLeft)
        self.titleBar.hBoxLayout.insertWidget(3, self._title_btn, 0, Qt.AlignCenter)
        self.titleBar.hBoxLayout.addStretch()
        self.titleBar.hBoxLayout.setSpacing(10)
        self.titleBar.setContentsMargins(5, 0, 5, 0)

        # 创建垂直分割器，用于调整上下组件高度
        self._vertical_splitter = QSplitter(Qt.Vertical, self._center)
        self._vertical_splitter.setHandleWidth(6)
        self._vertical_splitter.setChildrenCollapsible(False)

        # 创建下方内容容器（包含 slider_container 和 edit_panel）
        bottom_container = QWidget(self._center)
        bottom_container_layout = QVBoxLayout(bottom_container)
        bottom_container_layout.setContentsMargins(0, 8, 0, 0)
        bottom_container_layout.setSpacing(8)
        bottom_container_layout.addWidget(slider_container, 0)
        bottom_container_layout.addWidget(self._edit_panel, 1)

        # 将组件添加到垂直分割器中
        self._vertical_splitter.addWidget(self._split)
        self._vertical_splitter.addWidget(bottom_container)
        self._vertical_splitter.setStretchFactor(0, 3)
        self._vertical_splitter.setStretchFactor(1, 1)
        self._vertical_splitter.setSizes([500, 340])

        # 将垂直分割器添加到主布局
        main_content_layout.addWidget(self._vertical_splitter, 1)

        layout.addWidget(main_content, 1)


        # self.addSubInterface(self._center, FluentIcon.MUSIC, "配音编辑", NavigationItemPosition.TOP)

        self._subtitle_panel.block_selected.connect(self._on_block_selected)
        self._controller.video_player.positionChanged.connect(self._subtitle_panel.update_playhead)
        self._controller.video_player.positionChanged.connect(self._update_progress_slider)
        self._controller.video_player.durationChanged.connect(self._update_slider_range)
        self._edit_panel.submit_requested.connect(self._on_submit_requested)

        self._apply_soft_theme()

        self.show()
        # self._video_panel._update_border_style(True)
        # self._video_panel._set_drag_overlay_init(True)

    def show_animation(self):
        width  = 1400
        height = 840
        screen = QDesktopWidget().screenGeometry()
        x = (screen.width()  - width)  // 2
        y = (screen.height() - height) // 2
        self.setGeometry(x, y, width, height)
        self.setWindowOpacity(0)
        self.animation = QPropertyAnimation(self, b"windowOpacity")
        self.animation.setDuration(300)
        self.animation.setStartValue(0)
        self.animation.setEndValue(1)
        self.animation.setEasingCurve(QEasingCurve.InOutQuad)
        self.animation.start()
        # self.show()
        self._video_panel._update_border_style(True)
        self._video_panel._set_drag_overlay_init(True)

    def _on_slider_pressed(self) -> None:
        self._is_slider_dragging = True
        self._controller.pause()

    def _on_slider_released(self) -> None:
        self._is_slider_dragging = False
        position = self._progress_slider.value()
        self._controller.seek(position)
        self._controller.play()

    def _on_slider_value_changed(self, value: int) -> None:
        if self._is_slider_dragging:
            self._controller.seek(value)

    def _update_progress_slider(self, position_ms: int) -> None:
        # self._progress_slider.setValue(position_ms)
        if not self._is_slider_dragging:
            if abs(position_ms - self._progress_slider.value()) >10:
                self._progress_slider.setValue(position_ms)
        # self._progress_slider.blockSignals(False)

    def _update_slider_range(self, duration_ms: int) -> None:
        print(duration_ms,"时长"),
        if duration_ms > 0:
            self._progress_slider.setEnabled(True)
            self._progress_slider.setRange(0, duration_ms)
        else:
            self._progress_slider.setEnabled(False)
            self._progress_slider.setValue(0)

    def closeEvent(self, event) -> None:
        self._controller.shutdown()
        super().closeEvent(event)

    def _apply_soft_theme(self) -> None:
        self._center.setStyleSheet(
            """
            QWidget { background-color: #FAFAFA; color: #2B2B2B; }
            QSplitter::handle { background: #E0E8F5; }
            """
        )

    def _on_project_imported(self, result) -> None:
        print(result)
        if not result.ok or not result.paths:
            InfoBar.error(
                title="导入失败",
                content="该文件夹不是配音项目"+result.message,
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP_RIGHT,
                duration=5000,
                parent=self,
            )
            return

        self._paths = result.paths
        # self.setWindowTitle(f"配音编辑界面 - {result.paths.project_name}")
        self._title_btn.setText(f"配音编辑界面 - {result.paths.project_name}")

        subs, roles_raw = parse_subtitle_uncertain(self._paths.subtitle)
        if not subs:
            InfoBar.error(
                title="导入失败",
                content="字幕解析失败或文件为空",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP_RIGHT,
                duration=5000,
                parent=self,
            )
            return

        self._subtitles = subs
        if roles_raw and len(roles_raw) == len(subs):
            self._roles = roles_raw
        else:
            self._roles = ["default"] * len(subs)

        self._controller.set_paths(self._paths)
        self._video_panel.bind_paths(bool(self._paths.background), bool(self._paths.vocal))
        self._video_panel.reset_default_switches()
        self._subtitle_panel.set_subtitles(self._subtitles, self._roles)
        self._edit_panel.clear()
        self._progress_slider.setEnabled(True)
        self._save_btn.setEnabled(True)

        InfoBar.success(
            title="导入成功",
            content="已复制到 workspace，后续操作仅作用于副本",
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP_RIGHT,
            duration=2500,
            parent=self,
        )



    def _on_import_project(self, folder: str="") -> None:
        if not folder:
            folder = QFileDialog.getExistingDirectory(self, "选择项目文件夹")
        if not folder:
            return
        result = import_project_folder(folder)
        if not result.ok or not result.paths:
            box = Dialog("导入失败", "该文件夹不是配音项目"+result.message, self)
            box.exec()
            # InfoBar.error(
            #     title="导入失败",
            #     content="该文件夹不是配音项目"+result.message,
            #     orient=Qt.Horizontal,
            #     isClosable=True,
            #     position=InfoBarPosition.TOP_RIGHT,
            #     duration=5000,
            #     parent=self,
            # )
            return

        self._paths = result.paths
        # self.setWindowTitle(f"配音编辑界面 - {result.paths.project_name}")
        self._title_btn.setText(f"配音编辑界面 - {result.paths.project_name}")

        subs, roles_raw = parse_subtitle_uncertain(self._paths.subtitle)
        if not subs:
            box = Dialog("导入失败", "字幕解析失败或文件为空", self)
            box.exec()
            return

        self._subtitles = subs
        if roles_raw and len(roles_raw) == len(subs):
            self._roles = roles_raw
        else:
            self._roles = ["default"] * len(subs)

        self._controller.set_paths(self._paths)
        self._video_panel.bind_paths(bool(self._paths.background), bool(self._paths.vocal))
        self._video_panel.reset_default_switches()
        self._subtitle_panel.set_subtitles(self._subtitles, self._roles)
        self._edit_panel.clear()
        self._progress_slider.setEnabled(True)
        self._save_btn.setEnabled(True)

        InfoBar.success(
            title="导入成功",
            content="已复制到 workspace，后续操作仅作用于副本",
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP_RIGHT,
            duration=2500,
            parent=self,
        )

    def _on_block_selected(self, idx: int) -> None:
        if not self._paths or idx < 0 or idx >= len(self._subtitles):
            return
        start_ms = timecode_to_ms(self._subtitles[idx]["start"])
        self._controller.seek(start_ms)
        self._controller.play()
        self._edit_panel.load_block(self._paths, idx, self._subtitles[idx])

    def _on_submit_requested(self, idx: int, text: str, speed: float, audio_bytes: Optional) -> None:
        if not self._paths or idx < 0 or idx >= len(self._subtitles):
            self._edit_panel.set_submit_busy(False)
            return

        from PyQt5.QtMultimedia import QMediaPlayer

        was_playing = self._controller.video_player.state() == QMediaPlayer.PlayingState

        # 计算新的结束时间
        start_ms = timecode_to_ms(self._subtitles[idx]["start"])
        base_duration_ms = timecode_to_ms(self._subtitles[idx]["end"]) - start_ms

        if audio_bytes:
            # 如果有重新配音的音频，使用音频实际时长
            import io
            from pydub import AudioSegment
            import numpy as np
            audio_segment = AudioSegment.from_file(io.BytesIO(audio_bytes), format="mp3")
            audio_segment = audio_segment.set_frame_rate(44100)
            samples = np.array(audio_segment.get_array_of_samples())
            samples = samples.astype(np.float64) / 32768.0
            audio_duration_ms = len(samples) / 44.1  # 44100 Hz
            adjusted_duration_ms = int(audio_duration_ms / speed)
            new_end_ms = start_ms + adjusted_duration_ms
        else:
            # 使用原始时长
            adjusted_duration_ms = int(base_duration_ms / speed)
            new_end_ms = start_ms + adjusted_duration_ms

        # 检查是否有重叠
        if idx < len(self._subtitles) - 1:
            next_start_ms = timecode_to_ms(self._subtitles[idx + 1]["start"])
            if new_end_ms > next_start_ms:
                self._edit_panel.set_submit_busy(False)
                InfoBar.error(
                    title="提交失败",
                    content=f"调整后的结束时间与下一条字幕重叠。当前结束时间: {new_end_ms:.0f}ms，下一条开始时间: {next_start_ms}ms",
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP_RIGHT,
                    duration=5000,
                    parent=self,
                )
                return

        try:
            # 更新字幕文本
            self._subtitles[idx]["text"] = text
            # 更新字幕时间
            end_time = self._subtitles[idx]["end"]
            self._subtitles[idx]["end"] = ms_to_timecode(new_end_ms)
            write_merged_subtitle(self._paths.subtitle, self._subtitles, self._roles)
        except OSError as exc:
            self._edit_panel.set_submit_busy(False)
            self._on_submit_finished_err(str(exc), was_playing)
            return

        # 如果有重新配音的音频，需要替换音频段
        if audio_bytes:
            dub_path = self._paths.dub_vocal_audio
            end_ms = timecode_to_ms(end_time)

            def task() -> None:
                # 替换音频段并应用速度调整
                from ReviewInterface.dubbingedit_app.utils.audio_edit import replace_segment_with_speed
                replace_segment_with_speed(dub_path, start_ms, end_ms, audio_bytes, speed)

            self._worker = FunctionWorker(task, self)


            self._worker.started.connect(lambda: self._prepare_for_audio_edit())
            self._worker.finished_ok.connect(lambda i=idx, t=text: self._on_submit_finished_ok(i, t, was_playing))
            self._worker.failed.connect(lambda msg: self._on_submit_finished_err(msg, was_playing))
            self._worker.start()
        else:
            # 没有音频替换，只需要应用速度调整
            if speed != 1.0:
                dub_path = self._paths.dub_vocal_audio
                end_ms = timecode_to_ms(end_time)

                # print(self._subtitles[idx]["end"])
                # print(self._subtitles[idx]["start"])

                def task() -> None:
                    apply_speed_to_segment(dub_path, start_ms, end_ms, speed)

                self._worker = FunctionWorker(task, self)

                # self._prepare_for_audio_edit()
                self._worker.started.connect(lambda: self._prepare_for_audio_edit())
                self._worker.finished_ok.connect(lambda i=idx, t=text: self._on_submit_finished_ok(i, t, was_playing))
                self._worker.failed.connect(lambda msg: self._on_submit_finished_err(msg, was_playing))
                self._worker.start()
            else:
                # 只是文本修改，不需要处理音频
                self._edit_panel.set_submit_busy(False)
                self._subtitle_panel.refresh_card_text(idx, text)
                InfoBar.success(
                    title="提交成功",
                    content="字幕已保存",
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP_RIGHT,
                    duration=2500,
                    parent=self,
                )

    def _prepare_for_audio_edit(self) -> None:
        from PyQt5.QtMultimedia import QMediaContent

        self._controller.pause()
        self._controller.dub_player.setMedia(QMediaContent())

    def _on_submit_finished_ok(self, idx: int, text: str, was_playing: bool) -> None:
        self._edit_panel.set_submit_busy(False)
        self._controller.reload_dub_track()
        self._subtitle_panel.refresh_card_text(idx, text)

        if was_playing:
            self._controller.play()

        # 检查是否有重新配音的音频
        if self._edit_panel._redubbed_audio_bytes:
            InfoBar.success(
                title="提交成功",
                content="字幕已保存，重新配音的音频已替换并应用速度调整",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP_RIGHT,
                duration=2500,
                parent=self,
            )
            # 清空重新配音的音频
            self._edit_panel._redubbed_audio_bytes = None
        else:
            InfoBar.success(
                title="提交成功",
                content="字幕已保存，本段倍速已应用到 workspace 配音人声",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP_RIGHT,
                duration=2500,
                parent=self,
            )

    def _on_submit_finished_err(self, msg: str, was_playing: bool) -> None:
        self._edit_panel.set_submit_busy(False)
        self._controller.reload_dub_track()

        if was_playing:
            self._controller.play()

        InfoBar.error(
            title="提交失败",
            content=msg,
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP_RIGHT,
            duration=5000,
            parent=self,
        )

    def _on_save_video(self) -> None:
        if not self._paths:
            return

        if self._worker and self._worker.isRunning():
            return

        dubbed_video = self._paths.dubbed_video
        if not dubbed_video or not os.path.isfile(dubbed_video):
            InfoBar.error(
                title="保存失败",
                content="配音视频文件不存在",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP_RIGHT,
                duration=5000,
                parent=self,
            )
            return

        if not self._paths.background or not self._paths.dub_vocal_audio:
            InfoBar.warning(
                title="保存跳过",
                content="缺少背景音乐或配音音频",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP_RIGHT,
                duration=3000,
                parent=self,
            )
            return

        histmp_dir = os.path.join(self._paths.workspace_dir, "histmp")
        os.makedirs(histmp_dir, exist_ok=True)

        timestamp = int(time.time() * 1000)
        stem, ext = os.path.splitext(os.path.basename(dubbed_video))
        backup_name = f"{stem}_{timestamp}{ext}"
        backup_path = os.path.join(histmp_dir, backup_name)

        from PyQt5.QtMultimedia import QMediaContent
        from PyQt5.QtCore import QCoreApplication

        # 1. 彻底停止所有播放器
        self._controller.stop()
        
        # 2. 清空所有播放器的媒体内容
        self._controller.video_player.setMedia(QMediaContent())
        self._controller.bgm_player.setMedia(QMediaContent())
        self._controller.vocal_player.setMedia(QMediaContent())
        self._controller.dub_player.setMedia(QMediaContent())
        
        # 3. 重置滑动条
        self._progress_slider.setValue(0)
        self._progress_slider.setEnabled(False)
        
        # 4. 强制处理 Qt 事件循环，确保资源释放
        QCoreApplication.processEvents()

        shutil.move(dubbed_video, backup_path)

        self._busy_dialog = QDialog(self)
        self._busy_dialog.setWindowTitle("请稍候")
        self._busy_dialog.setWindowFlags(
            self._busy_dialog.windowFlags() & ~Qt.WindowCloseButtonHint
        )
        self._busy_dialog.setWindowModality(Qt.ApplicationModal)
        self._busy_dialog.setFixedSize(240, 100)

        layout = QVBoxLayout(self._busy_dialog)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setAlignment(Qt.AlignCenter)

        from qfluentwidgets import IndeterminateProgressRing, BodyLabel
        ring = IndeterminateProgressRing(self._busy_dialog)
        ring.setFixedSize(40, 40)
        label = BodyLabel("正在保存配音视频…", self._busy_dialog)
        label.setAlignment(Qt.AlignCenter)

        layout.addSpacing(4)
        layout.addWidget(ring, 0, Qt.AlignCenter)
        layout.addSpacing(8)
        layout.addWidget(label, 0, Qt.AlignCenter)

        self._busy_dialog.show()

        def task() -> None:
            self._merge_audio_to_video(
                backup_path,
                self._paths.background,
                self._paths.dub_vocal_audio,
                dubbed_video,
            )

        self._worker = FunctionWorker(task, self)
        self._worker.finished_ok.connect(self._on_save_finished_ok)
        self._worker.failed.connect(
            lambda msg: self._on_save_finished_err(msg, backup_path, dubbed_video)
        )
        self._worker.start()

    def _close_busy_dialog(self) -> None:
        if self._busy_dialog is not None:
            self._busy_dialog.close()
            self._busy_dialog.deleteLater()
            self._busy_dialog = None

    def _reload_video_player(self) -> None:
        if not self._paths:
            return
        from PyQt5.QtCore import QCoreApplication
        from PyQt5.QtMultimedia import QMediaContent, QMediaPlayer
        
        # 确保所有播放器都停止
        self._controller.stop()
        QCoreApplication.processEvents()
        
        # 重新设置媒体内容
        self._controller.video_player.setMedia(
            QMediaContent(QUrl.fromLocalFile(self._paths.dubbed_video))
        )
        if self._paths.background:
            self._controller.bgm_player.setMedia(
                QMediaContent(QUrl.fromLocalFile(self._paths.background))
            )
        else:
            self._controller.bgm_player.setMedia(QMediaContent())
        if self._paths.vocal:
            self._controller.vocal_player.setMedia(
                QMediaContent(QUrl.fromLocalFile(self._paths.vocal))
            )
        else:
            self._controller.vocal_player.setMedia(QMediaContent())
        self._controller.dub_player.setMedia(
            QMediaContent(QUrl.fromLocalFile(self._paths.dub_vocal_audio))
        )
        
        # 应用音轨静音设置
        self._controller.apply_track_mutes()
        
        # 重置到起始位置
        self._controller._seek_all(0)
        
        # 重新启用滑动条
        self._progress_slider.setEnabled(True)

    def _on_save_finished_ok(self) -> None:
        self._close_busy_dialog()
        self._reload_video_player()
        InfoBar.success(
            title="保存成功",
            content="配音视频已更新",
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP_RIGHT,
            duration=3000,
            parent=self,
        )

    def _on_save_finished_err(self, msg: str, backup_path: str, target_path: str) -> None:
        temp_audio = target_path.replace('.mp4', '_temp_audio.wav')
        try:
            if os.path.exists(temp_audio):
                os.remove(temp_audio)
        except OSError:
            pass

        try:
            if os.path.exists(target_path):
                os.remove(target_path)
        except OSError:
            pass

        try:
            shutil.move(backup_path, target_path)
        except Exception:
            pass

        self._close_busy_dialog()
        self._reload_video_player()
        InfoBar.error(
            title="保存失败",
            content=f"已回滚到保存前状态: {msg}",
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP_RIGHT,
            duration=5000,
            parent=self,
        )
    
    def _on_help_clicked(self) -> None:
        from qfluentwidgets import TextEdit

        dialog = QDialog(self)
        dialog.setWindowTitle("使用说明")
        dialog.setMinimumWidth(650)
        dialog.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        # dialog.setFixedSize(460, 340)
        dialog.setStyleSheet("""
            QDialog {
                background-color: #FAFAFA;
            }
        """)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        from qfluentwidgets import SubtitleLabel, BodyLabel
        title_label = SubtitleLabel("配音编辑 - 使用说明", dialog)

        info_widget = QWidget(dialog)
        info_layout = QVBoxLayout(info_widget)
        info_layout.setContentsMargins(8, 8, 8, 8)
        info_layout.setSpacing(14)

        tips = [
            ("1. 工作空间隔离",
             "导入项目后，系统会在项目目录下自动创建 workspace 文件夹，所有编辑操作均作用于该副本，原始项目文件不受任何影响。"),
            ("2. 单句编辑",
             "选中任意字幕条目后，可对该句进行以下操作：调整语速（加速/减速）、重新配音、静音删除以及修改文本内容。"),
            ("3. 提交与保存",
             "点击「提交修改」仅会修改配音音频文件；如需将配音音频与背景音乐合并为完整的视频文件，请点击「保存」按钮。"),
            ("4. 直达文件夹",
             "点击「窗口标题」可打开文件夹查看所有文件。"),
        ]

        for tip_title, tip_content in tips:
            card = QWidget(info_widget)
            card.setStyleSheet("""
                QWidget#tipCard {
                    background-color: #FFFFFF;
                    border: 1px solid #E0E0E0;
                    border-radius: 8px;
                }
            """)
            card.setObjectName("tipCard")
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(14, 10, 14, 10)
            card_layout.setSpacing(4)

            t = BodyLabel(tip_title, card)
            t.setStyleSheet("font-weight: bold; font-size: 15px; color: #2B2B2B;")
            c = BodyLabel(tip_content, card)
            c.setWordWrap(True)
            c.setStyleSheet("font-size: 14px; color: #555555;")

            card_layout.addWidget(t)
            card_layout.addWidget(c)
            # card_layout.setSpacing(10)
            info_layout.addWidget(card)

        layout.addWidget(title_label)
        layout.addWidget(info_widget, 1)
        dialog.exec_()

    def _on_title_clicked(self) -> None:
        """点击标题时打开workspace文件夹"""
        if self._paths and self._paths.workspace_dir:
            path = self._paths.workspace_dir
            if os.path.exists(path):
                if os.path.isdir(path):
                    # 如果是文件夹，直接打开
                    QDesktopServices.openUrl(QUrl.fromLocalFile(path))
                elif os.path.isfile(path):
                    # 如果是文件，打开文件所在文件夹并定位到该文件
                    # folder_path = os.path.dirname(path)
                    # QDesktopServices.openUrl(QUrl.fromLocalFile(folder_path))
                    # 在 Windows 上，可以使用 explorer.exe 来定位文件
                    print(sys.platform)
                    if sys.platform == "win32":
                        os.system(f'explorer /select,"{path}"')
            else:
                print("Path does not exist")
            # QDesktopServices.openUrl(f"file:///{self._paths.workspace_dir}")
    
    def _merge_audio_to_video(self, video_path: str, bgm_path: str, vocal_path: str, output_path: str) -> None:
        """
        使用 ffmpeg 将视频与合并后的音频（bgm + vocal）重新编码
        """
        # 先合并 bgm 和 vocal 音频
        temp_audio = output_path.replace('.mp4', '_temp_audio.wav')
        
        # 使用 ffmpeg 的 amix 滤镜合并音频
        merge_cmd = [
            'ffmpeg', '-y',
            '-i', bgm_path,
            '-i', vocal_path,
            '-filter_complex', '[0:a][1:a]amix=inputs=2:duration=longest[aout]',
            '-map', '[aout]',
            temp_audio
        ]
        subprocess.run(merge_cmd, check=True, capture_output=True)
        
        # 将合并后的音频与视频合并
        final_cmd = [
            'ffmpeg', '-y',
            '-i', video_path,
            '-i', temp_audio,
            '-c:v', 'copy',
            '-c:a', 'aac',
            '-map', '0:v',
            '-map', '1:a',
            '-shortest',
            output_path
        ]
        subprocess.run(final_cmd, check=True, capture_output=True)
        
        # 删除临时音频文件
        try:
            os.remove(temp_audio)
        except OSError:
            pass

if __name__ == '__main__':
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)

    app = QApplication(sys.argv)
    setTheme(Theme.LIGHT)
    from Service.ccTest import read_config
    read_config()

    window = DubbingEditorInterface()
    window.show_animation()
    window._on_import_project("E:\offer\AI配音web版\\26.3.30角色标注\AIDubbing-QT\OutputFolder\project_result\批量视频配音-a视频_test20260412-185844\\a视频_test-视频一键配音结果-20260412-185849")
    app.exec_()