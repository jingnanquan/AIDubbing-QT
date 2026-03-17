import os
import time
import traceback

# import ffmpeg
from PyQt5.QtCore import QThread, pyqtSignal

# import soundfile as sf
# from pyparsing import originalTextFor, original_text_for
# from scipy import signal
# from shapely.ops import orient

# from Service.ERes2NetV2.audiosimilarity import SpeakerEmbeddingCluster
# from Service.ERes2NetV2.launch_visualization import launch_visualization_safely
# from Service.dubbingMain.llmAPI import LLMAPI
from Service.subtitleUtils import parse_subtitle_uncertain


class BatchDubbingWorker(QThread):
    """
    QThread worker that uses a ThreadPoolExecutor to annotate roles for each (video, srt) pair in parallel.
    """
    finished = pyqtSignal(dict)
    progress = pyqtSignal(int, str)

    def __init__(self, pairs, output_root_dir, extraOutput=False, max_workers=3, if_translate: bool = False, language: str = "", cps="",
                 voice_params=None):
        super().__init__()
        if voice_params is None:
            voice_params = {}
        self.voice_params = voice_params
        self.cps = cps
        self.pairs = pairs
        self.output_root_dir = output_root_dir
        self.max_workers = max_workers
        self.extraOutput = extraOutput
        self.if_translate = if_translate
        self.language = language
        # if self.if_translate:
        #     self.max_workers = 3

    def on_progress(self, value, msg):
        self.progress.emit(value, msg)

    def get_voices_count(self):
        try:
            from Service.dubbingMain.dubbingElevenlabs3 import dubbingElevenLabs

            elevenlabs = dubbingElevenLabs.getInstance().elevenlabs
            response = elevenlabs.voices.search(page_size=100, sort="created_at_unix", sort_direction="asc",voice_type="non-default")
            print(f"已获取{len(response.voices)}个声源")
            return response.total_count
        except Exception as e:
            print(f"获取声源数量失败: {e}")
            return 0

    def run(self):
        try:
            voice_count = self.get_voices_count()
            # print(voice_count)1
            print(self.voice_params)
            param_cloned_voice_count = sum(1 for param in self.voice_params.values() if param=="")   # 自动克隆为空
            # print(param_cloned_voice_count)
            if voice_count + param_cloned_voice_count > 660:
                self.finished.emit({
                    "msg": f"警告，此次配音需要克隆{param_cloned_voice_count}个声源，请删除已经克隆的声音，使其小于{660-param_cloned_voice_count}个",
                    "result_path": ""
                })
                return

            os.makedirs(self.output_root_dir, exist_ok=True)
            self.summary_dir = os.path.join(self.output_root_dir, "剧情简介")
            self.srt_dir = os.path.join(self.output_root_dir, "字幕")
            self.role_dir = os.path.join(self.output_root_dir, "角色表")
            self.processing_dir = os.path.join(self.output_root_dir, "中间结果")

            from Service.dubbingMain.llmAPI import LLMAPI
            LLMAPI.getInstance()  # initialize once
            failed = []

            from Service.dubbingMain.dubbingElevenlabs3 import dubbingElevenLabs3
            ElevenLabsAPI = dubbingElevenLabs3.getInstance()

            for idx, (video_path, subtitle_path) in enumerate(self.pairs):
                try:
                    print(idx, video_path, subtitle_path)
                    self.progress.emit(idx, f"正在处理 {os.path.basename(video_path)}")
                    target_subs, role_match_list = parse_subtitle_uncertain(subtitle_path)
                    if not role_match_list:
                        raise ValueError(f"字幕文件 {os.path.basename(subtitle_path)} 中未检测到角色")
                    if not target_subs:
                        raise ValueError(f"字幕文件 {os.path.basename(subtitle_path)} 中未检测到有效字幕")

                    this_voice_param = {}
                    for role_name in set(role_match_list):
                        this_voice_param[role_name] = self.voice_params.get(role_name, "")
                    result = ElevenLabsAPI.dubbing_new_split2(target_subs, role_match_list,
                                                             video_path, this_voice_param,
                                                             self.output_root_dir, self.cps, on_progress=self.on_progress)
                    if "error" in result:
                        raise ValueError(result["error"])
                except Exception as e:
                    print(e)
                    print(traceback.format_exc())
                    self.progress.emit(idx, f"处理 {os.path.basename(video_path)} 时发生错误: {e}")
                    failed.append((os.path.basename(video_path), os.path.basename(subtitle_path), str(e), traceback.format_exc()))
                    time.sleep(1.5)
                    continue

            if failed:
                error_log_path = os.path.join(self.output_root_dir, "error_log.txt")
                with open(error_log_path, 'w', encoding='utf-8') as f:
                    f.write("发生错误的条目如下:\n\n")
                    for vname, sname, err, tb in failed:
                        f.write(f"视频: {vname}  字幕: {sname}\n错误: {err}\n{tb}\n---\n")

            msg = f"批量配音完成，成功 {len(self.pairs) - len(failed)}，失败 {len(failed)}。"
            self.finished.emit({
                "msg": msg,
                "result_path": self.output_root_dir
            })
        except Exception as e:
            print(e)
            print(traceback.format_exc())
            self.finished.emit({
                "msg": f"发生错误: {e}",
                "result_path": self.output_root_dir if os.path.isdir(self.output_root_dir) else ""
            })

