from PyQt5.QtCore import Qt, QThread, QTimer
from PyQt5.QtGui import QBrush, QColor
from PyQt5.QtWidgets import QWidget, QFileDialog, QFrame, QVBoxLayout, \
    QSizePolicy, QLabel
import os

from qfluentwidgets import Dialog, StrongBodyLabel

from Compoment.HiddenScrollArea import HiddenScrollArea
from Compoment.HistoryCard import HistoryCardItem
from Compoment.PathDialog import PrettyPathDialog
from UI.Ui_voiceChanger2 import Ui_VoiceChanger
from functools import lru_cache
from importlib import import_module


@lru_cache(maxsize=None)
def _load_module(path: str):
    return import_module(path)


def _get_attr(module_path: str, attr_name: str):
    return getattr(_load_module(module_path), attr_name)


class VoiceChangerInterface(Ui_VoiceChanger, QFrame):

    def __init__(self, parent=None):
        super().__init__(parent)
        print("bbb")
        self.setupUi(self)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # self.voice_paths = []

        # 设置为可点击，可拖拽
        self.setAcceptDrops(True)
        self.uploadFrame.setCursor(Qt.PointingHandCursor)  # 显示为可点击
        self.uploadFrame.mousePressEvent = self.upload_files

        # 设置隐藏的滑动窗，用来显示上传的文件
        self.pathScroll = HiddenScrollArea()
        self.verticalLayout_2.addWidget(self.pathScroll)
        self.clearButton.clicked.connect(self.pathScroll.clear_files)
        # 设置滑动条
        self.stabilitySlider.setMaximum(100)
        self.similaritySlider.setMaximum(100)
        self.exaggerationSlider.setMaximum(100)
        self.stabilitySlider.valueChanged.connect(lambda value: self.on_slider_move(value, self.StabilityValue))
        self.similaritySlider.valueChanged.connect(lambda value: self.on_slider_move(value, self.SimilarityValue))
        self.exaggerationSlider.valueChanged.connect(lambda value: self.on_slider_move(value, self.ExaggerationValue))
        self.stabilitySlider.setProperty("value", 50)
        self.similaritySlider.setProperty("value", 70)
        self.exaggerationSlider.setProperty("value", 0)
        # 参数和生成按钮设置
        self.voiceDict = {}
        self.voiceSelector.clear()
        self.voiceSelector.addItem("加载中...")
        self.voiceSelector.setEnabled(False)
        QTimer.singleShot(0, self._hydrate_voice_selector)
        self.AIModelSet = ['eleven_multilingual_sts_v2']
        for model in self.AIModelSet:
            self.modelSelector.addItem(model)
        self.generateButton.clicked.connect(self.generate_voice)
        self.resetButton.clicked.connect(self.reset_slider)
        # 历史滚动记录设置
        self.historyState = False
        self.dirs = []
        self.tabWidget.currentChanged.connect(self.on_tab_changed)
        self.setup_unfinished_ui()

    def _hydrate_voice_selector(self):
        datasetUtils = _get_attr("Service.datasetUtils", "datasetUtils")
        try:
            voice_dict = datasetUtils.getInstance().query_voice_id(1)
        except Exception as exc:
            print(f"加载声音列表失败: {exc}")
            self.voiceSelector.clear()
            self.voiceSelector.addItem("加载失败")
            self.voiceSelector.setEnabled(True)
            return
        self.voiceDict = voice_dict or {}
        self.voiceSelector.clear()
        for name in self.voiceDict.keys():
            self.voiceSelector.addItem(name)
        self.voiceSelector.setEnabled(True)

    def reset_slider(self):
        self.stabilitySlider.setProperty("value", 50)
        self.similaritySlider.setProperty("value", 70)
        self.exaggerationSlider.setProperty("value", 0)

    def on_tab_changed(self,  index):
        print(index)
        if index==1 and not self.historyState:
            self.historyState = True
            self.thread = QThread()
            self.thread.started.connect(lambda: self.incremental_update_scroll_conetnt())
            self.thread.start()


    #         label = StrongBodyLabel("文件夹："+dir.split("\\")[-1])
    #         self.historyLayout.addWidget(label)
    #         audio_paths = self.get_audio_files_in_folder(dir)
    #         print(audio_paths)
    #         for audio_path in audio_paths:
    #             print(audio_path)
    #             card = HistoryCardItem(os.path.basename(audio_path), audio_path)
    #             self.historyLayout.addWidget(card)

    # 增量更新，类比于vue的diff虚拟dom
    def incremental_update_scroll_conetnt(self):
        datasetUtils = _get_attr("Service.datasetUtils", "datasetUtils")
        dirs = datasetUtils.getInstance().query_changer_audio_dir()
        for dir in dirs:
            if dir not in self.dirs:
                self.dirs.append(dir)
                print(dir)
                label = StrongBodyLabel("文件夹：" + dir.split("\\")[-1])
                self.historyLayout.insertWidget(0,  label)
                audio_paths = self.get_audio_files_in_folder(dir)
                print(audio_paths)
                i = 1
                for audio_path in audio_paths:
                    print(audio_path)
                    card = HistoryCardItem(os.path.basename(audio_path), audio_path)
                    # self.historyLayout.addWidget(card)
                    self.historyLayout.insertWidget(i, card)
                    i+=1

    def setup_unfinished_ui(self):
        self.tabWidget.setCurrentIndex(0)

        self.HistoryScroll.setWidgetResizable(True)  # 允许内部控件自适应
        self.SubListContainer = QWidget()
        self.SubListContainer.setObjectName("HistoryCardContainer")
        # self.container.setFixedWidth(280)  # 宽度略小于滚动区域以避免水平滚动条
        self.historyLayout = QVBoxLayout()
        self.historyLayout.setAlignment(Qt.AlignTop)  # 内容顶部对齐
        self.SubListContainer.setLayout(self.historyLayout)
        # 将容器添加到滚动区域
        self.HistoryScroll.setWidget(self.SubListContainer)
        self.HistoryScroll.setStyleSheet(
            """ QScrollArea{ background: transparent;border: None; } #HistoryCardContainer{ background: transparent; } """)



    def generate_voice(self):
        VoiceChangerWorker = _get_attr("ThreadWorker.VoiceChangerWorker", "VoiceChangerWorker")
        voice_id =  self.voiceLineEdit.text()
        if not self.pathScroll.voice_paths:
            w = Dialog("警告", "请上传音频文件", self)
            w.exec()
            return
        get_text = self.voiceSelector.text if hasattr(self.voiceSelector, "text") else self.voiceSelector.currentText
        selector_voice = get_text()
        if not voice_id and not selector_voice:
            w = Dialog("警告", "请选择声音或输入声音ID", self)
            w.exec()
            return
        if not voice_id:
            if not self.voiceDict or selector_voice not in self.voiceDict:
                w = Dialog("警告", "声音列表尚未加载完成", self)
                w.exec()
                return
        resolved_voice_id = voice_id if voice_id else self.voiceDict[selector_voice]
        params = {"voice_files": self.pathScroll.voice_paths, "voice_id": resolved_voice_id,
                  "model_id": self.modelSelector.text(), "stability": self.stabilitySlider.value() / 100, "similarity": self.similaritySlider.value() / 100,
                  "exaggeration": self.exaggerationSlider.value() / 100,
                  "remove_background_noise": self.removeBgNoiseCheck.isChecked(),
                  "use_speaker_boost": self.speakerBoostCheck.isChecked()}
        self.generateButton.setEnabled(False)
        self.generateButton.setText("请稍等...")
        # 是否根据角色提示列表进行标记
        self.worker = VoiceChangerWorker(params)
        self.worker.finished.connect(self.on_task_finished)
        self.worker.item_finished.connect(self.modify_item_state)
        self.worker.start()

    def modify_item_state(self, index):
        print(index)
        item = self.pathScroll.list_widget.item(index)
        # item.setText(item.text()+"已完成")
        item.setBackground(QBrush(QColor(153, 212, 144)))

    def on_task_finished(self, result):
        dlg = PrettyPathDialog("声线转换完成", "音频存储位置：", result["result_path"], parent=self)
        dlg.exec_()
        self.pathScroll.clear_files()
        for path in result["unfinished_files"]:
            self.pathScroll.add_item(path)
        self.generateButton.setText("生成声音")
        self.generateButton.setEnabled(True)
        self.thread = QThread()
        self.thread.started.connect(lambda: self.incremental_update_scroll_conetnt())
        self.thread.start()

    def on_slider_move(self, value, label: QLabel):
        # print(value)
        label.setText(f"{value} / 100")

    def add_voice_list(self, paths):
        for path in paths:
            self.pathScroll.add_item(path)

    def upload_files(self, event):
        print("选择音频文件")
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Audio Files",
            "",
            "Audio Files (*.mp3 *.wav *.flac *.m4a *.ogg);;All Files (*)"
        )
        self.add_voice_list(files)
        # self.voice_paths.extend(files)


    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            print("enter")
            self.uploadFrame.setStyleSheet("""QFrame#uploadFrame{
                    background-color: #F8F8F8;
                    border: 2px dashed #a1bbd7;
                    border-radius: 12px;
            }""")
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        self.uploadFrame.setStyleSheet("""QFrame#uploadFrame{
                        background-color: #FFFFFF;
                        border: 2px dashed #CED4DA;
                        border-radius: 12px;
                }""")

    def dropEvent(self, event):
        pos = event.pos()
        self.uploadFrame.setStyleSheet("""QFrame#uploadFrame{
                background-color: #FFFFFF;
                border: 2px dashed #CED4DA;
                border-radius: 12px;
        }""")
        if not self.uploadFrame.geometry().contains(pos):
            print("Drop outside uploadFrame, ignored.")
            return

        urls = event.mimeData().urls()
        paths = [url.toLocalFile() for url in urls]
        print(paths)

        audio_paths = []
        for path in paths:
            if os.path.isdir(path):
                audio_paths.extend(self.get_audio_files_in_folder(path))
            elif self.is_audio_file(path):
                audio_paths.append(path)
        self.add_voice_list(audio_paths)
        # self.voice_paths.extend(audio_paths)

    def get_audio_files_in_folder(self, folder):
        audio_exts = ('.mp3', '.wav', '.flac', '.m4a', '.ogg')
        return [
            os.path.join(root, file)
            for root, _, files in os.walk(folder)
            for file in files
            if file.lower().endswith(audio_exts)
        ]

    def is_audio_file(self, path):
        return path.lower().endswith(('.mp3', '.wav', '.flac', '.m4a', '.ogg'))

