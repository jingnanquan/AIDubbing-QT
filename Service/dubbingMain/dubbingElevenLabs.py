import datetime
import io
import os
import traceback

# 延迟导入重量级库
import librosa
import numpy as np
import soundfile as sf
import time
import ffmpeg
from pydub import AudioSegment

from Config import RESULT_OUTPUT_FOLDER
from Service.ccTest import API_KEY_ElevenLabs
from ProjectCompoment.dubbingEntity import Subtitle
from Service.datasetUtils import datasetUtils
from Service.dubbingMain.dubbingInterface import dubbingInterface
from Service.dubbingMain.llmAPI import LLMAPI
from Service.generalUtils import calculate_time, get_result_path
from Service.generalUtils2 import decrypt_string
from Service.videoUtils import get_audio_zeronp_from_video


class dubbingElevenLabs(dubbingInterface):
    """
    dubbingMiniMax类，继承自dubbingInterface
    这个类是典型的配音类，可以有多个api或自定义实现。
    主要的函数为传入音频文件和字幕文件
    音频的文件会截取，并生成每个role的音频文件
    通过api克隆角色语音，clone完成后。
    根据字幕的时间戳，逐级生成语音
    """
    _instance = None
    _elevenlabs_client = None
    _tokenizer = None

    @calculate_time
    def __init__(self):
        super().__init__()
        print("elevenlabs初始化中")
        # 延迟初始化，不在构造函数中立即创建客户端
        self._initialized = False

    def _ensure_initialized(self):
        """确保ElevenLabs客户端已初始化"""
        if not self._initialized:
            self._initialize_client()
            self._initialized = True

    def _initialize_client(self):
        """实际初始化ElevenLabs客户端"""
        try:
            from elevenlabs.client import ElevenLabs
            import tiktoken
            
            self._elevenlabs_client = ElevenLabs(
                api_key=decrypt_string(API_KEY_ElevenLabs, "AIDubbing"),
            )
            self._tokenizer = tiktoken.encoding_for_model("gpt-3.5-turbo")
            print("ElevenLabs客户端初始化完成")
        except Exception as e:
            print(f"ElevenLabs客户端初始化失败: {e}")
            raise

    @property
    def elevenlabs(self):
        """获取ElevenLabs客户端，延迟初始化"""
        self._ensure_initialized()
        return self._elevenlabs_client

    @property
    def tokenizer(self):
        """获取tokenizer，延迟初始化"""
        self._ensure_initialized()
        return self._tokenizer

    def voice_isolate(self, origin_audio_path, vocal_path: str):
        """
        人声分离
        """
        try:
            
            audio_data = io.BytesIO(open(origin_audio_path, "rb").read())
            vocal_audio_data = self.elevenlabs.audio_isolation.convert(audio=audio_data)

            audio_bytes = b''.join(vocal_audio_data)
            dub_audio = AudioSegment.from_file(io.BytesIO(audio_bytes))  # 读取配音音频段
            dub_audio = dub_audio.set_frame_rate(44100)
            res_audio = np.array(dub_audio.get_array_of_samples())
            res_audio = res_audio.astype(np.float64) / 32768.0
            res_audio = np.vstack([res_audio, res_audio]).T  # 变为双声道

            sf.write(vocal_path, res_audio, 44100)
            return True
        except Exception as e:
            print(f"人声分离过程发生错误: {e}")
            return False

    def video_voice_isolate(self, origin_video_path, vocal_path: str):
        
        audio = AudioSegment.from_file(origin_video_path)
        # 将音频数据转为 WAV 格式的字节流
        audio_data = io.BytesIO()
        audio.export(audio_data, format="wav")  # 写入内存字节流
        audio_data.seek(0)  # 重置指针以便后续读取

        vocal_audio_data = self.elevenlabs.audio_isolation.convert(audio=audio_data)

        audio_bytes = b''.join(vocal_audio_data)
        dub_audio = AudioSegment.from_file(io.BytesIO(audio_bytes))  # 读取配音音频段
        dub_audio = dub_audio.set_frame_rate(44100)
        res_audio = np.array(dub_audio.get_array_of_samples())
        res_audio = res_audio.astype(np.float64) / 32768.0
        res_audio = np.vstack([res_audio, res_audio]).T  # 变为双声道

        sf.write(vocal_path, res_audio, 44100)


    def dubbing_end_to_end(self, video_path: str, target_lang: str) -> dict:
        try:
            
            audio_data = io.BytesIO(open(video_path, "rb").read())
            print(audio_data)
            audio_data.name = os.path.basename(video_path)
            print(audio_data.name)
            print("read success")
            dubbed = self.elevenlabs.dubbing.create(
                file=audio_data, target_lang=target_lang
            )
            print("submit api")
            while True:
                status = self.elevenlabs.dubbing.get(dubbed.dubbing_id).status
                print(status)
                if status == "dubbed":
                    dubbed_file = self.elevenlabs.dubbing.audio.get(dubbed.dubbing_id, target_lang)
                    output_video_file = get_result_path(
                        "视频-配音-{}.mp4".format(datetime.datetime.now().strftime("%Y%m%d-%H%M%S")))
                    print(output_video_file)
                    with open(output_video_file, "wb") as f:
                        for chunk in dubbed_file:
                            if chunk:
                                f.write(chunk)
                    return {"video_file": output_video_file}
                else:
                    print("Video is still being dubbed...")
                    time.sleep(5)
        except Exception as e:
            print(f"配音过程发生错误: {e}")
            return {"error": f"配音过程发生错误: {e}"}

    def directed_dubbing(self, target_subs: list, role_match_list: list, video_path: str, voice_param: dict, on_progress=None):
        ## 这里为直接配音
        print(voice_param)
        if on_progress:
            on_progress(20, "背景声音处理中...")
        timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        back_audio, samplerate = get_audio_zeronp_from_video(video_path)
        left = 0
        right = 0
        
        # 延迟导入
        import time
        time1 = time.time()
        
        try:
            while right < len(target_subs):
                role = role_match_list[left]
                start = target_subs[left]['start']
                left_end = self.time_str_to_ms(target_subs[left]['end'])  # 获得毫秒数
                text = ""
                can_conn = True
                while right < len(target_subs):
                    if role_match_list[right] != role:
                        break
                    right_start = self.time_str_to_ms(target_subs[right]['start'])
                    state = self.judge_conn(right_start - left_end, can_conn, text)
                    if state != 2:
                        text += target_subs[right]['text'] + ','
                        left_end = self.time_str_to_ms(target_subs[right]['end'])  # 获得毫秒数
                        right += 1
                        if state == 1:
                            can_conn = False
                    else:
                        break
                end = target_subs[right - 1]['end']  # 还需要检查时间是否连续
                print(role, start, end, text)
                if on_progress:
                    on_progress(min(20+int((right*86)/len(target_subs)), 100), "")
                audio = self.elevenlabs.text_to_speech.convert(
                    text=text,
                    voice_id=voice_param[role] if role in voice_param else "JBFqnCBsd6RMkjVDRZzb",
                    model_id="eleven_multilingual_v2",
                    output_format="mp3_44100_128",
                )
                audio_bytes = b''.join(audio)
                dub_audio = AudioSegment.from_file(io.BytesIO(audio_bytes))
                dub_audio = dub_audio.set_frame_rate(samplerate)
                res_audio = np.array(dub_audio.get_array_of_samples())
                res_audio = res_audio.astype(np.float64) / 32768.0
                res_audio = np.vstack([res_audio, res_audio]).T
                start = int((self.time_str_to_ms(start) * samplerate) / 1000)
                if start + res_audio.shape[0] > back_audio.shape[0]:  # 那肯定需要截断
                    break
                back_audio[start:start + res_audio.shape[0]] += res_audio
                left = right
            if on_progress:
                on_progress(98, "保存文件中...")
            output_audio_file = get_result_path("音频-配音-{}.mp3".format(timestamp))
            output_video_file = get_result_path("视频-配音-{}.mp4".format(timestamp))
            print(output_audio_file)
            sf.write(output_audio_file, back_audio, samplerate)
            self.merge_audio_video2(video_path, output_audio_file, output_video_file)
            time2 = time.time()
            print("配音完成，耗时: {}秒".format(time2 - time1))
            return {"audio_file": output_audio_file, "video_file": output_video_file}
        except Exception as e:
            # 处理特定异常
            print(f"配音过程发生错误: {e}")
            return {"error": f"配音过程发生错误: {e}"}

        pass

    def dubbing(self, vocal_path: str, back_path: str, subtitles: list, target_subs: list, role_match_list: list,
                video_path: str,
                voice_param: dict, on_progress=None) -> dict:
        """
        处理音频和字幕
        传入的路径必是已经处理过的
        该函数为自定义的配音流程，包含了人声分离、裁剪、clone、tts、拼接全流程。
        注意职责分离，
        所有的role_match_list均是采用数组调用，要确保role_match_list长度大于等于subs，不越界
        """
        # 延迟导入
        
        # if not self.validate_inputs(vocal_path, back_path):
        #     return {"error": "Invalid input files."}
        back_audio, samplerate = sf.read(back_path)
        print(back_audio.shape)

        try:
            # 以role为key的字幕、原始音频、采样率、角色音频路径
            if on_progress:
                on_progress(25, "角色干音分片中...")
            role_subtitles, vocal_audio, _, role_audio_path = self.parse_roles_numpy_separate(subtitles,
                                                                                              role_match_list,
                                                                                              vocal_path, voice_param)
            timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
            if on_progress:
                on_progress(30, "角色声音克隆中...")
            voice_ids = self.batch_clone_text(role_subtitles, role_audio_path, timestamp, voice_param)
        except Exception as e:
            print(f"克隆过程发生错误: {e}")
            return {"error": f"克隆过程发生错误: {e}"}

        if on_progress:
            on_progress(40, "正在进行配音...")
        left = 0
        right = 0
        time1 = time.time()
        try:
            while right < len(target_subs):
                role = role_match_list[left]
                start = target_subs[left]['start']
                left_end = self.time_str_to_ms(target_subs[left]['end'])  # 获得毫秒数
                text = ""
                can_conn = True
                while right < len(target_subs):
                    if role_match_list[right] != role:
                        break
                    right_start = self.time_str_to_ms(target_subs[right]['start'])
                    state = self.judge_conn(right_start - left_end, can_conn, text)
                    if state != 2:
                        text += target_subs[right]['text'] + ','
                        left_end = self.time_str_to_ms(target_subs[right]['end'])  # 获得毫秒数
                        right += 1
                        if state == 1:
                            can_conn = False
                    else:
                        break
                end = target_subs[right - 1]['end']  # 还需要检查时间是否连续
                print(role, start, end, text)
                if on_progress:
                    on_progress(min(40+int((right*56)/len(target_subs)), 100), "")
                audio = self.elevenlabs.text_to_speech.convert(
                    text=text,
                    voice_id=voice_ids[role] if role in voice_ids else "JBFqnCBsd6RMkjVDRZzb",
                    model_id="eleven_multilingual_v2",
                    output_format="mp3_44100_128",
                )
                audio_bytes = b''.join(audio)
                dub_audio = AudioSegment.from_file(io.BytesIO(audio_bytes))
                dub_audio = dub_audio.set_frame_rate(samplerate)
                res_audio = np.array(dub_audio.get_array_of_samples())
                res_audio = res_audio.astype(np.float64) / 32768.0
                res_audio = np.vstack([res_audio, res_audio]).T
                start = int((self.time_str_to_ms(start) * samplerate) / 1000)
                if start + res_audio.shape[0] > back_audio.shape[0]:  # 那这里肯定出了问题
                    break
                back_audio[start: start + res_audio.shape[0]] += res_audio
                left = right
            if on_progress:
                on_progress(98, "保存文件中...")
            output_audio_file = get_result_path("音频-配音-{}.mp3".format(timestamp))
            output_video_file = get_result_path("视频-配音-{}.mp4".format(timestamp))
            print(output_audio_file)
            print(output_video_file)
            sf.write(output_audio_file, back_audio, samplerate)
            self.merge_audio_video2(video_path, output_audio_file, output_video_file)
            time2 = time.time()
            print("配音完成，耗时: {}秒".format(time2 - time1))
            return {"audio_file": output_audio_file, "video_file": output_video_file}
        except Exception as e:
            # 处理特定异常
            print(f"配音过程发生错误: {e}")
            output_audio_file = get_result_path("音频-配音-错误保留{}.mp3".format(timestamp))
            sf.write(output_audio_file, back_audio, samplerate)
            return {"audio_file": output_audio_file, "error": f"配音过程发生错误: {e}"}



    def dubbing_high_quality(self, vocal_path: str, back_path: str, subtitles: list, target_subs: list, role_match_list: list,video_path: str, voice_param: dict, on_progress=None) -> dict:
        '''
        我在这里加上了当前配音的前两句，以提高生成的稳定性, 但是其实是基于音素切分的，它实际上是生成了更长的音频，然后裁剪的
        '''
        back_audio, samplerate = sf.read(back_path)
        assert isinstance(back_audio, np.ndarray)
        target_voice_audio = np.zeros_like(back_audio)  # 初始化目标人声音频
        print(back_audio.shape)

        try:
            # 以role为key的字幕、原始音频、采样率、角色音频路径
            if on_progress:
                on_progress(25, "角色干音分片中...")
            role_subtitles, vocal_audio, _, role_audio_path = self.parse_roles_numpy_separate(subtitles,
                                                                                              role_match_list,
                                                                                              vocal_path, voice_param)
            timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
            if on_progress:
                on_progress(30, "角色声音克隆中...")
            voice_ids = self.batch_clone_text(role_subtitles, role_audio_path, timestamp, voice_param)
        except Exception as e:
            print(f"克隆过程发生错误: {e}")
            return {"error": f"克隆过程发生错误: {e}"}

        if on_progress:
            on_progress(40, "正在进行配音...")
        left = 0
        right = 0
        previous1 = ""
        previous2 = ""
        dubbing_subtitle_entitys = []
        voice_setting = {"stability": 0.6, "similarity_boost": 0.75, "style": 0.15, "use_speaker_boost": True, "speed": 1.0}
        time1 = time.time()
        try:
            while right < len(target_subs):
                role = role_match_list[left]
                start = target_subs[left]['start']
                left_end = self.time_str_to_ms(target_subs[left]['end'])  # 获得毫秒数
                text = ""
                origin_text = ""
                can_conn = True
                while right < len(target_subs):
                    if role_match_list[right] != role:
                        break
                    right_start = self.time_str_to_ms(target_subs[right]['start'])
                    state = self.judge_conn(right_start - left_end, can_conn, text)
                    if state != 2:
                        text += target_subs[right]['text'] + ','
                        origin_text += subtitles[right]['text'] + ','
                        left_end = self.time_str_to_ms(target_subs[right]['end'])  # 获得毫秒数
                        right += 1
                        if state == 1:
                            can_conn = False
                    else:
                        break
                end = target_subs[right - 1]['end']  # 还需要检查时间是否连续

                start_str = start
                end_str = end
                start = int((self.time_str_to_ms(start) * samplerate) / 1000)
                end = int((self.time_str_to_ms(end) * samplerate) / 1000)
                print(role, start, end, text)
                if on_progress:
                    on_progress(min(40+int((right*56)/len(target_subs)), 100), "")
                audio = self.elevenlabs.text_to_speech.convert(
                    text=text,
                    voice_id=voice_ids[role] if role in voice_ids else "JBFqnCBsd6RMkjVDRZzb",
                    model_id="eleven_multilingual_v2",
                    output_format="mp3_44100_128",
                    voice_settings= voice_setting,
                    previous_text = previous1+" "+previous2
                )
                audio_bytes = b''.join(audio)
                dub_audio = AudioSegment.from_file(io.BytesIO(audio_bytes)) # 读取配音音频段
                dub_audio = dub_audio.set_frame_rate(samplerate)
                res_audio = np.array(dub_audio.get_array_of_samples())
                res_audio = res_audio.astype(np.float64) / 32768.0
                res_audio = self.trim_silence(res_audio, samplerate)  # 去除静音段
                res_audio = np.vstack([res_audio, res_audio]).T  # 在变为双声道之前，先去除收尾的空


                source_frames = end-start
                res_frames = res_audio.shape[0]
                if res_frames - source_frames > 7000:  # 超出太多，就应该加速，大概冗余0.16s
                    print("时长超出太多，应该加速")
                    speed = res_frames / (source_frames+7000)
                    # 使用librosa加速音频
                    res_audio_mono = res_audio[:, 0]  # 取单声道
                    original_rms = librosa.feature.rms(y=res_audio_mono)[0].mean()
                    res_audio_stretched = librosa.effects.time_stretch(res_audio_mono, rate = speed)
                    res_audio_stretched = res_audio_stretched * (original_rms / (librosa.feature.rms(y=res_audio_stretched)[0].mean() + 1e-6))  # 恢复到原音量
                    # 保持双声道
                    res_audio_stretched = np.vstack([res_audio_stretched, res_audio_stretched]).T
                    res_audio = res_audio_stretched
                dubbing_duration = int((res_audio.shape[0]/samplerate)*1000)
                dubbing_subtitle_entitys.append(
                    Subtitle(original_subtitle=origin_text, target_subtitle=text, start_time=start_str,
                             end_time=end_str, role_name=role, dubbing_duration=dubbing_duration,
                             voice_id=voice_ids[role] if role in voice_ids else "JBFqnCBsd6RMkjVDRZzb", api_id=1))
                if start + res_audio.shape[0] > back_audio.shape[0]:  # 那这里肯定出了问题
                    target_voice_audio[start: back_audio.shape[0]] += res_audio[:back_audio.shape[0] - start]
                target_voice_audio[start: start + res_audio.shape[0]] += res_audio
                left = right
                previous1 = previous2
                previous2 = text
            if on_progress:
                on_progress(98, "保存文件中...")
            target_voice_audio = target_voice_audio*2  # 增强目标人声音量
            target_voice_audio = np.clip(target_voice_audio, -1.0, 1.0)

            back_audio+=target_voice_audio
            output_audio_file = get_result_path("音频-配音-{}.mp3".format(timestamp))
            target_voice_audio_path = get_result_path("音频-目标人声-{}.mp3".format(timestamp))
            output_video_file = get_result_path("视频-配音-{}.mp4".format(timestamp))
            print(output_audio_file)
            print(output_video_file)
            sf.write(output_audio_file, back_audio, samplerate)
            sf.write(target_voice_audio_path, target_voice_audio, samplerate)
            self.merge_audio_video2(video_path, output_audio_file, output_video_file)
            time2 = time.time()
            print("配音完成，耗时: {}秒".format(time2 - time1))

            # 我只在成功的时候进行保存，并且这个
            self.save_project(original_video_path=video_path, original_voice_audio_path=vocal_path, original_bgm_audio_path=back_path, target_voice_audio_path= target_voice_audio_path, target_dubbing_audio_path=output_audio_file, target_video_path=output_video_file, dubbing_subtitles=dubbing_subtitle_entitys)

            return {"audio_file": output_audio_file, "video_file": output_video_file}
        except Exception as e:
            # 处理特定异常
            print(f"配音过程发生错误: {e}")
            traceback.print_exc()
            output_audio_file = get_result_path("音频-配音-错误保留{}.mp3".format(timestamp))
            sf.write(output_audio_file, back_audio, samplerate)
            return {"audio_file": output_audio_file, "error": f"配音过程发生错误: {e}"}

    def dubbing_without_clone(self, target_subs: list, role_match_list: list, voice_param: dict, modified_subs: list[list], on_progress=None) -> dict:
        '''
        跟原音视频无关，直接调用api和声音
        '''
        print("====进入配音====")
        print(self.elevenlabs.models.list())
        print(target_subs)
        print(role_match_list)
        print(voice_param)
        timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")

        try:
            if on_progress:
                on_progress(25, "合并角色配音字幕中...")
            role_subs = ""
            i = 0
            for subtitle in target_subs:
                role_subs += f"""{subtitle["index"]} | {subtitle["start"]} --> {subtitle["end"]} | {subtitle["text"]} | {role_match_list[i]}\n"""
                i += 1

            dubbing_subs = LLMAPI.getInstance().merge_subtitle(role_subs)
            print(dubbing_subs)
            if not dubbing_subs: raise Exception("合并角色配音字幕错误")

            if on_progress:
                on_progress(40, "正在进行配音...")

            voice_setting = {"stability": 0.6, "similarity_boost": 0.75, "style": 0.15, "use_speaker_boost": True,
                             "speed": 1.0}

            previous_dict = {}
            role_set = set(role_match_list)
            for role in role_set:
                previous_dict[role] = ""

            length = len(dubbing_subs)
            all_audio = None
            for i, subtitle in enumerate(dubbing_subs.values()):
                if on_progress:
                    on_progress(min(40+int((i*56)/length), 100), "")

                role = subtitle["role"]
                voice_id = voice_param[role] if role in voice_param else "JBFqnCBsd6RMkjVDRZzb"
                if not voice_id:
                    voice_id = "JBFqnCBsd6RMkjVDRZzb"  # 默认的voice_id

                audio = self.elevenlabs.text_to_speech.convert(
                    text=subtitle["text"],
                    voice_id= voice_id,
                    model_id="eleven_multilingual_v2",
                    output_format="mp3_44100_128",
                    voice_settings= voice_setting,
                    previous_text = previous_dict[role]
                )

                previous_dict[role] = subtitle["text"]  # 更新前一句话

                audio_bytes = b''.join(audio)
                dub_audio = AudioSegment.from_file(io.BytesIO(audio_bytes)) # 读取配音音频段
                dub_audio = dub_audio.set_frame_rate(44100)
                res_audio = np.array(dub_audio.get_array_of_samples())
                res_audio = res_audio.astype(np.float64) / 32768.0
                res_audio = np.vstack([res_audio, res_audio]).T

                if all_audio is None:
                    all_audio = np.copy(res_audio)
                else:
                    empty_array = np.zeros((88200, 2), dtype=res_audio.dtype)
                    all_audio = np.concatenate([all_audio, empty_array, res_audio])

            result_dir = os.path.join(RESULT_OUTPUT_FOLDER, "{}-视频配音结果-{}".format(role_match_list[0], timestamp))   # 创建一个文件夹
            os.makedirs(result_dir, exist_ok=True)
            print(result_dir)


            target_voice_audio_path = os.path.join(result_dir, "音频-目标人声-{}.mp3".format(timestamp))
            target_subtitles_path = os.path.join(result_dir, "字幕-配音字幕-{}.txt".format(timestamp))
            print(target_voice_audio_path)
            print(target_subtitles_path)
            sf.write(target_voice_audio_path, all_audio, 44100)
            with open(target_subtitles_path, "w", encoding="utf-8") as f:
                for i, subtitle in enumerate(dubbing_subs.values()):
                    f.write(f"{str(i)}\n{subtitle['start']} --> {subtitle['end']}\n{subtitle['role']}:{subtitle['text']}\n\n")
            if len(modified_subs[0]) > 0:   # 待调整的字幕条数大于0
                modified_subtitles_path = os.path.join(result_dir, "字幕-调整后字幕.txt")
                try:
                    with open(modified_subtitles_path, 'w', encoding='utf-8') as f:
                        for subtitle in target_subs:
                            f.write(
                                f"{subtitle['index']}\n{subtitle['start']} --> {subtitle['end']}\n {subtitle['text']}\n\n")
                        f.write("\n\n")
                        adjust_indices, adjust_list, compressed_texts = modified_subs
                        for i in range(len(adjust_indices)):
                            f.write(f"{adjust_indices[i]}:{adjust_list[i]} --> {compressed_texts[i]}\n")
                except Exception as e:
                    print(f"Error write subtitle: {e}")
            return {"result_path": result_dir}
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
            voice_id = self.clone_text(key, role_audio_path[key], timestamp)
            voice_ids[key] = voice_id
            db_connect.save_voice_id(api_id=1, voice_name="{}-{}".format(key, timestamp), voice_id=voice_id)
        return voice_ids

    def write_text(self, text, role: str):
        for i in range(0, 1000):
            text += text
        with open(f"{role}.txt", "w", encoding="utf-8") as f:
            f.write(text.strip())

    def clone_text(self, key: str, audio_path: str, timestamp: str):
        voice = self.elevenlabs.voices.ivc.create(
            name="{}-{}".format(key, timestamp),
            # Replace with the paths to your audio files.
            # The more files you add, the better the clone will be.
            files=[io.BytesIO(open(audio_path, "rb").read())]
        )
        print(voice)
        return voice.voice_id

    @classmethod
    def getInstance(cls)-> "dubbingElevenLabs":
        if not cls._instance:
            cls._instance = dubbingElevenLabs()
        return cls._instance


if __name__ == '__main__':
    dub = dubbingElevenLabs.getInstance()
    # dub.voice_isolate(r"E:\offer\AI配音web版\7.28\AIDubbing-QT-main\Service\pyannote\audio.mp3", "result.mp3")
    dub.voice_isolate(r"E:\offer\AI配音web版\7.28\AIDubbing-QT-main\Service\pyannote\video.mp4", "result2.mp3")
    # audio_url = (
    #     "https://storage.googleapis.com/eleven-public-cdn/audio/marketing/nicole.mp3"
    # )
    # response = requests.get(audio_url)
    # audio_data = io.BytesIO(response.content)
    # audio_data.name = "audio.mp3"
    # print(audio_data.name)
    #
    # dub = dubbingElevenLabs.getInstance()
    # dub.dubbing_end_to_end("E:\\offer\\AI配音pyqt版\\AIDubbing-QT-main\\a视频_test.mp4", "en")

