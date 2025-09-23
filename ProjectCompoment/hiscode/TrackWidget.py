import copy
import re
import soundfile as sf
import numpy as np
from PyQt5.QtWidgets import  QSizePolicy, QVBoxLayout, QStyleOptionSlider, QStyle, QFrame
from PyQt5.QtWidgets import QWidget, QSlider, QHBoxLayout
from PyQt5.QtCore import Qt, QRect, QSize, pyqtSignal, QPointF, QRectF
from PyQt5.QtGui import QPainter, QColor, QPen, QFont, QBrush
from qfluentwidgets import Slider
from scipy.signal import resample

from ProjectCompoment.TrackBar2 import TrackBar
from ProjectCompoment.dubbingEntity import Subtitle, Project


class TimeBar(QWidget):

    def __init__(self, total_ms, parent=None, init_scale=100):
        super().__init__(parent)
        self.real_ms = total_ms
        self.total_ms = total_ms + 2000  # 增加2秒的缓冲
        self.height_fixed = 48  # 48
        self.current_ms = 0
        self.setMinimumHeight(self.height_fixed)
        self.setMaximumHeight(self.height_fixed)
        self.scale = init_scale  # 1s = scale px

        self.slider = QSlider(Qt.Horizontal)
        self.slider.setMinimum(0)
        self.slider.setMaximum(self.total_ms)
        self.slider.setValue(self.current_ms)
        self.offset = 5
        self.scale_changed = True

        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.slider)
        layout.setAlignment(self.slider, Qt.AlignBottom)
        self.setLayout(layout)
        self.setSizePolicy(self.sizePolicy().horizontalPolicy(), QSizePolicy.Fixed)

    def on_scale_changed(self, value):
        self.scale = value
        self.update()

    def paintEvent(self, event):

        # 这些部分只有scale改变时才会触发
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        # 画背景
        painter.fillRect(self.rect(), QColor(245, 245, 245))
        px_per_sec = self.scale

        total_seconds = int(self.total_ms / 1000)
        total_length = total_seconds * px_per_sec
        self.setFixedWidth(total_length + self.offset * 2)
        # 画刻度
        font = QFont("Microsoft YaHei", 10, QFont.Normal)
        # font.setPointSize(10)
        painter.setFont(font)
        # 计算小刻度数
        sub_ticks = 10
        if px_per_sec <= 100:
            sub_ticks = 5
        if px_per_sec <= 50:
            sub_ticks = 2
        for sec in range(total_seconds + 1):
            x = int(sec * px_per_sec) + self.offset
            # 大刻度
            painter.setPen(QPen(QColor(80, 80, 80), 2))
            painter.drawLine(x, 0, x, 13)
            # 时间文本
            if px_per_sec >= 20:
                painter.drawText(x - 4, 25, f"{sec}s")
            # 小刻度
            if sec < total_seconds:
                for i in range(1, sub_ticks):
                    sub_x = x + int(i * px_per_sec / sub_ticks)
                    painter.setPen(QPen(QColor(160, 160, 160), 1))
                    painter.drawLine(sub_x, 0, sub_x, 8)

        # 开始绘制”时间线“
        try:
            painter.setRenderHint(QPainter.Antialiasing)
            height = self.height()

            slider = self.slider

            # 正确初始化样式选项
            option = QStyleOptionSlider()
            slider.initStyleOption(option)  # 正确调用方式

            # 获取滑块位置（考虑DPI缩放）
            handle_rect = slider.style().subControlRect(
                QStyle.CC_Slider,
                option,
                QStyle.SC_SliderHandle,
                slider
            )

            # 转换为全局坐标再转换回当前控件坐标
            global_pos = slider.mapToGlobal(handle_rect.center())
            handle_pos = self.mapFromGlobal(global_pos).x()

            # handle_pos = handle_rect.center()
            # 绘制当前时间指示线
            painter.setPen(QPen(Qt.black, 2))
            painter.drawLine(handle_pos, 0, handle_pos, height)

        finally:
            painter.end()

    def sizeHint(self):
        total_seconds = int(self.total_ms / 1000)
        px_per_sec = self.scale
        return QSize(total_seconds * px_per_sec, self.height_fixed)


class TrackWidget(QFrame):
    slider_changed = pyqtSignal(int)

    def __init__(self, total_ms, parent=None, init_scale=100, subtitles: list[Subtitle] = None,
                 project: Project = None):
        super().__init__(parent)
        if project and subtitles:
            self.setObjectName("TrackWidget")
            self.timebar = TimeBar(total_ms, init_scale=init_scale)
            self.timebar.slider.valueChanged.connect(self.on_timebar_changed)  # 触发画线事件
            self.subtitles = copy.deepcopy(subtitles)
            self.project = copy.deepcopy(project)
            self.setStyleSheet("#TrackWidget { background: #111111; }")

            # 定义n个常用颜色（在#292929深色背景上清晰可见）
            role_colors = [
                "#FF6F61",  # 红色
                "#FF99C8",  # 粉色
                "#6BCB77",  # 绿色
                "#727AE6",  # 蓝色
                "#F8333C",  # 红色
                "#FFD93D",  # 黄色
                "#A66CFF",  # 紫色
                "#FF922B",  # 橙色
                "#43C6AC",  # 青色
            ]
            # 为每个角色分配颜色
            rolename_to_color = {}
            color_idx = 0
            for subtitle in self.subtitles:
                rolename = subtitle.role_name
                if rolename not in rolename_to_color:
                    rolename_to_color[rolename] = role_colors[color_idx % len(role_colors)]
                    color_idx = (color_idx + 1) % len(role_colors)

            # 构建带颜色的时间列表
            self.original_time_list = [
                [
                    self.time_str_to_ms(subtitle.start_time),
                    self.time_str_to_ms(subtitle.end_time),
                    rolename_to_color[subtitle.role_name]
                ]
                for subtitle in self.subtitles
            ]
            self.target_time_list = [
                [
                    self.time_str_to_ms(subtitle.start_time),
                    self.time_str_to_ms(subtitle.start_time) + subtitle.dubbing_duration,
                    rolename_to_color[subtitle.role_name]
                ]
                for subtitle in self.subtitles
            ]

            # self.original_time_list = [[self.time_str_to_ms(subtitle.start_time), self.time_str_to_ms(subtitle.end_time)] for subtitle in self.subtitles]
            # self.target_time_list = [[self.time_str_to_ms(subtitle.start_time), (self.time_str_to_ms(subtitle.start_time)+int((subtitle.dubbing_duration/44100)*1000))] for subtitle in self.subtitles]
            print(self.target_time_list)

            self.trackbars = []
            self.bgm_trackbar = TrackBar([], audio_path=self.project.original_bgm_audio_path, scale=init_scale)
            self.original_voice_trackbar = TrackBar(self.original_time_list,
                                                    audio_path=self.project.original_voice_audio_path, scale=init_scale)
            self.target_voice_trackbar = TrackBar(self.target_time_list,
                                                  audio_path=self.project.target_voice_audio_path, scale=init_scale)
            self.trackbars = [self.bgm_trackbar, self.original_voice_trackbar, self.target_voice_trackbar]

            self.layout = QVBoxLayout()
            self.layout.setContentsMargins(0, 0, 0, 0)
            self.layout.setSpacing(5)
            self.layout.setAlignment(Qt.AlignTop)
            self.setLayout(self.layout)
            self.layout.addWidget(self.timebar)
            for trackbar in self.trackbars:
                self.layout.addWidget(trackbar)

    def on_timebar_changed(self, ms):
        if self.timebar.current_ms != ms:
            print(self.timebar.current_ms)
            self.timebar.current_ms = ms
            self.slider_changed.emit(ms)
            self.timebar.update()
            # self.update()

    def repaint_wave(self):
        for trackbar in self.trackbars:
            trackbar.repaint_wave()

    def on_scale_changed(self, value):
        self.timebar.on_scale_changed(value)
        for trackbar in self.trackbars:
            trackbar.on_scale_changed(value)

    def time_str_to_ms(self, time_str: str) -> float:
        """
        将SRT时间格式 (00:00:00,150) 转换为毫秒
        """
        # 使用正则表达式解析时间
        match = re.match(r'(\d{2}):(\d{2}):(\d{2}),(\d{3})', time_str)
        if not match:
            raise ValueError(f"无效的时间格式: {time_str}")

        hours, minutes, seconds, milliseconds = map(int, match.groups())
        return (hours * 3600 + minutes * 60 + seconds) * 1000 + milliseconds



class TrackBar(QWidget):
    def __init__(self, time_ranges: list = [], audio_path: str = "", scale=100, parent=None):
        super().__init__(parent)
        self.audio_path = audio_path

        self.time_ranges = time_ranges
        self.selected_index = None  # 当前选中的区间索引

        self.offset = 5
        self.scale = scale  # pixels per second
        self.data = None
        self.samplerate = 44100
        self.waveform = self._load_waveform()
        self.selected = False
        self.setMouseTracking(True)
        self.setFixedHeight(50)

    def _load_waveform(self, max_points=1000):
        try:
            if not self.audio_path:
                raise FileNotFoundError("no audio file")
            data, samplerate = sf.read(self.audio_path)
            if data.ndim > 1:
                data = data.mean(axis=1)  # Convert to mono
            self.data = data
            self.samplerate = samplerate
            max_points = int(len(data) * (self.scale / samplerate))
            print(self.scale)
            # Only sample max_points for display
            if len(data) > max_points:
                waveform = resample(data, max_points)
            else:
                waveform = data
            # Normalize to [-1, 1]
            if waveform.size > 0:
                waveform = waveform / np.max(np.abs(waveform))
            return waveform
        except Exception as e:
            self.data = np.array([])
            print(f"Error loading audio: {e}")
            return np.array([])

    def on_scale_changed(self, scale):
        self.scale = scale
        # Resample for display without reloading audio
        # self.waveform = self._load_waveform()
        self.update()

    def repaint_wave(self):
        self.waveform = self._load_waveform()
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.waveform.size == 0:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Draw background
        painter.fillRect(self.rect(), QColor("#292929"))

        # Draw waveform as vertical lines
        pen = QPen(QColor("#1E90FF"))
        pen.setWidth(1)
        painter.setPen(pen)

        h = self.height()
        half_h = h / 2
        w = self.width()

        n = len(self.waveform)
        if n == 0:
            return
        x_step = w / n
        max_height = half_h - 1  # Maximum amplitude height

        for i, val in enumerate(self.waveform):
            x = i * x_step + self.offset
            line_height = abs(val) * max_height
            y1 = half_h - line_height
            y2 = half_h + line_height
            painter.drawLine(QPointF(x, y1), QPointF(x, y2))

        for idx, (start_time, end_time, role_color) in enumerate(self.time_ranges):
            start_x = int((start_time * self.scale) / 1000)
            end_x = int((end_time * self.scale) / 1000)
            rect_w = end_x - start_x
            highlight_rect = QRectF(start_x + self.offset, 0, rect_w, h)
            if self.selected_index == idx:
                fill_color = QColor(0, 120, 215)
                fill_color.setAlpha(150)
                border_color = QColor(0, 120, 215)
            else:
                fill_color = QColor(role_color)
                fill_color.setAlpha(20)
                border_color = QColor(role_color)
                # 0, 120, 215
            painter.setBrush(QBrush(fill_color))
            pen = QPen(border_color)
            pen.setWidth(2)
            painter.setPen(pen)
            painter.drawRect(highlight_rect)

    def mousePressEvent(self, event):
        h = self.height()
        for idx, (start_time, end_time, _) in enumerate(self.time_ranges):
            start_x = int((start_time * self.scale) / 1000)
            end_x = int((end_time * self.scale) / 1000)
            highlight_rect = QRectF(start_x + self.offset, 0, end_x - start_x, h)
            if highlight_rect.contains(event.pos()):
                self.selected_index = idx
                print(f"选中区间索引: {idx}")
                self.update()
                break
        else:
            self.selected_index = None
            self.update()
        super().mousePressEvent(event)





