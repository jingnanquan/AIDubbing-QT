import datetime
import io
import os

import librosa
import numpy as np
import requests
import soundfile as sf
import time
import ffmpeg
from elevenlabs import VoiceSettings
from pydub import AudioSegment
from Config import AUDIO_SEPARATION_FOLDER
from Service.datasetUtils import datasetUtils
from Service.dubbingMain.dubbingElevenLabs import dubbingElevenLabs
from Service.dubbingMain.dubbingInterface import dubbingInterface
from Service.generalUtils import  calculate_time, get_result_path


class voiceElevenLabs(dubbingInterface):
    """
    可以用继承的方式，去继承dubbingElevenLabs，代理触发父类方法。
    1.如果要重新初始化，则会破坏单例，并且形成多个elevenlab连接
    2.如果不初始化，则需要修改其他地方的代码
    """
    _instance = None

    @calculate_time
    def __init__(self):
        from elevenlabs.client import ElevenLabs
        super().__init__()
        print("voice_elevenlabs初始化中")
        self.elevenlabs = dubbingElevenLabs.getInstance().elevenlabs
        self.tokenizer = dubbingElevenLabs.getInstance().tokenizer


    # def get_voice_list(self):
    #     return dubbingElevenLabs.getInstance().get_voice_list()

    def setting_voice(self, params:dict):
        print(params)
        if "voice_id" in params.keys():
            return self.elevenlabs.voices.settings.update(
                voice_id=params["voice_id"],
                request=VoiceSettings(
                    stability=params["stability"] if "stability" in params.keys() else 0.5,
                    use_speaker_boost=params["use_speaker_boost"] if "use_speaker_boost" in params.keys() else True,
                    similarity_boost=params["similarity_boost"] if "similarity_boost" in params.keys() else 0.75,
                    style=params["exaggeration"] if "exaggeration" in params.keys() else 0,
                    speed=1.0,
                ),
            )
        else:
            return False

    def voice_changer(self, voice_file: str, result_path: str, params:dict):
        # 关于相似度、稳定度等属性是对于voice的改变，ok
        # voice_edit
        try:
            filename = os.path.basename(voice_file)
            filename = os.path.splitext(filename)[0]

            audio_data = io.BytesIO(open(voice_file, "rb").read())
            save_file_path = os.path.join(result_path, "{}-声线转换.mp3".format(filename))

            audio_stream = self.elevenlabs.speech_to_speech.convert(
                voice_id=params["voice_id"],
                audio=audio_data,
                model_id=params["model_id"],
                remove_background_noise  = params["remove_background_noise"],
                output_format="mp3_44100_128",
            )

            with open(save_file_path, "wb") as f:
                for chunk in audio_stream:
                    if chunk:
                        f.write(chunk)
            print(f"{save_file_path}: A new audio file was saved successfully!")
            return True
        except Exception as e:
            print(f"{voice_file}转换过程发生错误: {e}")
            return False

    def video_voice_changer(self, vocal_path: str, back_path: str, target_subs: list, role_match_list: list,
                video_path: str, voice_param: dict, on_progress=None) -> dict:
        '''
        我们给定一整段视频，在填写参数表时对选定的角色进行声线替换，注意是选定的角色
        vocal_path: 人声，在这里只需要截取不需要替换的部分与back_path合成新的back_path
        我可以从subtitles+role_matchlist提取到需要的替换声线的字幕
        通过voice_param来确定具体的配音id。可以设定为有声音id的为声音id,没有的为空

        这里不需要干音分片，因为不需要克隆声音。
        '''
        back_audio, samplerate = sf.read(back_path)
        vocal_audio, _ = sf.read(vocal_path)
        print(back_audio.shape)

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

        if on_progress:
            on_progress(40, "正在进行声线转换...")
        left = 0
        right = 0
        time1 = time.time()
        try:
            while right < len(target_subs):
                role = role_match_list[left]
                if not voice_param[role]:  # 该角色无需声线转换
                    left += 1
                    right += 1
                    continue
                start = target_subs[left]['start']
                left_end = self.time_str_to_ms(target_subs[left]['end'])  # 获得毫秒数
                text = ""
                can_conn = True
                while right < len(target_subs):
                    if role_match_list[right] != role:  # 角色不一致，left的role是符合的、right符不符合需要下轮判断
                        break
                    right_start = self.time_str_to_ms(target_subs[right]['start'])
                    state = self.judge_conn(right_start - left_end, can_conn, text)
                    if state != 2:
                        text += target_subs[right]['text'] + ','
                        left_end = self.time_str_to_ms(target_subs[right]['end'])  # 获得毫秒数
                        right += 1
                        if state == 1:
                            can_conn = False
                    else:  # state为2时，不需要拼接台词了
                        break
                end = target_subs[right - 1]['end']  # 还需要检查时间是否连续
                print(role, start, end, text)
                # 这里需要进行二重判断，该角色是否需要重配
                if on_progress:
                    on_progress(min(40 + int((right * 56) / len(target_subs)), 100), "")
                # 提前转为毫秒，需要去截取音频数据
                start = int((self.time_str_to_ms(start) * samplerate) / 1000)
                end = int((self.time_str_to_ms(end) * samplerate) / 1000)

                audio_data = io.BytesIO()
                sf.write(audio_data, vocal_audio[start:end], samplerate, format='WAV')
                audio_data.seek(0)

                audio = self.elevenlabs.speech_to_speech.convert(
                    voice_id=voice_param[role] if voice_param[role] else "JBFqnCBsd6RMkjVDRZzb",
                    audio=audio_data,
                    model_id="eleven_multilingual_sts_v2",
                    output_format="mp3_44100_128",
                )
                audio_bytes = b''.join(audio)
                dub_audio = AudioSegment.from_file(io.BytesIO(audio_bytes))
                dub_audio = dub_audio.set_frame_rate(samplerate)
                res_audio = np.array(dub_audio.get_array_of_samples())
                res_audio = res_audio.astype(np.float64) / 32768.0
                res_audio = np.vstack([res_audio, res_audio]).T
                # start = int((self.time_str_to_ms(start) * samplerate) / 1000)
                if start + res_audio.shape[0] > back_audio.shape[0]:  # 那这里肯定出了问题
                    break
                vocal_audio[start: end] = 0
                vocal_audio[start: start + res_audio.shape[0]] += res_audio
                left = right
            if on_progress:
                on_progress(98, "保存文件中...")
            output_audio_file = get_result_path("音频-配音-{}.mp3".format(timestamp))
            output_video_file = get_result_path("视频-配音-{}.mp4".format(timestamp))
            print(output_audio_file)
            print(output_video_file)
            back_audio += vocal_audio
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
        pass

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

    @classmethod
    def getInstance(cls):
        if not cls._instance:
            cls._instance = voiceElevenLabs()
        return cls._instance



