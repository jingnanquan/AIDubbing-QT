#!/usr/bin/python3
# -*- coding: utf-8 -*-
import tempfile
from base64 import b64encode

from PyQt5 import QtWidgets, QtGui, QtCore
from PyQt5.QtCore import Qt, QPoint, QLine, QRect, QRectF, pyqtSignal
from PyQt5.QtGui import QPainter, QColor, QFont, QBrush, QPalette, QPen, QPolygon, QPainterPath, QPixmap
from PyQt5.QtWidgets import QWidget, QFrame, QScrollArea, QVBoxLayout, QApplication, QMainWindow
import sys
import os

from numpy import load

__textColor__ = QColor(187, 187, 187)
__backgroudColor__ = QColor(60, 63, 65)
__font__ = QFont('Decorative', 10)


class VideoSample:

    def __init__(self, duration, color=Qt.darkYellow, picture=None, audio=None):
        self.duration = duration
        self.color = color  # Floating color
        self.defColor = color  # DefaultColor
        if picture is not None:
            self.picture = picture.scaledToHeight(45)
        else:
            self.picture = None
        self.startPos = 0  # Inicial position
        self.endPos = self.duration  # End position


class TimeBarArea(QWidget):
    positionChanged = pyqtSignal(int)
    selectionChanged = pyqtSignal(VideoSample)

    def __init__(self, duration, scale = 50):
        super(QWidget, self).__init__()
        self.duration = duration
        self.pixels_per_second = scale  # 每秒的像素数，默认100

        # Set variables
        self.backgroundColor = __backgroudColor__
        self.textColor = __textColor__
        self.font = __font__
        self.pos = None
        self.pointerPos = None
        self.pointerTimePos = None
        self.selectedSample = None
        self.clicking = False  # Check if mouse left button is being pressed
        self.is_in = False  # check if user is in the widget
        self.videoSamples = []  # List of videos samples

        self.setMouseTracking(True)  # Mouse events
        self.setAutoFillBackground(True)  # background

        self.initUI()

    def initUI(self):
        self.setWindowTitle("TESTE")
        # 根据duration和pixels_per_second设置宽度
        self.updateWidth()

        # Set Background
        pal = QPalette()
        pal.setColor(QPalette.Background, self.backgroundColor)
        self.setPalette(pal)

    def updateWidth(self):
        """根据duration和pixels_per_second更新组件宽度"""
        # 计算总宽度：duration(秒) * pixels_per_second + 一些边距
        total_width = int(self.duration * self.pixels_per_second) + 100
        self.setFixedWidth(total_width)

    def on_scale_changed(self, pixels_per_second):
        """设置每秒的宽度"""
        self.pixels_per_second = pixels_per_second
        self.updateWidth()
        self.update()

    def paintEvent(self, event):
        qp = QPainter()
        qp.begin(self)
        qp.setPen(self.textColor)
        qp.setFont(self.font)
        qp.setRenderHint(QPainter.Antialiasing)

        # Draw time
        # 每秒的像素数
        px_per_sec = self.pixels_per_second
        # 计算总秒数
        total_seconds = int(self.duration)

        # 绘制大刻度（每秒）
        for sec in range(total_seconds + 1):
            x_pos = sec * px_per_sec
            # 绘制时间文字
            qp.drawText(x_pos - 20, 2, 40, 100, Qt.AlignHCenter, self.get_time_string(sec))
            # 绘制大刻度线
            qp.setPen(QPen(Qt.darkCyan, 3, Qt.SolidLine))
            qp.drawLine(x_pos, 40, x_pos, 20)
            qp.setPen(self.textColor)

            # 根据每秒像素数决定是否绘制小刻度
            if 50 <= px_per_sec < 100:
                # 每秒画5个小刻度
                for i in range(1, 5):
                    small_x = x_pos + i * (px_per_sec // 5)
                    qp.drawLine(small_x, 40, small_x, 30)
            elif px_per_sec >= 100:
                # 每秒画10个小刻度
                for i in range(1, 10):
                    small_x = x_pos + i * (px_per_sec // 10)
                    qp.drawLine(small_x, 40, small_x, 30)

        if self.pos is not None and self.is_in:
            qp.drawLine(self.pos.x(), 0, self.pos.x(), 40)

        # Draw down line
        qp.setPen(QPen(Qt.darkCyan, 5, Qt.SolidLine))
        qp.drawLine(0, 40, self.width(), 40)

        if self.pointerPos is not None:
            line = QLine(QPoint(self.pointerTimePos / self.getScale(), 40),
                         QPoint(self.pointerTimePos / self.getScale(), self.height()))
            poly = QPolygon([QPoint(self.pointerTimePos / self.getScale() - 5, 35),
                             QPoint(self.pointerTimePos / self.getScale() + 5, 35),
                             QPoint(self.pointerTimePos / self.getScale(), 40)])
            rect = QRect(self.pointerTimePos / self.getScale() - 5, 25, 10, 10)
        else:
            line = QLine(QPoint(0, 0), QPoint(0, self.height()))
            poly = QPolygon([QPoint(-5, 35), QPoint(5, 35), QPoint(0, 40)])
            rect = QRect( -4, 25, 8, 10 )

        # Draw samples
        t = 0
        for sample in self.videoSamples:
            # Clear clip path
            path = QPainterPath()
            path.addRoundedRect(QRectF(t / self.getScale(), 50, sample.duration / self.getScale(), 200), 10, 10)
            qp.setClipPath(path)

            # Draw sample
            path = QPainterPath()
            qp.setPen(sample.color)
            path.addRoundedRect(QRectF(t / self.getScale(), 50, sample.duration / self.getScale(), 50), 10, 10)
            sample.startPos = t / self.getScale()
            sample.endPos = t / self.getScale() + sample.duration / self.getScale()
            qp.fillPath(path, sample.color)
            qp.drawPath(path)

            # Draw preview pictures
            if sample.picture is not None:
                if sample.picture.size().width() < sample.duration / self.getScale():
                    path = QPainterPath()
                    path.addRoundedRect(QRectF(t / self.getScale(), 52.5, sample.picture.size().width(), 45), 10, 10)
                    qp.setClipPath(path)
                    qp.drawPixmap(QRect(t / self.getScale(), 52.5, sample.picture.size().width(), 45), sample.picture)
                else:
                    path = QPainterPath()
                    path.addRoundedRect(QRectF(t / self.getScale(), 52.5, sample.duration / self.getScale(), 45), 10,
                                        10)
                    qp.setClipPath(path)
                    pic = sample.picture.copy(0, 0, sample.duration / self.getScale(), 45)
                    qp.drawPixmap(QRect(t / self.getScale(), 52.5, sample.duration / self.getScale(), 45), pic)
            t += sample.duration

        # Clear clip path
        path = QPainterPath()
        path.addRect(self.rect().x(), self.rect().y(), self.rect().width(), self.rect().height())
        qp.setClipPath(path)

        # Draw pointer
        qp.setPen(Qt.darkCyan)
        qp.setBrush(QBrush(Qt.darkCyan))

        qp.drawPolygon(poly)
        qp.drawRect(rect)
        qp.drawLine(line)
        qp.end()

    # Mouse movement
    def mouseMoveEvent(self, e):
        self.pos = e.pos()

        # if mouse is being pressed, update pointer
        if self.clicking:
            x = self.pos.x()
            self.pointerPos = x
            self.positionChanged.emit(x)
            self.checkSelection(x)
            self.pointerTimePos = self.pointerPos * self.getScale()

        self.update()

    # Mouse pressed
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            x = e.pos().x()
            self.pointerPos = x
            self.positionChanged.emit(x)
            self.pointerTimePos = self.pointerPos * self.getScale()

            self.checkSelection(x)

            self.update()
            self.clicking = True  # Set clicking check to true

    # Mouse release
    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.clicking = False  # Set clicking check to false

    # Enter
    def enterEvent(self, e):
        self.is_in = True

    # Leave
    def leaveEvent(self, e):
        self.is_in = False
        self.update()

    # check selection
    def checkSelection(self, x):
        # Check if user clicked in video sample
        for sample in self.videoSamples:
            if sample.startPos < x < sample.endPos:
                sample.color = Qt.darkCyan
                if self.selectedSample is not sample:
                    self.selectedSample = sample
                    self.selectionChanged.emit(sample)
            else:
                sample.color = sample.defColor

    # Get time string from seconds
    def get_time_string(self, seconds):
        m, s = divmod(seconds, 60)
        h, m = divmod(m, 60)
        return "%02d:%02d:%02d" % (h, m, s)

    # Get scale from length
    def getScale(self):
        return float(self.duration) / float(self.width())

    # Get duration
    def getDuration(self):
        return self.duration

    # Get selected sample
    def getSelectedSample(self):
        return self.selectedSample

    # Set background color
    def setBackgroundColor(self, color):
        self.backgroundColor = color

    # Set text color
    def setTextColor(self, color):
        self.textColor = color

    # Set Font
    def setTextFont(self, font):
        self.font = font


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = QMainWindow()
    window.setWindowTitle('TimeBar Test')
    # 假设总时长为3分钟
    timeline = TimeBarArea(180)  # 3分钟=180秒
    window.setCentralWidget(timeline)
    window.show()
    sys.exit(app.exec_())