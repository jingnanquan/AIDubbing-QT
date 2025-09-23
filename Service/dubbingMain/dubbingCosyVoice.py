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
from Config import PROMPT_AUDIO_FOLDER, cosyvoice_url
from Service.datasetUtils import datasetUtils
from Service.dubbingMain.dubbingInterface import dubbingInterface
from Service.generalUtils import  calculate_time, get_result_path



class dubbingCosyVoice(dubbingInterface):
    """
    """
    _instance = None

    @calculate_time
    def __init__(self):
        import tiktoken
        super().__init__()
        # cosyvoice初始化中
        self.tokenizer = tiktoken.encoding_for_model("gpt-3.5-turbo")
        print("cosyvoice初始化完毕")

    def dubbing_single_clone(self, vocal_path: str, back_path: str, subtitles: list, target_subs: list, role_match_list: list,video_path: str, target_lang: str, on_progress=None) -> dict:
        back_audio, samplerate = sf.read(back_path)
        vocal_audio, _ = sf.read(vocal_path)

        target_lang = "<|{}|>".format(target_lang)
        print(target_lang)
        print(back_audio.shape)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        left = 0
        right = 0
        time1 = time.time()
        try:
            while right < len(target_subs):
                role = role_match_list[left]
                start = target_subs[left]['start']
                left_end = self.time_str_to_ms(target_subs[left]['end'])  # 获得毫秒数
                text = ""
                prompt_text = ""
                can_conn = True
                state_remain = 1  # 额度为1，允许2次正常连接，1次长连接
                while right < len(target_subs):
                    if role_match_list[right] != role:
                        break
                    right_start = self.time_str_to_ms(target_subs[right]['start'])
                    state = self.judge_conn(right_start - left_end, text)
                    state_remain -= state
                    if state_remain>=0:
                        text += target_subs[right]['text']
                        prompt_text += subtitles[right]['text']+","
                        left_end = self.time_str_to_ms(target_subs[right]['end'])  # 获得毫秒数
                        right += 1
                    else:
                        break
                end = target_subs[right - 1]['end']  # 还需要检查时间是否连续
                text = target_lang+text
                print(role, start, end, text, prompt_text)
                if on_progress:
                    on_progress(min(20+int((right*76)/len(target_subs)), 100), "")
                start = int((self.time_str_to_ms(start) * samplerate) / 1000)
                end = int((self.time_str_to_ms(end) * samplerate) / 1000)

                clip = vocal_audio[start: end]
                prompt_audio_url = os.path.join(PROMPT_AUDIO_FOLDER, f"{role}_分句_{str(start)}_{timestamp}.mp3")
                sf.write(prompt_audio_url, clip, samplerate)
                print(prompt_audio_url)

                target_audio_url = requests.post(cosyvoice_url+"single_cross_dubbing", json={
                        "target_text": text,
                        "prompt_text": prompt_text,
                        "prompt_audio_url": prompt_audio_url  
                })
                print(target_audio_url)
                if target_audio_url.status_code == 200:
                    print(target_audio_url.text)
                    target_audio_url = json.loads(target_audio_url.text)
                    target_audio_url = target_audio_url["file_path"]

                    dub_audio = AudioSegment.from_file(target_audio_url)
                    dub_audio = dub_audio.set_frame_rate(samplerate)
                    res_audio = np.array(dub_audio.get_array_of_samples())
                    print(res_audio.dtype)
                    print(res_audio.shape)
                    res_audio = res_audio.astype(np.float64) / 32768.0
                    res_audio = np.vstack([res_audio, res_audio]).T
                    
                    source_frames = end-start
                    res_frames = res_audio.shape[0]
                    if res_frames - source_frames > 7000:  # 超出太多，就应该加速
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
        

    def dubbing_single_clone_high_quality(self, vocal_path: str, back_path: str, subtitles: list, target_subs: list, role_match_list: list,video_path: str, target_lang: str, on_progress=None) -> dict:
        back_audio, samplerate = sf.read(back_path)
        vocal_audio, _ = sf.read(vocal_path)

        target_lang = "<|{}|>".format(target_lang)
        print(target_lang)
        print(back_audio.shape)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

        dubbing_subtitle_info = {}
        left = 0
        right = 0
        time1 = time.time()
        try:
            while right < len(target_subs):
                role = role_match_list[left]
                start = target_subs[left]['start']
                left_end = self.time_str_to_ms(target_subs[left]['end'])  # 获得毫秒数
                text = ""
                prompt_text = ""
                state_remain = 1  # 额度为1，允许2次正常连接，1次长连接
                while right < len(target_subs):
                    if role_match_list[right] != role:
                        break
                    right_start = self.time_str_to_ms(target_subs[right]['start'])
                    state = self.judge_conn(right_start - left_end, text)
                    state_remain -= state
                    if state_remain>=0:
                        text += target_subs[right]['text']
                        prompt_text += subtitles[right]['text']+","
                        left_end = self.time_str_to_ms(target_subs[right]['end'])  # 获得毫秒数
                        right += 1
                    else:
                        break
                end = target_subs[right - 1]['end']  # 还需要检查时间是否连续
                text = target_lang+text
                prompt_text = prompt_text[:-1]+"." 
                print("配音字幕：", role, start, end, text, prompt_text)
                if on_progress:
                    on_progress(min(20+int((right*76)/len(target_subs)), 100), "")
                start_frame = int((self.time_str_to_ms(start) * samplerate) / 1000)
                end_frame = int((self.time_str_to_ms(end) * samplerate) / 1000)
                duration = self.time_str_to_ms(end) - self.time_str_to_ms(start)  # 算得的时间为ms
                clip = vocal_audio[start_frame: end_frame]
                prompt_audio_url = os.path.join(PROMPT_AUDIO_FOLDER, f"{role}_分句_{str(start_frame)}_{timestamp}.mp3")
                sf.write(prompt_audio_url, clip, samplerate)
                print("  ", prompt_audio_url)
                '''
                在这里这要做的事只有3个，1.记录start、end、总持续ms数、音频保存路径、role、text、prompt_text
                '''
                if role not in dubbing_subtitle_info:
                    dubbing_subtitle_info[role]=[]
                dubbing_subtitle_info[role].append(dubbingSubtitle(start_frame, end_frame, duration, text, prompt_text, prompt_audio_url))

                left = right

            for role, sublist in dubbing_subtitle_info.items():
                for i in range(len(sublist)):
                    dubbing_subtitle = sublist[i]
                    assert isinstance(dubbing_subtitle, dubbingSubtitle), "dubbing_subtitle must be an instance of dubbingSubtitle"
                    start = dubbing_subtitle.start
                    end = dubbing_subtitle.end
                    prompt_text = dubbing_subtitle.prompt_text
                    prompt_audio_url = dubbing_subtitle.prompt_audio_url
                    print("配音字幕2", dubbing_subtitle)
                    if dubbing_subtitle.duration <= 4500:
                        print("prompt音频太短，启用分句延长")
                        prompt_audio, srate = sf.read(dubbing_subtitle.prompt_audio_url)
                        offset = (i+1)%len(sublist)
                        while len(prompt_audio) < 6 * srate:  # 延长至4.5s及以上
                            next_audio, _ = sf.read(sublist[offset].prompt_audio_url)
                            prompt_audio = np.concatenate([prompt_audio, np.zeros((30000, 2), dtype=prompt_audio.dtype),  next_audio])
                            prompt_text += sublist[offset].prompt_text
                            offset = (offset+1)%len(sublist)
                        prompt_audio_url = os.path.join(PROMPT_AUDIO_FOLDER, f"{role}_延长分句_{str(i)}_{timestamp}.mp3")

                        sf.write(prompt_audio_url, prompt_audio, srate)
                        print(prompt_text)
                        print(prompt_audio_url)
                    target_audio_url = requests.post(cosyvoice_url+"single_cross_dubbing", json={
                        "target_text": dubbing_subtitle.target_text,
                        "prompt_text": prompt_text,
                        "prompt_audio_url": prompt_audio_url
                    })
                    while target_audio_url.status_code != 200:
                        target_audio_url = requests.post(cosyvoice_url+"single_cross_dubbing", json={
                            "target_text": dubbing_subtitle.target_text,
                            "prompt_text": prompt_text,
                            "prompt_audio_url": prompt_audio_url
                        })
                    print(target_audio_url)
                    if target_audio_url.status_code == 200:
                        print(target_audio_url.text)
                        target_audio_url = json.loads(target_audio_url.text)
                        target_audio_url = target_audio_url["file_path"]

                        dub_audio = AudioSegment.from_file(target_audio_url)  # 读取配音音频段
                        dub_audio = dub_audio.set_frame_rate(samplerate)
                        res_audio = np.array(dub_audio.get_array_of_samples())
                        res_audio = res_audio.astype(np.float64) / 32768.0
                        res_audio = self.trim_silence(res_audio, samplerate)  # 去除静音段
                        res_audio = np.vstack([res_audio, res_audio]).T  # 在变为双声道之前，先去除收尾的空音

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

    def dubbing_role_clone_high_quality(self, vocal_path: str, back_path: str, subtitles: list, target_subs: list, role_match_list: list,video_path: str, target_lang: str, on_progress=None) -> dict:
        back_audio, samplerate = sf.read(back_path)
        vocal_audio, _ = sf.read(vocal_path)

        target_lang = "<|{}|>".format(target_lang)
        print(target_lang)
        print(back_audio.shape)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

        dubbing_subtitle_info = {}
        left = 0
        right = 0
        time1 = time.time()
        try:
            while right < len(target_subs):
                role = role_match_list[left]
                start = target_subs[left]['start']
                left_end = self.time_str_to_ms(target_subs[left]['end'])  # 获得毫秒数
                text = ""
                prompt_text = ""
                state_remain = 1  # 额度为1，允许2次正常连接，1次长连接
                while right < len(target_subs):
                    if role_match_list[right] != role:
                        break
                    right_start = self.time_str_to_ms(target_subs[right]['start'])
                    state = self.judge_conn(right_start - left_end, text)
                    state_remain -= state
                    if state_remain>=0:
                        text += target_subs[right]['text']
                        prompt_text += subtitles[right]['text']+","
                        left_end = self.time_str_to_ms(target_subs[right]['end'])  # 获得毫秒数
                        right += 1
                    else:
                        break
                end = target_subs[right - 1]['end']  # 还需要检查时间是否连续
                text = target_lang+text
                prompt_text = prompt_text[:-1]+"." 
                print("配音字幕：", role, start, end, text, prompt_text)
                if on_progress:
                    on_progress(min(20+int((right*20)/len(target_subs)), 100), "")
                start_frame = int((self.time_str_to_ms(start) * samplerate) / 1000)
                end_frame = int((self.time_str_to_ms(end) * samplerate) / 1000)
                duration = self.time_str_to_ms(end) - self.time_str_to_ms(start)  # 算得的时间为ms
                clip = vocal_audio[start_frame: end_frame]
                prompt_audio_url = os.path.join(PROMPT_AUDIO_FOLDER, f"{role}_分句_{str(start_frame)}_{timestamp}.mp3")
                sf.write(prompt_audio_url, clip, samplerate)
                print("  ", prompt_audio_url)
                '''
                在这里这要做的事只有3个，1.记录start、end、总持续ms数、音频保存路径、role、text、prompt_text
                '''
                if role not in dubbing_subtitle_info:
                    dubbing_subtitle_info[role]=[]
                dubbing_subtitle_info[role].append(dubbingSubtitle(start_frame, end_frame, duration, text, prompt_text, prompt_audio_url))

                left = right

            voice_param = {}
            for role, sublist in dubbing_subtitle_info.items():
                prompt_audio, srate = sf.read(sublist[0].prompt_audio_url)
                prompt_text = sublist[0].prompt_text

                for offset in range(1, len(sublist)):  # 拼接所有的音频
                    if prompt_audio.shape[0] > 26*srate: # 超过30s，就直接break，音频太长无法克隆
                        prompt_audio = prompt_audio[:26*srate]  
                        break
                    if prompt_audio.shape[0] > 20*srate: # 超过20s，就直接break，音频太长无法克隆  
                        break
                    next_audio, _ = sf.read(sublist[offset].prompt_audio_url)
                    prompt_audio = np.concatenate([prompt_audio, np.zeros((30000, 2), dtype=prompt_audio.dtype),  next_audio])
                    prompt_text += sublist[offset].prompt_text
                prompt_audio_url = os.path.join(PROMPT_AUDIO_FOLDER, f"{role}_全干音分句_{timestamp}.mp3")
                sf.write(prompt_audio_url, prompt_audio, srate)
                voice_name = "{}_spkid_{}".format(role, timestamp)
                print(prompt_text)
                print(prompt_audio_url)
                voice_param[role] = voice_name
                clone_res = requests.post(cosyvoice_url+"clone_voice", json={
                        "prompt_text": prompt_text,
                        "prompt_audio_url": prompt_audio_url,
                        "voice_name": voice_name
                })
                print(clone_res)
                assert clone_res.status_code == 200, "{}, clone_voice失败".format(role)
                print(voice_param, "克隆成功")

                # 开始配音
                for i in range(len(sublist)):
                    dubbing_subtitle = sublist[i]
                    assert isinstance(dubbing_subtitle, dubbingSubtitle), "dubbing_subtitle must be an instance of dubbingSubtitle"
                    start = dubbing_subtitle.start
                    end = dubbing_subtitle.end
                    target_audio_url = requests.post(cosyvoice_url+"single_cross_dubbing", json={
                        "target_text": dubbing_subtitle.target_text,
                        "prompt_text": "",
                        "prompt_audio_url": "",
                        "voice_name": voice_param[role]
                    })
                    while target_audio_url.status_code != 200:
                        target_audio_url = requests.post(cosyvoice_url+"single_cross_dubbing", json={
                            "target_text": dubbing_subtitle.target_text,
                            "prompt_text": "",
                            "prompt_audio_url": "",
                            "voice_name": voice_param[role]
                        })
                    if on_progress:
                        on_progress(min(40+int((i*50)/len(sublist)), 100), "")
                    print(target_audio_url)
                    if target_audio_url.status_code == 200:
                        print(target_audio_url.text)
                        target_audio_url = json.loads(target_audio_url.text)
                        target_audio_url = target_audio_url["file_path"]

                        dub_audio = AudioSegment.from_file(target_audio_url)  # 读取配音音频段
                        dub_audio = dub_audio.set_frame_rate(samplerate)
                        res_audio = np.array(dub_audio.get_array_of_samples())
                        res_audio = res_audio.astype(np.float64) / 32768.0
                        res_audio = self.trim_silence(res_audio, samplerate)  # 去除静音段
                        res_audio = np.vstack([res_audio, res_audio]).T  # 在变为双声道之前，先去除收尾的空音

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


    
    def dubbing_role_clone(self, vocal_path: str, back_path: str, subtitles: list, target_subs: list, role_match_list: list,video_path: str, target_lang: str, on_progress=None) -> dict:
        back_audio, samplerate = sf.read(back_path)
        vocal_audio, _ = sf.read(vocal_path)

        target_lang = "<|{}|>".format(target_lang)
        print(target_lang)

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

        role_audio_path = self.parse_roles_no_voice_param(subtitles, role_match_list, vocal_path)
        print(role_audio_path)
        
        left = 0
        right = 0
        time1 = time.time()
        try:
            while right < len(target_subs):
                role = role_match_list[left]
                start = target_subs[left]['start']
                left_end = self.time_str_to_ms(target_subs[left]['end'])  # 获得毫秒数
                text = ""
                prompt_text = ""
                can_conn = True
                state_remain = 1  # 额度为1，允许2次正常连接，1次长连接
                while right < len(target_subs):
                    if role_match_list[right] != role:
                        break
                    right_start = self.time_str_to_ms(target_subs[right]['start'])
                    state = self.judge_conn(right_start - left_end, text)
                    state_remain -= state
                    if state_remain>=0:
                        text += target_subs[right]['text']
                        prompt_text += subtitles[right]['text']+","
                        left_end = self.time_str_to_ms(target_subs[right]['end'])  # 获得毫秒数
                        right += 1
                    else:
                        break
                end = target_subs[right - 1]['end']  # 还需要检查时间是否连续
                text = target_lang+text
                print(role, start, end, text, prompt_text)
                if on_progress:
                    on_progress(min(20+int((right*76)/len(target_subs)), 100), "")
                start = int((self.time_str_to_ms(start) * samplerate) / 1000)
                end = int((self.time_str_to_ms(end) * samplerate) / 1000)

                target_audio_url = requests.post(cosyvoice_url+"single_cross_dubbing", json={
                        "target_text": text,
                        "prompt_text": "", # 不需要传入text，防止误解
                        "prompt_audio_url": role_audio_path[role]  
                })
                print(target_audio_url)
                if target_audio_url.status_code == 200:
                    print(target_audio_url.text)
                    target_audio_url = json.loads(target_audio_url.text)
                    target_audio_url = target_audio_url["file_path"]

                    dub_audio = AudioSegment.from_file(target_audio_url)
                    dub_audio = dub_audio.set_frame_rate(samplerate)
                    res_audio = np.array(dub_audio.get_array_of_samples())
                    res_audio = res_audio.astype(np.float64) / 32768.0
                    res_audio = np.vstack([res_audio, res_audio]).T

                    source_frames = end-start
                    res_frames = res_audio.shape[0]
                    if res_frames - source_frames > 7000:  # 超出太多，就应该加速
                        speedtime1 = time.time()
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
                        speedtime2 = time.time()
                        print("加速时长:", speedtime2 - speedtime1)

                    if start + res_audio.shape[0] > back_audio.shape[0]:  # 那这里肯定出了问题
                        back_audio[start: back_audio.shape[0]] += res_audio[:back_audio.shape[0] - start]
                    back_audio[start: start + res_audio.shape[0]] += res_audio

                # 这里得到分句，能够从分句中得到start、end、text、prompttext
                # 需要先测试一下mp3格式模型能不能处理
                # 后续尝试是否能 不用来回保存音频文件，而是直接输入到模型
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



    def judge_conn(self, time, text: str):
        """
        0.代表无条件连接
        1.消耗连接次数
        2.无条件拒绝连接
        相较于elevenlab，语句连接条件宽松一些
        """
        token_len = len(self.tokenizer.encode(text))
        if token_len >= 28:
            print(token_len)
            return 2
        if time < 260:
            return 0
        elif time < 380:
            return 0.5
        elif time < 620:
            if token_len <= 8:
                return 1
        print("毫秒差值：", time)
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
    def getInstance(cls)-> 'dubbingCosyVoice':
        if not cls._instance:
            cls._instance = dubbingCosyVoice()
        return cls._instance



class dubbingSubtitle:
    def __init__(self, start: int, end: int, duration: int, target_text: str, prompt_text: str, prompt_audio_url: str):
        self.start = start
        self.end = end
        self.duration = duration
        self.target_text = target_text
        self.prompt_text = prompt_text
        self.prompt_audio_url = prompt_audio_url
    def __repr__(self):
        return (f"dubbingSubtitle(start={self.start}, end={self.end}, duration={self.duration}, "
                f"target_text={self.target_text!r}, prompt_text={self.prompt_text!r}, "
                f"prompt_audio_url={self.prompt_audio_url!r})")

# if __name__ == '__main__':
    # a = np.array([[1,1],[2,2],[3,3],[4,4]])
    # b = np.array([[7,7],[8,8]])
    # print(a)
    # print(b)
    # a[1:1+b.shape[0]] +=b
    # print(a)

    # back_filename = os.path.join(AUDIO_SEPARATION_FOLDER, 'background-{}-{}.mp3'.format("test","test1"))
    #
    # original, sr = librosa.load(get_result_path("音频-配音-20250530_104541.mp3"), sr=None)  # 保持原始采样率
    # vocal, sr_vocal = librosa.load(os.path.join(AUDIO_SEPARATION_FOLDER, "vocal-音频-配音-20250530_104541-20250603_155418.mp3"), sr=sr)  # 强制统一采样率
    # # 检查长度是否一致
    # if len(original) != len(vocal):
    #     print("不一致")
    #     min_len = min(len(original), len(vocal))
    #     original = original[:min_len]
    #     vocal = vocal[:min_len]
    #
    # numerator = np.dot(original, vocal)
    # denominator = np.dot(vocal, vocal)
    # alpha = denominator/numerator
    # print(numerator)
    # print(denominator)
    # print(alpha)
    #
    # # matched_vocal = self.match_volume(original, vocal, sr)
    # # 计算背景音（原始 - 人声）
    # background = original - vocal*10
    # # 避免溢出（裁剪到[-1, 1]范围内）
    # background = np.clip(background, -1.0, 1.0)
    # # 保存结果
    # sf.write(back_filename, background, sr)

    # audio_url = (
    #     "https://storage.googleapis.com/eleven-public-cdn/audio/marketing/nicole.mp3"
    # )
    # response = requests.get(audio_url)
    # audio_data = io.BytesIO(response.content)
    # audio_data.name = "audio.mp3"
    # print(audio_data.name)

    # dub = dubbingElevenLabs.getInstance()
    # dub.dubbing_end_to_end("E:\\offer\\AI配音pyqt版\\AIDubbing-QT-main\\a视频_test.mp4", "en")
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
