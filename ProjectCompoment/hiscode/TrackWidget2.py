import copy
import re
import soundfile as sf
import numpy as np
from PyQt5.QtWidgets import (QSizePolicy, QVBoxLayout, QStyleOptionSlider,
                             QStyle, QFrame, QGraphicsView, QGraphicsScene,
                             QGraphicsRectItem, QGraphicsItem, QGraphicsPathItem,
                             QSlider, QHBoxLayout, QWidget)
from PyQt5.QtCore import Qt, QRect, QSize, pyqtSignal, QPointF, QRectF, QTimer
from PyQt5.QtGui import (QPainter, QColor, QPen, QFont, QBrush, QLinearGradient,
                         QPainterPath, QTransform)
from qfluentwidgets import Slider
from scipy.signal import resample

from ProjectCompoment.dubbingEntity import Subtitle, Project


class TimeBarItem(QGraphicsRectItem):
    def __init__(self, total_ms, scale, parent=None):
        super().__init__(parent)
        self.total_ms = total_ms
        self.scale = scale
        self.setZValue(100)  # 确保时间轴在最上层
        self.height_fixed = 48
        self.offset = 5
        self.updateSize()

    def updateSize(self):
        total_seconds = int(self.total_ms / 1000)
        total_length = total_seconds * self.scale + self.offset * 2
        self.setRect(0, 0, total_length, self.height_fixed)

    def setScale(self, scale):
        self.scale = scale
        self.updateSize()
        self.update()

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)
        # 绘制背景
        painter.fillRect(self.rect(), QColor(245, 245, 245))

        px_per_sec = self.scale
        total_seconds = int(self.total_ms / 1000)

        # 绘制刻度
        font = QFont("Microsoft YaHei", 10, QFont.Normal)
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


class TimeIndicatorItem(QGraphicsRectItem):
    def __init__(self, height, parent=None):
        super().__init__(parent)

        # self.setPen(Qt.NoPen)
        self.setBrush(QColor(255, 0, 0))
        self.setRect(0, 0, 2, height)
        self.setZValue(1000)  # 确保指示线在最顶层


class TrackBarItem(QGraphicsRectItem):
    def __init__(self, time_ranges, audio_path, scale, height=50):
        super().__init__()
        self.time_ranges = time_ranges
        self.selected_index = None
        self.audio_path = audio_path
        self.scale = scale
        self.height = height
        self.waveform_path = None
        self.data = None
        self.samplerate = 44100
        self.setFlag(QGraphicsItem.ItemClipsChildrenToShape, True)

        # 加载波形数据
        self.load_waveform()

    def setScale(self, scale):
        self.scale = scale
        self.updateWaveform()

    def load_waveform(self):
        try:
            if not self.audio_path:
                self.data = np.array([])
                return

            data, samplerate = sf.read(self.audio_path)
            if data.ndim > 1:
                data = data.mean(axis=1)  # 转换为单声道

            self.data = data
            self.samplerate = samplerate
            self.updateWaveform()
        except Exception as e:
            self.data = np.array([])
            print(f"加载音频错误: {e}")

    def updateWaveform(self):
        if self.data is None or len(self.data) == 0:
            self.waveform_path = None
            return

        # 计算显示所需的点数
        total_seconds = len(self.data) / self.samplerate
        max_points = int(total_seconds * self.scale)

        # 重采样以匹配显示分辨率
        if len(self.data) > max_points:
            waveform = resample(self.data, max_points)
        else:
            waveform = waveform = self.data

        # 归一化
        if waveform.size > 0:
            waveform = waveform / np.max(np.abs(waveform))

        # 创建波形路径
        path = QPainterPath()
        n = len(waveform)
        if n == 0:
            self.waveform_path = None
            return

        w = total_seconds * self.scale
        h = self.height
        half_h = h / 2
        max_height = half_h - 1

        # 优化路径生成
        path.moveTo(0, half_h)
        for i, val in enumerate(waveform):
            x = i * w / n
            y = half_h - val * max_height
            path.lineTo(x, y)

        for i, val in enumerate(reversed(waveform)):
            x = w - i * w / n
            y = half_h + val * max_height
            path.lineTo(x, y)

        path.closeSubpath()
        self.waveform_path = path
        self.update()

    def paint(self, painter, option, widget=None):
        # 绘制背景
        painter.fillRect(self.rect(), QColor("#292929"))

        # 绘制波形
        if self.waveform_path:
            painter.setRenderHint(QPainter.Antialiasing)
            gradient = QLinearGradient(0, 0, 0, self.height)
            gradient.setColorAt(0, QColor("#1E90FF"))
            gradient.setColorAt(1, QColor("#0A5FAE"))
            painter.setBrush(gradient)
            painter.setPen(Qt.NoPen)

            # 应用变换使波形适合轨道宽度
            transform = QTransform()
            transform.scale(self.rect().width() / self.waveform_path.boundingRect().width(), 1)
            painter.setTransform(transform, True)
            painter.drawPath(self.waveform_path)
            painter.setTransform(QTransform(), False)

        # 绘制时间区间
        painter.setRenderHint(QPainter.Antialiasing, False)
        for idx, (start_time, end_time, role_color) in enumerate(self.time_ranges):
            start_x = (start_time * self.scale) / 1000
            end_x = (end_time * self.scale) / 1000
            rect_w = end_x - start_x

            if self.selected_index == idx:
                fill_color = QColor(0, 120, 215)
                fill_color.setAlpha(150)
                border_color = QColor(0, 120, 215)
            else:
                fill_color = QColor(role_color)
                fill_color.setAlpha(20)
                border_color = QColor(role_color)

            painter.setBrush(fill_color)
            painter.setPen(QPen(border_color, 2))
            painter.drawRect(QRectF(start_x, 0, rect_w, self.height))

    def mousePressEvent(self, event):
        pos = event.pos()
        for idx, (start_time, end_time, _) in enumerate(self.time_ranges):
            start_x = (start_time * self.scale) / 1000
            end_x = (end_time * self.scale) / 1000
            rect = QRectF(start_x, 0, end_x - start_x, self.height)

            if rect.contains(pos):
                self.selected_index = idx
                print(f"选中区间索引: {idx}")
                self.update()
                break
        else:
            self.selected_index = None
            self.update()
        super().mousePressEvent(event)


class TrackWidget(QGraphicsView):
    slider_changed = pyqtSignal(int)

    def __init__(self, total_ms, parent=None, init_scale=100, subtitles: list[Subtitle] = None,
                 project: Project = None):
        super().__init__(parent)
        self.setObjectName("TrackWidget")
        self.setStyleSheet("#TrackWidget { background: #111111; }")
        self.setRenderHint(QPainter.Antialiasing)
        self.setRenderHint(QPainter.SmoothPixmapTransform)
        self.setRenderHint(QPainter.TextAntialiasing)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        # 创建场景
        self.scene = QGraphicsScene()
        self.setScene(self.scene)

        self.total_ms = total_ms + 2000  # 增加2秒缓冲
        self.scale = init_scale
        self.current_ms = 0

        # 创建时间轴
        self.timebar = TimeBarItem(self.total_ms, self.scale)
        self.scene.addItem(self.timebar)

        # 创建时间指示线
        self.time_indicator = TimeIndicatorItem(self.height())
        self.time_indicator.setVisible(False)
        self.scene.addItem(self.time_indicator)

        # 创建滑块
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setMinimum(0)
        self.slider.setMaximum(self.total_ms)
        self.slider.valueChanged.connect(self.on_slider_changed)

        # 设置项目数据
        if project and subtitles:
            self.subtitles = copy.deepcopy(subtitles)
            self.project = copy.deepcopy(project)

            # 角色颜色映射
            role_colors = [
                "#FF6F61", "#FF99C8", "#6BCB77", "#727AE6", "#F8333C",
                "#FFD93D", "#A66CFF", "#FF922B", "#43C6AC"
            ]
            rolename_to_color = {}
            for i, subtitle in enumerate(self.subtitles):
                rolename = subtitle.role_name
                if rolename not in rolename_to_color:
                    rolename_to_color[rolename] = role_colors[i % len(role_colors)]

            # 构建时间区间
            self.original_time_list = [
                [self.time_str_to_ms(subtitle.start_time),
                 self.time_str_to_ms(subtitle.end_time),
                 rolename_to_color[subtitle.role_name]]
                for subtitle in self.subtitles
            ]

            self.target_time_list = [
                [self.time_str_to_ms(subtitle.start_time),
                 self.time_str_to_ms(subtitle.start_time) + subtitle.dubbing_duration,
                 rolename_to_color[subtitle.role_name]]
                for subtitle in self.subtitles
            ]

            # 创建轨道
            self.track_items = []
            self.bgm_track = TrackBarItem([], self.project.original_bgm_audio_path, self.scale)
            self.original_voice_track = TrackBarItem(
                self.original_time_list, self.project.original_voice_audio_path, self.scale)
            self.target_voice_track = TrackBarItem(
                self.target_time_list, self.project.target_voice_audio_path, self.scale)

            self.track_items = [self.bgm_track, self.original_voice_track, self.target_voice_track]

            # 添加轨道到场景
            self.layoutTracks()

        # 设置滑块布局
        self.slider_container = QWidget()
        slider_layout = QHBoxLayout()
        slider_layout.addWidget(self.slider)
        slider_layout.setContentsMargins(5, 0, 5, 0)
        self.slider_container.setLayout(slider_layout)
        self.slider_container.setMinimumWidth(self.scene.width())

        # 主布局
        main_layout = QVBoxLayout()
        main_layout.addWidget(self)
        main_layout.addWidget(self.slider_container)
        self.setLayout(main_layout)

        # 初始更新
        QTimer.singleShot(100, self.updateIndicatorPosition)

    def layoutTracks(self):
        y_pos = self.timebar.rect().height() + 10
        track_height = 50
        spacing = 5

        for track in self.track_items:
            track.setRect(0, 0, self.timebar.rect().width(), track_height)
            track.setPos(0, y_pos)
            self.scene.addItem(track)
            y_pos += track_height + spacing

        # 更新场景大小
        self.scene.setSceneRect(0, 0, self.timebar.rect().width(), y_pos)

    def on_slider_changed(self, ms):
        self.current_ms = ms
        self.slider_changed.emit(ms)
        self.updateIndicatorPosition()

    def updateIndicatorPosition(self):
        if not self.time_indicator:
            return

        x_pos = (self.current_ms * self.scale) / 1000
        self.time_indicator.setPos(x_pos, 0)
        self.time_indicator.setVisible(True)

        # 确保时间轴在视图中可见
        self.centerOn(x_pos, 0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.time_indicator:
            self.time_indicator.setRect(0, 0, 2, self.scene.height())
        self.updateIndicatorPosition()

    def on_scale_changed(self, value):
        self.scale = value
        self.timebar.setScale(value)

        for track in self.track_items:
            track.setScale(value)

        self.layoutTracks()
        self.updateIndicatorPosition()

    def repaint_wave(self):
        for track in self.track_items:
            track.load_waveform()

    def time_str_to_ms(self, time_str: str) -> float:
        match = re.match(r'(\d{2}):(\d{2}):(\d{2}),(\d{3})', time_str)
        if not match:
            raise ValueError(f"无效的时间格式: {time_str}")

        hours, minutes, seconds, milliseconds = map(int, match.groups())
        return (hours * 3600 + minutes * 60 + seconds) * 1000 + milliseconds