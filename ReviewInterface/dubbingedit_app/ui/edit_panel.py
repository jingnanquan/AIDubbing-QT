from __future__ import annotations

import base64
import io
import os
import tempfile
from typing import Any, Optional

import librosa
import numpy as np
import soundfile as sf

from PyQt5.QtCore import QThread, QTimer, QUrl, pyqtSignal, Qt
from PyQt5.QtGui import QFont
from PyQt5.QtMultimedia import QMediaContent, QMediaPlayer
from PyQt5.QtWidgets import (QComboBox, QFileDialog, QHBoxLayout, QLabel,
                             QSizePolicy, QVBoxLayout, QWidget, QMainWindow, QSpacerItem, QApplication)
from pydub import AudioSegment

from qfluentwidgets import (
    BodyLabel, ComboBox, DoubleSpinBox,
    IndeterminateProgressRing, PlainTextEdit, PrimaryPushButton,
    PushButton, StrongBodyLabel, SubtitleLabel, ToolTipFilter,
    ToolTipPosition
)

from ReviewInterface.dubbingedit_app.core.subtitle_parser import timecode_to_ms
# from dubbingedit_app.core.workspace_paths import WorkspacePaths
# from ReviewInterface.dubbingedit_app.utils.audio_utils import export_segment_wav

from ReviewInterface.dubbingedit_app.core.workspace_paths import WorkspacePaths
from ReviewInterface.dubbingedit_app.utils.audio_edit import export_segment_wav



# 配音线程
class RedubbingThread(QThread):
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(bytes, str)  # audio_data, error_message
    error = pyqtSignal(str)

    def __init__(self, text: str, voice_id: str, elevenlabs_client = None):
        # from Service.dubbingMain.dubbingElevenLabs import dubbingElevenLabs
        # from Service.dubbingMain.dubbingElevenlabs3 import dubbingElevenLabs3
        super().__init__()
        self.text = text
        self.voice_id = voice_id
        self.elevenlabs_client = None  # 延迟到run()中初始化


    def run(self):
        try:
            # 延迟初始化elevenlabs客户端，在run()中执行，避免阻塞主线程
            from Service.dubbingMain.dubbingElevenLabs import dubbingElevenLabs
            self.progress.emit(10, "初始化AI服务...")
            self.elevenlabs_client = dubbingElevenLabs.getInstance().elevenlabs
            self.progress.emit(20, "正在生成配音...")
            audio = self.elevenlabs_client.text_to_speech.convert(
                text=self.text,
                voice_id=self.voice_id,
                model_id="eleven_multilingual_v2",
                output_format="mp3_44100_192"
            )


            audio_bytes = b''.join(audio)
            self.progress.emit(100, "配音完成")
            self.finished.emit(audio_bytes, "")
        except Exception as e:
            self.error.emit(str(e))


# 重新配音模态框
class RedubbingDialog(QMainWindow):
    replace_requested = pyqtSignal()  # 替换信号
    cancel_requested = pyqtSignal()   # 取消信号

    def __init__(self, parent=None, voice_ids=None, text="", start_ms=0, end_ms=0, vocal_audio_path=None):
        super().__init__(parent)
        self.setWindowTitle("重新配音")
        self.setMinimumWidth(500)
        self.setWindowModality(Qt.ApplicationModal)

        self.voice_ids = voice_ids if voice_ids else {}
        self.text = text
        self.start_ms = start_ms
        self.end_ms = end_ms
        self.vocal_audio_path = vocal_audio_path
        self.generated_audio_bytes = None
        self.temp_audio_path = None
        self.is_processing = False  # 是否正在处理中

        self._init_ui()
        # self._setup_elevenlabs()

    def _setup_elevenlabs(self):
        from Service.dubbingMain.dubbingElevenlabs3 import dubbingElevenLabs3
        """使用dubbingElevenLabs3的单例模式获取client"""
        try:
            self.elevenlabs_client = dubbingElevenLabs3.getInstance().connect.elevenlabs
            print("成功使用dubbingElevenLabs3单例模式获取client")
        except Exception as e:
            print(f"初始化ElevenLabs客户端失败: {e}")

    def _init_ui(self):
        # 创建中心部件和布局（QMainWindow 需要 central widget）
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        # 角色选择
        role_label = BodyLabel("选择配音角色:", self)
        layout.addWidget(role_label)

        self.role_combo = ComboBox(self)
        self._populate_roles()
        layout.addWidget(self.role_combo)

        # 文本预览
        text_label = BodyLabel("配音文本:", self)
        layout.addWidget(text_label)

        self.text_preview = PlainTextEdit(self)
        self.text_preview.setPlainText(self.text)
        self.text_preview.setMaximumHeight(100)
        self.text_preview.setEnabled(False)
        layout.addWidget(self.text_preview)

        # 播放原声按钮
        self.play_original_btn = PushButton("播放原音频", self)
        self.play_original_btn.clicked.connect(self._on_play_original)
        layout.addWidget(self.play_original_btn)

        # 进度显示布局
        progress_layout = QHBoxLayout()
        self.progress_label = BodyLabel("", self)
        progress_layout.addWidget(self.progress_label)
        progress_layout.addStretch(1)
        self.progress_ring = IndeterminateProgressRing(self)
        self.progress_ring.setFixedSize(40, 40)
        self.progress_ring.hide()
        progress_layout.addWidget(self.progress_ring)
        layout.addLayout(progress_layout)

        # 按钮布局
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)
        self.redub_btn = PrimaryPushButton("开始配音", self)
        self.redub_btn.clicked.connect(self._on_redub)

        self.preview_btn = PushButton("试听配音", self)
        self.preview_btn.setEnabled(False)
        self.preview_btn.clicked.connect(self._on_preview_new)

        self.replace_btn = PushButton("替换", self)
        self.replace_btn.setEnabled(False)
        self.replace_btn.clicked.connect(self._on_replace)

        self.cancel_btn = PushButton("取消", self)
        self.cancel_btn.clicked.connect(self._on_cancel)

        btn_layout.addWidget(self.redub_btn)
        btn_layout.addWidget(self.preview_btn)
        btn_layout.addWidget(self.replace_btn)
        btn_layout.addWidget(self.cancel_btn)

        layout.addLayout(btn_layout)
        layout.addStretch(1)  # 添加弹性空间，使控件不拥挤

        # 播放器
        self._player = QMediaPlayer(self, QMediaPlayer.LowLatency)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._stop_preview)

    def _populate_roles(self):
        self.role_combo.clear()
        for role_name in sorted(self.voice_ids.keys()):
            self.role_combo.addItem(f"{role_name} ({self.voice_ids[role_name]})", userData=self.voice_ids[role_name])

    def _on_play_original(self):
        if not self.vocal_audio_path:
            return
        self._player.setMedia(QMediaContent(QUrl.fromLocalFile(self.vocal_audio_path)))
        self._player.setPosition(self.start_ms)
        self._player.play()
        wall_ms = max(1, self.end_ms - self.start_ms)
        self._timer.start(wall_ms + 80)

    def _on_redub(self):
        # print(self.role_combo.currentText())
        # print(self.role_combo.currentData())
        # print(self.role_combo.currentIndex())
        selected_data = self.role_combo.itemData(self.role_combo.currentIndex())
        print(selected_data)

        if not selected_data:
            from qfluentwidgets import InfoBar, InfoBarPosition
            InfoBar.warning(
                title="警告",
                content="请选择配音角色",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP_RIGHT,
                duration=2000,
                parent=self,
            )
            return

        voice_id = selected_data
        text = self.text_preview.toPlainText()

        # 标记为处理中
        self.is_processing = True
        # 禁用所有按钮
        self._set_buttons_enabled(False)
        self.progress_ring.show()

        QApplication.processEvents()

        # 启动配音线程
        self.redub_thread = RedubbingThread(text, voice_id, None)
        # self.redub_thread.progress.connect(self._on_redub_progress)
        self.redub_thread.finished.connect(self._on_redub_finished)
        self.redub_thread.error.connect(self._on_redub_error)
        self.redub_thread.start()

    def _on_redub_progress(self, value: int, message: str):
        self.progress_label.setText(message)
        self.progress_ring.show()  # 进度环始终显示

    def _on_redub_finished(self, audio_bytes: bytes, error_msg: str):
        self.progress_ring.hide()
        if error_msg:
            from qfluentwidgets import InfoBar, InfoBarPosition
            InfoBar.error(
                title="配音失败",
                content=error_msg,
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP_RIGHT,
                duration=4000,
                parent=self,
            )
            self._set_buttons_enabled(True)
            self._restore_close_button()
            return

        # 保存音频到临时文件
        self.generated_audio_bytes = audio_bytes
        self.temp_audio_path = tempfile.mktemp(suffix=".mp3")
        with open(self.temp_audio_path, "wb") as f:
            f.write(audio_bytes)

        self.progress_label.setText("配音完成")
        self._set_buttons_enabled(True)
        self._restore_close_button()

    def _on_redub_error(self, error_msg: str):
        self.progress_ring.hide()
        from qfluentwidgets import InfoBar, InfoBarPosition
        InfoBar.error(
            title="配音失败",
            content=error_msg,
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP_RIGHT,
            duration=4000,
            parent=self,
        )
        self._set_buttons_enabled(True)
        self._restore_close_button()

    def _on_preview_new(self):
        if not self.temp_audio_path:
            return
        self._player.setMedia(QMediaContent(QUrl.fromLocalFile(self.temp_audio_path)))
        self._player.play()

    def _stop_preview(self):
        self._player.stop()

    def _on_replace(self):
        if not self.generated_audio_bytes:
            return
        self.replace_requested.emit()
        self.close()

    def _on_cancel(self):
        self.cancel_requested.emit()
        self.close()

    def _set_buttons_enabled(self, enabled: bool):
        self.redub_btn.setEnabled(enabled)
        if enabled and not self.generated_audio_bytes:
            self.preview_btn.setEnabled(False)
            self.replace_btn.setEnabled(False)
        else:
            self.preview_btn.setEnabled(enabled)
            self.replace_btn.setEnabled(enabled)
        self.cancel_btn.setEnabled(enabled)

    def _restore_close_button(self):
        """恢复窗口关闭按钮"""
        self.is_processing = False
        self.setWindowFlags(self.windowFlags() | Qt.WindowCloseButtonHint)
        self.show()  # 重新显示窗口以应用窗口标志

    def closeEvent(self, event):
        print("调用我")
        """重写关闭事件"""
        if self.is_processing:
            # 如果正在处理中，阻止关闭
            from qfluentwidgets import InfoBar, InfoBarPosition
            InfoBar.warning(
                title="提示",
                content="正在生成配音，请等待完成后再关闭",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP_RIGHT,
                duration=2000,
                parent=self,
            )
            event.ignore()
        else:
            # 正常关闭
            self.cancel_requested.emit()
            super().closeEvent(event)

    def get_generated_audio(self) -> Optional[bytes]:
        return self.generated_audio_bytes

    def closeEvent(self, event):
        self._stop_preview()
        if hasattr(self, 'temp_audio_path') and self.temp_audio_path and os.path.exists(self.temp_audio_path):
            try:
                os.remove(self.temp_audio_path)
            except Exception:
                pass
        super().closeEvent(event)


class EditPanel(QWidget):
    """底部字幕编辑：文本、倍速、本段预览、提交、下载。"""

    submit_requested = pyqtSignal(int, str, float)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._paths: Optional[WorkspacePaths] = None
        self._index: int = -1
        self._start_ms = 0
        self._end_ms = 0
        self._original_start_ms = 0
        self._original_end_ms = 0
        self._current_subtitle: Optional[dict] = None
        self._redubbed_audio_bytes = None

        self._title = SubtitleLabel("字幕编辑（请选择一条字幕）", self)
        self._editor = PlainTextEdit(self)
        self._editor.setFont(QFont("Microsoft YaHei", 12))
        self._editor.setMinimumHeight(100)
        self._editor.setPlaceholderText("选中字幕后在此编辑文本…")

        # 起止时间显示
        time_info_layout = QHBoxLayout()
        self._start_time_label = BodyLabel("起始: --", self)
        self._end_time_label = BodyLabel("终止: --", self)
        self._duration_label = BodyLabel("时长: --", self)
        time_info_layout.addWidget(self._start_time_label)
        time_info_layout.addStretch(1)
        time_info_layout.addWidget(self._end_time_label)
        time_info_layout.addStretch(1)
        time_info_layout.addWidget(self._duration_label)

        self._speed = DoubleSpinBox(self)
        self._speed.setRange(0.5, 2.0)
        self._speed.setSingleStep(0.1)
        self._speed.setValue(1.0)
        self._speed.setDecimals(1)
        self._speed.valueChanged.connect(self._update_time_display)

        self._preview_btn = PushButton("预览本段配音", self)
        self._preview_btn.clicked.connect(self._on_preview)

        self._submit_btn = PrimaryPushButton("提交修改", self)
        self._submit_btn.clicked.connect(self._on_submit)

        self._download_btn = PushButton("下载本段人声", self)
        self._download_btn.clicked.connect(self._on_download)

        self._redub_btn = PrimaryPushButton("重新配音", self)
        self._redub_btn.clicked.connect(self._on_redub)
        self._redub_btn.setToolTip("使用AI重新生成该段配音")
        self._redub_btn.installEventFilter(ToolTipFilter(self._redub_btn, showDelay=500, position=ToolTipPosition.TOP))

        self._preview_player = QMediaPlayer(self, QMediaPlayer.LowLatency)
        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.timeout.connect(self._stop_preview)

        row = QHBoxLayout()
        row.addWidget(BodyLabel("倍速", self))
        row.addWidget(self._speed)
        row.addSpacing(16)
        row.addWidget(self._preview_btn)
        row.addWidget(self._submit_btn)
        row.addWidget(self._download_btn)
        spacerItem = QSpacerItem(0,0, QSizePolicy.Expanding, QSizePolicy.Expanding)
        row.addItem(spacerItem)
        row.addStretch(1)
        row.addWidget(self._redub_btn)


        lay = QVBoxLayout(self)
        lay.addWidget(self._title)
        lay.addWidget(self._editor, 1)
        lay.addLayout(time_info_layout)
        lay.addLayout(row)

        self._overlay = QWidget(self)
        self._overlay.setStyleSheet("QWidget { background: rgba(255,255,255,0.72); }")
        ov = QVBoxLayout(self._overlay)
        ov.addStretch(1)
        self._ring = IndeterminateProgressRing(self._overlay)
        self._ring.setFixedSize(64, 64)
        self._ring_label = BodyLabel("处理中…", self._overlay)
        hl = QHBoxLayout()
        hl.addStretch(1)
        hl.addWidget(self._ring)
        hl.addStretch(1)
        ov.addLayout(hl)
        hl2 = QHBoxLayout()
        hl2.addStretch(1)
        hl2.addWidget(self._ring_label)
        hl2.addStretch(1)
        ov.addLayout(hl2)
        ov.addStretch(1)
        self._overlay.hide()
        self._overlay.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.setMinimumHeight(200)
        self._set_enabled(False)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._overlay.setGeometry(self.rect())

    def set_submit_busy(self, busy: bool) -> None:
        self._submit_btn.setEnabled(not busy)
        if busy:
            self._overlay.show()
            self._ring.start()
        else:
            self._ring.stop()
            self._overlay.hide()
            self._speed.setValue(1.0)

    def _set_enabled(self, on: bool) -> None:
        self._editor.setEnabled(on)
        self._speed.setEnabled(on)
        self._preview_btn.setEnabled(on)
        self._submit_btn.setEnabled(on)
        self._download_btn.setEnabled(on)
        self._redub_btn.setEnabled(on)

    def clear(self) -> None:
        self._paths = None
        self._index = -1
        self._redubbed_audio_bytes = None
        self._editor.clear()
        self._title.setText("字幕编辑（请选择一条字幕）")
        self._speed.setValue(1.0)
        self._set_enabled(False)
        self._start_time_label.setText("起始: --")
        self._end_time_label.setText("终止: --")
        self._duration_label.setText("时长: --")

    def load_block(
        self,
        paths: WorkspacePaths,
        list_index: int,
        subtitle: dict[str, Any],
    ) -> None:
        self._paths = paths
        self._index = list_index
        self._current_subtitle = subtitle
        self._start_ms = timecode_to_ms(subtitle["start"])
        self._end_ms = timecode_to_ms(subtitle["end"])
        self._original_start_ms = self._start_ms
        self._original_end_ms = self._end_ms
        self._redubbed_audio_bytes = None
        self._speed.setValue(1.0)
        self._editor.setPlainText(subtitle.get("text", ""))
        self._title.setText(f"字幕编辑 · #{subtitle.get('index', list_index)}")
        self._update_time_display()
        self._set_enabled(True)

    def current_text(self) -> str:
        return self._editor.toPlainText()

    def current_speed(self) -> float:
        return float(self._speed.value())

    def _update_time_display(self) -> None:
        """更新时间显示，根据速度调整尾部时间"""
        speed = float(self._speed.value())
        base_duration_ms = self._original_end_ms - self._original_start_ms

        # 计算调整后的终止时间
        if self._redubbed_audio_bytes:
            # 如果有重新配音的音频，使用音频实际时长
            audio_segment = AudioSegment.from_file(io.BytesIO(self._redubbed_audio_bytes), format="mp3")
            audio_segment = audio_segment.set_frame_rate(44100)
            samples = np.array(audio_segment.get_array_of_samples())
            samples = samples.astype(np.float64) / 32768.0
            audio_duration_ms = len(samples) / 44.1  # 44100 Hz

            # 应用速度调整
            adjusted_duration_ms = audio_duration_ms / speed
            self._end_ms = self._start_ms + adjusted_duration_ms
        else:
            # 使用原始时长
            adjusted_duration_ms = base_duration_ms / speed
            self._end_ms = self._start_ms + adjusted_duration_ms

        # 格式化时间显示 (HH:MM:SS,mmm)
        def format_time(ms: int) -> str:
            hours = ms // (3600 * 1000)
            minutes = (ms % (3600 * 1000)) // (60 * 1000)
            seconds = (ms % (60 * 1000)) // 1000
            milliseconds = ms % 1000
            return f"{hours:02}:{minutes:02}:{seconds:02},{milliseconds:03}"

        self._start_time_label.setText(f"起始: {format_time(int(self._start_ms))}")
        self._end_time_label.setText(f"终止: {format_time(int(self._end_ms))}")
        duration_ms = self._end_ms - self._start_ms
        duration_sec = duration_ms / 1000.0
        self._duration_label.setText(f"时长: {duration_sec:.3f}s ({speed:.1f}x)")

    def _on_preview(self) -> None:
        if not self._paths or self._index < 0:
            return
        rate = float(self._speed.value())
        self._preview_player.setMedia(QMediaContent(QUrl.fromLocalFile(self._paths.dub_vocal_audio)))
        self._preview_player.setPlaybackRate(max(0.5, min(2.0, rate)))
        self._preview_player.setPosition(self._start_ms)
        self._preview_player.play()
        wall_ms = max(1, int((self._end_ms - self._start_ms) / rate))
        self._preview_timer.start(wall_ms + 80)

    def _stop_preview(self) -> None:
        self._preview_player.stop()

    def _on_submit(self) -> None:
        if not self._paths or self._index < 0:
            return
        self.set_submit_busy(True)
        # 如果有重新配音的音频，使用调整后的速度
        if self._redubbed_audio_bytes:
            speed = self.current_speed()
            self.submit_requested.emit(self._index, self.current_text(), speed)
        else:
            self.submit_requested.emit(self._index, self.current_text(), self.current_speed())

    def _on_download(self) -> None:
        if not self._paths or self._index < 0:
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "保存本段配音人声",
            f"segment_{self._index + 1}.wav",
            "WAV 文件 (*.wav)",
        )
        if not path:
            return
        try:
            export_segment_wav(self._paths.dub_vocal_audio, self._start_ms, self._end_ms, path)
            from qfluentwidgets import InfoBar, InfoBarPosition

            InfoBar.success(
                title="导出成功",
                content="已保存所选片段（纯配音人声）",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP_RIGHT,
                duration=2000,
                parent=self.window(),
            )
        except Exception as exc:
            from qfluentwidgets import InfoBar, InfoBarPosition

            InfoBar.error(
                title="导出失败",
                content=str(exc),
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP_RIGHT,
                duration=4000,
                parent=self.window(),
            )

    def _on_redub(self) -> None:
        if not self._paths or self._index < 0 or not self._current_subtitle:
            return

        # 检查是否有voice_ids映射
        if not hasattr(self._paths, 'voice_ids_mapping') or not self._paths.voice_ids_mapping:
            from qfluentwidgets import InfoBar, InfoBarPosition
            InfoBar.warning(
                title="警告",
                content="项目中没有可用的配音角色信息",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP_RIGHT,
                duration=3000,
                parent=self.window(),
            )
            return

        # 显示重新配音模态框
        dialog = RedubbingDialog(
            self,
            voice_ids=self._paths.voice_ids_mapping,
            text=self.current_text(),
            start_ms=self._start_ms,
            end_ms=self._end_ms,
            vocal_audio_path=self._paths.dub_vocal_audio
        )

        # 连接信号
        dialog.replace_requested.connect(lambda: self._handle_redub_replace(dialog))
        dialog.cancel_requested.connect(lambda: None)  # 取消不做任何操作

        dialog.show()

    def _handle_redub_replace(self, dialog):
        """处理重新配音的替换操作"""
        audio_bytes = dialog.get_generated_audio()
        if audio_bytes:
            # 保存重新配音的音频，但不立即提交
            self._redubbed_audio_bytes = audio_bytes
            # 重置起始时间为原始起始时间
            self._start_ms = self._original_start_ms
            # 更新时间显示，让用户可以手动调整速度
            self._update_time_display()

            from qfluentwidgets import InfoBar, InfoBarPosition
            InfoBar.success(
                title="配音生成成功",
                content="已生成新配音，请调整速度后点击提交",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP_RIGHT,
                duration=3000,
                parent=self.window(),
            )

