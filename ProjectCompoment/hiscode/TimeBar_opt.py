import copy
import re
from PyQt5.QtWidgets import QWidget, QSlider, QHBoxLayout, QSizePolicy, QVBoxLayout, QFrame, QStyleOptionSlider, QStyle
from PyQt5.QtCore import Qt, QSize, pyqtSignal
from PyQt5.QtGui import QPainter, QColor, QPen, QFont, QPixmap
from ProjectCompoment.hiscode.TrackBar_opt import TrackBar

class TimeBar(QWidget):
    def __init__(self, total_ms, parent=None, init_scale=100):
        super().__init__(parent)
        self.real_ms = total_ms
        self.total_ms = total_ms + 2000  # 增加2秒的缓冲
        self.height_fixed = 48
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
        self._ticks_pixmap = None
        self._last_width = 0
        self._last_scale = self.scale

    def on_scale_changed(self, value):
        self.scale = value
        self._ticks_pixmap = None
        self.update()

    def _update_ticks_pixmap(self):
        total_seconds = int(self.total_ms / 1000)
        px_per_sec = self.scale
        total_length = total_seconds * px_per_sec
        w = total_length + self.offset * 2
        h = self.height_fixed
        pixmap = QPixmap(w, h)
        pixmap.fill(QColor(245, 245, 245))
        painter = QPainter(pixmap)
        font = QFont("Microsoft YaHei", 10, QFont.Normal)
        painter.setFont(font)
        sub_ticks = 10
        if px_per_sec <= 100:
            sub_ticks = 5
        if px_per_sec <= 50:
            sub_ticks = 2
        for sec in range(total_seconds + 1):
            x = int(sec * px_per_sec) + self.offset
            painter.setPen(QPen(QColor(80, 80, 80), 2))
            painter.drawLine(x, 0, x, 13)
            if px_per_sec >= 20:
                painter.drawText(x - 4, 25, f"{sec}s")
            if sec < total_seconds:
                for i in range(1, sub_ticks):
                    sub_x = x + int(i * px_per_sec / sub_ticks)
                    painter.setPen(QPen(QColor(160, 160, 160), 1))
                    painter.drawLine(sub_x, 0, sub_x, 8)
        painter.end()
        self._ticks_pixmap = pixmap
        self._last_width = w
        self._last_scale = self.scale
        self.setFixedWidth(w)

    def paintEvent(self, event):
        if self._ticks_pixmap is None or self._last_width != self.width() or self._last_scale != self.scale:
            self._update_ticks_pixmap()
        painter = QPainter(self)
        painter.drawPixmap(0, 0, self._ticks_pixmap)

    def sizeHint(self):
        total_seconds = int(self.total_ms / 1000)
        px_per_sec = self.scale
        return QSize(total_seconds * px_per_sec, self.height_fixed)

class TrackWidget(QFrame):
    slider_changed = pyqtSignal(int)

    def __init__(self, total_ms, parent=None, init_scale=100, subtitles=None, project=None):
        super().__init__(parent)
        if project and subtitles:
            self.setObjectName("TrackWidget")
            self.timebar = TimeBar(total_ms, init_scale=init_scale)
            self.timebar.slider.valueChanged.connect(self.on_timebar_changed)
            self.subtitles = copy.deepcopy(subtitles)
            self.project = copy.deepcopy(project)
            self.setStyleSheet("#TrackWidget { background: #111111; }")
            role_colors = [
                "#FF6F61", "#FF99C8", "#6BCB77", "#727AE6", "#F8333C", "#FFD93D", "#A66CFF", "#FF922B", "#43C6AC",
            ]
            rolename_to_color = {}
            color_idx = 0
            for subtitle in self.subtitles:
                rolename = subtitle.role_name
                if rolename not in rolename_to_color:
                    rolename_to_color[rolename] = role_colors[color_idx % len(role_colors)]
                    color_idx = (color_idx + 1) % len(role_colors)
            self.original_time_list = [
                [self.time_str_to_ms(subtitle.start_time), self.time_str_to_ms(subtitle.end_time), rolename_to_color[subtitle.role_name]]
                for subtitle in self.subtitles
            ]
            self.target_time_list = [
                [self.time_str_to_ms(subtitle.start_time), self.time_str_to_ms(subtitle.start_time) + subtitle.dubbing_duration, rolename_to_color[subtitle.role_name]]
                for subtitle in self.subtitles
            ]
            self.trackbars = []
            self.bgm_trackbar = TrackBar([], audio_path=self.project.original_bgm_audio_path, scale=init_scale)
            self.original_voice_trackbar = TrackBar(self.original_time_list, audio_path=self.project.original_voice_audio_path, scale=init_scale)
            self.target_voice_trackbar = TrackBar(self.target_time_list, audio_path=self.project.target_voice_audio_path, scale=init_scale)
            self.trackbars = [self.bgm_trackbar, self.original_voice_trackbar, self.target_voice_trackbar]

            self.layout = QVBoxLayout()
            self.layout.setContentsMargins(0, 0, 0, 0)
            self.layout.setSpacing(5)
            # self.layout.setContentsMargins(0,0,10,0)
            self.layout.setAlignment(Qt.AlignTop)
            self.setLayout(self.layout)
            self.layout.addWidget(self.timebar)
            for trackbar in self.trackbars:
                self.layout.addWidget(trackbar)
            # self.layout.addWidget(self.bgm_trackbar)
            # self.layout.addWidget(self.original_voice_trackbar)
            # self.layout.addWidget(self.target_voice_trackbar)

    def on_timebar_changed(self, ms):
        if self.timebar.current_ms != ms:
            self.timebar.current_ms = ms
            self.slider_changed.emit(ms)
            self.update()

    def repaint_wave(self):
        for trackbar in self.trackbars:
            trackbar.repaint_wave()
        # self.bgm_trackbar.repaint_wave()
        # self.original_voice_trackbar.repaint_wave()
        # self.target_voice_trackbar.repaint_wave()

    def on_scale_changed(self, value):
        self.timebar.on_scale_changed(value)
        for trackbar in self.trackbars:
            trackbar.on_scale_changed(value)
        # self.bgm_trackbar.on_scale_changed(value)
        # self.original_voice_trackbar.on_scale_changed(value)
        # self.target_voice_trackbar.on_scale_changed(value)
        self.update()

    def time_str_to_ms(self, time_str: str) -> float:
        match = re.match(r'(\d{2}):(\d{2}):(\d{2}),(\d{3})', time_str)
        if not match:
            raise ValueError(f"无效的时间格式: {time_str}")
        hours, minutes, seconds, milliseconds = map(int, match.groups())
        return (hours * 3600 + minutes * 60 + seconds) * 1000 + milliseconds

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.Antialiasing)
            height = self.height()

            # 安全获取slider引用
            if not hasattr(self, 'timebar') or not hasattr(self.timebar, 'slider'):
                return

            slider = self.timebar.slider

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

            # 绘制当前时间指示线
            painter.setPen(QPen(Qt.white, 2))
            painter.drawLine(handle_pos, self.timebar.height(), handle_pos, height)


        finally:
            painter.end()

        # 统一在最上层绘制当前时间线
        # if not hasattr(self, 'timebar'):
        #     return
        # ms = self.timebar.current_ms
        # scale = self.timebar.scale
        # offset = self.timebar.offset
        # h = self.height()
        # # 计算时间线x坐标
        # line_x = int((ms / 1000.0) * scale) + offset
        # painter = QPainter(self)
        # painter.setRenderHint(QPainter.Antialiasing)
        # painter.setPen(QPen(Qt.white, 2))
        # painter.drawLine(line_x, self.timebar.height(), line_x, h)
