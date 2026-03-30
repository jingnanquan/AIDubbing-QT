from PyQt5.QtCore import Qt
from PyQt5.QtGui import QStandardItemModel, QFont
from PyQt5.QtWidgets import QFrame, QVBoxLayout, QLabel, QHBoxLayout, QComboBox


class SubtitleListItem(QFrame):
    """自定义列表项（高度固定）"""
    def __init__(self, subtitle: dict, roles_model: QStandardItemModel, parent=None):
        super().__init__(parent)
        # self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setStyleSheet("""
            SubtitleListItem {
                border: 1px solid #ccc;
                border-radius: 4px;
                margin: 2px;
                padding: 5px;
                background: #f9f9f9;
            }
            QLabel, ComboBox, QComboBox {
                font-size: 14px;  /* 像素单位 */
                font-family: "Microsoft YaHei";
            }
        """)

        index, start, end, text = subtitle.values()
        layout = QVBoxLayout()
        row1_layout = QHBoxLayout()
        self.start = start
        self.end = end
        self.index = QLabel(f'编号：{index}')
        self.time = QLabel(f'{start}-->{end}')
        self.index.setFont(QFont("Microsoft YaHei", 12))
        self.time.setFont(QFont("Microsoft YaHei", 12))
        self.text = QLabel(text)
        self.text.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.text.setWordWrap(True)
        self.roles = QComboBox()
        self.roles.setModel(roles_model)
        row1_layout.addWidget(self.index)
        row1_layout.addWidget(self.roles)

        # layout.addWidget(self.roles)
        # layout.addWidget(self.index)
        layout.addLayout(row1_layout)
        layout.addWidget(self.time)
        layout.addWidget(self.text)
        self.setLayout(layout)

    def get_subtitle(self):
        """
        获取字幕信息
        :return: 字幕信息
        """
        return {
            "index": self.index.text(),
            "start": self.time.text(),
            "end": self.time.text(),
            "text": self.text.text(),
            "role": self.roles.currentText()
        }
