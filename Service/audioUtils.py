import datetime
import os

import numpy as np
import soundfile as sf
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