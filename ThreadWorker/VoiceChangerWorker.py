import os
import time
import datetime

from PyQt5.QtCore import QThread, pyqtSignal

from Config import CHANGER_RESULT_OUTPUT_FOLDER
from Service.datasetUtils import datasetUtils
from Service.dubbingMain.roleExtractAPI import RoleExtractAPI
from Service.dubbingMain.voiceElevenLabs import voiceElevenLabs


class VoiceChangerWorker(QThread):
    # 定义一个信号，用于在任务完成后更新 GUI
    finished = pyqtSignal(dict)
    item_finished = pyqtSignal(int)

    def __init__(self, param: dict):
        super().__init__()
        self.param = param
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.result_path  = os.path.join(CHANGER_RESULT_OUTPUT_FOLDER, timestamp)
        # 创建这样一个目录用于存放结果
        os.makedirs(self.result_path)

    def run(self):
        print("enter: 语音转换")
        voiceElevenlabsAPI = voiceElevenLabs.getInstance()
        voice_files = self.param["voice_files"]
        self.param.pop("voice_files")
        voiceElevenlabsAPI.setting_voice(self.param)

        print(self.param)
        print(voice_files)
        unfinished_files = []
        i = 0
        for voice_file in voice_files:
            print(voice_file)
            if not voiceElevenlabsAPI.voice_changer(voice_file, self.result_path, self.param):
                unfinished_files.append(voice_file)
            else:
                self.item_finished.emit(i)
            i+=1
        datasetUtils.getInstance().sava_changer_audio_dir(self.result_path)
        self.finished.emit({"msg": "语音转换完成",  "result_path": self.result_path, "unfinished_files":unfinished_files})

