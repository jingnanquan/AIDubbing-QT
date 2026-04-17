import base64
import copy
import datetime
import io
import json
import os
import time
import traceback

import librosa
from librosa.feature import rms
import numpy as np
import soundfile as sf
import ffmpeg
from pydub import AudioSegment

from Config import AUDIO_SEPARATION_FOLDER, RESULT_OUTPUT_FOLDER, tolerate_factor
from ProjectCompoment.dubbingEntity import Subtitle
from Service.audioUtils import split_roles_audio
from Service.datasetUtils import datasetUtils
from Service.dubbingMain.dubbingElevenLabs import dubbingElevenLabs
from Service.dubbingMain.dubbingInterface import dubbingInterface
from Service.dubbingMain.llmAPI import LLMAPI
from Service.dubbingMain.llmAPI2 import LLMAPI2
from Service.generalUtils import calculate_time, ms_to_time_str
from Service.subtitleUtils import adjust_subtitles_cps, parse_subtitle_uncertain
from Service.uvrMain.separate import AudioPre
from Service.videoUtils import get_audio_np_from_video


class dubbingElevenLabs3(dubbingInterface):
    """
    #TODO: 还未完成需减速的字幕的对齐，需要修改llm的prompt
    """
    _instance = None

    @classmethod
    def getInstance(cls) -> "dubbingElevenLabs3":
        if not cls._instance:
            cls._instance = dubbingElevenLabs3()
        return cls._instance

    @calculate_time
    def __init__(self):
        self.connect = dubbingElevenLabs.getInstance()


    def dubbing_new_split(self, target_subs: list, role_match_list: list, video_path: str, voice_param: dict, output_path: str=RESULT_OUTPUT_FOLDER, cps: str="", on_progress=None, delete=False) -> dict:
        '''
        delete 代表配音完是否删除克隆的声音
        '''
        if not os.path.exists(output_path):
            output_path = RESULT_OUTPUT_FOLDER
        timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        result_dir = os.path.join(output_path, "{}-视频一键配音结果-{}".format(os.path.basename(video_path).split('.')[0], timestamp))  # 创建一个文件夹
        os.makedirs(result_dir, exist_ok=True)


        try:
            video_audio, samplerate = get_audio_np_from_video(video_path)
            assert isinstance(video_audio, np.ndarray)
            back_audio = np.zeros_like(video_audio)
            # target_voice_audio = np.zeros_like(video_audio)  # 初始化目标人声音频
            all_audio = None
            print(back_audio.shape)
            video_audio_path = os.path.join(result_dir, "视频-原音频.mp3")
            sf.write(video_audio_path, video_audio, samplerate)

            if cps:
                if on_progress: on_progress(10, "调整字幕cps中...")
                target_subs, adjust_list, compressed_texts, adjust_indices = adjust_subtitles_cps(target_subs, int(cps), tolerate_factor)
            if on_progress: on_progress(20, "合并配音字幕中...")

            dubbing_subs1 = LLMAPI2.getInstance().merge_subtitle_with_index(target_subs, role_match_list)
            if not dubbing_subs1: raise Exception("合并配音字幕出现错误")
            print(dubbing_subs1)
            dubbing_subs = LLMAPI2.getInstance().correct_punctuation(dubbing_subs1)
            print(dubbing_subs)


            # role_subs = ""
            # i = 0
            # for subtitle in target_subs:
            #     role_subs += f"""{subtitle["index"]} | {subtitle["start"]} --> {subtitle["end"]} | {subtitle["text"]} | {role_match_list[i]}\n"""
            #     i += 1
            # dubbing_subs = LLMAPI.getInstance().merge_subtitle_with_index(role_subs)
            # dubbing_subs = {}
            # dubbing_subs_list, role_ = parse_subtitle_uncertain(r"E:\offer\AI配音web版\8.13\AIDubbing-QT-main\OutputFolder\project_result\a视频_test-视频一键配音结果-20250820-095619\字幕-合并后的配音字幕.txt")
            # for i in range(len(dubbing_subs_list)):
            #     dubbing_subs[i] = {"start": dubbing_subs_list[i]["start"], "end":dubbing_subs_list[i]["end"],"text":dubbing_subs_list[i]["text"],"role":role_[i]}

            print(dubbing_subs)
            if not dubbing_subs: raise Exception("矫正字幕标点出现错误")

            if on_progress: on_progress(30, "角色干音分片中...")
            back_path, vocal_path = AudioPre.getInstance()._path_audio_(video_audio_path, output_path=result_dir)
            back_audio, _ = sf.read(back_path)
            target_voice_audio = np.zeros_like(back_audio)
            role_subtitles, vocal_audio, _, role_audio_path = split_roles_audio(dubbing_subs, vocal_path, output_path= result_dir)
            if on_progress:
                print("角色声音克隆中...")
                on_progress(35, "角色声音克隆中...")
            voice_ids = self.batch_clone_text(role_subtitles, role_audio_path, timestamp, voice_param)

            if on_progress:
                on_progress(40, "正在进行配音...")

            voice_setting = {"stability": 0.6, "similarity_boost": 0.75, "style": 0.05, "use_speaker_boost": True,
                             "speed": 1.0}
            previous_dict = {}
            role_set = set(role_match_list)
            for role in role_set:
                previous_dict[role] = []

            length = len(dubbing_subs)
            dubbing_subtitle_entitys = []
            dubbing_subs_list = list(dubbing_subs.values())
            for i, (key, subtitle) in enumerate(dubbing_subs.items()):
                if on_progress:
                    on_progress(min(40 + int((i * 56) / length), 100), "")

                print(subtitle)
                role = subtitle["role"]
                start_str = subtitle["start"]
                end_str = subtitle["end"]
                text = subtitle["text"]
                voice_id = voice_ids[role] if role in voice_ids else "JBFqnCBsd6RMkjVDRZzb"
                if not voice_id or voice_id == "-1":
                    continue


                start = int((self.time_str_to_ms(start_str) * samplerate) / 1000)
                end = int((self.time_str_to_ms(end_str) * samplerate) / 1000)
                circle = True  # 是否进行循环
                retry = 3
                source_frames = end - start
                res_audio = None
                request_id = None
                time_alignments = None

                # language_code = "id",
                while circle and retry > 0:
                    audio = self.connect.elevenlabs.text_to_speech.with_raw_response.convert_with_timestamps(
                        text = text,
                        voice_id=voice_id,
                        model_id="eleven_multilingual_v2",
                        output_format="mp3_44100_192",
                        voice_settings=voice_setting,
                        previous_request_ids = previous_dict[role][-3:])

                    request_id = audio._response.headers.get("request-id")


                    time_alignments = audio.data.normalized_alignment
                    audio_bytes = base64.b64decode(audio.data.audio_base_64)
                    dub_audio = AudioSegment.from_file(io.BytesIO(audio_bytes))  # 读取配音音频段
                    dub_audio = dub_audio.set_frame_rate(samplerate)
                    res_audio = np.array(dub_audio.get_array_of_samples())
                    res_audio = res_audio.astype(np.float64) / 32768.0
                    res_audio = np.vstack([res_audio, res_audio]).T
                    res_frames = res_audio.shape[0]

                    if all_audio is None:   # all_audio用于记录所有生成的音频便于后续剪辑
                        all_audio = np.copy(res_audio)
                    else:
                        empty_array = np.zeros((44100, 2), dtype=res_audio.dtype)  # 1s间隔
                        all_audio = np.concatenate([all_audio, empty_array, res_audio])

                    print("-音频长度(s):", res_frames/samplerate)
                    print("-限定长度(s):", source_frames/samplerate)
                    if res_frames-source_frames >= 70000 and (res_frames/source_frames) >= 1.7:  # 超出1.6s且超出1.7倍
                        print("-超出长度1级: debug debug")
                        res_audio, time_alignments = self.trim_silence_remodify_time_alignments(res_audio,samplerate,time_alignments)
                        res_frames = res_audio.shape[0]
                        print("-二次校验的音频长度(s):", res_frames/samplerate)
                        if res_frames - source_frames >= 70000 and (res_frames / source_frames) >= 1.7:
                            print("-超出长度2级: debug debug")
                            circle = True  # 该句，重新进行生成
                            retry -= 1
                            if retry<=0:
                                print("-这句过于异常，取消配音")
                                break
                        else:
                            circle = False
                    else:
                        circle = False

                print("*时长判定结束")
                if request_id: previous_dict[role].append(request_id)
                speed = 1
                res_audio, characters, time_seconds = self.trim_silence_with_time_alignments(res_audio, time_alignments)
                res_frames = res_audio.shape[0]
                print("*去除首尾空音(s):",res_frames/samplerate)

                # 这里tolerance需要调整，如果下一句的role也是我自己，则tolerance需要进行强制桥准，不能以7000为标准
                next_sub_index = i+1
                next_start_offset = 7000

                if i+1<len(dubbing_subs_list):
                    next_sub = dubbing_subs_list[next_sub_index]
                    next_start_temp = int((self.time_str_to_ms(next_sub["start"]) * samplerate) / 1000)
                    off = next_start_temp-end
                    next_start_offset = max(off*0.95, off-4410)  #不能完全贴在一起吧，要不0.1s，要不0.95，选最大的，同一人的连续说话
                else:
                    next_start_offset = back_audio.shape[0]-end
                up_tolerance = [min(7000, next_start_offset), next_start_offset]  # 0是判定阈值，1是底线

                if res_frames - source_frames > up_tolerance[0]:  # 超出太多，就应该加速，大概冗余0.16s
                    speed = res_frames / (source_frames + up_tolerance[0])
                    print("^时长超出太多，应该加速:", speed)
                elif source_frames - res_frames > 7000:
                    speed = (res_frames+7000) / source_frames  # speed小于0，声音被拉长
                    print("^时长不够，应该减速:", speed)

                res_audio = self.adjust_speed(res_audio, speed, characters, time_seconds, source_frames, sr=samplerate, up_tolerance=up_tolerance)
                print("!全部调整结束，音频时间(s)", res_audio.shape[0]/samplerate)
                dubbing_duration = int((res_audio.shape[0] / samplerate) * 1000)
                dubbing_subtitle_entitys.append(
                    Subtitle(original_subtitle="", target_subtitle=subtitle["text"], start_time=start_str,
                             end_time=end_str, role_name=role, dubbing_duration=dubbing_duration,
                             voice_id=voice_id, api_id=1))
                end2 = min(start + res_audio.shape[0], len(target_voice_audio))
                target_voice_audio[start:end2] += res_audio[:end2 - start]
                # 更新 dubbing_subs 中对应的字幕 end 时间
                end2_ms = int((end2 * 1000) / samplerate)
                dubbing_subs[key]["end"] = ms_to_time_str(end2_ms)
                print("==**##&&==**##&&")

            target_voice_audio = target_voice_audio * 2  # 增强目标人声音量
            target_voice_audio = np.clip(target_voice_audio, -1.0, 1.0)

            back_audio += target_voice_audio


            output_audio_file = os.path.join(result_dir, "配音音频-人声+背景-{}.mp3".format(timestamp))
            target_voice_audio_path = os.path.join(result_dir, "配音音频-纯人声-{}.mp3".format(timestamp))
            target_initial_voice_audio_path = os.path.join(result_dir, "配音音频-纯人声无加速无对齐-{}.mp3".format(timestamp))
            output_video_file = os.path.join(result_dir, "视频-配音-{}.mp4".format(timestamp))
            target_subtitles_path = os.path.join(result_dir, "字幕-合并后的配音字幕.txt")
            modified_subtitles_path = os.path.join(result_dir, "字幕-cps.txt")
            modified_subtitles_path2 = os.path.join(result_dir, "字幕-cps+角色.txt")

            print(output_audio_file)
            print(output_video_file)
            sf.write(output_audio_file, back_audio, samplerate)
            sf.write(target_voice_audio_path, target_voice_audio, samplerate)
            sf.write(target_initial_voice_audio_path, all_audio, samplerate)
            self.merge_audio_video2(video_path, output_audio_file, output_video_file)
            try:
                with open(target_subtitles_path, "w", encoding="utf-8") as f:
                    for i, subtitle in enumerate(dubbing_subs.values()):
                        f.write(
                            f"{str(i)}\n{subtitle['start']} --> {subtitle['end']}\n{subtitle['role']}:{subtitle['text']}\n\n")
                if cps:
                    with open(modified_subtitles_path, 'w', encoding='utf-8') as f:
                        for subtitle in target_subs:
                            f.write(
                                f"{subtitle['index']}\n{subtitle['start']} --> {subtitle['end']}\n{subtitle['text']}\n\n")
                    with open(modified_subtitles_path2, 'w', encoding='utf-8') as f:
                        i = 0
                        for subtitle in target_subs:
                            f.write(
                                f"{subtitle['index']}\n{subtitle['start']} --> {subtitle['end']}\n{role_match_list[i]}:{subtitle['text']}\n\n")
                            i += 1
            except Exception as e:
                print(f"Error write subtitle: {e}")

            if delete:
                if "旁白" in voice_ids: voice_ids.pop("旁白")
                for key, value in voice_ids.items():
                    try:
                        if value:
                            self.connect.elevenlabs.voices.delete(voice_id=value,)
                    except Exception as e:
                        print(e, "删除该声音失败")


            return {"result_path": result_dir, "audio_file": output_audio_file, "video_file": output_video_file}
        except Exception as e:
            # 处理特定异常
            print(f"配音过程发生错误: {e}")
            traceback.print_exc()
            return {"error": f"配音过程发生错误: {e}"}

    def dubbing_new_split2(self, target_subs: list, role_match_list: list, video_path: str, voice_param: dict,
                          output_path: str = RESULT_OUTPUT_FOLDER, cps: str = "", on_progress=None,
                          delete=False) -> dict:
        '''
        delete 代表配音完是否删除克隆的声音
        '''
        if not os.path.exists(output_path):
            output_path = RESULT_OUTPUT_FOLDER
        timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        result_dir = os.path.join(output_path,
                                  "{}-视频一键配音结果-{}".format(os.path.basename(video_path).split('.')[0],
                                                                  timestamp))  # 创建一个文件夹
        os.makedirs(result_dir, exist_ok=True)

        try:
            video_audio, samplerate = get_audio_np_from_video(video_path)
            assert isinstance(video_audio, np.ndarray)
            back_audio = np.zeros_like(video_audio)
            # target_voice_audio = np.zeros_like(video_audio)  # 初始化目标人声音频
            all_audio = None
            print(back_audio.shape)
            video_audio_path = os.path.join(result_dir, "视频-原音频.mp3")
            sf.write(video_audio_path, video_audio, samplerate)

            if cps:
                if on_progress: on_progress(10, "调整字幕cps中...")
                target_subs, adjust_list, compressed_texts, adjust_indices = adjust_subtitles_cps(target_subs, int(cps),
                                                                                                  tolerate_factor)
            if on_progress: on_progress(20, "合并配音字幕中...")

            dubbing_subs1, subtitle_indices = LLMAPI2.getInstance().merge_subtitle_with_index(target_subs, role_match_list)
            if not dubbing_subs1: raise Exception("合并配音字幕出现错误")
            print(dubbing_subs1)
            # dubbing_subs = dubbing_subs1
            dubbing_subs = LLMAPI2.getInstance().correct_punctuation(dubbing_subs1)
            print(dubbing_subs)
            if not dubbing_subs: raise Exception("矫正字幕标点出现错误")

            if on_progress: on_progress(30, "角色干音分片中...")
            back_path, vocal_path = AudioPre.getInstance()._path_audio_(video_audio_path, output_path=result_dir)
            back_audio, _ = sf.read(back_path)
            target_voice_audio = np.zeros_like(back_audio)
            role_subtitles, vocal_audio, _, role_audio_path = split_roles_audio(dubbing_subs, vocal_path,
                                                                                output_path=result_dir)
            if on_progress:
                print("角色声音克隆中...")
                on_progress(35, "角色声音克隆中...")
            voice_ids = self.batch_clone_text(role_subtitles, role_audio_path, timestamp, voice_param)

            if on_progress:
                on_progress(40, "正在进行配音...")

            voice_setting = {"stability": 0.8, "similarity_boost": 0.9, "style": 0, "use_speaker_boost": True,
                             "speed": 1.0}
            previous_dict = {}
            role_set = set(role_match_list)
            for role in role_set:
                previous_dict[role] = []

            length = len(dubbing_subs)
            dubbing_subtitle_entitys = []
            dubbing_subs_list = list(dubbing_subs.values())
            for i, (key, subtitle) in enumerate(dubbing_subs.items()):
                if on_progress:
                    on_progress(min(40 + int((i * 56) / length), 100), "")

                print(subtitle)
                role = subtitle["role"]
                start_str = subtitle["start"]
                end_str = subtitle["end"]
                text = subtitle["text"]
                voice_id = voice_ids[role] if role in voice_ids else "JBFqnCBsd6RMkjVDRZzb"
                if not voice_id or voice_id == "-1":
                    continue

                start = int((self.time_str_to_ms(start_str) * samplerate) / 1000)
                end = int((self.time_str_to_ms(end_str) * samplerate) / 1000)
                circle = True  # 是否进行循环
                retry = 3
                source_frames = end - start
                res_audio = None
                request_id = None
                time_alignments = None

                # language_code = "id",
                while circle and retry > 0:
                    audio = self.connect.elevenlabs.text_to_speech.with_raw_response.convert_with_timestamps(
                        text=text,
                        voice_id=voice_id,
                        model_id="eleven_multilingual_v2",
                        output_format="mp3_44100_192",)
                        # voice_settings=voice_setting,
                        # previous_request_ids=previous_dict[role][-3:])


                    time_alignments = audio.data.normalized_alignment
                    audio_bytes = base64.b64decode(audio.data.audio_base_64)
                    dub_audio = AudioSegment.from_file(io.BytesIO(audio_bytes))  # 读取配音音频段
                    dub_audio = dub_audio.set_frame_rate(samplerate)
                    res_audio = np.array(dub_audio.get_array_of_samples())
                    res_audio = res_audio.astype(np.float64) / 32768.0
                    res_audio = np.vstack([res_audio, res_audio]).T
                    res_frames = res_audio.shape[0]

                    if all_audio is None:  # all_audio用于记录所有生成的音频便于后续剪辑
                        all_audio = np.copy(res_audio)
                    else:
                        empty_array = np.zeros((44100, 2), dtype=res_audio.dtype)  # 1s间隔
                        all_audio = np.concatenate([all_audio, empty_array, res_audio])

                    print("-音频长度(s):", res_frames / samplerate)
                    print("-限定长度(s):", source_frames / samplerate)
                    if res_frames - source_frames >= 60000 and (res_frames / source_frames) >= 1.8:  # 超出1.36s且超出1.8倍
                        print("-超出长度1级: debug debug")
                        circle = True
                        retry -= 1
                        if retry <= 0:
                            print("-这句过于异常，取消配音")
                            break
                    else:
                        request_id = audio._response.headers.get("request-id")   # 重新配音时，不要修改requestid
                        circle = False

                print("*时长判定结束")
                if request_id: previous_dict[role].append(request_id)
                speed = 1
                res_audio, characters, time_seconds = self.trim_silence_with_time_alignments(res_audio, time_alignments, rate=0.2)
                res_frames = res_audio.shape[0]
                print("*去除首尾空音(s):", res_frames / samplerate)

                # 这里tolerance需要调整，如果下一句的role也是我自己，则tolerance需要进行强制桥准，不能以7000为标准
                # next_sub_index = i + 1
                # next_start_offset = 7000
                #
                # if i + 1 < len(dubbing_subs_list):
                #     next_sub = dubbing_subs_list[next_sub_index]
                #     next_start_temp = int((self.time_str_to_ms(next_sub["start"]) * samplerate) / 1000)
                #     off = next_start_temp - end
                #     next_start_offset = max(off * 0.95, off - 4410)  # 不能完全贴在一起吧，要不0.1s，要不0.95，选最大的，同一人的连续说话
                # else:
                #     next_start_offset = back_audio.shape[0] - end
                # up_tolerance = [min(7000, next_start_offset), next_start_offset]  # 0是判定阈值，1是底线
                #
                # if res_frames - source_frames > up_tolerance[0]:  # 超出太多，就应该加速，大概冗余0.16s
                #     speed = res_frames / (source_frames + up_tolerance[0])
                #     print("^时长超出太多，应该加速:", speed)
                # elif source_frames - res_frames > 7000:
                #     speed = (res_frames + 7000) / source_frames  # speed小于0，声音被拉长
                #     print("^时长不够，应该减速:", speed)

                speed = res_frames / source_frames
                res_audio = self.adjust_speed2(res_audio, characters, time_seconds, source_frames, sr=samplerate, subtitle = subtitle, index=i, target_subtitles = target_subs, subtitle_indices = subtitle_indices)

                # res_audio = self.adjust_speed(res_audio, speed, characters, time_seconds, source_frames, sr=samplerate,
                #                               up_tolerance=up_tolerance)
                print("!全部调整结束，音频时间(s)", res_audio.shape[0] / samplerate)
                dubbing_duration = int((res_audio.shape[0] / samplerate) * 1000)
                dubbing_subtitle_entitys.append(
                    Subtitle(original_subtitle="", target_subtitle=subtitle["text"], start_time=start_str,
                             end_time=end_str, role_name=role, dubbing_duration=dubbing_duration,
                             voice_id=voice_id, api_id=1))
                end2 = min(start + res_audio.shape[0], len(target_voice_audio))
                target_voice_audio[start:end2] += res_audio[:end2 - start]
                # 更新 dubbing_subs 中对应的字幕 end 时间
                end2_ms = int((end2 * 1000) / samplerate)
                dubbing_subs[key]["end"] = ms_to_time_str(end2_ms)
                print("==**##&&==**##&&")

            target_voice_audio = target_voice_audio * 2  # 增强目标人声音量
            target_voice_audio = np.clip(target_voice_audio, -1.0, 1.0)

            back_audio += target_voice_audio

            output_audio_file = os.path.join(result_dir, "配音音频-人声+背景-{}.mp3".format(timestamp))
            target_voice_audio_path = os.path.join(result_dir, "配音音频-纯人声-{}.mp3".format(timestamp))
            target_initial_voice_audio_path = os.path.join(result_dir,
                                                           "配音音频-纯人声无加速无对齐-{}.mp3".format(timestamp))
            output_video_file = os.path.join(result_dir, "视频-配音-{}.mp4".format(timestamp))
            target_subtitles_path = os.path.join(result_dir, "字幕-合并后的配音字幕.txt")
            modified_subtitles_path = os.path.join(result_dir, "字幕-cps.txt")
            modified_subtitles_path2 = os.path.join(result_dir, "字幕-cps+角色.txt")
            copyed_video_path = os.path.join(result_dir, "{}-原视频.mp4".format(os.path.basename(video_path).split('.')[0]))


            print(output_audio_file)
            print(output_video_file)
            sf.write(output_audio_file, back_audio, samplerate)
            sf.write(target_voice_audio_path, target_voice_audio, samplerate)
            sf.write(target_initial_voice_audio_path, all_audio, samplerate)
            self.merge_audio_video2(video_path, output_audio_file, output_video_file)
            self.merge_audio_video2(video_path, video_audio_path, copyed_video_path)

            try:
                with open(target_subtitles_path, "w", encoding="utf-8") as f:
                    for i, subtitle in enumerate(dubbing_subs.values(), start=1):
                        f.write(
                            f"{str(i)}\n{subtitle['start']} --> {subtitle['end']}\n{subtitle['role']}:{subtitle['text']}\n\n")
                if cps:
                    with open(modified_subtitles_path, 'w', encoding='utf-8') as f:
                        for subtitle in target_subs:
                            f.write(
                                f"{subtitle['index']}\n{subtitle['start']} --> {subtitle['end']}\n{subtitle['text']}\n\n")
                    with open(modified_subtitles_path2, 'w', encoding='utf-8') as f:
                        i = 0
                        for subtitle in target_subs:
                            f.write(
                                f"{subtitle['index']}\n{subtitle['start']} --> {subtitle['end']}\n{role_match_list[i]}:{subtitle['text']}\n\n")
                            i += 1
            except Exception as e:
                print(f"Error write subtitle: {e}")

            if delete:
                if "旁白" in voice_ids: voice_ids.pop("旁白")
                for key, value in voice_ids.items():
                    try:
                        if value:
                            self.connect.elevenlabs.voices.delete(voice_id=value, )
                    except Exception as e:
                        print(e, "删除该声音失败")

            self.save_project(original_video_path=copyed_video_path, original_voice_audio_path=vocal_path,
                              original_bgm_audio_path=back_path, target_voice_audio_path=target_voice_audio_path,
                              target_dubbing_audio_path=output_audio_file, target_video_path=output_video_file,
                              dubbing_subtitles=dubbing_subtitle_entitys)

            # 保存voice_ids到JSON文件
            voice_ids_path = os.path.join(result_dir, "voice_ids.json")
            try:
                with open(voice_ids_path, "w", encoding="utf-8") as f:
                    json.dump(voice_ids, f, ensure_ascii=False, indent=2)
                print(f"voice_ids已保存到: {voice_ids_path}")
            except Exception as e:
                print(f"保存voice_ids文件失败: {e}")

            return {"result_path": result_dir, "audio_file": output_audio_file, "video_file": output_video_file}
        except Exception as e:
            # 处理特定异常
            print(f"配音过程发生错误: {e}")
            traceback.print_exc()
            return {"error": f"配音过程发生错误: {e}"}



    def judge_conn(self, time, state: bool, text: str):
        """
        0.代表无条件连接
        1.消耗连接次数
        2.无条件拒绝连接
        """
        token_len = len(self.tokenizer.encode(text))
        print("毫秒差值：", time)
        if token_len >= 36:
            print(token_len)
            return 2
        if time < 240:
            return 0
        elif time < 360 and state:
            return 1
        elif time < 600 and state:
            if token_len <= 7:
                return 1
        return 2

    def merge_audio_video2(self, video_path: str, audio_path: str, output_path: str):
        # 加载视频（自动丢弃原音频）
        video_stream = ffmpeg.input(video_path)
        audio_stream = ffmpeg.input(audio_path)

        # 合成并输出
        ffmpeg.output(video_stream.video, audio_stream.audio, output_path,
                      vcodec='copy', acodec='aac', shortest=None).run()

    def batch_clone_text(self, role_subtitles: dict, role_audio_path: dict, timestamp: str, voice_param: dict) -> dict:
        # role_texts = {}
        voice_ids = voice_param.copy()
        print(voice_ids)
        db_connect = datasetUtils.getInstance()
        for key in role_subtitles.keys():
            if not voice_ids[key]:
                voice_id = self.clone_text(key, role_audio_path[key], timestamp)
                voice_ids[key] = voice_id
                db_connect.save_voice_id_withtime(api_id=1, voice_name="{}-{}".format(key, timestamp),
                                                  voice_id=voice_id, create_time=int(time.time()))
        return voice_ids

    def get_audio_duration_for_target_size(self, audio_path: str, target_size_bytes: int) -> float:
        """
        通过二分查找，计算出能使WAV文件大小最接近但不超过 target_size_bytes 的最大时长（秒）。
        """
        audio = AudioSegment.from_wav(audio_path)
        original_duration_ms = len(audio)
        original_file_size = os.path.getsize(audio_path)

        if original_file_size <= target_size_bytes:
            return original_duration_ms / 1000.0  # 返回原始时长（秒）

        # WAV是无损格式，文件大小与时长基本成线性关系
        # 估算一个初始的裁剪时长
        estimated_duration_ms = int((target_size_bytes / original_file_size) * original_duration_ms)

        # 确保不会超过原始长度
        estimated_duration_ms = min(estimated_duration_ms, original_duration_ms)

        # 为了更精确，可以简单地按比例裁剪
        # 对于大多数情况，这已经足够精确
        return estimated_duration_ms / 1000.0

    def clone_text(self, key: str, audio_path: str, timestamp: str):
        MAX_FILE_SIZE_BYTES = 8 * 1024 * 1024  # 8 MB
        # --- 新增：检查并裁剪文件 ---
        file_size = os.path.getsize(audio_path)
        if file_size > MAX_FILE_SIZE_BYTES:
            print(f"Audio file is {file_size / (1024 * 1024):.2f} MB, larger than 8MB. Trimming...")
            target_duration_sec = self.get_audio_duration_for_target_size(audio_path, MAX_FILE_SIZE_BYTES)
            audio = AudioSegment.from_wav(audio_path)
            trimmed_audio = audio[:int(target_duration_sec * 1000)]  # pydub 使用毫秒

            # 将裁剪后的音频保存到内存中的字节流
            audio_buffer = io.BytesIO()
            trimmed_audio.export(audio_buffer, format="wav")
            audio_buffer.seek(0)
            audio_files = [audio_buffer]
        else:
            # 文件大小符合要求，直接读取
            audio_files = [io.BytesIO(open(audio_path, "rb").read())]
        # --- 裁剪逻辑结束 ---

        voice = self.connect.elevenlabs.voices.ivc.create(
            name="{}-{}".format(key, timestamp),
            files=audio_files
        )
        print(voice)
        return voice.voice_id

    def clone_text_cast(self, key: str, audio_path: str, timestamp: str):
        voice = self.connect.elevenlabs.voices.ivc.create(
            name="{}-{}".format(key, timestamp),
            # Replace with the paths to your audio files.
            # The more files you add, the better the clone will be.
            files=[io.BytesIO(open(audio_path, "rb").read())]
        )
        print(voice)
        return voice.voice_id

    def adjust_speed(self, input_audio: np.ndarray, speed:float, characters:list, time_seconds:list, target_frames:int, sr=44100, up_tolerance=None):
        if up_tolerance is None:
            up_tolerance = [7000, 7000]
        res_audio = copy.deepcopy(input_audio)
        time_seconds = np.array(time_seconds)
        if speed == 1:
            return res_audio
        use_speed = speed
        if speed > 1.15:
            print("!加速容忍值：", up_tolerance)
            mask = np.ones(res_audio.shape[0], dtype=bool)
            for i in range(len(characters)):
                if characters[i] == " " and i < len(time_seconds) - 1:
                    start_time = time_seconds[i]
                    end_time = time_seconds[i + 1]

                    start_frame = int(start_time * sr)
                    end_frame = int(end_time * sr)
                    duration_frames = end_frame - start_frame

                    remove_frames = int(duration_frames * 0.8)
                    if remove_frames > 0:
                        center_frame = (start_frame + end_frame) // 2
                        half_remove = remove_frames // 2
                        remove_start = max(start_frame, center_frame - half_remove)
                        remove_end = min(end_frame, center_frame + half_remove)
                        # 标记该范围为False
                        mask[remove_start:remove_end] = False
            res_audio = res_audio[mask]
            print("!加速调整后时长(s):", res_audio.shape[0]/sr )
            speed_up1 = res_audio.shape[0]/(target_frames+up_tolerance[0])  # 一般加速比
            speed_up2 = res_audio.shape[0]/(target_frames+up_tolerance[1])  # 这个是最小加速比，加速必须超过这个
            if up_tolerance[0] < up_tolerance[1]: # 说明speed_up1肯定是大于speed_up2的
                if 1.28 >= speed_up2:
                    use_speed = min(speed_up1, 1.28)
                else:
                    use_speed = min(speed_up1, speed_up2)
            else:
                use_speed = speed_up1
            print("!三者数据:", speed_up1, speed_up2, 1.28)
            print("!加速后--speed", use_speed)
        elif speed>=0.96:
            print("!阈值内--speed", use_speed)
            pass
        elif speed >= 0.92:
            use_speed = 0.96
            print("!减速后1--speed", use_speed)
        else:
            use_speed = max(use_speed, 0.92)
            print("!减速后2--speed", use_speed)


        res_audio_mono = res_audio[:, 0]  # 取单声道
        original_rms = librosa.feature.rms(y=res_audio_mono)[0].mean()
        res_audio_stretched = librosa.effects.time_stretch(res_audio_mono, rate=use_speed)
        res_audio_stretched = res_audio_stretched * (
                original_rms / (librosa.feature.rms(y=res_audio_stretched)[0].mean() + 1e-6))  # 恢复到原音量
        res_audio_stretched = np.vstack([res_audio_stretched, res_audio_stretched]).T
        res_audio = res_audio_stretched
        return res_audio






if __name__ == '__main__':
    eleven = dubbingElevenLabs3.getInstance()
    # eleven.connect.elevenlabs.voices.delete(voice_id="-1")
    audio = eleven.connect.elevenlabs.text_to_speech.with_raw_response.convert_with_timestamps(
        text="这是一个非常奇怪的句子！——~~~，iwant to know if any chars can be record, even the * & word is wrongr。。。.. 😅 ✅ ś(❁´◡`❁)  \n สวัสดี ขอบคุณ  sa-wat-dii Teşekkür ederim.  Привет Cześć Спасибо.  شكرا   啊啊 مرحبا",
        voice_id="JBFqnCBsd6RMkjVDRZzb",
        model_id="eleven_multilingual_v2",
        output_format="mp3_44100_128",
    )
    request_id = audio._response.headers.get("request-id")
    data = audio.data
    time_alignments = audio.data.normalized_alignment

    from elevenlabs import play
    play(base64.b64decode(audio.data.audio_base_64))
