import numpy as np
import soundfile as sf

from Config import VIDEO_UPLOAD_FOLDER
from Service.generalUtils import time_str_to_ms
from Service.subtitleUtils import parse_subtitle_uncertain
from Service.uvrMain.separate import AudioPre


def get_subtitle_text(target_subs: list, role_match_list: list):
    role_subs = ""
    i = 0
    for subtitle in target_subs:
        role_subs += f"""{subtitle["index"]} | {subtitle["start"]} --> {subtitle["end"]} | {subtitle["text"]} | {role_match_list[i]}\n"""
        i += 1
    return role_subs


origin_subtitles1, roles1 = parse_subtitle_uncertain(r"E:\offer\配音任务2\伤心者联盟\__测试声纹校验\1_2.mp4_角色标注.srt")
origin_subtitles2, roles2 = parse_subtitle_uncertain(r"E:\offer\配音任务2\伤心者联盟\__测试声纹校验\3_4角色标注.srt")

_, vocal_path1 = AudioPre.getInstance()._path_audio_(r"E:\offer\配音任务2\伤心者联盟\__测试声纹校验\1_2.mp4", output_path=VIDEO_UPLOAD_FOLDER)
pure_vocal_audio1, samplerate = sf.read(vocal_path1)

_, vocal_path2 = AudioPre.getInstance()._path_audio_(r"E:\offer\配音任务2\伤心者联盟\__测试声纹校验\3_4.mp4", output_path=VIDEO_UPLOAD_FOLDER)
pure_vocal_audio2, samplerate = sf.read(vocal_path2)


# def get_embs(vad_subtitles: list, pure_vocal_audio: np.ndarray, samplerate: int):
#     vad_separate_audios = []
#     for sub in vad_subtitles:
#         start = time_str_to_ms(sub["start"])
#         end = time_str_to_ms(sub["end"])
#         start_frame = int((start * samplerate) / 1000)
#         end_frame = int((end * samplerate) / 1000)
#         audio = pure_vocal_audio[start_frame: end_frame]
#
#         new_length = int(len(audio) * 16000 / samplerate)
#         sf.write(os.path.join(self.processing_dir, f"{srt_name}_{idx}_{sub['text']}_src.mp3"),
#                  audio, samplerate)
#         audio_data = signal.resample(audio, new_length)
#         sf.write(os.path.join(self.processing_dir, f"{srt_name}_{idx}_{sub['text']}.mp3"), audio_data, 16000)
#         vad_separate_audios.append(audio_data)
#
#         print(vad_separate_audios)
#
#
# embs, labels = SpeakerEmbeddingCluster.get_instance().analyze_speakers(vad_separate_audios, visualize=False)






# origin_subtitles1_text = get_subtitle_text(origin_subtitles1, roles1)
# origin_subtitles2_text = get_subtitle_text(origin_subtitles2, roles2)
#
# print(origin_subtitles1_text)
# print(origin_subtitles2_text)
#
# from Service.dubbingMain.llmAPI import LLMAPI
#
# llm = LLMAPI.getInstance()  # initialize once
#
# merged_subtitles1 = llm.merge_subtitle_with_index(origin_subtitles1_text)
# merged_subtitles2 = llm.merge_subtitle_with_index(origin_subtitles2_text)
#
# target_subtitles_path1 = r"E:\offer\配音任务2\伤心者联盟\__测试声纹校验\1_2_merged.srt"
# target_subtitles_path2 = r"E:\offer\配音任务2\伤心者联盟\__测试声纹校验\3_4_merged.srt"
#
# with open(target_subtitles_path1, "w", encoding="utf-8") as f:
#     for i, subtitle in enumerate(merged_subtitles1.values()):
#         f.write(
#             f"{str(i)}\n{subtitle['start']} --> {subtitle['end']}\n{subtitle['role']}:{subtitle['text']}\n\n")
#
# with open(target_subtitles_path2, "w", encoding="utf-8") as f:
#     for i, subtitle in enumerate(merged_subtitles2.values()):
#         f.write(
#             f"{str(i)}\n{subtitle['start']} --> {subtitle['end']}\n{subtitle['role']}:{subtitle['text']}\n\n")



