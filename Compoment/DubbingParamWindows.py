import os


from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QLabel,
    QPushButton, QVBoxLayout, QFormLayout, QGridLayout, QSizePolicy, QMessageBox, QProgressBar, QButtonGroup
)
from PyQt5.QtCore import  pyqtSignal
from qfluentwidgets import ComboBox, PushButton, LineEdit, ProgressBar, RadioButton, StrongBodyLabel

from Compoment.DubbingParamWindows2 import tolerate_factor, language_cps
from Compoment.PathDialog import PrettyPathDialog
from Service.datasetUtils import datasetUtils
from Service.dubbingMain.dubbingCosyVoice import dubbingCosyVoice
from Service.dubbingMain.dubbingElevenlabs2 import dubbingElevenLabs2
from Service.dubbingMain.dubbingMiniMax import dubbingMiniMax
from Service.subtitleUtils import parse_subtitle, adjust_subtitles_cps
import threading


# 所有更新界面的操作，都不应该在子进程中执行
language_codes = {
    "English": "en",
    "Chinese (Simplified)": "zh",
    "Chinese (Traditional)": "zh-TW",
    "Japanese": "jp",
    "Korean": "ko",
    "French": "fr",
    "German": "de",
    "Spanish": "es",
    "Portuguese": "pt",
    "Russian": "ru",
    "Italian": "it",
    "Dutch": "nl",
    "Polish": "pl",
    "Turkish": "tr",
    "Arabic": "ar",
    "Hindi": "hi",
    "Vietnamese": "vi",
    "Thai": "th",
    "Indonesian": "id",
    "Czech": "cs",
    "Swedish": "sv",
    "Danish": "da",
    "Finnish": "fi",
    "Greek": "el"
}

def create_expanding_widget() -> QWidget:
    widget = QWidget()
    size_policy = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
    widget.setSizePolicy(size_policy)
    return widget

"""
这个普通配音也做了区分，现在可以填写声音id
"""
class DubbingParamsWindow(QMainWindow):
    button_clicked = pyqtSignal(list)

    '''
    我需要在这里直接去调用worker进行配音工作，这样就不用阻塞了。
    问题在于，配音过程中，该窗口不能关闭。需要哪些参数呢
    1.  origin_subs_path = param[0]
        target_subs_path = param[1]
        origin_lang  = param[2]
        target_lang = param[3]
        voice_param: dict = param[4]  # 这些参数是我自己的
    2. video_file 需要视频的文件路径
    3. role_match_list
    '''
    def closeEvent(self, event):
        if not self.allow_close:
            QMessageBox.information(self, "提示", "当前不允许关闭窗口。")
            event.ignore()
        else:
            event.accept()

    def __init__(self, subtitlePaths:list, role_match_list: list, api_id: int, video_file: str, video_duration: int):
        super().__init__()
        # 1.是elevenlabs
        # 2.是minimax
        # 3.是elevenlabs端到端
        self.thread = None
        self.allow_close = True
        self.first = True
        self.video_file = video_file
        self.api_id = api_id
        self.base_height = 250

        self.role_match_list = role_match_list.copy()
        self.video_duration = video_duration

        self.subtitlePaths = subtitlePaths.copy()
        self.roleSet = list(set(role_match_list))
        self.voiceDict = datasetUtils.getInstance().query_voice_id(api_id)
        self.voiceNameList = ["自动克隆"]
        self.voiceNameList.extend(self.voiceDict.keys())
        print(self.voiceNameList)
        self.voiceDict["自动克隆"] = ""
        self.setMinimumHeight(self.base_height)
        self.setMinimumWidth(500)

        print(self.roleSet)
        print(self.subtitlePaths)
        self.setWindowTitle("配音参数设置")

        # 主体 widget 和布局
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)
        form_layout = QGridLayout()
        layout.addLayout(form_layout)
        self.v_layout = QVBoxLayout()
        layout.addLayout(self.v_layout)
        self.voice_combox_ref = []
        self.voice_edit_ref = []

        self.combo_original_subs = ComboBox()
        self.combo_target_subs = ComboBox()
        self.combo_original_lang = ComboBox()
        self.combo_target_lang = ComboBox()
        self.combo_target_subtitle_lang = ComboBox()

        self.label1 = QLabel("原始字幕:")
        self.label2 = QLabel("目标字幕:")
        self.label1.setFont(QFont("Microsoft YaHei", 11))
        self.label2.setFont(QFont("Microsoft YaHei", 11))
        self.label3 = QLabel("原始语言:")
        self.label4 = QLabel("目标语言:")
        self.label3.setFont(QFont("Microsoft YaHei", 11))
        self.label4.setFont(QFont("Microsoft YaHei", 11))
        self.label5 = QLabel("配音字幕语言:")
        self.label5.setFont(QFont("Microsoft YaHei", 11))

        # 示例选项（你可以在其他地方填充)
        self.combo_original_subs.addItems([os.path.basename(path) for path in subtitlePaths])
        self.combo_target_subs.addItems([os.path.basename(path) for path in subtitlePaths])
        self.combo_original_lang.addItems([lang for lang in language_codes.keys()])
        self.combo_target_lang.addItems([lang for lang in language_codes.keys()])
        self.combo_target_subtitle_lang.addItems(list(language_cps.keys()))


        # 添加到表单布局
        form_layout.addWidget(self.label1, 0, 0)
        form_layout.addWidget(self.combo_original_subs, 0, 1)
        form_layout.addWidget(create_expanding_widget(), 0, 2)
        form_layout.addWidget(self.label2, 1, 0)
        form_layout.addWidget(self.combo_target_subs, 1, 1)
        form_layout.addWidget(create_expanding_widget(), 1, 2)
        offset = 2

        if api_id == 3:
            form_layout.addWidget(self.label3, 2, 0)
            form_layout.addWidget(self.combo_original_lang, 2, 1)
            form_layout.addWidget(create_expanding_widget(), 2, 2)
            form_layout.addWidget(self.label4, 3, 0)
            form_layout.addWidget(self.combo_target_lang, 3, 1)
            form_layout.addWidget(create_expanding_widget(), 3, 2)
            offset = 4
        else:
            form_layout.addWidget(self.label5, 2, 0)
            form_layout.addWidget(self.combo_target_subtitle_lang, 2, 1)
            form_layout.addWidget(create_expanding_widget(), 2, 2)
            offset = 3

        if api_id != 3:
            for i, role in enumerate(self.roleSet):
                label = QLabel(role+"：")
                label.setFont(QFont("Microsoft YaHei", 11))
                combo_box = ComboBox()
                combo_box.addItems(self.voiceNameList)  # 下拉框的选项
                self.voice_combox_ref.append(combo_box)
                line_edit = LineEdit()
                line_edit.setPlaceholderText("选择声音或在此处填写声音id。")
                self.voice_edit_ref.append(line_edit)
                # form_layout.addRow(label, combo_box, line_edit)
                row = i+offset  # 计算行号
                # column = i % 2  # 计算列号
                form_layout.addWidget(label, row, 0)  # 标签放在偶数列
                form_layout.addWidget(combo_box, row, 1)  # 下拉框放在奇数列
                form_layout.addWidget(line_edit, row, 2)

        # 配音按钮
        self.dub_button = PushButton()
        self.dub_button.setText("开始配音")
        self.v_layout.addWidget(self.dub_button)
        self.dub_button.clicked.connect(self.pass_param)

        self.state_label = QLabel()
        self.processbar = QProgressBar()
        self.processbar.setRange(0, 100)
        self.processbar.setValue(0)
        self.v_layout.addWidget(self.state_label)
        self.v_layout.addWidget(self.processbar)
        self.state_label.hide()
        self.processbar.hide()
        central_widget.setLayout(layout)


    def pass_param(self):
        print("on_task_finished thread:", threading.current_thread())
        try:
            self.allow_close=False
            self.dub_button.setEnabled(False)
            self.dub_button.setText("请稍等...")
            self.processbar.setValue(0)
            self.state_label.setText("")
            if self.first:
                self.setMinimumHeight(self.height()+50)
                self.first = False
            self.state_label.show()
            self.processbar.show()
            params = {}
            if self.api_id  == 3:
                params = {"video_file":  self.video_file, "target_lang": language_codes[self.combo_target_lang.text()]}
            else:
                voice_param = {self.roleSet[i]: self.voiceDict[self.voice_combox_ref[i].currentText()] if self.voice_edit_ref[i].text() == "" else
                                self.voice_edit_ref[i].text() for i in range(len(self.voice_edit_ref))}
                params = {"origin_subs_path":  self.subtitlePaths[self.combo_original_subs.currentIndex()], "target_subs_path": self.subtitlePaths[self.combo_target_subs.currentIndex()],
                          "video_file": self.video_file, "role_match_list": self.role_match_list, "voice_param":  voice_param, "cps": language_cps[self.combo_target_subtitle_lang.currentText()]}
            print("配音参数：", params)
            self.worker = DubbingWorker(self, params, self.api_id)
            self.worker.finished.connect(self.on_task_finished)
            self.worker.progress.connect(self.update_process)
            self.worker.start()
        except Exception as e:
            print(e)
            self.on_task_finished({"error": str(e)})

    def on_task_finished(self, result: dict):
        if "error" in result:
            QMessageBox.warning(self, "配音出现错误", result["error"])
        elif "video_file" in result:
            dlg = PrettyPathDialog("配音完成", "视频存储位置：", result["video_file"], parent=self)
            dlg.exec_()

        print("on_task_finished thread:", threading.current_thread())
        self.allow_close = True
        self.dub_button.setEnabled(True)
        self.dub_button.setText("开始配音")

    def update_process(self, value: int,  text:str):
        if value!=-1:
            self.processbar.setValue(value)
        if text:
            self.state_label.setText(text)


from PyQt5.QtCore import QThread, pyqtSignal

class DubbingWorker(QThread):
    finished = pyqtSignal(dict)
    progress = pyqtSignal(int, str)

    def on_progress(self, value, msg):
        self.progress.emit(value, msg)

    def __init__(self, parent, params, api_id):
        super().__init__()
        self.params = params
        self.api_id = api_id
        self.parent = parent  # 为了调用 QMessageBox 等界面组件

    def run(self):
        from Service.dubbingMain.dubbingElevenLabs import dubbingElevenLabs
        from Service.uvrMain.separate import AudioPre

        try:
            params = self.params
            api_id = self.api_id
            result = {}
            if api_id == 3:
                ElevenLabsAPI = dubbingElevenLabs.getInstance()
                result = ElevenLabsAPI.dubbing_end_to_end(params["video_file"], params["target_lang"])
            elif api_id == 1 or api_id == 2:
                self.progress.emit(2, "解析字幕中...")
                origin_subs = parse_subtitle(params["origin_subs_path"])
                target_subs = parse_subtitle(params["target_subs_path"])
                if not origin_subs or not target_subs:
                    raise ValueError("字幕文件内容错误！")
                elif len(origin_subs) != len(target_subs) or len(params["role_match_list"])<len(origin_subs):
                    raise ValueError("字幕与角色标注不匹配！")
                else:
                    print(params["cps"])
                    self.progress.emit(3, "调整字幕语速...")
                    target_subs, adjust_list, compressed_texts, adjust_indices = adjust_subtitles_cps(target_subs, params["cps"], tolerate_factor)

                    self.progress.emit(4, "正在分离音频...")
                    voice_isolator = AudioPre.getInstance()
                    back_file, vocal_file = voice_isolator._path_audio_(params["video_file"], on_progress=self.on_progress)
                    self.progress.emit(20, "正在进行配音...")
                    if api_id == 1:
                        ElevenLabsAPI = dubbingElevenLabs2.getInstance()
                        result = ElevenLabsAPI.dubbing_high_quality(vocal_file, back_file, origin_subs, target_subs, params["role_match_list"], params["video_file"], params["voice_param"],on_progress=self.on_progress)
                    elif api_id == 2:
                        MiniMaxAPI = dubbingMiniMax.getInstance()
                        result = MiniMaxAPI.dubbing_high_quality(vocal_file, back_file, origin_subs, target_subs, params["role_match_list"], params["video_file"], params["voice_param"],on_progress=self.on_progress)
                    self.progress.emit(100, "配音完成...")
            print("结束配音")
            self.finished.emit(result)  # 任务完成，发出信号
        except  Exception as e:
            print(e)
            self.finished.emit({"error": str(e)})




"""
直接配音不涉及到原始声音，因为原始要么没声音，要么会被丢弃

"""

class DirectedDubbingParamsWindow(QMainWindow):
    button_clicked = pyqtSignal(list)
    def closeEvent(self, event):
        if not self.allow_close:
            QMessageBox.information(self, "提示", "当前不允许关闭窗口。")
            event.ignore()
        else:
            event.accept()

    def __init__(self, subtitlePaths:list, role_match_list: list, api_id: int, video_file: str, video_duration: int):
        super().__init__()
        # 1.是elevenlabs
        # 2.是minimax
        # 3.是elevenlabs端到端
        self.thread = None
        self.allow_close = True
        self.video_file = video_file
        self.api_id = api_id
        self.role_match_list = role_match_list.copy()
        self.video_duration = video_duration

        self.subtitlePaths = subtitlePaths.copy()
        self.roleSet = list(set(role_match_list))
        self.voiceDict = datasetUtils.getInstance().query_voice_id(api_id)
        self.voiceNameList = self.voiceDict.keys()
        print(self.voiceNameList)
        self.setMinimumHeight(280)
        self.setMinimumWidth(500)

        print(self.roleSet)
        print(self.subtitlePaths)
        self.setWindowTitle("配音参数设置")

        # 主体 widget 和布局
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)
        form_layout = QGridLayout()
        layout.addLayout(form_layout)
        self.v_layout = QVBoxLayout()
        layout.addLayout(self.v_layout)
        self.voice_combox_ref = []
        self.voice_edit_ref = []

        self.combo_target_subs = ComboBox()
        self.label2 = StrongBodyLabel("目标字幕:")
        # self.label2.setFont(QFont("Microsoft YaHei", 11))

        # 示例选项（你可以在其他地方填充)
        self.combo_target_subs.addItems([os.path.basename(path) for path in subtitlePaths])

        # 添加到表单布局
        form_layout.addWidget(self.label2, 0, 0)
        form_layout.addWidget(self.combo_target_subs, 0, 1)
        form_layout.addWidget(create_expanding_widget(), 0, 2)
        offset = 1

        for i, role in enumerate(self.roleSet):
            label = StrongBodyLabel(role+"：")
            # label.setFont(QFont("Microsoft YaHei", 11))
            combo_box = ComboBox()
            combo_box.addItems(self.voiceNameList)  # 下拉框的选项
            self.voice_combox_ref.append(combo_box)
            line_edit = LineEdit()
            line_edit.setPlaceholderText("选择声音或在此处填写声音id。")
            self.voice_edit_ref.append(line_edit)
            # form_layout.addRow(label, combo_box, line_edit)
            row = i+offset  # 计算行号
            # column = i % 2  # 计算列号
            form_layout.addWidget(label, row, 0)  # 标签放在偶数列
            form_layout.addWidget(combo_box, row, 1)  # 下拉框放在奇数列
            form_layout.addWidget(line_edit, row, 2)
            offset2 = row

        self.radio_dict = {
            "完全保留背景音": 0,
            "去除背景音人声": 1
        }

        button2 = RadioButton(list(self.radio_dict.keys())[0])
        button3 = RadioButton(list(self.radio_dict.keys())[1])
        button2.setChecked(True)
        self.radio_widget = QWidget()
        # 将单选按钮添加到互斥的按钮组
        self.buttonGroup = QButtonGroup(self.radio_widget)
        self.buttonGroup.addButton(button2)
        self.buttonGroup.addButton(button3)
        self.v_layout.addWidget(button2)
        self.v_layout.addWidget(button3)


        # 配音按钮
        self.dub_button = PushButton()
        self.dub_button.setText("开始配音")
        self.v_layout.addWidget(self.dub_button)
        self.dub_button.clicked.connect(self.pass_param)

        self.state_label = QLabel()
        self.processbar = QProgressBar()
        self.processbar.setRange(0, 100)
        self.processbar.setValue(0)
        self.v_layout.addWidget(self.state_label)
        self.v_layout.addWidget(self.processbar)
        self.state_label.hide()
        self.processbar.hide()
        central_widget.setLayout(layout)


    def pass_param(self):
        print("on_task_finished thread:", threading.current_thread())
        try:
            self.allow_close=False
            self.dub_button.setEnabled(False)
            self.dub_button.setText("请稍等...")
            self.processbar.setValue(0)
            self.state_label.setText("")
            self.state_label.show()
            self.setMinimumHeight(self.height() + 50)
            self.processbar.show()
            params = {}
            print(self.radio_dict[self.buttonGroup.checkedButton().text()])
            voice_param = {self.roleSet[i]: self.voiceDict[self.voice_combox_ref[i].currentText()] if self.voice_edit_ref[i].text() == "" else
                            self.voice_edit_ref[i].text() for i in range(len(self.voice_edit_ref))}
            for item in voice_param.values():
                if not item:
                    QMessageBox.warning(self, "警告", "请填写声音id！")
                    self.on_task_finished({})
                    return
            params = {"radio_id": self.radio_dict[self.buttonGroup.checkedButton().text()] ,"target_subs_path": self.subtitlePaths[self.combo_target_subs.currentIndex()], "video_file": self.video_file,
                      "role_match_list": self.role_match_list, "voice_param": voice_param}
            print("配音参数：", params)
            self.worker = DirectedDubbingWorker(self, params)
            self.worker.finished.connect(self.on_task_finished)
            self.worker.progress.connect(self.update_process)
            self.worker.start()
        except Exception as e:
            print(e)
            self.on_task_finished({"error": str(e)})

    def on_task_finished(self, result: dict):
        if "error" in result:
            QMessageBox.warning(self, "配音出现错误", result["error"])
        elif "video_file" in result:
            dlg = PrettyPathDialog("配音完成", "视频存储位置：", result["video_file"], parent=self)
            dlg.exec_()

        print("on_task_finished thread:", threading.current_thread())
        self.allow_close = True
        self.dub_button.setEnabled(True)
        self.dub_button.setText("开始配音")

    def update_process(self, value: int,  text:str):
        if value!=-1:
            self.processbar.setValue(value)
        if text:
            self.state_label.setText(text)


class DirectedDubbingWorker(QThread):
    finished = pyqtSignal(dict)
    progress = pyqtSignal(int, str)

    def on_progress(self, value, msg):
        self.progress.emit(value, msg)

    def __init__(self, parent, params):
        super().__init__()
        self.params = params
        self.parent = parent  # 为了调用 QMessageBox 等界面组件

    def run(self):
        from Service.dubbingMain.dubbingElevenLabs import dubbingElevenLabs

        try:
            result = {}
            self.progress.emit(2, "解析字幕中...")
            target_subs = parse_subtitle(self.params["target_subs_path"])
            if not target_subs:
                QMessageBox.warning(self.parent, "错误", "字幕文件内容错误！")
            elif len(self.params["role_match_list"]) < len(target_subs):
                QMessageBox.warning(self.parent, "警告", "字幕与角色标注不匹配！")
            else:
                self.progress.emit(5, "正在进行配音...")
                ElevenLabsAPI = dubbingElevenLabs.getInstance()
                result = ElevenLabsAPI.directed_dubbing(target_subs, self.params["role_match_list"], self.params["video_file"], self.params["voice_param"], on_progress=self.on_progress)
                self.progress.emit(100, "配音完成...")

            print("结束配音")
            self.finished.emit(result)  # 任务完成，发出信号
        except Exception as e:
            print(e)
            self.finished.emit({"error": str(e)})




"""
基于cosyvoice的配音
"""


cosy_language_codes = {
    "English": "en",
    "Chinese (Simplified)": "zh",
    "Japanese": "jp",
    "Korean": "ko",
}

class CosyDubbingParamsWindow(QMainWindow):
    button_clicked = pyqtSignal(list)

    def closeEvent(self, event):
        if not self.allow_close:
            QMessageBox.information(self, "提示", "当前不允许关闭窗口。")
            event.ignore()
        else:
            event.accept()

    def __init__(self, subtitlePaths:list, role_match_list: list, api_id: int, video_file: str, video_duration: int):
        super().__init__()
        self.thread = None
        self.allow_close = True
        self.video_file = video_file
        self.api_id = api_id
        self.role_match_list = role_match_list.copy()
        self.video_duration = video_duration

        self.subtitlePaths = subtitlePaths.copy()
        self.roleSet = list(set(role_match_list))

        self.setMinimumHeight(280)
        self.setMinimumWidth(500)

        print(self.roleSet)
        print(self.subtitlePaths)
        self.setWindowTitle("配音参数设置")

        # 主体 widget 和布局
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)
        form_layout = QGridLayout()
        layout.addLayout(form_layout)
        self.v_layout = QVBoxLayout()
        layout.addLayout(self.v_layout)
        self.voice_combox_ref = []
        self.voice_edit_ref = []

        self.combo_original_subs = ComboBox()
        self.combo_target_subs = ComboBox()
        self.combo_original_lang = ComboBox()
        self.combo_target_lang = ComboBox()
        self.label1 = QLabel("原始字幕:")
        self.label2 = QLabel("目标字幕:")
        self.label1.setFont(QFont("Microsoft YaHei", 11))
        self.label2.setFont(QFont("Microsoft YaHei", 11))
        self.label3 = QLabel("原始语言:")
        self.label4 = QLabel("目标语言:")
        self.label3.setFont(QFont("Microsoft YaHei", 11))
        self.label4.setFont(QFont("Microsoft YaHei", 11))

        # 添加下拉选择框数据
        self.combo_original_subs.addItems([os.path.basename(path) for path in subtitlePaths])
        self.combo_target_subs.addItems([os.path.basename(path) for path in subtitlePaths])
        self.combo_original_lang.addItems([lang for lang in cosy_language_codes.keys()])
        self.combo_target_lang.addItems([lang for lang in cosy_language_codes.keys()])

        # 添加到表单布局
        form_layout.addWidget(self.label1, 0, 0)
        form_layout.addWidget(self.combo_original_subs, 0, 1)
        form_layout.addWidget(create_expanding_widget(), 0, 2)
        form_layout.addWidget(self.label2, 1, 0)
        form_layout.addWidget(self.combo_target_subs, 1, 1)
        form_layout.addWidget(create_expanding_widget(), 1, 2)
        form_layout.addWidget(self.label4, 2, 0)
        form_layout.addWidget(self.combo_target_lang, 2, 1)
        form_layout.addWidget(create_expanding_widget(), 2, 2)
        # form_layout.addWidget(self.label4, 3, 0)
        # form_layout.addWidget(self.combo_target_lang, 3, 1)
        # form_layout.addWidget(create_expanding_widget(), 3, 2)
        # offset = 4

        # 配音按钮
        self.dub_button = PushButton()
        self.dub_button.setText("开始配音")
        self.v_layout.addWidget(self.dub_button)
        self.dub_button.clicked.connect(self.pass_param)

        self.state_label = QLabel()
        self.processbar = QProgressBar()
        self.processbar.setRange(0, 100)
        self.processbar.setValue(0)
        self.v_layout.addWidget(self.state_label)
        self.v_layout.addWidget(self.processbar)
        self.state_label.hide()
        self.processbar.hide()
        central_widget.setLayout(layout)


    def pass_param(self):
        print("on_task_finished thread:", threading.current_thread())
        try:
            self.allow_close=False
            self.dub_button.setEnabled(False)
            self.dub_button.setText("请稍等...")
            self.processbar.setValue(0)
            self.state_label.setText("")
            self.state_label.show()
            self.setMinimumHeight(self.height() + 50)
            self.processbar.show()
            params = {}
            params = {"origin_subs_path":  self.subtitlePaths[self.combo_original_subs.currentIndex()], "target_subs_path": self.subtitlePaths[self.combo_target_subs.currentIndex()],
                          "video_file": self.video_file, "role_match_list": self.role_match_list, "target_lang": cosy_language_codes[self.combo_target_lang.text()]}

            print("配音参数：", params)
            self.worker = CosyDubbingWorker(self, params, self.api_id)
            self.worker.finished.connect(self.on_task_finished)
            self.worker.progress.connect(self.update_process)
            self.worker.start()
        except Exception as e:
            print(e)
            self.on_task_finished({"error": str(e)})

    def on_task_finished(self, result: dict):
        if "error" in result:
            QMessageBox.warning(self, "配音出现错误", result["error"])
        elif "video_file" in result:
            dlg = PrettyPathDialog("配音完成", "视频存储位置：", result["video_file"], parent=self)
            dlg.exec_()

        print("on_task_finished thread:", threading.current_thread())
        self.allow_close = True
        self.dub_button.setEnabled(True)
        self.dub_button.setText("开始配音")

    def update_process(self, value: int,  text:str):
        if value!=-1:
            self.processbar.setValue(value)
        if text:
            self.state_label.setText(text)


from PyQt5.QtCore import QThread, pyqtSignal

class CosyDubbingWorker(QThread):
    finished = pyqtSignal(dict)
    progress = pyqtSignal(int, str)

    def on_progress(self, value, msg):
        self.progress.emit(value, msg)

    def __init__(self, parent, params, api_id):
        super().__init__()
        self.params = params
        self.api_id = api_id
        self.parent = parent  # 为了调用 QMessageBox 等界面组件

    def run(self):
        from Service.dubbingMain.dubbingElevenLabs import dubbingElevenLabs
        from Service.uvrMain.separate import AudioPre

        try:
            params = self.params
            api_id = self.api_id
            result = {}
            self.progress.emit(2, "解析字幕中...")
            origin_subs = parse_subtitle(params["origin_subs_path"])
            target_subs = parse_subtitle(params["target_subs_path"])

            if not origin_subs or not target_subs:
                QMessageBox.warning(self.parent, "错误", "字幕文件内容错误！")
            elif len(origin_subs) != len(target_subs) or len(params["role_match_list"])<len(origin_subs):
                QMessageBox.warning(self.parent, "警告", "字幕与角色标注不匹配！")
            else:
                self.progress.emit(4, "正在分离音频...")
                voice_isolator = AudioPre.getInstance()
                back_file, vocal_file = voice_isolator._path_audio_(params["video_file"], on_progress=self.on_progress)
                self.progress.emit(20, "正在进行配音...")
                # ElevenLabsAPI = dubbingElevenLabs.getInstance()
                # result = ElevenLabsAPI.dubbing_high_quality(vocal_file, back_file, origin_subs, target_subs,params["role_match_list"], params["video_file"], params["voice_param"],on_progress=self.on_progress)
                
                
                CosyVoiceAPI = dubbingCosyVoice.getInstance()
                result = CosyVoiceAPI.dubbing_single_clone_high_quality(vocal_file, back_file, origin_subs, target_subs, params["role_match_list"], params["video_file"], params["target_lang"],on_progress=self.on_progress)
                self.progress.emit(100, "配音完成...")
            print("结束配音")
            self.finished.emit(result)  # 任务完成，发出信号
        except  Exception as e:
            print(e)
            self.finished.emit({"error": str(e)})







