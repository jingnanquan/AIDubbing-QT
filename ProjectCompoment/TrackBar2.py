import sys
import numpy as np
import soundfile as sf
from scipy.signal import resample
from PyQt5.QtCore import Qt, QRectF, QPointF
from PyQt5.QtGui import QPainter, QColor, QBrush, QPen, QPolygonF
from PyQt5.QtWidgets import QWidget, QApplication, QMainWindow, QOpenGLWidget


class TrackBar(QWidget):
    def __init__(self, time_ranges: list=[], audio_path: str = "",  scale=100, parent=None):
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
            start_x = int((start_time * self.scale)/1000)
            end_x = int((end_time * self.scale)/1000)
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
            start_x = int((start_time * self.scale)/1000)
            end_x = int((end_time * self.scale)/1000)
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


# if __name__ == '__main__':
#     app = QApplication(sys.argv)
#     window = QMainWindow()
#     window.setWindowTitle('TimeBar Test')
#     window.resize(1000, 200)
#     trackbar = TrackBar('E:\\offer\\AI配音web版\\7.18\\AIDubbing-QT-main\\OutputFolder\\audio_separation\\background-a视频_test-20250722_093016.mp3', 11, 19)
#     window.setCentralWidget(trackbar)
#     window.show()
#     sys.exit(app.exec_())
