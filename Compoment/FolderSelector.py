from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout,
                             QPushButton, QLineEdit, QFileDialog, QHBoxLayout, QLabel)
from PyQt5.QtCore import Qt
import sys

from qfluentwidgets import LineEdit, PushButton


class SingleFolderSelector(QWidget):
    def __init__(self, path:str=""):
        super().__init__()
        self.path = path
        self.initUI()

    def initUI(self):
        # 主布局
        layout = QHBoxLayout()
        layout.setContentsMargins(0,0,0,0)

        self.label = QLabel("保存路径:")
        self.label.setFont(QFont("Microsoft YaHei", 11))
        # 文本框：显示选择的文件夹路径
        self.folder_path_display = LineEdit()
        self.folder_path_display.setPlaceholderText("未选择文件夹")
        if self.path: self.folder_path_display.setText(self.path)
        self.folder_path_display.setReadOnly(True)  # 设置为只读

        # 按钮：触发文件夹选择
        self.select_button = PushButton("选择")
        self.select_button.clicked.connect(self.open_folder_dialog)

        # 添加到布局
        layout.addWidget(self.label)
        layout.addWidget(self.folder_path_display)
        layout.addWidget(self.select_button)

        self.setLayout(layout)
        self.setWindowTitle('文件夹选择器')
        self.show()

    def open_folder_dialog(self):
        # 打开文件夹选择对话框
        folder_path = QFileDialog.getExistingDirectory(
            self,
            "选择文件夹",
            "",  # 默认路径（空字符串表示当前目录）
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )

        # 如果用户选择了文件夹（没有点击取消）
        if folder_path:
            self.folder_path_display.setText(folder_path)
            self.folder_path_display.setToolTip(folder_path)  # 设置悬停提示

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = SingleFolderSelector()
    sys.exit(app.exec_())