import os

from PyQt5.QtGui import QBrush, QColor
from PyQt5.QtWidgets import (
    QWidget, QScrollArea, QListWidget, QVBoxLayout, QListWidgetItem, QApplication
)
from PyQt5.QtCore import Qt
from qfluentwidgets import ListWidget

'''
可隐藏的滚动窗口
'''


class HiddenScrollArea(QScrollArea):
    def __init__(self, parent=None, max_height=None):
        super().__init__(parent)
        self.max_height = max_height or 400
        print(self.max_height)
        self.setWidgetResizable(True)

        # 内容容器
        self.container = QWidget()
        self.container.setObjectName("ScrollContainer")
        self.setWidget(self.container)

        self.setContentsMargins(0,0,0,0)
        self.container.setContentsMargins(0,0,0,0)
        # 布局和 QListWidget
        self.layout = QVBoxLayout(self.container)
        self.layout.setContentsMargins(0,0,0,0)
        self.layout.setSpacing(0)
        self.list_widget = ListWidget()
        self.list_widget.setContentsMargins(0,0,0,0)
        self.layout.addWidget(self.list_widget)

        self.setStyleSheet("""
            QScrollArea{
                background: transparent;
            }
            #ScrollContainer{
                background: transparent;
            }
            """
        )
        # 初始化高度为 0
        self.setFixedHeight(0)
        self.voice_paths = []
        # 样式可选
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setFrameShape(QScrollArea.NoFrame)

    def add_item(self, text: str):
        self.voice_paths.append(text)
        self.list_widget.addItem(QListWidgetItem(os.path.basename(text)))
        # self.list_widget.item(0).setBackground(QBrush(QColor(0, 255, 0)))
        self.update_height()

    def clear_files(self):
        self.voice_paths = []
        self.list_widget.clear()
        self.setFixedHeight(0)

    def update_height(self):
        count = self.list_widget.count()
        if count == 0:
            self.setFixedHeight(0)
            return

        # 获取单个 item 的高度
        item_height = self.list_widget.sizeHintForRow(0)
        spacing = self.list_widget.spacing() if hasattr(self.list_widget, "spacing") else 5
        new_height = min((count-1) * item_height + spacing + 65, self.max_height)
        self.setFixedHeight(new_height)






if __name__ == '__main__':
    import sys
    from PyQt5.QtWidgets import QPushButton, QVBoxLayout, QWidget

    app = QApplication(sys.argv)
    window = QWidget()
    layout = QVBoxLayout(window)

    scroll = HiddenScrollArea()
    layout.addWidget(scroll)

    btn = QPushButton("Add Item")
    layout.addWidget(btn)

    i = [0]
    def add():
        i[0] += 1
        scroll.add_item(f"Item {i[0]}")

    btn.clicked.connect(add)

    window.resize(300, 200)
    window.show()
    sys.exit(app.exec_())
