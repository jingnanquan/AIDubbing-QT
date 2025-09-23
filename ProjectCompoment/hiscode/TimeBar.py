from PyQt5.QtWidgets import QApplication, QMainWindow, QSizePolicy
import sys
from PyQt5.QtWidgets import QWidget, QSlider, QHBoxLayout
from PyQt5.QtCore import Qt, QRect, QSize, pyqtSignal
from PyQt5.QtGui import QPainter, QColor, QPen, QFont


class LineOverlay(QWidget):
    """A transparent overlay for drawing the red timeline indicator."""
    def __init__(self, timebar):
        super().__init__(timebar)
        self.timebar = timebar
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.show()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        height = self.height()
        px_per_sec = self.timebar.scale

        # 绘制当前时间指示线
        if self.timebar.total_ms > 0:
            line_x = int((self.timebar.current_ms / 1000.0) * px_per_sec) + self.timebar.offset
            painter.setPen(QPen(Qt.red, 2))
            # Draw the line from top to bottom of the overlay
            painter.drawLine(line_x, 0, line_x, height)
        painter.end()


class TimeBar(QWidget):
    slider_changed = pyqtSignal(int)

    def __init__(self, total_ms, parent=None, init_scale=100):
        super().__init__(parent)
        self.total_ms = total_ms
        self.height_fixed = 60
        self.current_ms = 0
        self.setMinimumHeight(self.height_fixed)
        self.setMaximumHeight(self.height_fixed)
        self.scale = init_scale  # 1s = scale px
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setMinimum(0)
        self.slider.setMaximum(total_ms)
        self.slider.setValue(0)
        self.slider.valueChanged.connect(self.set_current_time)
        self.offset = 5

        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.slider)
        self.setLayout(layout)
        self.setSizePolicy(self.sizePolicy().horizontalPolicy(), QSizePolicy.Fixed)

        # Create the overlay for the red line
        self.overlay = LineOverlay(self)

    def on_scale_changed(self, value):
        self.scale = value
        self.update()
        self.overlay.update()

    def set_current_time(self, ms):
        """Slot to update the current time and redraw the vertical line."""
        if self.current_ms != ms:
            self.current_ms = ms
            self.slider_changed.emit(ms)
            # We update the overlay, not the main widget's paintEvent for the line
            self.overlay.update()
            self.update() # Update the main widget for other visual changes if any

    def resizeEvent(self, event):
        """Ensure the overlay always covers the entire widget."""
        self.overlay.resize(event.size())
        super().resizeEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        height = self.height_fixed
        total_seconds = int(self.total_ms / 1000)
        px_per_sec = self.scale
        total_length = total_seconds * px_per_sec
        self.setFixedWidth(total_length + self.offset * 2)

        # 画背景
        painter.fillRect(self.rect(), QColor(245, 245, 245))
        # 画刻度
        font = QFont()
        font.setPointSize(8)
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
            painter.drawLine(x, 0, x, 20)
            # 时间文本
            if px_per_sec >= 20:
                painter.drawText(x - 2, 40, f"{sec}s")
            # 小刻度
            if sec < total_seconds:
                for i in range(1, sub_ticks):
                    sub_x = x + int(i * px_per_sec / sub_ticks)
                    painter.setPen(QPen(QColor(160, 160, 160), 1))
                    painter.drawLine(sub_x, 0, sub_x, 15)

        # The red line is no longer drawn here. It's handled by the overlay.
        painter.end()


    def sizeHint(self):
        total_seconds = int(self.total_ms / 1000)
        px_per_sec = self.scale
        return QSize(total_seconds * px_per_sec, self.height_fixed)





if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = QMainWindow()
    window.setWindowTitle('TimeBar Test')
    window.resize(1000, 100)
    # 假设总时长为3分钟
    total_ms = 3 * 60 * 1000
    timebar = TimeBar(total_ms)
    window.setCentralWidget(timebar)
    window.show()
    sys.exit(app.exec_())
