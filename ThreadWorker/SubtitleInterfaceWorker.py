import datetime
import os
import time

from PyQt5.QtCore import QThread, pyqtSignal
from Service.datasetUtils import datasetUtils
from Service.subtitleUtils import parse_subtitle_uncertain


class PullVoiceWorker(QThread):
    """
    拉取可用声音列表
    """
    # 定义一个信号，用于在任务完成后更新 GUI
    finished = pyqtSignal(str)

    def __init__(self):
        super().__init__()

    def run(self):
        from Service.dubbingMain.dubbingElevenLabs import dubbingElevenLabs

        try:
            elevenlabs = dubbingElevenLabs.getInstance().elevenlabs
            response = elevenlabs.voices.search(page_size=100, sort="created_at_unix", sort_direction="asc", category="cloned")

            voice_list = response.voices
            total_voice_count = response.total_count - len(voice_list)
            print(len(voice_list))
            while total_voice_count > 0:
                response = elevenlabs.voices.search(next_page_token=response.next_page_token, page_size=100,
                                                    sort="created_at_unix", sort_direction="asc", category="cloned")
                voice_list.extend(response.voices)
                total_voice_count = response.total_count - len(voice_list)
                print(f"已获取{len(voice_list)}个声源")

            # 只保留 name 中包含 '-' 的 voice
            # voice_list = [
            #     {"api_id": 1, "voice_name": voice.name, "voice_id": voice.voice_id}
            #     for voice in voice_list if '-' in voice.name
            # ]

            voice_list = [
                {"api_id": 1, "voice_name": voice.name, "voice_id": voice.voice_id}
                for voice in voice_list
            ]
            datasetUtils.getInstance().update_voice_id(voice_list)
            self.finished.emit("已更新声音列表！")
        except Exception as e:
            self.finished.emit(f"更新声音列表时出错：{e}")


class ExportRolesWorker(QThread):
    """
    导出角色列表
    """
    # 定义一个信号，用于在任务完成后更新 GUI
    finished = pyqtSignal(str)

    def __init__(self, subtitle_file_name: str, folder: str, role_macth_list: list):
        super().__init__()
        self.subtitle_file_name = subtitle_file_name
        self.folder = folder
        self.role_macth_list = role_macth_list

    def run(self):
        try:
            file_name = os.path.splitext(os.path.basename(self.subtitle_file_name))[0]
            timestamp = datetime.datetime.now().strftime(
                "%Y%m%d%H%M%S")
            dir = os.path.join(self.folder, "{}-角色表导出-{}".format(file_name, timestamp))
            os.makedirs(dir, exist_ok=True)
            file_path = os.path.join(dir, "{}-角色表-{}.txt".format(file_name, timestamp))
            srt_path = os.path.join(dir, "{}-字幕带角色-{}.txt".format(file_name, timestamp))
            srt2_path = os.path.join(dir, "{}-字幕-{}.srt".format(file_name, timestamp))
            print(file_path)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(";".join(self.role_macth_list))

            subtitles, _ = parse_subtitle_uncertain(self.subtitle_file_name)
            with open(srt_path, "w", encoding="utf-8") as f:
                i=0
                for subtitle in subtitles:
                    f.write(f"{subtitle['index']}\n{subtitle['start']} --> {subtitle['end']}\n{self.role_macth_list[i]}: {subtitle['text']}\n\n")
                    i += 1
            with open(srt2_path, "w", encoding="utf-8") as f:
                for subtitle in subtitles:
                    f.write(f"{subtitle['index']}\n{subtitle['start']} --> {subtitle['end']}\n{subtitle['text']}\n\n")
            self.finished.emit("角色列表导出完成！")
        except Exception as e:
            self.finished.emit(f"导出角色列表出错：{e}")
