import sys

from PyQt5.QtWidgets import (QFrame, QVBoxLayout, QHBoxLayout, QLabel,
                             QFileDialog, QScrollArea, QWidget, QListWidget,
                             QListWidgetItem, QSpacerItem, QSizePolicy, QApplication, QMainWindow)
from PyQt5.QtCore import Qt, pyqtSignal, QUrl
from PyQt5.QtGui import QFont, QDragEnterEvent, QDropEvent, QMouseEvent, QDesktopServices
from pypinyin import pinyin
from qfluentwidgets import PushButton, ListWidget
import os

from Service.generalUtils import mixed_sort_key


class FileUploadArea(QFrame):
    """文件上传组件"""

    # 文件添加信号
    filesAdded = pyqtSignal(list)

    def __init__(self, parent=None, file_types=None, label_text=None):
        super().__init__(parent)
        self.file_types = file_types or ["*.*"]  # 默认接受所有文件
        self.label_text = label_text or "点击或拖动上传文件"
        self.file_paths = []
        self.file_scroll = None

        self.setup_ui()
        self.setup_connections()

    def setup_ui(self):
        self.setObjectName("uploadFrame")
        self.setStyleSheet("""
            #uploadFrame {
                background-color: #FFFFFF;
                border: 2px dashed #CED4DA;
                border-radius: 12px;
            }
            #uploadFrame:hover {
                background-color: #FFFFFF;
                border: 2px dashed #a1bbd7;
                border-radius: 12px;
            }
        """)

        """设置UI界面"""
        self.setFrameShape(QFrame.StyledPanel)
        self.setFrameShadow(QFrame.Raised)
        self.setAcceptDrops(True)
        self.setCursor(Qt.PointingHandCursor)

        # 主布局
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setSpacing(10)
        self.main_layout.setContentsMargins(20, 20, 20, 20)

        # 顶部按钮布局
        self.button_layout = QHBoxLayout()
        self.button_layout.setContentsMargins(-1, -1, -1, 0)
        self.clear_button = PushButton("清空")
        self.clear_button.setObjectName("clearButton")
        spacer = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.button_layout.addItem(spacer)
        self.button_layout.addWidget(self.clear_button)
        self.main_layout.addLayout(self.button_layout)

        # 中间空白区域
        spacer_top = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)
        self.main_layout.addItem(spacer_top)

        # 上传图标
        self.upload_icon_label = QLabel("📁")
        font = QFont()
        font.setFamily("Segoe UI")
        font.setPointSize(36)
        self.upload_icon_label.setFont(font)
        self.upload_icon_label.setAlignment(Qt.AlignCenter)
        self.main_layout.addWidget(self.upload_icon_label)

        # 上传文本
        self.upload_text_label = QLabel(self.label_text)
        font = QFont()
        font.setFamily("Microsoft JhengHei UI")
        font.setPointSize(12)
        font.setBold(True)
        self.upload_text_label.setFont(font)
        self.upload_text_label.setAlignment(Qt.AlignCenter)
        self.main_layout.addWidget(self.upload_text_label)

        # 支持格式文本
        format_text = "支持格式: " + ", ".join(self.file_types)
        self.format_label = QLabel(format_text)
        font = QFont()
        font.setFamily("Microsoft JhengHei UI")
        font.setPointSize(10)
        font.setBold(False)
        self.format_label.setFont(font)
        self.format_label.setAlignment(Qt.AlignCenter)
        self.main_layout.addWidget(self.format_label)

        # 底部空白区域
        spacer_bottom = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)
        self.main_layout.addItem(spacer_bottom)

        # 文件列表滚动区域
        # print(self.height())
        self.file_scroll = HiddenScrollArea(max_height=self.height()/2)
        self.main_layout.addWidget(self.file_scroll)

    def setup_connections(self):
        """设置信号连接"""
        self.clear_button.clicked.connect(self.clear_files)
        self.mousePressEvent = self._on_click

    def _on_click(self, event: QMouseEvent):
        """点击事件处理"""
        self.upload_files()

    def resizeEvent(self, event):
        """重写resizeEvent，当组件大小改变时调整滚动区域的最大高度"""
        super().resizeEvent(event)
        self._on_height_changed()

    def _on_height_changed(self):
        """当自身高度变化时触发的事件"""
        # 设置HiddenScrollArea的最大高度为当前组件高度的一半
        new_max_height = self.height() / 2
        if self.file_scroll:
            # print("触发设置", new_max_height)
            self.file_scroll.set_max_height(new_max_height)
            # 更新滚动区域的高度
            self.file_scroll.update_height()

    def upload_files(self):
        """打开文件选择对话框"""
        # 构建文件过滤器
        if self.file_types == ["*.*"]:
            filter_str = "所有文件 (*)"
        else:
            extensions = " ".join([f"*.{ext}" if not ext.startswith("*") else ext for ext in self.file_types])
            filter_str = f"支持文件 ({extensions});;所有文件 (*)"

        files, _ = QFileDialog.getOpenFileNames(
            self,
            "选择文件",
            "",
            filter_str
        )

        if files:
            self.add_files(files)



    def dragEnterEvent(self, event: QDragEnterEvent):
        """拖拽进入事件"""
        if event.mimeData().hasUrls():
            self.setStyleSheet("""
                #uploadFrame {
                    background-color: #F8F8F8;
                    border: 2px dashed #a1bbd7;
                    border-radius: 12px;
                }
            """)
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        """拖拽离开事件"""
        self.setStyleSheet("""
            #uploadFrame {
                background-color: #FFFFFF;
                border: 2px dashed #CED4DA;
                border-radius: 12px;
            }
            #uploadFrame:hover {
                background-color: #FFFFFF;
                border: 2px dashed #a1bbd7;
                border-radius: 12px;
            }
        """)

    def dropEvent(self, event: QDropEvent):
        """拖拽释放事件"""
        self.setStyleSheet("""
            #uploadFrame {
                background-color: #FFFFFF;
                border: 2px dashed #CED4DA;
                border-radius: 12px;
            }
            #uploadFrame:hover {
                background-color: #FFFFFF;
                border: 2px dashed #a1bbd7;
                border-radius: 12px;
            }
        """)

        urls = event.mimeData().urls()
        paths = [url.toLocalFile() for url in urls]

        # 处理文件和文件夹
        all_files = []
        for path in paths:
            if os.path.isdir(path):
                # 如果是文件夹，递归获取符合条件的文件
                all_files.extend(self._get_files_from_first_folder(path))
            elif os.path.isfile(path) and self._is_valid_file(path):
                # 如果是文件且符合格式要求
                all_files.append(path)

        if all_files:
            self.add_files(all_files)

    def _get_files_from_first_folder(self, folder_path):
        """从第一个文件夹中获取符合条件的文件"""
        valid_files = []
        # 使用 os.listdir 获取当前目录下的所有条目
        for entry in os.listdir(folder_path):
            # 拼接完整路径
            full_path = os.path.join(folder_path, entry)
            # 只处理文件，跳过目录
            if os.path.isfile(full_path) and self._is_valid_file(full_path):
                valid_files.append(full_path)
        return valid_files

    def _get_files_from_folder(self, folder_path):
        """从文件夹中获取符合条件的文件"""
        valid_files = []
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                file_path = os.path.join(root, file)
                if self._is_valid_file(file_path):
                    valid_files.append(file_path)
        return valid_files

    def _is_valid_file(self, file_path):
        """检查文件是否符合格式要求"""
        if self.file_types == ["*.*"]:
            return True

        file_ext = os.path.splitext(file_path)[1].lower()
        for ext in self.file_types:
            if ext.startswith("*"):
                if file_ext == ext[1:].lower():
                    return True
            else:
                if file_ext == f".{ext}".lower():
                    return True
        return False

    def add_files(self, file_paths):
        """添加文件到列表"""
        new_files = []
        for path in file_paths:
            if path not in self.file_paths:
                self.file_paths.append(path)
                new_files.append(path)

        if new_files:
            self.file_paths = sorted(self.file_paths, key=lambda x: mixed_sort_key(x))
            self.file_scroll.clear_files()
            self.file_scroll.add_items(self.file_paths)

        self.filesAdded.emit(self.file_paths)



    def clear_files(self):
        """清空文件列表"""
        self.file_paths.clear()
        self.file_scroll.clear_files()

    def get_files(self):
        """获取所有文件路径"""
        return self.file_paths[:]


class HiddenScrollArea(QScrollArea):
    def __init__(self, parent=None, max_height=None):
        super().__init__(parent)
        self.max_height = max_height or 400
        # print(self.max_height)
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
        self.file_paths = []
        # 样式可选
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setFrameShape(QScrollArea.NoFrame)

    def set_max_height(self, max_height):
        """设置最大高度"""
        self.max_height = max_height
        self.update_height()

    # def add_item(self, text: str):
    #     self.file_paths.append(text)
    #     self.list_widget.addItem(QListWidgetItem(os.path.basename(text)))
    #     self.update_height()

    def add_items(self, file_paths: []):
        """添加文件项"""
        for path in file_paths:
            self.file_paths.append(path)
            file_name = os.path.basename(path)
            self.list_widget.addItem(QListWidgetItem(file_name))

        self.list_widget.itemClicked.connect(self.on_item_clicked)
        self.update_height()

    def clear_files(self):
        self.file_paths = []
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
        new_height = int(min((count-1) * item_height + spacing + 65, self.max_height))
        self.setFixedHeight(new_height)

    def on_item_clicked(self, item):
        index = self.list_widget.row(item)
        path = self.file_paths[index]
        if os.path.exists(path):
            if os.path.isdir(path):
                # 如果是文件夹，直接打开
                QDesktopServices.openUrl(QUrl.fromLocalFile(path))
            elif os.path.isfile(path):
                print(sys.platform)
                if sys.platform == "win32":
                    os.system(f'explorer /select,"{path}"')
                else:
                    folder_path = os.path.dirname(path)
                    QDesktopServices.openUrl(QUrl.fromLocalFile(folder_path))
        else:
            print("Path does not exist")



if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = QMainWindow()
    window.setGeometry(300,300,700,300)
    window.setMaximumHeight(300)
    upload_area = FileUploadArea()
    window.setCentralWidget(upload_area)
    window.show()
    print(upload_area.height())
    sys.exit(app.exec_())
