import os
import re

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QTextCursor
from PyQt5.QtWidgets import QTextEdit

class DraggableTextEdit(QTextEdit):
    """ Text edit """

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setAcceptDrops(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.style = self.styleSheet()

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            print("enter")
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        cursor_before = self.textCursor()
        pos_before = cursor_before.position()

        super().dropEvent(event)
        # ✅ 拖拽后，记录新的光标位置
        cursor_after = self.textCursor()
        pos_after = cursor_after.position()

        # ✅ 删除中间插入的 file:///xxx 内容（不使用正则）
        delete_cursor = self.textCursor()
        delete_cursor.setPosition(pos_before)
        delete_cursor.setPosition(pos_after, QTextCursor.KeepAnchor)
        delete_cursor.removeSelectedText()

        if event.mimeData().hasUrls():
            event.setDropAction(Qt.CopyAction)  # 可为 CopyAction，而不是 IgnoreAction
            event.accept()

            urls = event.mimeData().urls()
            paths = [url.toLocalFile() for url in urls]

            info_paths = []
            for path in paths:
                if os.path.isdir(path):
                    info_paths.extend(self.get_txt_files_in_folder(path))
                else:
                    info_paths.append(path)


            cursor = self.textCursor()
            cursor.movePosition(QTextCursor.End)

            for file_name in info_paths:
                try:
                    with open(file_name, 'r', encoding='utf-8') as f:
                        content = f.read()
                        cursor.insertText(content+"\n")
                except Exception as e:
                    print(f"Error reading file: {file_name}: {e}")

        else:
            event.ignore()


    def get_txt_files_in_folder(self, folder):
        return [
            os.path.join(root, file)
            for root, _, files in os.walk(folder)
            for file in files
            if file.lower().endswith('.txt')  # 注意应为字符串 '.txt'
        ]