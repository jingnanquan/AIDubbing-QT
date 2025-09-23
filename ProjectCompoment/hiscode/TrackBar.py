import sys

import librosa
import numpy as np
import soundfile as sf
from PyQt5.QtCore import Qt, QRectF, QPointF
from PyQt5.QtGui import QPainter, QColor, QBrush, QPen, QPainterPath
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QApplication, QMainWindow


class TrackBar(QWidget):
    def __init__(self, audio_path, start_time, end_time, scale=100, parent=None):
        super().__init__(parent)
        self.audio_path = audio_path
        self.start_time = start_time
        self.end_time = end_time
        self.offset = 5
        self.scale = scale  # pixels per second
        self.data = None
        self.samplerate = 44100
        self.waveform = self._load_waveform()
        self.selected = False
        self.setMouseTracking(True)
        self.setFixedHeight(50)

    def _load_waveform(self):
        try:
            data, samplerate = sf.read(self.audio_path)
            if data.ndim > 1:
                data = data.mean(axis=1)  # Convert to mono
            # Resample for display to a manageable number of points
            self.data = data
            self.samplerate = samplerate
            num_samples = int(len(data) * (self.scale / samplerate))  # 相当于对1s中的数据长度进行采样
            if num_samples > 0:
                waveform = librosa.resample(y=self.data, orig_sr=self.samplerate, target_sr=self.scale)
                return waveform
            else:
                return np.array([])
        except Exception as e:
            self.data = np.array([])
            print(f"Error loading audio: {e}")
            return np.array([])

    def on_scale_changed(self, scale):
        self.scale = scale
        self.waveform = librosa.resample(y=self.data, orig_sr=self.samplerate, target_sr=self.scale)
        # self.waveform = self._load_waveform() # Reload or just redraw
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.waveform.size == 0:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Draw background
        painter.fillRect(self.rect(), QColor("#333333"))

        # Draw waveform
        pen = QPen(QColor("#1E90FF"))
        pen.setWidth(1)
        painter.setPen(pen)

        h = self.height()
        half_h = h / 2
        w = self.width()

        # Adjust waveform drawing to total duration
        total_duration = len(self.waveform) / self.scale
        audio_w = self.scale * total_duration

        path = QPainterPath()
        path.moveTo(self.offset, half_h)

        for i, val in enumerate(self.waveform):
            x = ((i / len(self.waveform)) * audio_w)+self.offset if len(self.waveform) > 0 else 0
            if x > w:
                break
            y = half_h - val * half_h
            path.lineTo(x, y)
        painter.drawPath(path)

        # Draw highlight rect for subtitles
        start_x = self.start_time * self.scale
        end_x = self.end_time * self.scale
        rect_w = end_x - start_x

        highlight_rect = QRectF(start_x+self.offset, 0, rect_w, h)

        if self.selected:
            fill_color = QColor(0, 120, 215, 150)  # Blueish, semi-transparent
            border_color = QColor(0, 120, 215)
        else:
            fill_color = QColor(255, 255, 0, 80)  # Yellowish, semi-transparent
            border_color = QColor(255, 255, 0)

        painter.setBrush(QBrush(fill_color))
        pen = QPen(border_color)
        pen.setWidth(2)
        painter.setPen(pen)
        painter.drawRect(highlight_rect)


    def mousePressEvent(self, event):
        start_x = self.start_time * self.scale
        end_x = self.end_time * self.scale
        highlight_rect = QRectF(start_x+self.offset, 0, end_x - start_x, self.height())

        if highlight_rect.contains(event.pos()):
            self.selected = not self.selected
            self.update()
        else:
            self.selected = False
            self.update()
        super().mousePressEvent(event)



if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = QMainWindow()
    window.setWindowTitle('TimeBar Test')
    window.resize(1000, 200)
    # 假设总时长为3分钟

    trackbar = TrackBar('/OutputFolder/audio_separation/background-a视频_test-20250722_093016.mp3', 11, 19)
    window.setCentralWidget(trackbar)
    window.show()
    sys.exit(app.exec_())
