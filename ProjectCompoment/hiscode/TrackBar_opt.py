import numpy as np
import soundfile as sf
from scipy.signal import resample
from PyQt5.QtCore import Qt, QRectF, QPointF
from PyQt5.QtGui import QPainter, QColor, QBrush, QPen, QPixmap
from PyQt5.QtWidgets import QWidget

class TrackBar(QWidget):
    def __init__(self, time_ranges: list = [], audio_path: str = "", scale=100, parent=None):
        super().__init__(parent)
        self.audio_path = audio_path
        self.time_ranges = time_ranges
        self.selected_index = None
        self.offset = 5
        self.scale = scale  # pixels per second
        self.data = None
        self.samplerate = 44100
        self.waveform = None
        self.waveform_pixmap = None
        self.selected = False
        self.setMouseTracking(True)
        self.setFixedHeight(50)
        self.current_ms = 0  # 当前时间线位置（毫秒）
        self._load_waveform()

    def _load_waveform(self, max_points=2000):
        try:
            if not self.audio_path:
                self.data = np.array([])
                self.waveform = np.array([])
                self.waveform_pixmap = None
                return
            data, samplerate = sf.read(self.audio_path)
            if data.ndim > 1:
                data = data.mean(axis=1)
            self.data = data
            self.samplerate = samplerate
            # 只采样可见区域的点数
            visible_points = min(max_points, self.width())
            if len(data) > visible_points:
                waveform = resample(data, visible_points)
            else:
                waveform = data
            if waveform.size > 0:
                waveform = waveform / np.max(np.abs(waveform))
            self.waveform = waveform
            self._update_waveform_pixmap()
        except Exception as e:
            self.data = np.array([])
            self.waveform = np.array([])
            self.waveform_pixmap = None
            print(f"Error loading audio: {e}")

    def _update_waveform_pixmap(self):
        if self.waveform is None or self.waveform.size == 0:
            self.waveform_pixmap = None
            return
        w = self.width()
        h = self.height()
        pixmap = QPixmap(w, h)
        pixmap.fill(QColor("#292929"))
        painter = QPainter(pixmap)
        pen = QPen(QColor("#1E90FF"))
        pen.setWidth(1)
        painter.setPen(pen)
        half_h = h / 2
        n = len(self.waveform)
        x_step = w / n if n > 0 else 1
        max_height = half_h - 1
        for i, val in enumerate(self.waveform):
            x = int(i * x_step + self.offset)
            line_height = abs(val) * max_height
            y1 = int(half_h - line_height)
            y2 = int(half_h + line_height)
            painter.drawLine(x, y1, x, y2)
        painter.end()
        self.waveform_pixmap = pixmap

    def resizeEvent(self, event):
        self._load_waveform()
        super().resizeEvent(event)

    def on_scale_changed(self, scale):
        self.scale = scale
        self._load_waveform()
        self.update()

    def repaint_wave(self):
        self._load_waveform()
        self.update()

    def set_current_time(self, ms):
        self.current_ms = ms
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        # 画缓存的波形
        if self.waveform_pixmap:
            painter.drawPixmap(0, 0, self.waveform_pixmap)
        h = self.height()
        # 画区间高亮
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
            painter.setBrush(QBrush(fill_color))
            pen = QPen(border_color)
            pen.setWidth(2)
            painter.setPen(pen)
            painter.drawRect(highlight_rect)
        # 画当前时间线
        if self.current_ms is not None:
            line_x = int((self.current_ms / 1000.0) * self.scale) + self.offset
            painter.setPen(QPen(Qt.white, 2))
            painter.drawLine(line_x, 0, line_x, h)

    def mousePressEvent(self, event):
        h = self.height()
        for idx, (start_time, end_time, _) in enumerate(self.time_ranges):
            start_x = int((start_time * self.scale) / 1000)
            end_x = int((end_time * self.scale) / 1000)
            highlight_rect = QRectF(start_x + self.offset, 0, end_x - start_x, h)
            if highlight_rect.contains(event.pos()):
                self.selected_index = idx
                self.update()
                break
        else:
            self.selected_index = None
            self.update()
        super().mousePressEvent(event)
