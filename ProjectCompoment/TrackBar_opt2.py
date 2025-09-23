import numpy as np
import soundfile as sf
from scipy.signal import resample
from PyQt5.QtCore import QRectF, Qt
from PyQt5.QtGui import QPainter, QColor, QPen, QPixmap
from PyQt5.QtWidgets import QGraphicsItem, QGraphicsView, QGraphicsScene

class TrackBarItem(QGraphicsItem):
    def __init__(self, time_ranges=None, audio_path="", scale=100, height=50):
        super().__init__()
        self.audio_path = audio_path
        self.time_ranges = time_ranges or []
        self.scale = scale
        self.height = height
        self.data = None
        self.samplerate = 44100
        self.waveform = None
        self.waveform_pixmap = None
        self.selected_index = None
        self._load_waveform()
        self.setFlag(QGraphicsItem.ItemUsesExtendedStyleOption)

    def boundingRect(self):
        # 宽度由音频时长和scale决定
        if self.waveform is not None and self.samplerate > 0:
            duration = len(self.waveform) / self.samplerate
            width = int(duration * self.scale)
        else:
            width = 1000
        return QRectF(0, 0, width, self.height)

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
            visible_points = min(max_points, 2000)
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
        w = int(self.boundingRect().width())
        h = self.height
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
            x = int(i * x_step)
            line_height = abs(val) * max_height
            y1 = int(half_h - line_height)
            y2 = int(half_h + line_height)
            painter.drawLine(x, y1, x, y2)
        painter.end()
        self.waveform_pixmap = pixmap

    def paint(self, painter, option, widget=None):
        # 只绘制可见区域
        rect = option.exposedRect
        if self.waveform_pixmap:
            painter.drawPixmap(rect, self.waveform_pixmap, rect)
        h = self.height
        # 画区间高亮
        for idx, (start_time, end_time, role_color) in enumerate(self.time_ranges):
            start_x = int((start_time * self.scale) / 1000)
            end_x = int((end_time * self.scale) / 1000)
            rect_w = end_x - start_x
            highlight_rect = QRectF(start_x, 0, rect_w, h)
            fill_color = QColor(role_color)
            fill_color.setAlpha(20)
            border_color = QColor(role_color)
            painter.setBrush(fill_color)
            pen = QPen(border_color)
            pen.setWidth(2)
            painter.setPen(pen)
            painter.drawRect(highlight_rect)

    def set_scale(self, scale):
        self.scale = scale
        self._load_waveform()
        self.update()

    def set_time_ranges(self, time_ranges):
        self.time_ranges = time_ranges
        self.update()

class TrackBarView(QGraphicsView):
    def __init__(self, trackbar_item: TrackBarItem, parent=None):
        scene = QGraphicsScene(parent)
        super().__init__(scene, parent)
        self.setViewportUpdateMode(QGraphicsView.BoundingRectViewportUpdate)
        self.setRenderHint(QPainter.Antialiasing)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setFrameShape(QGraphicsView.NoFrame)
        self.trackbar_item = trackbar_item
        scene.addItem(trackbar_item)
        self.setSceneRect(trackbar_item.boundingRect())
        # GPU加速（如有OpenGL支持）
        try:
            from PyQt5.QtWidgets import QOpenGLWidget
            self.setViewport(QOpenGLWidget())
        except Exception:
            pass
