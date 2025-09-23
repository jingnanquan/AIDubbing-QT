import datetime
import io
import json
import os

import librosa
import numpy as np
import requests
import soundfile as sf
import time
import ffmpeg
from pydub import AudioSegment
from Service.ccTest import API_KEY_MiniMax
from Service.datasetUtils import datasetUtils
from Service.dubbingMain.dubbingInterface import dubbingInterface
from Service.generalUtils import  calculate_time, get_result_path
from Service.generalUtils2 import decrypt_string


class dubbingMiniMax(dubbingInterface):
    """
    dubbingMiniMax类，继承自dubbingInterface
    这个类是典型的配音类，可以有多个api或自定义实现。
    主要的函数为传入音频文件和字幕文件
    音频的文件会截取，并生成每个role的音频文件
    通过api克隆角色语音，clone完成后。
    根据字幕的时间戳，逐级生成语音
    """
    _instance = None

    @calculate_time
    def __init__(self):
        from elevenlabs.client import ElevenLabs
        import tiktoken
        super().__init__()
        print("minimax初始化中")
        self.group_id = '1924501514181677288'  # 请输入您的group_id
        self.api_key = decrypt_string(API_KEY_MiniMax, "AIDubbing")  # 请输入您的api_key
        self.tts_url = "https://api.minimax.chat/v1/t2a_v2?GroupId=" + self.group_id
        self.tts_headers = {"Content-Type": "application/json", "Authorization": "Bearer " + self.api_key}
        self.tokenizer = tiktoken.encoding_for_model("gpt-3.5-turbo")


    def dubbing_high_quality(self, vocal_path: str, back_path: str, subtitles: list, target_subs: list, role_match_list: list,video_path: str, voice_param: dict, on_progress=None) -> dict:
        back_audio, samplerate = sf.read(back_path)
        print(back_audio.shape)

        try:
            # 以role为key的字幕、原始音频、采样率、角色音频路径
            if on_progress:
                on_progress(25, "角色干音分片中...")
            role_subtitles, vocal_audio, _, role_audio_path = self.parse_roles_numpy_separate(subtitles,
                                                                                              role_match_list,
                                                                                              vocal_path, voice_param)
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            if on_progress:
                on_progress(30, "角色声音克隆中...")
            voice_ids = self.batch_clone_text(role_subtitles, role_audio_path, timestamp, voice_param)
            print(voice_ids)
            for key, value in voice_ids.items():
                if not value:
                    raise Exception(f"角色声音未填写!")
        except Exception as e:
            print(f"克隆过程发生错误: {e}")
            return {"error": f"克隆过程发生错误: {e}"}

        if on_progress:
            on_progress(40, "正在进行配音...")
        left = 0
        right = 0
        previous1 = ""
        previous2 = ""
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

                start = int((self.time_str_to_ms(start) * samplerate) / 1000)
                end = int((self.time_str_to_ms(end) * samplerate) / 1000)
                if on_progress:
                    on_progress(min(40+int((right*56)/len(target_subs)), 100), "")

                # 由elevenlab替换为minimax
                response = requests.request("POST", self.tts_url, headers=self.tts_headers,
                                            data=self.build_tts_body(text, voice_id=voice_ids[role]))
                result = response.content
                result = json.loads(result)  # 由json转为dict
                if 'data' in result:
                    if 'audio' in result["data"]:
                        audio = result["data"]["audio"]
                        audio_bytes = bytes.fromhex(audio)
                        print("get_audio")

                # audio = self.elevenlabs.text_to_speech.convert(
                #     text=text,
                #     voice_id=voice_ids[role] if role in voice_ids else "JBFqnCBsd6RMkjVDRZzb",
                #     model_id="eleven_multilingual_v2",
                #     output_format="mp3_44100_128",
                #     previous_text = previous1+" "+previous2
                # )
                # audio_bytes = b''.join(audio)
                        dub_audio = AudioSegment.from_file(io.BytesIO(audio_bytes))
                        dub_audio = dub_audio+6
                        dub_audio = dub_audio.set_frame_rate(samplerate)
                        res_audio = np.array(dub_audio.get_array_of_samples())
                        res_audio = res_audio.astype(np.float64) / 32768.0
                        res_audio = self.trim_silence(res_audio, samplerate)  # 去除静音段
                        res_audio = np.vstack([res_audio, res_audio]).T  # 在变为双声道之前，先去除收尾的空

                        source_frames = end-start
                        res_frames = res_audio.shape[0]
                        if res_frames - source_frames > 7000:  # 超出太多，就应该加速，大概冗余0.16s
                            print("时长超出太多，应该加速")
                            speedtime1 = time.time()
                            speed = res_frames / (source_frames+7000)
                            # 使用librosa加速音频
                            res_audio_mono = res_audio[:, 0]  # 取单声道
                            original_rms = librosa.feature.rms(y=res_audio_mono)[0].mean()
                            res_audio_stretched = librosa.effects.time_stretch(res_audio_mono, rate = speed)
                            res_audio_stretched = res_audio_stretched * (original_rms / (librosa.feature.rms(y=res_audio_stretched)[0].mean() + 1e-6))  # 恢复到原音量
                            # 保持双声道
                            res_audio_stretched = np.vstack([res_audio_stretched, res_audio_stretched]).T
                            res_audio = res_audio_stretched
                            speedtime2 = time.time()
                            print("加速时长:", speedtime2 - speedtime1)
                        if start + res_audio.shape[0] > back_audio.shape[0]:  # 那这里肯定出了问题
                            back_audio[start: back_audio.shape[0]] += res_audio[:back_audio.shape[0] - start]
                        back_audio[start: start + res_audio.shape[0]] += res_audio
                        left = right
                previous1 = previous2
                previous2 = text
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


    def build_tts_body(self, text: str, voice_id='') -> str:
        voice_id = "Chinese (Mandarin)_Gentle_Senior"
        body = json.dumps({
            "model": "speech-02-turbo",
            "text": text,
            "stream": False,
            "voice_setting": {
                "voice_id": voice_id if voice_id else "Chinese (Mandarin)_Gentle_Senior",
                "speed": 1.0,
                "vol": 1.0,
                "pitch": 0
            },
            'language_boost': "Chinese",
            "audio_setting": {
                "sample_rate": 44100,
                "bitrate": 128000,
                "format": "mp3",
                "channel": 1
            }
        })
        return body


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
            # voice_id = self.clone_text(key, role_audio_path[key], timestamp)
            # voice_ids[key] = voice_id
            # db_connect.save_voice_id(api_id=1, voice_name="{}-{}".format(key, timestamp), voice_id=voice_id)
            voice_ids[key] ="male-qn-qingse"
        return voice_ids

    def write_text(self, text, role: str):
        for i in range(0, 1000):
            text += text
        with open(f"{role}.txt", "w", encoding="utf-8") as f:
            f.write(text.strip())

    def clone_text(self, key: str, audio_path: str, timestamp: str):
        voice = self.elevenlabs.voices.ivc.create(
            name="{}-{}".format(key, timestamp),
            files=[io.BytesIO(open(audio_path, "rb").read())]
        )
        print(voice)
        return voice.voice_id

    @classmethod
    def getInstance(cls)-> 'dubbingMiniMax':
        if not cls._instance:
            cls._instance = dubbingMiniMax()
        return cls._instance


if __name__ == '__main__':
    audio_url = (
        "https://storage.googleapis.com/eleven-public-cdn/audio/marketing/nicole.mp3"
    )
    response = requests.get(audio_url)
    audio_data = io.BytesIO(response.content)
    audio_data.name = "audio.mp3"
    print(audio_data.name)

    dub = dubbingMiniMax.getInstance()
    dub.dubbing_end_to_end("E:\\offer\\AI配音pyqt版\\AIDubbing-QT-main\\a视频_test.mp4", "en")
    # dub.voice_isolate(get_result_path("
    # 音频-配音-20250530_104541.mp3"))
    # dub2 = dubbingElevenLabs.getInstance()
    # print(dub==dub2)

    # audio = dub.elevenlabs.text_to_speech.convert(
    #     text="The first move is what sets everything in motion.",
    #     voice_id="JBFqnCBsd6RMkjVDRZzb",
    #     model_id="eleven_multilingual_v2",
    #     output_format="mp3_44100_128",
    # )
    # audio_bytes = b''.join(audio)
    # dub_audio = AudioSegment.from_file(io.BytesIO(audio_bytes))
    # res_audio = np.array(dub_audio.get_array_of_samples())
    # print(res_audio.shape)
    # print(np.max(res_audio))
    # print(dub_audio)
    # print(res_audio)
    #
    # res_audio = res_audio.astype(np.float64) / 32767.0
    # res_audio = np.vstack([res_audio, res_audio]).T
    #
    # sf.write("test.mp3", res_audio, samplerate=44100)
    #
    # # dub_audio2 = sf.read(audio)
    # # print(dub_audio2)
    # #
    # # print(audio)
    #
    # play(audio)

    # # dub.dubbing(get_video_file("a视频2.mp3"), get_subtitle_file("a字幕.srt"))
    # asyncio.run(dub.dubbing(get_video_file("a视频2.mp3"), get_subtitle_file("a字幕.srt"), get_video_file("a视频2_instrument.wav")))

    # data1, samplerate1 = sf.read("sf_hex_tts2.mp3")
    # print(data1.dtype)
    # print(np.max(data1))
    # print(data1[0:30])
    # print(data1.shape)
    # # print(np.vstack([data1[0:30],data1[0:30]]).T)
    # print(samplerate1)
    # data1, samplerate1 = sf.read("sf_hex_tts2_2.mp3")
    # print(data1.dtype)
    # print(np.max(data1))
    # print(data1[0:30])
    # print(data1.shape)
    # # print(np.vstack([data1[0:30],data1[0:30]]).T)
    # print(samplerate1)
    # data1, samplerate1 = sf.read("byte_tts2.mp3")
    # print(data1.dtype)
    # print(np.max(data1))
    # print(data1[0:30])
    # print(data1.shape)
    # print(samplerate1)
