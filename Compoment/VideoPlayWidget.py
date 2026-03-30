import sys

from PyQt5.QtCore import Qt, QUrl, QEvent, pyqtSignal, QSizeF
from PyQt5.QtGui import QPainter, QBrush
from PyQt5.QtMultimedia import QMediaContent, QMediaPlayer
from PyQt5.QtMultimediaWidgets import QGraphicsVideoItem
from PyQt5.QtWidgets import (QPushButton,
                             QStyle, QHBoxLayout, QVBoxLayout,
                             QLabel, QSizePolicy, QMessageBox, QFrame, QGraphicsScene,
                             QGraphicsView, QApplication,)
from qfluentwidgets import BodyLabel, Slider
from PyQt5.QtCore import QTimer


class GraphicsVideoItem(QGraphicsVideoItem):
    """ Graphics video item """

    def paint(self, painter, option, widget=None):

        painter.setBrush(QBrush(Qt.black))
        # 填充整个视频项区域
        painter.drawRect(self.boundingRect())

        painter.setCompositionMode(QPainter.CompositionMode_Difference)
        # 先调用基类方法绘制原始视频
        super().paint(painter, option, widget)




class VideoPlayerWidget(QFrame):
    bar_slide = pyqtSignal(list)
    duration_get = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        # Initialize media player
        self.setSizePolicy( QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.mediaPlayer = QMediaPlayer(None, QMediaPlayer.VideoSurface)
        # Setup UI
        self.setup_ui()
        # Connect signals
        self.connect_signals()


    def setup_ui(self):
        self.scene = QGraphicsScene(self)
        self.view = QGraphicsView(self.scene)
        self.view.setFrameShape(QFrame.NoFrame)
        self.view.setAlignment(Qt.AlignCenter)
        self.view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.view.setDragMode(QGraphicsView.NoDrag)
        self.view.setAcceptDrops(False)
        self.view.viewport().setAcceptDrops(False)
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setAcceptDrops(False)
        # self.view.setViewport(QOpenGLWidget())
        self.videoItem = GraphicsVideoItem()
        self.scene.addItem(self.videoItem)
        # self.scene.setBackgroundBrush(Qt.black)

        # Play/pause button
        self.playButton = QPushButton()
        self.playButton.setEnabled(False)
        self.playButton.setIcon(self.style().standardIcon(QStyle.SP_MediaPause))

        # 时间显示label
        self.timeLabel = BodyLabel()
        self.timeLabel.setText("00:00:00,000")
        self.timeLabel.setMinimumWidth(100)
        self.timeLabel.setAlignment(Qt.AlignCenter)

        # Position slider
        self.positionSlider = Slider(Qt.Horizontal)
        self.positionSlider.setRange(0, 0)

        # Create layouts
        controlLayout = QHBoxLayout()
        controlLayout.setContentsMargins(0, 0, 0, 0)
        controlLayout.setStretch(0, 0)
        controlLayout.setStretch(1, 0)
        controlLayout.setStretch(2, 1)
        controlLayout.addWidget(self.playButton)
        controlLayout.addWidget(self.timeLabel)  # 新增
        controlLayout.addWidget(self.positionSlider)
        print(self.playButton.height())
        mainLayout = QVBoxLayout(self)
        mainLayout.addWidget(self.view)
        mainLayout.addLayout(controlLayout)

        self._position_timer = None

    def connect_signals(self):
        """Connect all media player signals"""

        # 设置positionChanged信号连接
        # self.mediaPlayer.positionChanged.connect(self.position_changed)

        self.mediaPlayer.durationChanged.connect(self.init_compoments)
        self.mediaPlayer.error.connect(self.handle_error)
        self.mediaPlayer.stateChanged.connect(self.change_timer)
        self.positionSlider.sliderMoved.connect(self.set_position)
        self.playButton.clicked.connect(self.play)
        # Click-to-toggle on video area
        self.view.viewport().installEventFilter(self)  # Install event filter for video view
        # React to native video size to keep fitting
        try:
            self.videoItem.nativeSizeChanged.connect(self._on_native_size_changed)
        except Exception:
            pass
        print("完成绑定")
    

    def eventFilter(self, obj, event):
        """事件过滤器处理"""
        if obj == self.view.viewport():
            if event.type() == QEvent.MouseButtonPress:
                if self.playButton.isEnabled():
                    self.play()
                return True  # 表示事件已处理
            # 让拖拽事件交给父级处理
            if event.type() in (QEvent.DragEnter, QEvent.DragMove, QEvent.DragLeave, QEvent.Drop):
                event.ignore()
                return False
        return super().eventFilter(obj, event)

    def closeEvent(self, event):
        if isinstance(self._position_timer, QTimer):
            self._position_timer.stop()
            self._position_timer.deleteLater()
            self._position_timer = None
        # 1. 停止播放
        self.mediaPlayer.stop()
        self.mediaPlayer.mediaStatusChanged.disconnect()
        self.mediaPlayer.deleteLater()
        super().closeEvent(event)

    def open_file(self, file_path):
        print("开始加载视频:", file_path)
        if self.mediaPlayer.state() == QMediaPlayer.PlayingState:
            self.mediaPlayer.pause()
        self.mediaPlayer.stop()
        self.mediaPlayer.setMedia(QMediaContent())
        self.mediaPlayer.setVideoOutput(None)
        # 设置新媒体内容
        self.mediaPlayer.setMedia(QMediaContent(QUrl.fromLocalFile(file_path)))
        self.mediaPlayer.setVideoOutput(self.videoItem)

        if isinstance(self._position_timer, QTimer):
            self._position_timer.stop()
            self._position_timer.deleteLater()
            self._position_timer = None

        self._position_timer = QTimer(self)
        self._position_timer.setInterval(100)  # 100ms刷新一次
        self._position_timer.timeout.connect(lambda: self.position_changed(self.mediaPlayer.position()))
        self._position_timer.start()

    def change_timer(self):
        if self.mediaPlayer.state() == QMediaPlayer.PlayingState and isinstance(self._position_timer, QTimer):
            if not self._position_timer.isActive():
                self._position_timer.start()
        elif self.mediaPlayer.state() == QMediaPlayer.PausedState and isinstance(self._position_timer, QTimer):
            if self._position_timer.isActive():
                self._position_timer.stop()
        elif self.mediaPlayer.state() == QMediaPlayer.StoppedState and isinstance(self._position_timer, QTimer):
            if self._position_timer.isActive():
                self._position_timer.stop()
            # self.positionSlider.setValue(0)
            # self.timeLabel.setText("00:00:00,000")
            self.playButton.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))

    def play(self):
        """Toggle play/pause"""
        if self.mediaPlayer.state() == QMediaPlayer.PlayingState:
            self.mediaPlayer.pause()
            self.playButton.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        elif self.mediaPlayer.state() == QMediaPlayer.PausedState:
            self.mediaPlayer.play()
            self.playButton.setIcon(self.style().standardIcon(QStyle.SP_MediaPause))
        elif self.mediaPlayer.state() == QMediaPlayer.StoppedState:
            self.mediaPlayer.play()
            self.playButton.setIcon(self.style().standardIcon(QStyle.SP_MediaPause))

    def pause(self):
        if self.mediaPlayer.state() == QMediaPlayer.PlayingState:
            self.mediaPlayer.pause()
            self.playButton.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))


    def position_changed(self, position):
        """Update position slider when media position changes"""
        self.positionSlider.setValue(position)
        self.timeLabel.setText(self.format_time(position))
        self.bar_slide.emit([position])
        # print(position)

    def format_time(self, ms):
        """将毫秒转换为 00:00:00,000 格式"""
        hours = ms // (3600 * 1000)
        minutes = (ms % (3600 * 1000)) // (60 * 1000)
        seconds = (ms % (60 * 1000)) // 1000
        milliseconds = ms % 1000
        return f"{hours:02}:{minutes:02}:{seconds:02},{milliseconds:03}"

    def init_compoments(self, duration):
        """Update slider range when duration changes"""
        self.playButton.setEnabled(True)
        self.playButton.setIcon(self.style().standardIcon(QStyle.SP_MediaPause))
        self.positionSlider.setRange(0, duration)
        self.mediaPlayer.play()


        # self.
        print("media异步初始化完毕，视频时长:", self.mediaPlayer.duration(),duration)
        # print(duration)
        if duration > 0:
            self.duration_get.emit(duration)
        print(self.mediaPlayer.state())
        # 确保初始也进行一次适配
        self._fit_video_in_view()

    def set_position(self, position):
        """Set media position when slider is moved"""
        self.mediaPlayer.setPosition(position)

    def handle_error(self):
        """Handle media player errors"""
        QMessageBox.critical(self, "Error", self.mediaPlayer.errorString())
        # self.playButton.setEnabled(False)
        # self.errorLabel.setText(f"Error: {self.mediaPlayer.errorString()}")

    def load_video(self, file_path):
        """Public method to load a video file"""
        self.open_file(file_path)

    def stop(self):
        """Public method to stop playback"""
        self.mediaPlayer.stop()
        self.playButton.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))

    def is_playing(self):
        """Check if media is currently playing"""
        return self.mediaPlayer.state() == QMediaPlayer.PlayingState

    def _on_native_size_changed(self, size: QSizeF):
        """Adjust the graphics item and fit view when the native video size changes"""
        try:
            if size and size.width() > 0 and size.height() > 0:
                self.videoItem.setSize(size)
                self.scene.setSceneRect(self.videoItem.boundingRect())
                self._fit_video_in_view()
        except Exception:
            pass

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._fit_video_in_view()

    def _fit_video_in_view(self):
        """Fit the video in the view while keeping aspect ratio. At least one side fills."""
        try:
            if hasattr(self, 'view') and hasattr(self, 'videoItem'):
                bounds = self.videoItem.boundingRect()
                if not bounds.isEmpty():
                    self.view.resetTransform()
                    self.view.fitInView(self.videoItem, Qt.KeepAspectRatio)
        except Exception:
            pass

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = VideoPlayerWidget()
    window.open_file(r"E:/offer/AI配音web版/8.28/AIDubbing-QT-main/a视频_test.mp4")
    window.show()
    sys.exit(app.exec_())


