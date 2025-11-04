import Config
import sys

from PyQt5.QtCore import Qt, QPropertyAnimation, QPoint, QTimer
from PyQt5.QtGui import QStandardItemModel, QStandardItem
from PyQt5.QtWidgets import QWidget, QFileDialog, QFrame, QVBoxLayout, \
    QInputDialog, QMessageBox, QMenu, QApplication, QSizePolicy, QDialog, QFormLayout, QLabel, QLineEdit, \
    QDialogButtonBox, QHBoxLayout
import os

from qfluentwidgets import LineEdit, BodyLabel, StrongBodyLabel, PushButton

from Compoment.FileUploadArea import FileUploadArea
from Compoment.PathDialog import PrettyPathDialog
from Service.videoUtils import _probe_video_duration_ms
from ThreadWorker.ToolsWorker import CompressVideoWorker, MergeVideoWorker, MergeSubtitleWorker, CloneVoiceWorker, \
    SplitSubtitleWorker, SyncSubtitleWorker, ClearBGMWorker, SplitVideoWorker
from UI.Ui_tools import Ui_Tools



class ToolsInterface(Ui_Tools, QFrame):


    def __init__(self, parent=None):
        super().__init__()
        print("工具子界面加载")
        self.setupUi(self)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.worker = None
        self.loading_msg = None
        # 初始化字幕滚动列表和角色列表
        self._setup_unfinished_ui()

    def _setup_unfinished_ui(self):
        self.scrollArea.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scrollArea.setStyleSheet(
            """ #scrollArea{ border: None; background: transparent; } #scrollAreaWidgetContents_2{ background: transparent; } """)

        self.compressBox.setLayout(QVBoxLayout())
        self.compressBox.layout().setContentsMargins(0,0,0,0)
        self.compress_video_upload_area = FileUploadArea(label_text="视频文件", file_types=["*.mp4", "*.avi"])
        self.compressBox.layout().addWidget(self.compress_video_upload_area)
        self.compressBtn.clicked.connect(self._compress_video)

        self.mergeSubtitleBox.setLayout(QVBoxLayout())
        self.mergeSubtitleBox.layout().setContentsMargins(0,0,0,0)
        self.mergeSubtitleVideoBox.setLayout(QVBoxLayout())
        self.mergeSubtitleVideoBox.layout().setContentsMargins(0,0,0,0)
        self.merge_subtitle_upload_area = FileUploadArea(label_text="上传字幕文件", file_types=["*.srt", "*.txt"])
        self.merge_subtitle_video_upload_area = FileUploadArea(label_text="上传视频文件", file_types=["*.mp4", "*.avi"])
        self.mergeSubtitleBox.layout().addWidget(self.merge_subtitle_upload_area)
        self.mergeSubtitleVideoBox.layout().addWidget(self.merge_subtitle_video_upload_area)
        self.mergeSubtitleBtn.clicked.connect(self._merge_subtitle)
        self.splitSubtitleBtn.clicked.connect(self._split_subtitle)

        self.mergeVideoBox.setLayout(QVBoxLayout())
        self.mergeVideoBox.layout().setContentsMargins(0,0,0,0)
        self.merge_video_upload_area = FileUploadArea(label_text="视频文件", file_types=["*.mp4", "*.avi"])
        self.mergeVideoBox.layout().addWidget(self.merge_video_upload_area)
        self.mergeVideoBtn.clicked.connect(self._merge_video)

        self.cloneVoiceBox.setLayout(QVBoxLayout())
        self.cloneVoiceBox.layout().setContentsMargins(0,0,0,0)
        self.clone_voice_upload_area = FileUploadArea(label_text="音频文件", file_types=["*.mp3", "*.wav", "*MP3"])
        self.cloneVoiceBox.layout().addWidget(self.clone_voice_upload_area)
        self.cloneVoiceBtn.clicked.connect(self._clone_voice)


        self.srcSubtitleBox.setLayout(QVBoxLayout())
        self.srcSubtitleBox.layout().setContentsMargins(0,0,0,0)
        self.dstSubtitleBox.setLayout(QVBoxLayout())
        self.dstSubtitleBox.layout().setContentsMargins(0,0,0,0)
        self.sync_src_subtitle_upload_area = FileUploadArea(label_text="已标注字幕文件", file_types=["*.srt", "*.txt"])
        self.sync_dst_subtitle_upload_area = FileUploadArea(label_text="待同步字幕文件", file_types=["*.srt", "*.txt"])
        self.srcSubtitleBox.layout().addWidget(self.sync_src_subtitle_upload_area)
        self.dstSubtitleBox.layout().addWidget(self.sync_dst_subtitle_upload_area)
        self.syncSubtitleBtn.clicked.connect(self._sync_subtitle)

        self.clearbgmBox.setLayout(QVBoxLayout())
        self.clearbgmBox.layout().setContentsMargins(0,0,0,0)
        self.clear_bgm_upload_area = FileUploadArea(label_text="视频文件", file_types=["*.mp4", "*.avi"])
        self.clearbgmBox.layout().addWidget(self.clear_bgm_upload_area)
        self.clearbgmBtn.clicked.connect(self._clear_bgm)

        self.srcVideoBox.setLayout(QVBoxLayout())
        self.srcVideoBox.layout().setContentsMargins(0,0,0,0)
        self.dstVideoBox.setLayout(QVBoxLayout())
        self.dstVideoBox.layout().setContentsMargins(0,0,0,0)
        self.split_src_video_upload_area = FileUploadArea(label_text="待分割的长视频文件(1个)", file_types=["*.mp4", "*.avi"])
        self.split_dst_video_upload_area = FileUploadArea(label_text="原视频文件列表", file_types=["*.mp4", "*.avi"])
        self.srcVideoBox.layout().addWidget(self.split_src_video_upload_area)
        self.dstVideoBox.layout().addWidget(self.split_dst_video_upload_area)
        self.splitVideoBtn.clicked.connect(self._split_video)



        # self.frame_1.setMinimumHeight(self.frame_1.sizeHint().height())
        # self.frame_2.setMinimumHeight(self.frame_2.sizeHint().height())
        # self.frame_3.setMinimumHeight(self.frame_3.sizeHint().height())
        # self.frame_4.setMinimumHeight(self.frame_4.sizeHint().height())
        # self.frame_5.setMinimumHeight(self.frame_5.sizeHint().height())
        # self.frame_6.setMinimumHeight(self.frame_6.sizeHint().height())
        # self.frame_7.setMinimumHeight(self.frame_7.sizeHint().height())
        # self.frame_8.setMinimumHeight(self.frame_8.sizeHint().height())

        # self.frame_4.setLayout(QVBoxLayout())
        # self.testarea1 = FileUploadArea(label_text="视频文件", file_types=["*.mp4", "*.avi"])
        # self.frame_4.layout().addWidget(self.testarea1)

        # self.frame_5.setLayout(QVBoxLayout())
        # self.testarea2 = FileUploadArea(label_text="视频文件", file_types=["*.mp4", "*.avi"])
        # self.frame_5.layout().addWidget(self.testarea2)
        #
        # self.frame_6.setLayout(QVBoxLayout())
        # self.testarea3 = FileUploadArea(label_text="视频文件", file_types=["*.mp4", "*.avi"])
        # self.frame_6.layout().addWidget(self.testarea3)

    def _compress_video(self):
        print("压缩视频")
        video_paths = self.compress_video_upload_area.file_paths
        if not video_paths:
            QMessageBox.warning(self, "警告", "请上传视频文件")
            return

        print(video_paths)
        self.loading_msg = QMessageBox(self)
        self.loading_msg.setWindowTitle("请稍候")
        self.loading_msg.setText("正在压缩中，请稍候...")
        self.loading_msg.setStandardButtons(QMessageBox.NoButton)
        self.loading_msg.setModal(True)
        self.loading_msg.show()
        QApplication.processEvents()

        self.worker = CompressVideoWorker(video_paths)
        self.worker.finished.connect(self._on_general_finished)
        self.worker.start()

    def _clear_bgm(self):
        print("清除背景音乐")
        video_paths = self.clear_bgm_upload_area.file_paths
        if not video_paths:
            QMessageBox.warning(self, "警告", "请上传视频文件")
            return

        print(video_paths)
        self.loading_msg = QMessageBox(self)
        self.loading_msg.setWindowTitle("请稍候")
        self.loading_msg.setText("正在清除背景音乐中，请稍候...")
        self.loading_msg.setStandardButtons(QMessageBox.NoButton)
        self.loading_msg.setModal(True)
        self.loading_msg.show()
        QApplication.processEvents()

        self.worker = ClearBGMWorker(video_paths)
        self.worker.finished.connect(self._on_general_finished)
        self.worker.start()

    def _merge_video(self):
        print("合并视频")
        video_paths = self.merge_video_upload_area.file_paths
        if not video_paths or len(video_paths) < 2:
            QMessageBox.warning(self, "警告", "请上传至少2个视频文件")
            return

        print(video_paths)
        self.loading_msg = QMessageBox(self)
        self.loading_msg.setWindowTitle("请稍候")
        self.loading_msg.setText("正在合并中，请稍候...")
        self.loading_msg.setStandardButtons(QMessageBox.NoButton)
        self.loading_msg.setModal(True)
        self.loading_msg.show()
        QApplication.processEvents()

        self.worker = MergeVideoWorker(video_paths)
        self.worker.finished.connect(self._on_general_finished)
        self.worker.start()

    def _clone_voice(self):
        print("克隆语音")
        voice_path = self.clone_voice_upload_area.file_paths
        if not voice_path:
            QMessageBox.warning(self, "警告", "请上传音频文件")
            return
        print(voice_path)
        self.loading_msg = QMessageBox(self)
        self.loading_msg.setWindowTitle("请稍候")
        self.loading_msg.setText("正在克隆中，请稍候...")
        self.loading_msg.setStandardButtons(QMessageBox.NoButton)
        self.loading_msg.setModal(True)
        self.loading_msg.show()
        QApplication.processEvents()

        self.worker = CloneVoiceWorker(voice_path)
        self.worker.finished.connect(self._on_general_finished)
        self.worker.start()

    def _sync_subtitle(self):
        print("同步字幕")
        src_subtitle_paths = self.sync_src_subtitle_upload_area.file_paths
        dst_subtitle_paths = self.sync_dst_subtitle_upload_area.file_paths
        if not src_subtitle_paths or not dst_subtitle_paths:
            QMessageBox.warning(self, "警告", "请上传源字幕文件和待同步字幕文件")
            return
        if len(src_subtitle_paths) != len(dst_subtitle_paths):
            QMessageBox.warning(self, "警告", "源字幕文件和待同步字幕文件数量不一致")
            return
        self.loading_msg = QMessageBox(self)
        self.loading_msg.setWindowTitle("请稍候")
        self.loading_msg.setText("正在同步中，请稍候...")
        self.loading_msg.setStandardButtons(QMessageBox.NoButton)
        self.loading_msg.setModal(True)
        self.loading_msg.show()
        QApplication.processEvents()

        self.worker = SyncSubtitleWorker(src_subtitle_paths, dst_subtitle_paths)
        self.worker.finished.connect(self._on_general_finished)
        self.worker.start()

    def _split_video(self):
        print("分割视频")
        src_video_path = self.split_src_video_upload_area.file_paths
        dst_video_paths = self.split_dst_video_upload_area.file_paths
        if not src_video_path or not dst_video_paths:
            QMessageBox.warning(self, "警告", "请上传待分割的长视频文件和原视频文件列表")
            return
        if len(src_video_path) >1:
            QMessageBox.warning(self, "警告", "待分割的长视频文件只能有一个")
            return

        print(src_video_path[0], dst_video_paths)
        self.loading_msg = QMessageBox(self)
        self.loading_msg.setWindowTitle("请稍候")
        self.loading_msg.setText("正在分割中，请稍候...")
        self.loading_msg.setStandardButtons(QMessageBox.NoButton)
        self.loading_msg.setModal(True)
        self.loading_msg.show()
        QApplication.processEvents()

        self.worker = SplitVideoWorker(src_video_path[0], dst_video_paths)
        self.worker.finished.connect(self._on_general_finished)
        self.worker.start()


    def _merge_subtitle(self):
        print("合并字幕")
        subtitle_paths = self.merge_subtitle_upload_area.file_paths
        video_paths = self.merge_subtitle_video_upload_area.file_paths
        if not subtitle_paths or len(subtitle_paths) < 2:
            QMessageBox.warning(self, "警告", "请上传至少2个字幕文件")
            return
        if not video_paths or len(video_paths) < 2:
            QMessageBox.warning(self, "警告", "请上传至少2个视频文件")
            return
        if not len(subtitle_paths) == len(video_paths):
            QMessageBox.warning(self, "警告", "字幕文件和视频文件数量不一致")
            return

        params = {}
        offset_ms=0
        for subtitle_path, video_path in zip(subtitle_paths, video_paths):
            try:
                duration_ms = _probe_video_duration_ms(video_path)
                params[subtitle_path] = int(offset_ms)
                offset_ms += duration_ms
            except ValueError:
                params[subtitle_path] = 0

        self.loading_msg = QMessageBox(self)
        self.loading_msg.setWindowTitle("请稍候")
        self.loading_msg.setText("正在合并中，请稍候...")
        self.loading_msg.setStandardButtons(QMessageBox.NoButton)
        self.loading_msg.setModal(True)
        self.loading_msg.show()
        QApplication.processEvents()

        self.worker = MergeSubtitleWorker(params)
        self.worker.finished.connect(self._on_general_finished)
        self.worker.start()

    def _split_subtitle(self):
        print("合并字幕")
        subtitle_paths = self.merge_subtitle_upload_area.file_paths
        video_paths = self.merge_subtitle_video_upload_area.file_paths
        if not subtitle_paths or len(subtitle_paths) != 1:
            QMessageBox.warning(self, "警告", "只能上传1个字幕文件用于拆分")
            return
        if not video_paths or len(video_paths) < 2:
            QMessageBox.warning(self, "警告", "请上传至少2个视频文件")
            return
        params = {}
        offset_ms=0
        for i, video_path in enumerate(video_paths):
            try:
                duration_ms = _probe_video_duration_ms(video_path)
                params[i] = int(offset_ms)
                offset_ms += duration_ms
            except ValueError:
                params[i] = 0

        self.loading_msg = QMessageBox(self)
        self.loading_msg.setWindowTitle("请稍候")
        self.loading_msg.setText("正在拆分中，请稍候...")
        self.loading_msg.setStandardButtons(QMessageBox.NoButton)
        self.loading_msg.setModal(True)
        self.loading_msg.show()
        QApplication.processEvents()
        self.worker = SplitSubtitleWorker(params, subtitle_paths[0])
        self.worker.finished.connect(self._on_general_finished)
        self.worker.start()


    # FIXME: 废弃代码
    def _merge_subtitle_cast(self):
        print("合并字幕")
        subtitle_paths = self.merge_subtitle_upload_area.file_paths
        if not subtitle_paths or len(subtitle_paths) < 2:
            QMessageBox.warning(self, "警告", "请上传至少2个字幕文件")
            return

        param_window = MergeSubtitleParamWindow(subtitle_paths=subtitle_paths, parent=self)
        if param_window.exec_() == QDialog.Accepted:  # 用户点击确定
            params = param_window.get_params()
            print("用户输入的偏移参数:", params)
            self.loading_msg = QMessageBox(self)
            self.loading_msg.setWindowTitle("请稍候")
            self.loading_msg.setText("正在合并中，请稍候...")
            self.loading_msg.setStandardButtons(QMessageBox.NoButton)
            self.loading_msg.setModal(True)
            self.loading_msg.show()
            QApplication.processEvents()

            self.worker = MergeSubtitleWorker(params)
            self.worker.finished.connect(self._on_general_finished)
            self.worker.start()
        else:
            print("用户取消操作")
            return

        # print(subtitle_paths)
        # self.loading_msg = QMessageBox(self)
        # self.loading_msg.setWindowTitle("请稍候")
        # self.loading_msg.setText("正在合并中，请稍候...")
        # self.loading_msg.setStandardButtons(QMessageBox.NoButton)
        # self.loading_msg.setModal(True)
        # self.loading_msg.show()
        # QApplication.processEvents()
        #
        # self.worker = MergeVideoWorker(subtitle_paths)
        # self.worker.finished.connect(self._on_general_finished)
        # self.worker.start()

    def _on_general_finished(self, result: dict):
        if isinstance(self.loading_msg, QMessageBox):
            self.loading_msg.hide()
        # QMessageBox.information(self, "提示", result["msg"])
        dlg = PrettyPathDialog("任务完成!", result["msg"], result["result_path"], parent=self)
        dlg.exec_()



class MergeSubtitleParamWindow(QDialog):
    def __init__(self, subtitle_paths, parent=None):
        super().__init__(parent)
        self.setWindowTitle("字幕合并参数设置")
        self.resize(400, 250)

        # 去掉标题栏上的 ? 按钮
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        self.subtitle_paths = subtitle_paths
        self.offset_inputs = {}  # 保存 path -> QLineEdit

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12,12,12,14)
        layout.setSpacing(12)

        # 顶部标题行（文件名 / 偏移时间）
        header_layout = QHBoxLayout()
        header_filename = StrongBodyLabel("文件名")
        header_filename.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        header_offset = StrongBodyLabel("偏移时间（ms）")
        header_offset.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        header_layout.addWidget(header_filename)
        header_layout.addStretch()
        header_layout.addWidget(header_offset)
        layout.addLayout(header_layout)

        # 表单布局：左文件名，右偏移输入框
        form_layout = QFormLayout()
        form_layout.setSpacing(10)
        for path in self.subtitle_paths:
            label = BodyLabel(path)
            label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

            offset_input = LineEdit()
            offset_input.setText("0")
            offset_input.setFixedWidth(100)  # 控制输入框宽度
            offset_input.setAlignment(Qt.AlignRight)

            self.offset_inputs[path] = offset_input
            form_layout.addRow(label, offset_input)

        layout.addLayout(form_layout)

        # 确认 & 取消按钮
        button_box = QDialogButtonBox()
        ok_button = button_box.addButton(PushButton("确认"), QDialogButtonBox.AcceptRole)
        cancel_button = button_box.addButton(PushButton("取消"), QDialogButtonBox.RejectRole)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def get_params(self):
        """
        返回用户填写的参数: dict[path -> int(offset_ms)]
        """
        result = {}
        for path, input_box in self.offset_inputs.items():
            try:
                result[path] = int(input_box.text().strip())
            except ValueError:
                result[path] = 0
        return result


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = ToolsInterface()
    window.show()
    sys.exit(app.exec_())




