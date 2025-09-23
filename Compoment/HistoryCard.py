import os

from PyQt5.QtCore import QUrl, pyqtSignal, QTimer, Qt
from PyQt5.QtGui import QStandardItemModel, QFont
from PyQt5.QtMultimedia import QMediaPlayer
from PyQt5.QtWidgets import QWidget, QFileDialog, QFrame, QVBoxLayout, QLabel, QPushButton, QSizePolicy, QHBoxLayout, \
    QInputDialog, QComboBox
from qfluentwidgets import BodyLabel, SubtitleLabel, PushButton, StrongBodyLabel
from qfluentwidgets.multimedia import SimpleMediaPlayBar

from Config import resource_path
from Service.dubbingMain.dubbingElevenlabs2 import dubbingElevenLabs2

'''
声线转换中的历史列表项
'''


class HistoryCardItem(QFrame):
    """自定义列表项（高度固定）"""
    def __init__(self, title: str, file_path: str, parent=None):
        super().__init__(parent)
        # self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        # border: 1px solid #ccc;
        self.setStyleSheet("""
            HistoryCardItem {
                border-radius: 8px;
                margin: 2px;
                padding: 5px;
                background: #f2f2f2;
            }
            HistoryCardItem:hover {
                background: #dddddd;
            }
        """)
        self.title_text = title
        self.file_path = file_path

        layout = QVBoxLayout()
        self.title = BodyLabel(self.title_text)
        self.bar = SimpleMediaPlayBar()
        # 本地音乐
        url = QUrl.fromLocalFile(self.file_path)
        self.bar.player.setSource(url)
        layout.addWidget(self.title)
        layout.addWidget(self.bar)
        self.setLayout(layout)



class VoiceCardItem(QFrame):
    btn_signal = pyqtSignal(str)
    self_click = pyqtSignal(str, str)

    """自定义列表项（高度固定）"""
    def __init__(self, title: str, file_path: str = "", voice_id: str= "",parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            VoiceCardItem {
                border-radius: 8px;
                margin: 2px;
                padding: 5px;
                background: #fafafa;
            }
            VoiceCardItem:hover {
                background: #dddddd;
                border: 1px solid #ccc;
            }
        """)
        self.title_text = title
        self.file_path = file_path
        self.voice_id = voice_id

        layout = QVBoxLayout()
        layout2 = QHBoxLayout()
        self.title = StrongBodyLabel(self.title_text)
        self.btn = PushButton("选择")
        self.btn.setFixedWidth(100)

        layout2.addWidget(self.title)
        layout2.addWidget(self.btn)
        layout.addLayout(layout2)

        self.setLayout(layout)
        self.btn.clicked.connect(lambda: self.btn_signal.emit(self.title_text))

    def mousePressEvent(self, event):
        """重写鼠标点击事件"""
        if event.button() == Qt.LeftButton:
            # 发出信号，传递当前卡片的信息
            self.self_click.emit(self.file_path, self.voice_id)
        super().mousePressEvent(event)

    # def setSelected(self, selected):
    #     """设置选中状态"""
    #     self.selected = selected
    #     if selected:
    #         self.setProperty("selected", "true")
    #     else:
    #         self.setProperty("selected", "false")
    #     self.style().polish(self)  # 刷新样式



class VoiceCardItem_cast(QFrame):
    btn_signal = pyqtSignal(str)

    """自定义列表项（高度固定）"""
    def __init__(self, title: str, file_path: str = "", voice_id: str= "",parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            VoiceCardItem {
                border-radius: 8px;
                margin: 2px;
                padding: 5px;
                background: #f2f2f2;
            }
            VoiceCardItem:hover {
                background: #dddddd;
            }
        """)
        self.title_text = title
        self.file_path = file_path
        self.voice_id = voice_id

        layout = QVBoxLayout()
        layout2 = QHBoxLayout()
        self.title = StrongBodyLabel(self.title_text)
        self.btn = PushButton("选择")
        self.btn.setFixedWidth(100)

        layout2.addWidget(self.title)
        layout2.addWidget(self.btn)
        layout.addLayout(layout2)

        self.bar = None

        if self.file_path or self.voice_id:
            self.bar = SimpleMediaPlayBar()
            layout.addWidget(self.bar)
            self.bar.playButton.clicked.connect(self.get_http_mp3)  # 都进行延迟加载获取音频

        self.setLayout(layout)
        self.btn.clicked.connect(lambda: self.btn_signal.emit(self.title_text))

    def get_http_mp3(self):
        """
        实现自动获取声音。
        本身会触发一次播放，但是没有音频，肯定播放不了。从这里开始加载音频，进行播放。
        加载完毕后，之后就不会再触发了
        """
        # print(self.bar.player.mediaStatus())
        if self.bar.player.mediaStatus() == QMediaPlayer.MediaStatus.NoMedia:
            if not self.file_path and self.voice_id:
                try:
                    self.file_path = dubbingElevenLabs2.getInstance().connect.elevenlabs.voices.get(voice_id = self.voice_id).preview_url
                except Exception as e:
                    print(f"获取声音失败: {e}")
                    self.file_path = os.path.join(resource_path, "prepared_voices","default.mp3")
            if not self.file_path:
                self.file_path = os.path.join(resource_path, "prepared_voices", "default.mp3")
            print(self.file_path)
            if self.file_path.startswith("http"):
                self.bar.player.setSource(QUrl(self.file_path))
            else:
                self.bar.player.setSource(QUrl.fromLocalFile(self.file_path))
            self.bar.play()






