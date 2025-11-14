import os
import re
import traceback
from copy import deepcopy

import ffmpeg
import numpy as np
from PyQt5.QtCore import QThread, pyqtSignal
import soundfile as sf
from scipy import signal

from Service.ERes2NetV2.audiosimilarity import SpeakerEmbeddingCluster
from Service.generalUtils import time_str_to_ms, ms_to_time_str
from Service.subtitleUtils import parse_subtitle_uncertain
from Service.uvrMain.separate import AudioPre
from Service.videoUtils import get_audio_np_from_video, _probe_video_duration_ms


'''
废弃原因，串行并且采用原始的情节提取+标注的方式，不准确
'''


class BatchAnnotationWorker_with_AudioFeature(QThread):
    """
    QThread worker that uses a ThreadPoolExecutor to annotate roles for each (video, srt) pair in parallel.
    """
    finished = pyqtSignal(dict)
    progress = pyqtSignal(int, str)

    def __init__(self, pairs, role_info_text, output_root_dir, extraOutput=False, max_workers=6):
        super().__init__()
        self.pairs = pairs
        self.role_info_text = role_info_text
        self.output_root_dir = output_root_dir
        self.max_workers = max_workers
        self.extraOutput = extraOutput

    def run(self):
        try:
            os.makedirs(self.output_root_dir, exist_ok=True)
            self.summary_dir = os.path.join(self.output_root_dir, "剧情简介")
            self.srt_dir = os.path.join(self.output_root_dir, "字幕")
            self.role_dir = os.path.join(self.output_root_dir, "角色表")
            self.processing_dir = os.path.join(self.output_root_dir, "中间结果")
            os.makedirs(self.summary_dir, exist_ok=True)
            os.makedirs(self.srt_dir, exist_ok=True)
            os.makedirs(self.role_dir, exist_ok=True)
            os.makedirs(self.processing_dir, exist_ok=True)

            total = len(self.pairs)
            completed = 0
            failed = []
            failed2 = []
            sub_results = [None for i in range(len(self.pairs))]
            self.progress.emit(0, f"开始处理，共 {total} 组...   ")

            for idx, (video_path, srt_path) in enumerate(self.pairs):
                try:
                    self.progress.emit(0, f"开始处理第 {idx + 1} 组: {video_path}  {srt_path}")
                    video_name = os.path.splitext(os.path.basename(video_path))[0]
                    srt_name = os.path.splitext(os.path.basename(srt_path))[0]

                    summary_path = os.path.join(self.summary_dir, f"剧情简介{idx}.txt")
                    output_srt_path = os.path.join(self.srt_dir, f"{srt_name}_{idx}_角色标注.srt")
                    role_table_file = os.path.join(self.role_dir, f"角色表{idx}.txt")
                    video_audio_path = os.path.join(self.processing_dir, f"{video_name}_{idx}.mp3")
                    vad_audio_path = os.path.join(self.processing_dir, f"去除空音_{video_name}_{idx}.mp3")

                    video_audio, samplerate = get_audio_np_from_video(video_path)
                    sf.write(video_audio_path, video_audio, samplerate)

                    vad_audio = np.zeros_like(video_audio)
                    vad_separate_audios = []
                    origin_subtitles, _ = parse_subtitle_uncertain(srt_path)

                    vad_subtitles = []
                    print(samplerate)
                    if origin_subtitles:
                        start_offset = 400  # offset以ms为单位，后续会转为帧
                        for sub in origin_subtitles:
                            print(sub)
                            new_sub = deepcopy(sub)
                            start = time_str_to_ms(sub["start"])
                            end = time_str_to_ms(sub["end"])

                            start_frame = int((start*samplerate)/1000)
                            end_frame = int((end*samplerate)/1000)
                            audio = video_audio[start_frame: end_frame]

                            start_2 = start_offset
                            end_2 = start_2
                            start_2_frame = int((start_2*samplerate)/1000)
                            end_2_frame = int((end_2*samplerate)/1000)+audio.shape[0]
                            end_2 = int((end_2_frame*1000)/samplerate)
                            vad_audio[start_2_frame: end_2_frame] = audio
                            new_sub["start"] = ms_to_time_str(start_2)
                            new_sub["end"] = ms_to_time_str(end_2)
                            vad_subtitles.append(new_sub)
                            start_offset = int(end_2+ 400)

                        vad_audio = vad_audio[:int((start_offset*samplerate)/1000)+20000]
                        # 为了将音频缩短，即去除空音，加快人声分离的速度
                        sf.write(vad_audio_path, vad_audio, samplerate)

                        # back_path, vocal_path = AudioPre.getInstance()._path_audio_(vad_audio_path, output_path=self.processing_dir)
                        # pure_vocal_audio, _ = sf.read(vocal_path)

                        pure_vocal_audio = vad_audio
                        # 获取纯净的人声音频段
                        for sub in vad_subtitles:
                            start = time_str_to_ms(sub["start"])
                            end = time_str_to_ms(sub["end"])
                            start_frame = int((start*samplerate)/1000)
                            end_frame = int((end*samplerate)/1000)
                            audio = pure_vocal_audio[start_frame: end_frame]

                            new_length = int(len(audio) * 16000 / samplerate)
                            audio_data = signal.resample(audio, new_length)
                            vad_separate_audios.append(audio_data)
                        # 合并人声
                        print(vad_separate_audios)
                        embs, labels=SpeakerEmbeddingCluster.get_instance().analyze_speakers(vad_separate_audios, visualize=True)
                        print(labels)
                        print(labels.__len__())
                        print(origin_subtitles.__len__())

                        with open(output_srt_path, 'w', encoding='utf-8') as f:
                            for i, sub in enumerate(origin_subtitles):
                                f.write(f"{sub['index']}\n")
                                f.write(f"{sub['start']} --> {sub['end']}\n")
                                f.write(f"{labels[i]}: {sub['text']}\n\n")
                        with open(role_table_file, "w", encoding="utf-8") as f:
                            f.write(";".join(labels.astype(str).tolist()))
                        duration_ms = _probe_video_duration_ms(video_path)
                        sub_results[idx] = (output_srt_path, duration_ms)

                    else:
                        raise Exception(f"字幕{idx}解析错误为空")

                    completed += 1
                    self.progress.emit(completed, f"已完成 {completed} 组，失败 {len(failed)} 组...   ")
                except Exception as e:
                    print(e)
                    print(traceback.format_exc())
                    failed.append((video_name, srt_name, e, traceback.format_exc()))
                pass


            # save error log if any
            if failed:
                error_log_path = os.path.join(self.output_root_dir, "error_log.txt")
                with open(error_log_path, 'w', encoding='utf-8') as f:
                    f.write("发生错误的条目如下:\n\n")
                    for vname, sname, err, tb in failed:
                        f.write(f"视频: {vname}  字幕: {sname}\n错误: {err}\n{tb}\n---\n")
            elif self.extraOutput:
                # 先合并字幕：使用成功项，按原顺序叠加 offset（累计时长）
                try:
                    self.progress.emit(1, "  合并字幕中...  ")
                    merged_subtitle_path = os.path.join(self.output_root_dir, "merged_subtitle.srt")
                    current_index = 1
                    merged_lines = []
                    cumulative_offset = 0
                    for res in sub_results:
                        if res is None:
                            continue
                        path, duration_ms = res
                        with open(path, "r", encoding="utf-8") as f:
                            content = f.read()
                        blocks = re.split(r"\n\s*\n", content.strip(), flags=re.MULTILINE)
                        i_block = 1
                        for block in blocks:
                            lines = block.strip().split("\n")
                            if len(lines) < 2:
                                raise Exception(f"字幕文件{path}第{i_block}块格式错误")
                            time_line = lines[1] if "-->" in lines[1] else lines[0]
                            m = re.match(r"(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})", time_line)
                            if not m:
                                raise Exception(f"字幕文件{path}第{i_block}块格式错误")
                            start_time, end_time = m.groups()
                            start_ms = int(time_str_to_ms(start_time) + cumulative_offset)
                            end_ms = int(time_str_to_ms(end_time) + cumulative_offset)
                            new_block = [str(current_index)]
                            new_block.append(f"{ms_to_time_str(start_ms)} --> {ms_to_time_str(end_ms)}")
                            if "-->" in lines[1]:
                                new_block.extend(lines[2:])
                            else:
                                raise Exception(f"字幕文件{path}第{i_block}块格式错误")
                            merged_lines.append("\n".join(new_block))
                            current_index += 1
                            i_block += 1
                        cumulative_offset += max(0, duration_ms)

                    with open(merged_subtitle_path, "w", encoding="utf-8") as f:
                        f.write("\n\n".join(merged_lines))
                except Exception:
                    failed2.append(("MERGE", "SUBTITLE", "合并字幕失败", traceback.format_exc()))

                try:
                    merged_video_path = os.path.join(self.output_root_dir, "merged_video.mp4")
                    video_files_ok = [v for (res, (v, s)) in zip(sub_results, self.pairs) if res is not None]
                    self.progress.emit(2, "  合并视频中...  ")
                    streams = []
                    for fpath in video_files_ok:
                        inp = ffmpeg.input(fpath)
                        v = inp.video
                        a = inp.audio.filter('aresample', **{'async': 1, 'first_pts': 0})
                        streams += [v, a]
                    concat = ffmpeg.concat(*streams, v=1, a=1, n=len(video_files_ok)).node
                    vcat, acat = concat[0], concat[1]
                    (
                        ffmpeg
                        .output(vcat, acat, merged_video_path, vcodec='libx264', acodec='aac')
                        .global_args('-fflags', '+genpts')
                        .overwrite_output()
                        .run()
                    )
                except Exception:
                    failed2.append(("MERGE", "VIDEO", "合并视频失败", traceback.format_exc()))


            msg = f"批量角色标注完成，成功 {total - len(failed)}，失败 {len(failed)}。"
            if failed2:
                msg2 = {info[2] for info in failed2}
                msg += str(msg2)
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

