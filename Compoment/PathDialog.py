from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QApplication
from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtGui import QDesktopServices
import sys
import os


'''
最后弹出的保存路径弹窗
'''

class PrettyPathDialog(QDialog):
    def __init__(self, title:str, msg:str, path, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(500)
        self.setMaximumWidth(750)

        self.setStyleSheet("QDialog{background:#f5f5f5}")
        layout = QVBoxLayout()
        self.setLayout(layout)

        info_label = QLabel(msg)
        info_label.setStyleSheet("font-size: 14px;")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        # 高亮路径并允许点击
        link_label = QLabel(f'<a href="{path}">{path}</a>')
        link_label.setTextInteractionFlags(Qt.TextBrowserInteraction)
        link_label.setOpenExternalLinks(False)
        link_label.setWordWrap(True)
        link_label.setStyleSheet("font-size: 13px; color: blue;background:#f5f5f5")
        link_label.linkActivated.connect(self.open_in_explorer)
        self.path = path
        layout.addWidget(link_label)

        # OK按钮
        ok_btn = QPushButton("确定")
        ok_btn.clicked.connect(self.accept)
        ok_btn.setFixedWidth(80)
        ok_btn.setStyleSheet("padding: 5px;")
        layout.addWidget(ok_btn, alignment=Qt.AlignRight)

    def open_in_explorer(self):
        """
        优化了打开逻辑
        """
        path = self.path
        if os.path.exists(path):
            if os.path.isdir(path):
                # 如果是文件夹，直接打开
                QDesktopServices.openUrl(QUrl.fromLocalFile(path))
            elif os.path.isfile(path):
                # 如果是文件，打开文件所在文件夹并定位到该文件
                # folder_path = os.path.dirname(path)
                # QDesktopServices.openUrl(QUrl.fromLocalFile(folder_path))
                # 在 Windows 上，可以使用 explorer.exe 来定位文件
                print(sys.platform)
                if sys.platform == "win32":
                    os.system(f'explorer /select,"{path}"')
        else:
            print("Path does not exist")


        # folder = os.path.dirname(self.path)
        # QDesktopServices.openUrl(QUrl.fromLocalFile(folder))

# 示例调用
if __name__ == "__main__":
    app = QApplication(sys.argv)
    dlg = PrettyPathDialog("a","b", r"E:\offer\AI配音pyqt版\AIDubbing-QT-main\OutputFolder\project_result")
    dlg.exec_()
