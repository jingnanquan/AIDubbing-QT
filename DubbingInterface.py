from qfluentwidgets import RadioButton, LineEdit, BodyLabel, ComboBox

from Compoment.DubbingParamWindows2 import spare_voices, prepared_voices, VoiceSelectorWindow
from Compoment.FolderSelector import SingleFolderSelector
from Config import ROLE_ANNO_FOLDER, RESULT_OUTPUT_FOLDER
import sys
import os
import datetime

from PyQt5.QtCore import Qt, QPropertyAnimation, QPoint, QTimer, QThread, pyqtSignal
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QWidget, QFileDialog, QFrame, QVBoxLayout, \
    QInputDialog, QMessageBox, QMenu, QApplication, QSizePolicy, QDialog, QFormLayout, QLabel, QButtonGroup, \
    QHBoxLayout, QLineEdit, QGridLayout

from Compoment.DraggableTextEdit import DraggableTextEdit
from Compoment.FileUploadArea import FileUploadArea
from Compoment.PathDialog import PrettyPathDialog
from Service.datasetUtils import datasetUtils
from Service.dubbingMain.dubbingElevenLabs import dubbingElevenLabs
from Service.generalUtils import time_str_to_ms, ms_to_time_str, mixed_sort_key, is_valid_cps
from ThreadWorker.BatchDubbingWorker import BatchDubbingWorker
# from Service.dubbingMain.llmAPI import LLMAPI
from Service.subtitleUtils import parse_subtitle, parse_subtitle_uncertain
from UI.Ui_dubbing import Ui_Dubbing


class VoiceSelectorWidget(QFrame):
    select_voice_signal = pyqtSignal(bool)

    def __init__(self, role_name, default_voice_name="", parent=None):
        super().__init__(parent)

        self.role_name = role_name
        self.default_voice_name = default_voice_name

        # 初始化界面组件
        self.label = None
        self.combo_box = None
        self.line_edit = None

        # 初始化界面
        self.init_ui()

        # self.setObjectName("VoiceSelectorWidget")
        self.setStyleSheet("""
            VoiceSelectorWidget {
                border-radius: 8px;
                background: #f8f8f8;
            }
        """)


    def init_ui(self):
        # 创建主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # 创建网格布局
        grid_layout = QGridLayout()
        grid_layout.setContentsMargins(7, 7, 7, 7)

        # 第一行：标签和组合框
        self.label = BodyLabel(self.role_name + "：")
        self.label.setFont(QFont("Microsoft YaHei", 11))

        self.combo_box = ComboBox()
        self.combo_box.clicked.connect(self.select_voice)
        if self.default_voice_name:
            self.combo_box.setText(self.default_voice_name)

        # 第二行：行编辑器
        self.line_edit = LineEdit()
        self.line_edit.setPlaceholderText("选择声音或在此处填写声音id。")

        # 添加到网格布局
        grid_layout.addWidget(self.label, 0, 0)
        grid_layout.addWidget(self.combo_box, 0, 1)
        grid_layout.addWidget(self.line_edit, 1, 0, 1, 2)  # 跨两列

        # 设置主布局
        main_layout.addLayout(grid_layout)

        # 设置组件引用（为了与现有代码保持一致）
        self.voice_combox_ref = self.combo_box
        self.voice_edit_ref = self.line_edit

    def select_voice(self):
        self.select_voice_signal.emit(True)  # 任务完成，发出信号

    def get_selected_voice(self):
        """获取选中的声音"""
        if self.line_edit.text():
            return self.line_edit.text()
        else:
            return self.combo_box.text()

    def set_voice_list(self, voice_list):
        """设置声音列表"""
        self.voice_list = voice_list
        self.combo_box.clear()
        if voice_list:
            self.combo_box.addItems(voice_list)





class DubbingInterface(Ui_Dubbing, QFrame):


    def __init__(self, parent=None):
        super().__init__()
        print("批量标注界面加载")
        self.setupUi(self)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.worker = None
        self.loading_msg = None
        self.voice_selector_widgets = []
        self.activate_sender = None
        self.voice_selector_window = None
        self.all_roles = []

        voiceDict1 = datasetUtils.getInstance().query_voice_id(1)
        voiceDict2 = {}
        for key, value in voiceDict1.items():
            voiceDict2[key] = [value, ""]  # 这里置为空
        self.voiceDict = spare_voices | voiceDict2 | prepared_voices
        self.voiceNameList = list(self.voiceDict.keys())

        # 初始化字幕滚动列表和角色列表
        self._setup_unfinished_ui()

    def _setup_unfinished_ui(self):

        self.folder_selector = SingleFolderSelector(RESULT_OUTPUT_FOLDER)
        self.operate_container.layout().insertWidget(0, self.folder_selector)

        self.cps_widget = QWidget()
        layout = QHBoxLayout(self.cps_widget)
        layout.setContentsMargins(0,0,0,0)
        # self.operate_container.setMinimumHeight(400)
        self.operate_container.layout().insertWidget(0, self.cps_widget)

        layout.addWidget(BodyLabel("cps阈值"))
        self.cps_input = LineEdit()
        self.cps_input.setText("23")
        layout.addWidget(self.cps_input)


        self.annotation_language_widget = QWidget()
        layout1 = QHBoxLayout(self.annotation_language_widget)
        layout1.setContentsMargins(0, 0, 0, 0)
        layout1.setSpacing(10)
        self.language_input = LineEdit()
        self.language_input.setText("中文")
        self.sub_language_input = LineEdit()
        self.sub_language_input.setText("中文")
        layout1.addWidget(BodyLabel("视频语言:"))
        layout1.addWidget(self.language_input)
        layout1.addWidget(BodyLabel("字幕语言:"))
        layout1.addWidget(self.sub_language_input)
        self.operate_container.layout().insertWidget(0, self.annotation_language_widget)


        self.font = QFont()
        self.font.setFamily("微软雅黑")
        self.font.setPointSize(15)
        self.font.setBold(True)
        self.font.setWeight(75)
        self.scrollArea.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.dubbingBtn.setFixedHeight(40)
        self.separateBtn.setFixedHeight(40)

        self.scrollArea.setStyleSheet(
            """ #scrollArea{ border: None; background: transparent; } #scrollAreaWidgetContents_2{ background: transparent; } """)
        self.roleScrollArea.setObjectName("roleScrollArea")
        self.scrollArea_2.setStyleSheet(
            """ #scrollArea_2{ border: None; background: transparent; } #roleScrollArea{ background: transparent; } """)

        self.roleFrame.setStyleSheet("""#roleFrame{ background: #FFFFFF; } """)
        self.VoiceSelectorLayout = QVBoxLayout()
        self.VoiceSelectorLayout.setAlignment(Qt.AlignTop)  # 内容顶部对齐
        self.VoiceSelectorLayout.setSpacing(12)
        self.VoiceSelectorLayout.setContentsMargins(0,9,9,9)
        self.roleScrollArea.setLayout(self.VoiceSelectorLayout)

        self.videoBox.setLayout(QVBoxLayout())
        self.videoBox.layout().setContentsMargins(0,0,0,0)
        self.compress_video_upload_area = FileUploadArea(label_text="视频文件", file_types=["*.mp4", "*.avi"])
        self.videoBox.layout().addWidget(self.compress_video_upload_area)

        self.subtitleBox.setLayout(QVBoxLayout())
        self.subtitleBox.layout().setContentsMargins(0,0,0,0)
        self.merge_subtitle_upload_area = FileUploadArea(label_text="待配音且已标注的字幕文件", file_types=["*.srt", "*.txt"])
        self.merge_subtitle_upload_area.filesAdded.connect(self._on_extract_roles)
        self.subtitleBox.layout().addWidget(self.merge_subtitle_upload_area)

        self.role_info_edit = DraggableTextEdit()
        self.role_info_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.role_info_edit.setPlaceholderText(
            "预留位置")
        self.role_info_edit.setFont(QFont("Microsoft YaHei", 12))
        self.role_info_edit.setStyleSheet("""
                    QTextEdit {
                        border: 1px solid #ddd;
                        border-radius: 6px;
                        padding: 8px;
                    }
                """)
        layout = QVBoxLayout()
        layout.setContentsMargins(2,0,9,0)
        label = QLabel("预留位置")
        label.setFont(self.font)
        layout.addWidget(label)
        layout.addWidget(self.role_info_edit)
        layout.setStretch(1, 4)
        self.info_container.setLayout(layout)
        self.info_container.setMinimumHeight(180)
        # wire button
        self.separateBtn.hide()
        self.dubbingBtn.clicked.connect(self._on_dubbing_clicked)
        self.operate_container.setMinimumHeight(220)


    def _add_role_selector(self, role_name: str):
        voice_selector_widget = VoiceSelectorWidget(role_name, self.voiceNameList[0])
        voice_selector_widget.select_voice_signal.connect(self.select_voice)
        self.VoiceSelectorLayout.addWidget(voice_selector_widget)
        self.voice_selector_widgets.append(voice_selector_widget)

    def select_voice(self, flag:bool=True):
        self.activate_sender = self.sender()
        assert isinstance(self.activate_sender, VoiceSelectorWidget)
        print(self.activate_sender.objectName())
        if self.voice_selector_window is not None and isinstance(self.voice_selector_window, VoiceSelectorWindow):
            self.voice_selector_window.show()
        else:
            self.voice_selector_window = VoiceSelectorWindow(self.voiceDict)
            self.voice_selector_window.setWindowModality(Qt.ApplicationModal)
            self.voice_selector_window.show()
            self.voice_selector_window.return_signal.connect(self.set_combobox_text)

    def set_combobox_text(self, voice_name):
        self.activate_sender.combo_box.setText(voice_name)

    def _on_general_finished(self, result: dict=None):
        if isinstance(self.loading_msg, QMessageBox):
            self.loading_msg.hide()
        if self.worker:
            self.worker.deleteLater()
            self.worker = None
        if result:
            dlg = PrettyPathDialog("任务完成!", result["msg"], result["result_path"], parent=self)
            dlg.exec_()

    def _on_extract_roles(self, file_paths: list):
        """提取字幕中的角色"""
        if not file_paths:
            return
        self.loading_msg = QMessageBox(self)
        self.loading_msg.setWindowTitle("请稍候")
        self.loading_msg.setText("正在解析字幕中的角色，请稍候...")
        self.loading_msg.setStandardButtons(QMessageBox.NoButton)
        self.loading_msg.setModal(True)
        self.loading_msg.show()
        QApplication.processEvents()

        all_roles = []
        for file_path in file_paths:
            _, roles = parse_subtitle_uncertain(file_path)
            if roles:
                all_roles.extend(roles)
        print(all_roles)

        if all_roles:
            self.all_roles = sorted(list(set(all_roles)), key=lambda x: mixed_sort_key(x))
            self._update_role_selector()

        self._on_general_finished()

    def _update_role_selector(self):
        """更新角色选择器"""
        for i in range(self.VoiceSelectorLayout.count()):
            self.VoiceSelectorLayout.itemAt(i).widget().deleteLater()
        self.voice_selector_widgets = []
        for role_name in self.all_roles:
            self._add_role_selector(role_name)


    def _on_dubbing_clicked(self):

        cps = self.cps_input.text()
        print(cps)
        """Validate inputs and start batch role annotation worker."""
        video_paths = self.compress_video_upload_area.file_paths if hasattr(self, 'compress_video_upload_area') else []
        subtitle_paths = self.merge_subtitle_upload_area.file_paths if hasattr(self, 'merge_subtitle_upload_area') else []
        role_info = self.role_info_edit.toPlainText().strip() if hasattr(self, 'role_info_edit') else ""

        if not video_paths or not subtitle_paths:
            QMessageBox.warning(self, "警告", "请同时上传视频文件和字幕文件")
            return

        if len(video_paths) != len(subtitle_paths):
            QMessageBox.warning(self, "警告", "视频与字幕数量不一致，请检查后重试")
            return

        if cps and not is_valid_cps(cps):
            QMessageBox.warning(self, "警告", "请输入3到40之间的整数, 或者不填写")
            return

        voice_count  = self.get_voices_count()
        if voice_count + len(self.voice_selector_widgets) > 160:
            QMessageBox.warning(self, "警告", f"请删除克隆的声音，使其小于{160-voice_count}个")
            return

        pairs = list(zip(video_paths, subtitle_paths))

        print(video_paths)

        # loading dialog
        self.loading_msg = QMessageBox(self)
        self.loading_msg.setWindowTitle("请稍候")
        self.loading_msg.setText("正在进行批量视频配音，请稍候...")
        self.loading_msg.setStandardButtons(QMessageBox.NoButton)
        self.loading_msg.setModal(True)
        self.loading_msg.show()
        QApplication.processEvents()

        # start worker
        timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        output_root = os.path.join(self.folder_selector.folder_path_display.text(), f"批量视频配音-{os.path.splitext(os.path.basename(video_paths[0]))[0]}{timestamp}")

        # if self.annotation_option == 0:
        #     self.worker = BatchAnnotationWorker(pairs, role_info, output_root, self.extraOutputBtn.isChecked())
        # else:
        #     self.worker = BatchAnnotationWorker_with_AudioFeature(pairs, role_info, output_root, self.extraOutputBtn.isChecked(), if_translate=self.language_input.text() != self.sub_language_input.text(), language= self.language_input.text())

        voice_params = {}
        for i in range(len(self.voice_selector_widgets)):
            widget = self.voice_selector_widgets[i]
            assert isinstance(widget, VoiceSelectorWidget)
            if widget.line_edit.text():
                voice_params[widget.role_name] = widget.line_edit.text()
            elif widget.combo_box.text() == "不配音":
                voice_params[widget.role_name] = "-1"
            else:
                voice_params[widget.role_name] = self.voiceDict[widget.combo_box.text()][0]

        print(voice_params)

        self.worker = BatchDubbingWorker(pairs, output_root, self.extraOutputBtn.isChecked(), cps=cps, voice_params = voice_params, language= self.language_input.text())
        self.worker.progress.connect(self._on_progress)
        self.worker.finished.connect(self._on_general_finished)
        self.worker.start()

    def _on_progress(self, value: int, text: str):
        if isinstance(self.loading_msg, QMessageBox):
            if value >= 0:
                if text:
                    self.loading_msg.setText(text)
            QApplication.processEvents()

    def get_voices_count(self):
        try:
            elevenlabs = dubbingElevenLabs.getInstance().elevenlabs
            response = elevenlabs.voices.search(page_size=100, sort="created_at_unix", sort_direction="asc",
                                                category="cloned")
            print(f"已获取{len(response.voices)}个声源")
            return response.total_count
        except Exception as e:
            print(f"获取声源数量失败: {e}")
            return 0


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = DubbingInterface()
    window.compress_video_upload_area.add_files([r"E:\offer\配音任务2\伤心者联盟\video\compress\compressed_伤心者同盟（英）-1.mp4", r"E:\offer\配音任务2\伤心者联盟\video\compress\compressed_伤心者同盟（英）-3.mp4"])
    # window.merge_subtitle_upload_area.add_files([r"E:\offer\配音任务2\伤心者联盟\1_2.srt"])
    window.merge_subtitle_upload_area.add_files([r"E:\offer\配音任务2\伤心者联盟\英语修改后的srt\1-cps-带角色.srt", r"E:\offer\配音任务2\伤心者联盟\英语修改后的srt\3.srt"])
    window.role_info_edit.setText("")
    window.show()
    sys.exit(app.exec_())

    #     window.role_info_edit.setText("""苏清雪：路辰的妻子，与江浩辰互相出轨
    # 路辰：苏清雪的丈夫
    # 江浩辰：童颜的丈夫，与苏清雪在外低俗娱乐
    # 童颜：江浩辰妻子
    # 吴佳佳：苏清雪闺蜜，煽风点火，推动剧情发展""")

