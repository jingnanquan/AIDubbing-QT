import copy
import sys

from PyQt5.QtCore import Qt, QPropertyAnimation, QPoint, QTimer
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QWidget, QFileDialog, QFrame, QVBoxLayout, \
    QInputDialog, QMessageBox, QMenu, QApplication, QSizePolicy, QDialog, QFormLayout, QLabel, QLineEdit, \
    QDialogButtonBox, QHBoxLayout

from Compoment.DraggableTextEdit import DraggableTextEdit
from Compoment.FileUploadArea import FileUploadArea
from Compoment.PathDialog import PrettyPathDialog
from UI.Ui_annotation import Ui_Annotation



class AnnotationInterface(Ui_Annotation, QFrame):


    def __init__(self, parent=None):
        super().__init__()
        print("批量标注界面加载")
        self.setupUi(self)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.worker = None
        self.loading_msg = None
        # 初始化字幕滚动列表和角色列表
        self._setup_unfinished_ui()

    def _setup_unfinished_ui(self):
        self.font = QFont()
        self.font.setFamily("微软雅黑")
        self.font.setPointSize(15)
        self.font.setBold(True)
        self.font.setWeight(75)
        self.scrollArea.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.extractBtn.setFixedHeight(40)
        self.scrollArea.setStyleSheet(
            """ #scrollArea{ border: None; background: transparent; } #scrollAreaWidgetContents_2{ background: transparent; } """)

        self.videoBox.setLayout(QVBoxLayout())
        self.videoBox.layout().setContentsMargins(0,0,0,0)
        self.compress_video_upload_area = FileUploadArea(label_text="视频文件", file_types=["*.mp4", "*.avi"])
        self.videoBox.layout().addWidget(self.compress_video_upload_area)

        self.subtitleBox.setLayout(QVBoxLayout())
        self.subtitleBox.layout().setContentsMargins(0,0,0,0)
        self.merge_subtitle_upload_area = FileUploadArea(label_text="字幕文件", file_types=["*.srt", "*.txt"])
        self.subtitleBox.layout().addWidget(self.merge_subtitle_upload_area)

        self.role_info_edit = DraggableTextEdit()
        self.role_info_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.role_info_edit.setPlaceholderText(
            "请在这里填写剧名、本集剧情概要、人物介绍、人物关系，可拖动文件自动解析文本。如果为空，系统会自动分析音视频内容生成剧情概要")
        self.role_info_edit.setFont(QFont("Microsoft YaHei", 10))
        self.role_info_edit.setStyleSheet("""
                    QTextEdit {
                        border: 1px solid #ddd;
                        border-radius: 6px;
                        padding: 8px;
                    }
                """)
        layout = QVBoxLayout()
        layout.setContentsMargins(9,0,9,0)
        label = QLabel("主角信息")
        label.setFont(self.font)
        layout.addWidget(label)
        layout.addWidget(self.role_info_edit)
        layout.setStretch(1, 4)
        self.info_container.setLayout(layout)


    def _on_general_finished(self, result: dict):
        if isinstance(self.loading_msg, QMessageBox):
            self.loading_msg.hide()
        # QMessageBox.information(self, "提示", result["msg"])
        dlg = PrettyPathDialog("任务完成!", result["msg"], result["result_path"], parent=self)
        dlg.exec_()






if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = AnnotationInterface()
    window.show()
    sys.exit(app.exec_())




