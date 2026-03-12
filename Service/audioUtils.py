import datetime
import os

import librosa
import numpy as np
import soundfile as sf
from pedalboard import Pedalboard
from torchaudio.transforms import TimeStretch

from Config import AUDIO_SEPARATION_FOLDER
from Service.generalUtils import time_str_to_ms


def split_roles_audio(subtitles: dict, audio_path: str, output_path = AUDIO_SEPARATION_FOLDER) -> tuple[dict, np.ndarray, int, dict]:
    # 设计一个dict, dict的key为role，value为[],把subtitles的role分类出来
    audio, samplerate = sf.read(audio_path)
    role_subtitles = {}
    role_audio = {}
    role_audio_path = {}

    i=0
    for subtitle in subtitles.values():
        role = subtitle["role"]
        if role not in role_subtitles:
            role_subtitles[role] = []
        role_subtitles[role].append(subtitle)
        i += 1
    for key in role_subtitles.keys():
        for subtitle in role_subtitles[key]:
            clip = audio[int((time_str_to_ms(subtitle["start"]) * samplerate) / 1000):int(
                (time_str_to_ms(subtitle["end"]) * samplerate) / 1000)]
            if key not in role_audio:
                role_audio[key] = clip
            else:
                empty_array = np.zeros((20000, 2), dtype=clip.dtype)
                role_audio[key] = np.concatenate([role_audio[key],empty_array, clip])
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    for key in role_audio.keys():
        clip = role_audio[key]
        if clip.shape[0] < 10*samplerate:
            empty_array = np.zeros((20000, 2), dtype=clip.dtype)
            clip = np.concatenate([clip, empty_array, clip])
        filePath = os.path.join(output_path, f"角色干音_{key}_{timestamp}.wav")
        role_audio_path[key] = filePath
        sf.write(filePath, clip, samplerate)
    return role_subtitles, audio, samplerate, role_audio_path


def audio_speed(audio: np.ndarray, speed: float) -> np.ndarray:
    """
    改变音频的播放速度
    :param audio: 输入音频数组
    :param speed: 播放速度倍数，大于1为加速，小于1为减速
    :param sr: 音频采样率，默认44100
    :return: 改变速度后的音频数组
    """
    # 计算新的音频长度
    if speed==1:
        return audio
    if audio.shape[1] == 2:
        res_audio_mono = audio[:, 0]  # 取单声道
        original_rms = librosa.feature.rms(y=res_audio_mono)[0].mean()
        res_audio_stretched = librosa.effects.time_stretch(res_audio_mono, rate=speed)
        # res_audio_stretched = res_audio_stretched * (
        #         original_rms / (librosa.feature.rms(y=res_audio_stretched)[0].mean() + 1e-6))  # 恢复到原音量
        res_audio_stretched = np.vstack([res_audio_stretched, res_audio_stretched]).T
        res_audio = res_audio_stretched
    else:
        res_audio_mono = audio
        original_rms = librosa.feature.rms(y=res_audio_mono)[0].mean()
        res_audio_stretched = librosa.effects.time_stretch(res_audio_mono, rate=speed)
        # res_audio_stretched = res_audio_stretched * (
        #         original_rms / (librosa.feature.rms(y=res_audio_stretched)[0].mean() + 1e-6))  # 恢复到原音量
        res_audio = res_audio_stretched

    return res_audio

# def audio_speed(audio: np.ndarray, speed: float, sr: int) -> np.ndarray:
#     if speed == 1:
#         return audio
#
#     board = Pedalboard([TimeStretch(speed)])
#     result = board(audio.T, sr)  # pedalboard 输入 shape [channels, samples]
#     return result.T

# if __name__ == '__main__':
#     from audiostretchy.stretch import stretch_audio
#
#     stretch_audio(r"C:\Users\瑠衣\Desktop\雷总声音\雷总声音.WAV", "output.wav", ratio=1.1)