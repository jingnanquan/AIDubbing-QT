import os

from PyQt5 import QtWidgets
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QLabel,
    QPushButton, QVBoxLayout, QFormLayout, QGridLayout, QSizePolicy, QMessageBox, QProgressBar, QButtonGroup
)
from PyQt5.QtCore import Qt, pyqtSignal, QThread
from qfluentwidgets import ComboBox, PushButton, LineEdit, ProgressBar, RadioButton, StrongBodyLabel, CheckBox

from Compoment.PathDialog import PrettyPathDialog
from Service.datasetUtils import datasetUtils
from Service.subtitleUtils import parse_subtitle
import threading


# 所有更新界面的操作，都不应该在子进程中执行
language_codes = {
    "English": "en",
    "Chinese (Simplified)": "zh",
    "Chinese (Traditional)": "zh-TW",
    "Japanese": "ja",
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


class VoiceChangerParamsWindow(QMainWindow):

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
        self.voiceNameList = ["无"]
        self.voiceNameList.extend(self.voiceDict.keys())
        self.voiceDict["无"] = ""
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
        self.voice_check_ref = []

        self.combo_target_subs = ComboBox()
        self.label2 = StrongBodyLabel("视频字幕:")
        self.combo_target_subs.addItems([os.path.basename(path) for path in subtitlePaths])

        # 添加到表单布局
        form_layout.addWidget(self.label2, 0, 0)
        form_layout.addWidget(self.combo_target_subs, 0, 1)
        form_layout.addWidget(create_expanding_widget(), 0, 2)
        offset = 1

        for i, role in enumerate(self.roleSet):
            # label = StrongBodyLabel(role+"：")
            label = CheckBox(role+"：")
            self.voice_check_ref.append(label)
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

        # 配音按钮
        self.dub_button = PushButton()
        self.dub_button.setText("执行声线转换")
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
        i = 0
        for check_box in self.voice_check_ref:
            if check_box.isChecked():
                if not self.voiceDict[self.voice_combox_ref[i].currentText()] and not self.voice_edit_ref[i].text():
                    QMessageBox.information(self, "提示", "请选择或填写声音id。")
                    return
            else:
                if self.voiceDict[self.voice_combox_ref[i].currentText()] or self.voice_edit_ref[i].text():
                    QMessageBox.information(self, "提示", "请选中角色。")
                    return
            i += 1
        try:
            self.allow_close=False
            self.dub_button.setEnabled(False)
            self.dub_button.setText("请稍等...")
            self.processbar.setValue(0)
            self.state_label.setText("")
            self.state_label.show()
            self.processbar.show()
            params = {}
            voice_param = {self.roleSet[i]: self.voiceDict[self.voice_combox_ref[i].currentText()] if self.voice_edit_ref[i].text() == "" else
                            self.voice_edit_ref[i].text() for i in range(len(self.voice_edit_ref))}
            # voice_param该为空，就要为空。但是为空的前提是checkbox未选中
            params = {"target_subs_path": self.subtitlePaths[self.combo_target_subs.currentIndex()],
                      "video_file": self.video_file, "role_match_list": self.role_match_list,
                      "voice_param": voice_param}
            print("声线转换参数：", params)
            self.worker = VideoVoiceChangerWorker(self, params)
            self.worker.finished.connect(self.on_task_finished)
            self.worker.progress.connect(self.update_process)
            self.worker.start()
        except Exception as e:
            print(e)
            self.on_task_finished({"error": str(e)})

    def on_task_finished(self, result: dict):
        if "error" in result:
            QMessageBox.warning(self, "声线转换出现错误", result["error"])
        elif "video_file" in result:
            dlg = PrettyPathDialog("声线转换完成", "视频存储位置：", result["video_file"], parent=self)
            dlg.exec_()

        print("on_task_finished thread:", threading.current_thread())
        self.allow_close = True
        self.dub_button.setEnabled(True)
        self.dub_button.setText("执行声线转换")

    def update_process(self, value: int,  text:str):
        if value!=-1:
            self.processbar.setValue(value)
        if text:
            self.state_label.setText(text)


from PyQt5.QtCore import QThread, pyqtSignal

class VideoVoiceChangerWorker(QThread):
    finished = pyqtSignal(dict)
    progress = pyqtSignal(int, str)

    def on_progress(self, value, msg):
        self.progress.emit(value, msg)

    def __init__(self, parent, params):
        super().__init__()
        self.params = params
        self.parent = parent  # 为了调用 QMessageBox 等界面组件

    def run(self):
        from Service.dubbingMain.voiceElevenLabs import voiceElevenLabs
        from Service.uvrMain.separate import AudioPre

        try:
            params = self.params
            result = {}
            self.progress.emit(2, "解析字幕中...")
            target_subs = parse_subtitle(params["target_subs_path"])
            if not target_subs:
                QMessageBox.warning(self.parent, "错误", "字幕文件内容错误！")
            elif len(self.params["role_match_list"]) < len(target_subs):
                QMessageBox.warning(self.parent, "警告", "字幕与角色标注不匹配！")
            else:
                self.progress.emit(4, "正在分离音频...")
                voice_isolator = AudioPre.getInstance()
                back_file, vocal_file = voice_isolator._path_audio_(params["video_file"], on_progress=self.on_progress)
                self.progress.emit(20, "正在进行声线转换...")
                ElevenLabsAPI = voiceElevenLabs.getInstance()
                result = ElevenLabsAPI.video_voice_changer(
                    vocal_file, back_file, target_subs,
                    params["role_match_list"], params["video_file"], params["voice_param"],
                    on_progress=self.on_progress
                )
                self.progress.emit(100, "声线转换完成...")
            print("结束声线转换")
            self.finished.emit(result)  # 任务完成，发出信号
        except  Exception as e:
            print(e)
            self.finished.emit({"error": str(e)})






