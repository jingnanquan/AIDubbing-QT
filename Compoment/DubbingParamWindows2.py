import datetime
import os
import sys
import traceback

import numpy as np
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QLabel, QVBoxLayout, QGridLayout, QSizePolicy, QMessageBox, QProgressBar,
    QApplication, QScrollArea
)
from PyQt5.QtCore import Qt, pyqtSignal, QUrl
from qfluentwidgets import ComboBox, PushButton, LineEdit
from qfluentwidgets.multimedia import SimpleMediaPlayBar

from Compoment.FolderSelector import SingleFolderSelector
from Compoment.HistoryCard import VoiceCardItem
from Compoment.PathDialog import PrettyPathDialog
from Config import resource_path, RESULT_OUTPUT_FOLDER, tolerate_factor, AUDIO_SEPARATION_FOLDER
from Service.datasetUtils import datasetUtils
from Service.dubbingMain.dubbingElevenLabs import dubbingElevenLabs
from Service.dubbingMain.dubbingElevenlabs2 import dubbingElevenLabs2
from Service.dubbingMain.dubbingElevenlabs3 import dubbingElevenLabs3
from Service.dubbingMain.llmAPI import LLMAPI
from Service.generalUtils import check_close_permission, time_str_to_ms, mixed_sort_key
from Service.subtitleUtils import parse_subtitle, adjust_subtitles_cps, parse_subtitle_uncertain
import threading
import soundfile as sf

from Service.videoUtils import get_audio_np_from_video

# 需要区分欧美和亚洲
language_region = {
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

language_cps = {
    "英语": 23,
    "汉语": 15,
    "日语": 17,
    "韩语": 16,
    "法语": 21,
    "葡萄牙语": 20,
    "俄罗斯语": 18,
    "越南语": 22,
    "泰语": 22,
    "印尼语": 18
}

language_code = {
    "英语": "en",
    "汉语": "zh",
    "日语": "ja",
    "韩语": "ko",
    "法语": "fr",
    "葡萄牙语": "pt",
    "俄罗斯语": "ru",
    "越南语": "vi",
    "泰语": "th",
    "印尼语": "id"
}
# 幼年、少年、青中年、中老年、老年   os.path.join(resource_path, "prepared_voices","default.mp3"
prepared_voices = {
    # "默认声音":                   ["uju3wxzG5OhpWcoi3SMy", os.path.join(resource_path, "prepared_voices","default.mp3")],
    "小孩-女-Daniela":            [  "tTdCI0IDTgFa2iLQiWu4", os.path.join(resource_path, "prepared_voices","小孩-女-Daniela.mp3")],
    "青年-女-Lily-Wolff":        [  "qBDvhofpxp92JgXJxDjB", os.path.join(resource_path, "prepared_voices","青年-女-Lily-Wolff.mp3")],
    "青年-女-Alexandra":         [  "kdmDKE6EkgrWrrykO9Qt", os.path.join(resource_path, "prepared_voices","青年-女-Alexandra.mp3")],
    "青年-女-Ivanan":            [  "4NejU5DwQjevnR6mh3mb", os.path.join(resource_path, "prepared_voices","青年-女-Ivanan.mp3")],
    "青年-女-Hope":              [  "tnSpp4vdxKPjI9w0GnoV", os.path.join(resource_path, "prepared_voices","青年-女-Hope.mp3")],
    "青年-女-Tanya":             [  "DusxpIechtn2D8hID1Jy", os.path.join(resource_path, "prepared_voices","青年-女-Tanya.mp3")],
    "青年-男-Hey Its Brad":      [  "f5HLTX707KIM4SzJYzSz", os.path.join(resource_path, "prepared_voices","青年-男-HeyItsBrad.mp3")],
    "青年-男-Mark":              [  "UgBBYS2sOqTuMpoF3BR0", os.path.join(resource_path, "prepared_voices","青年-男-Mark.mp3")],
    "青年-男-Patrack":           [  "IoYPiP0wwoQzmraBbiju", os.path.join(resource_path, "prepared_voices","青年-男-Patrack.mp3")],
    "青年-男-Viraj":             [  "bajNon13EdhNMndG3z05", os.path.join(resource_path, "prepared_voices","青年-男-Viraj.mp3")],
    "青年-男-Asher":             [  "tCI2WpOKOENuucvQrEeR", os.path.join(resource_path, "prepared_voices","青年-男-Asher.mp3")],
    "中年-女-Alexis Lancaster":  [  "O4fnkotIypvedJqBp4yb", os.path.join(resource_path, "prepared_voices","中年-女-AlexisLancaster.mp3")],
    "中年-女-Kylee_M":           [  "pcKdPWtbF6bM9o7NHjCI", os.path.join(resource_path, "prepared_voices","中年-女-Kylee_M.mp3")],
    "中年-女-Beatrice":          [  "kkPJzQOWz2Oz9cUaEaQd", os.path.join(resource_path, "prepared_voices","中年-女-Beatrice.mp3")],
    "中年-男-Peter":             [  "ZthjuvLPty3kTMaNKVKb", os.path.join(resource_path, "prepared_voices","中年-男-Peter.mp3")],
    "中年-男-Professor Bill":    [  "lnieQLGTodpbhjpZtg1k", os.path.join(resource_path, "prepared_voices","中年-男-ProfessorBill.mp3")],
    "中年-男-Shrey":             [  "x3gYeuNB0kLLYxOZsaSh", os.path.join(resource_path, "prepared_voices","中年-男-Shrey.mp3")],
    "老年-女-Leesie":             [   "FOBaORWwYmHBGhidTqtx", os.path.join(resource_path, "prepared_voices","老年-女-Leesie.mp3")],
    "老年-女-Fantine Art":        [   "LBy8sNrEohVcRSkF8TAd", os.path.join(resource_path, "prepared_voices","老年-女-FantineArt.mp3")],
    "老年-男-Oxley":              [   "NOpBlnGInO9m6vDvFkFC", os.path.join(resource_path, "prepared_voices","老年-男-Oxley.mp3")],
    "老年-男-Ralf Eisend":        [   "A9evEp8yGjv4c3WsIKuY", os.path.join(resource_path, "prepared_voices","老年-男-RalfEisend.mp3")],
}


spare_voices = {
    "自动克隆":  ["", ""],
    "不配音": ["",""],
    "默认声音":  ["uju3wxzG5OhpWcoi3SMy", os.path.join(resource_path, "prepared_voices", "default.mp3")],
}



def create_expanding_widget() -> QWidget:
    widget = QWidget()
    size_policy = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
    widget.setSizePolicy(size_policy)
    return widget

class VoiceSelectorWindow(QMainWindow):
    return_signal = pyqtSignal(str)

    def __init__(self, voices: dict = prepared_voices):
        super().__init__()

        self.setWindowTitle("声音列表")
        self.setMinimumWidth(750)
        self.setMinimumHeight(600)
        self.voices_dict = voices
        self.initUI()

    def initUI(self):
        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # 创建主布局
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10,10,10,10)


        # 创建并配置QScrollArea，命名为VoiceScroll
        self.VoiceScroll = QScrollArea()
        self.VoiceScroll.setWidgetResizable(True)  # 允许内容自动调整大小
        self.VoiceScroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.VoiceScroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.HistoryCardContainer = QWidget()

        self.HistoryCardContainer.setObjectName("HistoryCardContainer")

        self.VoiceLayout = QGridLayout()
        self.VoiceLayout.setAlignment(Qt.AlignTop)  # 内容顶部对齐
        self.VoiceLayout.setSpacing(10)
        self.VoiceLayout.setContentsMargins(5,5,9,5)

        self.audio_bar = SimpleMediaPlayBar()
        self.HistoryCardContainer.setLayout(self.VoiceLayout)
        # 将容器添加到滚动区域
        self.VoiceScroll.setWidget(self.HistoryCardContainer)
        self.VoiceScroll.setStyleSheet(
            """ QScrollArea{ background: transparent;border: None; } #HistoryCardContainer{ background: transparent; } """)

        main_layout.addWidget(self.VoiceScroll)
        main_layout.addWidget(self.audio_bar)
        central_widget.setLayout(main_layout)

        # 计算行和列的位置
        row = 0
        col = 0
        for key, value in self.voices_dict.items():
            print(key, value)
            card = VoiceCardItem(key, value[1], value[0])
            card.btn_signal.connect(self.return_voice)
            card.self_click.connect(self.set_voice_url)
            # 添加到网格布局中
            self.VoiceLayout.addWidget(card, row, col)

            # 更新列和行位置
            col += 1
            if col >= 2:  # 每行两个元素
                col = 0
                row += 1

        self.adjust_width()

    def return_voice(self, voice_name):
        self.hide()
        self.return_signal.emit(voice_name)

    def set_voice_url(self, file_path, voice_id):

        print(voice_id, file_path)
        if not file_path and voice_id:
            try:
                file_path = dubbingElevenLabs2.getInstance().connect.elevenlabs.voices.get(voice_id=voice_id).preview_url
            except Exception as e:
                print(f"获取声音失败: {e}")
                file_path = os.path.join(resource_path, "prepared_voices", "default.mp3")
        if not file_path:
            file_path = os.path.join(resource_path, "prepared_voices", "default.mp3")
        print(file_path)
        if file_path.startswith("http"):
            self.audio_bar.player.setSource(QUrl(file_path))
        else:
            self.audio_bar.player.setSource(QUrl.fromLocalFile(file_path))
        self.audio_bar.play()

    def adjust_width(self):
        self.setMinimumWidth(self.HistoryCardContainer.sizeHint().width()+80)


"""
这个普通配音也做了区分，现在可以填写声音id
"""
class ElevenDubbingParamsWindow(QMainWindow):
    button_clicked = pyqtSignal(list)

    def closeEvent(self, event):
        if not self.allow_close:
            QMessageBox.information(self, "提示", "当前不允许关闭窗口。")
            event.ignore()
        else:
            event.accept()

    def select_voice(self):
        self.activate_button = self.sender()
        assert isinstance(self.activate_button, ComboBox)
        print(self.activate_button)
        print(self.activate_button.text())
        if self.voice_selector_window is not None and isinstance(self.voice_selector_window, VoiceSelectorWindow):
            self.voice_selector_window.show()
        else:
            self.voice_selector_window = VoiceSelectorWindow(self.voiceDict)
            self.voice_selector_window.setWindowModality(Qt.ApplicationModal)
            self.voice_selector_window.show()
            self.voice_selector_window.return_signal.connect(self.set_combobox_text)

    def set_combobox_text(self, voice_name):
        self.activate_button.setText(voice_name)


    def __init__(self, subtitle_path: str, role_match_list: list):
        super().__init__()
        from Service.dubbingMain.dubbingElevenlabs2 import dubbingElevenLabs2

        self.thread = None
        self.allow_close = True
        self.first = True
        self.base_height = 250
        self.activate_button = None
        self.voice_selector_window = None

        self.role_match_list = role_match_list.copy()
        self.roleSet = sorted(list(set(role_match_list)))
        self.subtitlePaths = [subtitle_path]

        voiceDict1 = datasetUtils.getInstance().query_voice_id(1)
        # voiceDict2 = dubbingElevenLabs2.getInstance().get_http_mp3(voiceDict1)   # 在这里获取太慢了，应当随用随取
        voiceDict2 = {}
        for key, value in voiceDict1.items():
            # os.path.join(resource_path, "prepared_voices", "default.mp3")
            voiceDict2[key] = [value, ""]   # 这里置为空
        self.voiceDict = spare_voices | voiceDict2 | prepared_voices

        print(self.voiceDict)
        self.voiceNameList = list(self.voiceDict.keys())
        print(self.voiceNameList)
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
        self.combo_target_lang = ComboBox()
        self.label1 = QLabel("原始字幕:")
        self.label2 = QLabel("目标字幕:")
        self.label1.setFont(QFont("Microsoft YaHei", 11))
        self.label2.setFont(QFont("Microsoft YaHei", 11))
        self.label3 = QLabel("字幕语言:")
        self.label3.setFont(QFont("Microsoft YaHei", 11))


        # 示例选项（你可以在其他地方填充)
        self.combo_target_subs.addItems([os.path.basename(path) for path in self.subtitlePaths])
        self.combo_target_lang.addItems(list(language_cps.keys()))

        # 添加到表单布局
        form_layout.addWidget(self.label2, 1, 0)
        form_layout.addWidget(self.combo_target_subs, 1, 1)
        form_layout.addWidget(create_expanding_widget(), 1, 2)
        form_layout.addWidget(self.label3, 2, 0)
        form_layout.addWidget(self.combo_target_lang, 2, 1)
        form_layout.addWidget(create_expanding_widget(), 2, 2)
        offset = 3

        for i, role in enumerate(self.roleSet):
            label = QLabel(role+"：")
            label.setFont(QFont("Microsoft YaHei", 11))
            combo_box = ComboBox()
            combo_box.setText(self.voiceNameList[0])
            combo_box.clicked.connect(self.select_voice)
            self.voice_combox_ref.append(combo_box)
            line_edit = LineEdit()
            line_edit.setPlaceholderText("选择声音或在此处填写声音id。")
            self.voice_edit_ref.append(line_edit)
            row = i+offset  # 计算行号
            form_layout.addWidget(label, row, 0)  # 标签放在偶数列
            form_layout.addWidget(combo_box, row, 1)  # 下拉框放在奇数列
            form_layout.addWidget(line_edit, row, 2)

        # self.voice_combox_ref[0].view().viewport().installEventFilter(self)
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
            voice_param = {self.roleSet[i]: self.voiceDict[self.voice_combox_ref[i].text()][0] if self.voice_edit_ref[i].text() == "" else
                            self.voice_edit_ref[i].text() for i in range(len(self.voice_edit_ref))}
            params = {"target_subs_path": self.subtitlePaths[self.combo_target_subs.currentIndex()],
                      "role_match_list": self.role_match_list, "voice_param":  voice_param, "cps": language_cps[self.combo_target_lang.currentText()]}
            print("配音参数：", params)
            self.worker = ElevenDubbingWorker(self, params)
            self.worker.finished.connect(self.on_task_finished)
            self.worker.progress.connect(self.update_process)
            self.worker.start()
        except Exception as e:
            print(e)
            self.on_task_finished({"error": str(e)})

    def on_task_finished(self, result: dict):
        if "error" in result:
            QMessageBox.warning(self, "配音出现错误", result["error"])
        elif "result_path" in result:
            dlg = PrettyPathDialog("配音完成", "音频文件存储位置：", result["result_path"], parent=self)
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



class ElevenDubbingWorker(QThread):
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
            params = self.params
            result = {}

            self.progress.emit(2, "解析字幕中...")
            target_subs = parse_subtitle(params["target_subs_path"])
            if not target_subs:
                raise ValueError("字幕文件内容错误！")
            elif len(params["role_match_list"])<len(target_subs):
                raise ValueError("字幕与角色标注不匹配！")
            else:
                print("cps", params["cps"])
                print(target_subs)
                target_subs, adjust_list, compressed_texts, adjust_indices = adjust_subtitles_cps(target_subs, params["cps"], tolerate_factor)

                # # 这里不需要分离音频
                self.progress.emit(20, "正在进行配音...")
                ElevenLabsAPI = dubbingElevenLabs.getInstance()
                result = ElevenLabsAPI.dubbing_without_clone(target_subs, params["role_match_list"], params["voice_param"], [adjust_indices, adjust_list, compressed_texts], on_progress=self.on_progress)
                self.progress.emit(100, "配音完成...")
            print("结束配音")
            self.finished.emit(result)  # 任务完成，发出信号
        except  Exception as e:
            print(e)
            self.finished.emit({"error": str(e)})




@check_close_permission
class ElevenDubbingParamsWindow2(QMainWindow):
    button_clicked = pyqtSignal(list)

    def select_voice(self):
        self.activate_button = self.sender()
        assert isinstance(self.activate_button, ComboBox)
        print(self.activate_button)
        print(self.activate_button.text())
        if self.voice_selector_window is not None and isinstance(self.voice_selector_window, VoiceSelectorWindow):
            self.voice_selector_window.show()
        else:
            self.voice_selector_window = VoiceSelectorWindow(self.voiceDict)
            self.voice_selector_window.setWindowModality(Qt.ApplicationModal)
            self.voice_selector_window.show()
            self.voice_selector_window.return_signal.connect(self.set_combobox_text)

    def set_combobox_text(self, voice_name):
        self.activate_button.setText(voice_name)


    def __init__(self, subtitle_path: str, role_match_list: list, video_file: str):
        super().__init__()

        self.thread = None
        self.allow_close = True
        self.first = True
        self.base_height = 250
        self.activate_button = None
        self.voice_selector_window = None
        self.video_file = video_file

        self.role_match_list = role_match_list.copy()
        self.roleSet = sorted(list(set(role_match_list)), key=lambda x: mixed_sort_key(x))
        self.subtitlePaths = [subtitle_path]

        voiceDict1 = datasetUtils.getInstance().query_voice_id(1)
        voiceDict2 = {}
        for key, value in voiceDict1.items():
            voiceDict2[key] = [value, ""]   # 这里置为空
        self.voiceDict = spare_voices | voiceDict2 | prepared_voices

        print(self.voiceDict)
        self.voiceNameList = list(self.voiceDict.keys())
        print(self.voiceNameList)
        self.setMinimumHeight(self.base_height)
        self.setMinimumWidth(750)

        print(self.roleSet)
        print(self.subtitlePaths)
        self.setWindowTitle("配音参数设置")

        # 主体 widget 和布局
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)
        self.form_layout = QGridLayout()
        layout.addLayout(self.form_layout)
        self.v_layout = QVBoxLayout()
        layout.addLayout(self.v_layout)
        self.voice_combox_ref = []
        self.voice_edit_ref = []

        self.combo_original_subs = ComboBox()
        self.combo_target_subs = ComboBox()
        self.combo_target_lang = ComboBox()
        self.label1 = QLabel("原始字幕:")
        self.label2 = QLabel("目标字幕:")
        self.label1.setFont(QFont("Microsoft YaHei", 11))
        self.label2.setFont(QFont("Microsoft YaHei", 11))
        self.label3 = QLabel("字幕语言:")
        self.label3.setFont(QFont("Microsoft YaHei", 11))
        self.cps_input = LineEdit()
        self.cps_input.setPlaceholderText("cps语速阈值")


        # 示例选项（你可以在其他地方填充)
        self.combo_target_subs.addItems([os.path.basename(path) for path in self.subtitlePaths])
        self.combo_target_lang.addItems(list(language_cps.keys()))
        self.combo_target_lang.currentTextChanged.connect(self.set_cps)
        self.set_cps()

        # 添加到表单布局
        self.form_layout.addWidget(self.label2, 1, 0)
        self.form_layout.addWidget(self.combo_target_subs, 1, 1)
        self.form_layout.addWidget(create_expanding_widget(), 1, 2)
        self.form_layout.addWidget(self.label3, 2, 0)
        self.form_layout.addWidget(self.combo_target_lang, 2, 1)
        self.form_layout.addWidget(self.cps_input, 2, 2)
        offset = 3

        for i, role in enumerate(self.roleSet):
            label = QLabel(role+"：")
            label.setFont(QFont("Microsoft YaHei", 11))
            combo_box = ComboBox()
            combo_box.setText(self.voiceNameList[0])
            combo_box.clicked.connect(self.select_voice)
            self.voice_combox_ref.append(combo_box)
            line_edit = LineEdit()
            line_edit.setPlaceholderText("选择声音或在此处填写声音id。")
            self.voice_edit_ref.append(line_edit)
            row = i+offset  # 计算行号
            self.form_layout.addWidget(label, row, 0)  # 标签放在偶数列
            self.form_layout.addWidget(combo_box, row, 1)  # 下拉框放在奇数列
            self.form_layout.addWidget(line_edit, row, 2)

        # self.voice_combox_ref[0].view().viewport().installEventFilter(self)
        # 配音按钮
        self.dub_button = PushButton()
        self.dub_button.setText("开始配音")
        self.separate_button = PushButton()
        self.separate_button.setText("分离干音")
        self.folder_selector = SingleFolderSelector(RESULT_OUTPUT_FOLDER)
        self.v_layout.addWidget(self.folder_selector)
        self.v_layout.addWidget(self.dub_button)
        self.v_layout.addWidget(self.separate_button)
        self.dub_button.clicked.connect(self.pass_param)
        self.separate_button.clicked.connect(self.pass_param2)

        self.state_label = QLabel()
        self.processbar = QProgressBar()
        self.processbar.setRange(0, 100)
        self.processbar.setValue(0)
        self.v_layout.addWidget(self.state_label)
        self.v_layout.addWidget(self.processbar)
        self.state_label.hide()
        self.processbar.hide()
        central_widget.setLayout(layout)

    def set_cps(self):
        self.cps_input.setText(str(language_cps[self.combo_target_lang.currentText()]))

    def set_enable(self, enable: bool):
        self.dub_button.setEnabled(enable)
        self.separate_button.setEnabled(enable)
        if enable:
            self.dub_button.setText("开始配音")
            self.separate_button.setText("分离干音")
        else:
            self.dub_button.setText("请稍等...")
            self.separate_button.setText("请稍等...")

    def pass_param(self):
        print("on_task_finished thread:", threading.current_thread())
        try:
            self.allow_close=False
            self.set_enable(False)
            self.processbar.setValue(0)
            self.state_label.setText("")
            if self.first:
                self.setMinimumHeight(self.height()+50)
                self.first = False
            self.state_label.show()
            self.processbar.show()
            params = {}
            # voice_param = {self.roleSet[i]: self.voiceDict[self.voice_combox_ref[i].text()][0] if self.voice_edit_ref[i].text() == "" else
            #                 self.voice_edit_ref[i].text() for i in range(len(self.voice_edit_ref))}
            voice_param = {}
            for i in range(len(self.roleSet)):
                if self.voice_edit_ref[i].text():
                    voice_param[self.roleSet[i]] = self.voice_edit_ref[i].text()
                elif self.voice_combox_ref[i].text() == "不配音":
                    voice_param[self.roleSet[i]] = "-1"
                else:
                    voice_param[self.roleSet[i]] = self.voiceDict[self.voice_combox_ref[i].text()][0]

            params = {"target_subs_path": self.subtitlePaths[self.combo_target_subs.currentIndex()],
                      "role_match_list": self.role_match_list, "voice_param":  voice_param, "cps": self.cps_input.text(),
                      "video_file": self.video_file, "output_path": self.folder_selector.folder_path_display.text()}
            print("配音参数：", params)
            self.worker = ElevenDubbingWorker2(self, params)
            self.worker.finished.connect(self.on_task_finished)
            self.worker.progress.connect(self.update_process)
            self.worker.start()
        except Exception as e:
            print(e)
            self.on_task_finished({"error": str(e)})


    def pass_param2(self):
        print("on_task_finished thread:", threading.current_thread())
        try:
            self.allow_close=False
            self.set_enable(False)
            self.processbar.setValue(0)
            self.state_label.setText("")
            if self.first:
                self.setMinimumHeight(self.height()+50)
                self.first = False
            self.state_label.show()
            self.processbar.show()
            params = {}
            voice_param = {}
            for i in range(len(self.roleSet)):
                if self.voice_edit_ref[i].text():
                    voice_param[self.roleSet[i]] = self.voice_edit_ref[i].text()
                elif self.voice_combox_ref[i].text() == "不配音":
                    voice_param[self.roleSet[i]] = "-1"
                else:
                    voice_param[self.roleSet[i]] = self.voiceDict[self.voice_combox_ref[i].text()][0]

            params = {"target_subs_path": self.subtitlePaths[self.combo_target_subs.currentIndex()],
                      "role_match_list": self.role_match_list, "voice_param":  voice_param, "cps": self.cps_input.text(),
                      "video_file": self.video_file, "output_path": self.folder_selector.folder_path_display.text()}
            print("配音参数：", params)
            self.worker = SeparateWorker(self, params)
            self.worker.finished.connect(self.on_task_finished)
            self.worker.progress.connect(self.update_process)
            self.worker.start()
        except Exception as e:
            print(e)
            self.on_task_finished({"error": str(e)})

    def on_task_finished(self, result: dict):
        if "error" in result:
            QMessageBox.warning(self, "配音出现错误", result["error"])
        elif "result_path" in result:
            dlg = PrettyPathDialog("配音完成", "音频文件存储位置：", result["result_path"], parent=self)
            dlg.exec_()

        print("on_task_finished thread:", threading.current_thread())
        self.allow_close = True
        self.set_enable(True)

    def update_process(self, value: int,  text:str):
        if value!=-1:
            self.processbar.setValue(value)
        if text:
            self.state_label.setText(text)


from PyQt5.QtCore import QThread, pyqtSignal



class ElevenDubbingWorker2(QThread):
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
            params = self.params
            result = {}

            self.progress.emit(2, "解析字幕中...")
            # target_subs = parse_subtitle(params["target_subs_path"])
            target_subs,_ = parse_subtitle_uncertain(params["target_subs_path"])
            if not target_subs:
                raise ValueError("字幕文件内容错误！")
            elif len(params["role_match_list"])<len(target_subs):
                raise ValueError("字幕与角色标注不匹配！")
            else:
                cps = params["cps"]
                print("cps", cps)

                # # 这里不需要分离音频
                self.progress.emit(5, "正在进行配音...")
                ElevenLabsAPI = dubbingElevenLabs3.getInstance()
                result = ElevenLabsAPI.dubbing_new_split(target_subs, params["role_match_list"], params["video_file"], params["voice_param"], params["output_path"], cps, on_progress=self.on_progress)
                self.progress.emit(100, "配音完成...")
                print(result)
            print("结束配音")
            self.finished.emit(result)  # 任务完成，发出信号
        except  Exception as e:
            print(e)
            self.finished.emit({"error": str(e)})

class SeparateWorker(QThread):
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
            params = self.params
            result = {}

            self.progress.emit(2, "解析字幕中...")
            target_subs = parse_subtitle(params["target_subs_path"])
            if not target_subs:
                raise ValueError("字幕文件内容错误！")
            elif len(params["role_match_list"])<len(target_subs):
                raise ValueError("字幕与角色标注不匹配！")
            else:
                cps = params["cps"]
                print("cps", cps)
                # # 这里不需要分离音频
                self.progress.emit(5, "分离人声！")
                result = separate_audio(target_subs, params["role_match_list"], params["video_file"], params["voice_param"], params["output_path"], cps, on_progress=self.on_progress)
                self.progress.emit(100, "分离人声完成...")
                print(result)
            print("结束分离人声")
            self.finished.emit(result)  # 任务完成，发出信号
        except  Exception as e:
            print(e)
            self.finished.emit({"error": str(e)})


def separate_audio(target_subs_: list, role_match_list: list, video_path: str, voice_param: dict, output_path: str=AUDIO_SEPARATION_FOLDER, cps: str="", on_progress=None, delete=False) -> dict:
    '''
    我在这里加上了当前配音的前两句，以提高生成的稳定性, 但是其实是基于音素切分的，它实际上是生成了更长的音频，然后裁剪的
    '''
    if not os.path.exists(output_path) or output_path == RESULT_OUTPUT_FOLDER:
        output_path = AUDIO_SEPARATION_FOLDER
    timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    result_dir = os.path.join(output_path, "{}-分离人声结果-{}".format(os.path.basename(video_path).split('.')[0], timestamp))  # 创建一个文件夹
    os.makedirs(result_dir, exist_ok=True)

    dubbing_subs = {}
    if target_subs_ and role_match_list:
        merged_index = 1
        current_role = role_match_list[0]
        current_text = target_subs_[0]["text"]
        start_time = target_subs_[0]["start"]
        end_time = target_subs_[0]["end"]

        for i in range(1, len(target_subs_)):
            # 检查角色是否相同
            if role_match_list[i] == current_role:
                # 角色相同，合并文本和时间
                current_text += " " + target_subs_[i]["text"]
                end_time = target_subs_[i]["end"]  # 更新结束时间为当前字幕的结束时间
            else:
                # 角色不同，保存当前合并的字幕
                dubbing_subs[str(merged_index)] = {
                    "start": start_time,
                    "end": end_time,
                    "text": current_text,
                    "role": current_role
                }
                merged_index += 1

                # 开始新的角色字幕合并
                current_role = role_match_list[i]
                current_text = target_subs_[i]["text"]
                start_time = target_subs_[i]["start"]
                end_time = target_subs_[i]["end"]

        # 保存最后一个合并的字幕
        dubbing_subs[str(merged_index)] = {
            "start": start_time,
            "end": end_time,
            "text": current_text,
            "role": current_role
        }

    target_subs = list(dubbing_subs.values())

    for i in range(len(target_subs)):
        target_subs[i]["index"] = i+1

    print(target_subs)

    from Service.uvr5.audioseperate import AudioSeparator
    from Service.uvrMain.separate import AudioPre
    try:
        video_audio, samplerate = get_audio_np_from_video(video_path)
        assert isinstance(video_audio, np.ndarray)
        back_audio = np.zeros_like(video_audio)
        print(back_audio.shape)
        video_audio_path = os.path.join(result_dir, "视频-原音频.mp3")
        sf.write(video_audio_path, video_audio, samplerate)

        # 使用mdxnet分离获取干音
        result3 = os.path.join(result_dir, "mdxnet")
        os.makedirs(result3)
        mdxnet = AudioSeparator.get_instance()
        pure_vocal_path = mdxnet.isolate(video_audio_path, result3)
        print(pure_vocal_path)
        if pure_vocal_path:
            role_subtitles, vocal_audio, _, role_audio_path = parse_all_roles_numpy_separate(target_subs, role_match_list, pure_vocal_path, voice_param, output_path=result3)

        # 使用elevenlab分离获取干音
        result2 = os.path.join(result_dir, "elevenlab")
        os.makedirs(result2)
        elevenlab = dubbingElevenLabs.getInstance()
        pure_vocal_path = os.path.join(result2, "纯人声.mp3")
        elevenlab.voice_isolate(video_audio_path, pure_vocal_path)
        role_subtitles, vocal_audio, _, role_audio_path = parse_all_roles_numpy_separate(target_subs, role_match_list, pure_vocal_path, voice_param, output_path=result2)
        
        # # 使用2hp分离人声获取干音
        # result1 = os.path.join(result_dir, "2HP")
        # os.makedirs(result1)
        # back_path, vocal_path = AudioPre.getInstance()._path_audio_(video_audio_path, output_path=result1)
        # role_subtitles, vocal_audio, _, role_audio_path = parse_all_roles_numpy_separate(target_subs, role_match_list, vocal_path, voice_param, output_path=result1)

        return {"result_path": result_dir}
    except Exception as e:
        # 处理特定异常
        print(f"配音过程发生错误: {e}")
        traceback.print_exc()
        return {"error": f"配音过程发生错误: {e}"}

def parse_all_roles_numpy_separate(subtitles: list, role_match_list: list, audio_path: str, voice_param: dict, output_path = AUDIO_SEPARATION_FOLDER) -> tuple[dict, np.ndarray, int, dict]:
    # 设计一个dict, dict的key为role，value为[],把subtitles的role分类出来
    audio, samplerate = sf.read(audio_path)
    role_subtitles = {}
    role_audio = {}
    role_audio_path = {}

    i=0
    for subtitle in subtitles:
        role = subtitle["role"]
        if role not in role_subtitles:
            role_subtitles[role] = []
        role_subtitles[role].append(subtitle)
        i += 1
    for key in role_subtitles.keys():
        for subtitle in role_subtitles[key]:
            clip = audio[int((time_str_to_ms(subtitle["start"]) * samplerate) / 1000):int(
                (time_str_to_ms(subtitle["end"]) * samplerate) / 1000)]
            if key not in role_audio:
                role_audio[key] = clip
            else:
                empty_array = np.zeros((20000, 2), dtype=clip.dtype)
                role_audio[key] = np.concatenate([role_audio[key],empty_array, clip])
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    for key in role_audio.keys():
        clip = role_audio[key]
        if clip.shape[0] < 10*samplerate:
            empty_array = np.zeros((20000, 2), dtype=clip.dtype)
            clip = np.concatenate([clip, empty_array, clip])
        filePath = os.path.join(output_path, f"角色干音_{key}_{timestamp}.mp3")
        role_audio_path[key] = filePath
        sf.write(filePath, clip, samplerate)
    return role_subtitles, audio, samplerate, role_audio_path

if __name__ == '__main__':
    app = QApplication(sys.argv)
    role_str = "医生;医生;医生;陈女士;陈女士;陈女士;陈女士;陈女士;医生;医生;医生;医生;医生;医生;医生;医生;医生;医生;陈女士;陈女士;陈女士"
    role_match_list = [role.strip() for role in role_str.split(";")]
    print(role_match_list)
    window = ElevenDubbingParamsWindow2("E:\\offer\\AI配音web版\\7.28\\AIDubbing-QT-main\\1-英_test.srt", role_match_list, "E:\\offer\\AI配音web版\\7.28\\AIDubbing-QT-main\\a视频_test.mp4")
    # window = VoiceSelectorWindow()
    window.show()
    sys.exit(app.exec_())
