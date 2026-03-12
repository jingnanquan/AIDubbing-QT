import copy
import datetime
import logging
import os
import re
import time

import numpy as np
import soundfile as sf
from elevenlabs import CharacterAlignmentResponseModel

from Config import PROMPT_AUDIO_FOLDER, VIDEO_UPLOAD_FOLDER, AUDIO_SEPARATION_FOLDER
from ProjectCompoment.dubbingDatasetUtils import dubbingDatasetUtils
from ProjectCompoment.dubbingEntity import Project, Subtitle
from Service.audioUtils import audio_speed
from Service.generalUtils import calculate_time, find_substring_position, time_str_to_ms, \
    ends_with_character_or_punctuation


class dubbingInterface:
    """
    音频处理基类，定义音频处理的基本接口
    子类应实现具体的音频处理方法
    """

    # def dubbing(self, audio_path, subtitle_path):
    #     """
    #     处理音频和字幕
    #     传入的路径必是已经处理过的
    #     """
    #     raise NotImplementedError("子类必须实现dubbing方法")

    def validate_inputs(self, audio_path, subtitle_path):
        """
        查看路径上是否有该文件
        """
        if not os.path.exists(audio_path):
            return False
        if not os.path.exists(subtitle_path):  # or not subtitle_path.endswith(".srt")
            return False
        return True

    def parse_subtitle(self, subtitle_path):
        with open(subtitle_path, "r", encoding="utf-8") as f:
            content = f.read().strip()
            subtitles = []
            blocks = content.split("\n\n")  # SRT 以空行分隔字幕块

            for block in blocks:
                lines = block.split("\n")
                if len(lines) >= 3:
                    index = int(lines[0])
                    start, end = lines[1].split(" --> ")
                    text = "\n".join(lines[2:])
                    if index%2==1:
                        role="role1"
                    else:
                        role="role2"
                    subtitles.append({
                        "index": index,
                        "start": start,
                        "end": end,
                        "text": text,
                        "role": role,
                    })
            return subtitles

    # @calculate_time
    # def parse_roles(self, subtitles:list, audio_path):
    #     # 设计一个dict, dict的key为role，value为[],把subtitles的role分类出来
    #     audio = AudioFileClip(audio_path)
    #     role_subtitles = {}
    #     role_audio = {}
    #     for subtitle in subtitles:
    #         role = subtitle["role"]
    #         if role not in role_subtitles:
    #             role_subtitles[role] = []
    #         role_subtitles[role].append(subtitle)
    #     for key in role_subtitles.keys():
    #         for subtitle in role_subtitles[key]:
    #             clip = audio.subclipped(subtitle["start"], subtitle["end"])
    #             if key not in role_audio:
    #                 role_audio[key] = clip
    #             else:
    #                 role_audio[key] = concatenate_audioclips([role_audio[key], clip])
    #     timestamp = int(time.time())
    #     for key in role_audio.keys():
    #         role_audio[key].write_audiofile( os.path.join(VIDEO_UPLOAD_FOLDER, f"{key}_{timestamp}mpy.wav"))
    #         role_audio[key].close()
    #     audio.close()
    #     return role_subtitles

    @calculate_time
    def parse_roles_numpy(self, subtitles:list, audio_path)->tuple[dict, np.ndarray, int, dict]:
        """
        :param subtitles:
        :param audio_path:
        :return:
        """
        # 设计一个dict, dict的key为role，value为[],把subtitles的role分类出来
        audio, samplerate = sf.read(audio_path)
        role_subtitles = {}
        role_audio = {}
        role_audio_path = {}
        for subtitle in subtitles:
            role = subtitle["role"]
            if role not in role_subtitles:
                role_subtitles[role] = []
            role_subtitles[role].append(subtitle)
        for key in role_subtitles.keys():
            for subtitle in role_subtitles[key]:
                # 保存的clip仅用于声音克隆，时长不对也没问题
                clip = audio[int((self.time_str_to_ms(subtitle["start"])*samplerate)/1000):int((self.time_str_to_ms(subtitle["end"])*samplerate)/1000)]
                if key not in role_audio:
                    role_audio[key] = clip
                else:
                    role_audio[key] = np.concatenate([role_audio[key], clip])
        timestamp = int(time.time())
        for key in role_audio.keys():
            filePath = os.path.join(VIDEO_UPLOAD_FOLDER, f"{key}_{timestamp}sf.mp3")
            role_audio_path[key] = filePath
            sf.write(filePath, role_audio[key], samplerate)
            # role_audio[key].write_audiofile( os.path.join(BASE_DIR, VIDEO_UPLOAD_FOLDER, f"{key}_{timestamp}sf.wav"))
            # role_audio[key].close()
        # audio.close()
        return role_subtitles, audio, samplerate, role_audio_path

    @calculate_time
    def parse_roles_numpy_separate(self, subtitles: list, role_match_list: list, audio_path: str, voice_param: dict, output_path = AUDIO_SEPARATION_FOLDER) -> tuple[dict, np.ndarray, int, dict]:
        """
        根据roles和subtitles裁切合并音频、保存音频，用于语言克隆。因此需要很高的性能，这里采用numpy来进行合并
        role_match_list: 需要与subtitles一一对应，表示每个字幕的角色
        :param subtitles:
        :param role_match_list:
        :param audio_path:
        :return:
        """
        # 设计一个dict, dict的key为role，value为[],把subtitles的role分类出来
        audio, samplerate = sf.read(audio_path)
        role_subtitles = {}
        role_audio = {}
        role_audio_path = {}
        i=0
        for subtitle in subtitles:
            role = role_match_list[i]
            if not voice_param[role]:  # 如果该角色的语音参数为空“”，则进行配音
                if role not in role_subtitles:
                    role_subtitles[role] = []
                role_subtitles[role].append(subtitle)
            i += 1
        for key in role_subtitles.keys():
            for subtitle in role_subtitles[key]:
                clip = audio[int((self.time_str_to_ms(subtitle["start"]) * samplerate) / 1000):int(
                    (self.time_str_to_ms(subtitle["end"]) * samplerate) / 1000)]
                # clip = audio.subclipped(subtitle["start"], subtitle["end"])
                if key not in role_audio:
                    role_audio[key] = clip
                else:
                    empty_array = np.zeros((20000, 2), dtype=clip.dtype)
                    role_audio[key] = np.concatenate([role_audio[key],empty_array, clip])
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        for key in role_audio.keys():
            clip = role_audio[key]
            if clip.shape[0] < 10*samplerate:
                clip = np.tile(clip, (2,1))

            filePath = os.path.join(output_path, f"角色干音_{key}_{timestamp}.mp3")
            role_audio_path[key] = filePath
            sf.write(filePath, clip, samplerate)

        return role_subtitles, audio, samplerate, role_audio_path
    

    @calculate_time
    def parse_roles_no_voice_param(self, subtitles: list, role_match_list: list, audio_path: str) -> tuple[dict, np.ndarray, int, dict]:
        """
        numpy的意思是切分音频使用soundfile的方式，直接对音频操作
        """
        # 设计一个dict, dict的key为role，value为[],把subtitles的role分类出来
        audio, samplerate = sf.read(audio_path)
        role_subtitles = {}
        role_audio = {}
        role_audio_path = {}
        i=0
        for subtitle in subtitles:
            role = role_match_list[i]
            if role not in role_subtitles:
                role_subtitles[role] = []
            role_subtitles[role].append(subtitle)
            i += 1
        for key in role_subtitles.keys():
            for subtitle in role_subtitles[key]:
                clip = audio[int((self.time_str_to_ms(subtitle["start"]) * samplerate) / 1000):int(
                    (self.time_str_to_ms(subtitle["end"]) * samplerate) / 1000)]
                print(clip.shape)
                if key not in role_audio:
                    role_audio[key] = clip
                else:
                    empty_array = np.zeros((20000, 2), dtype=clip.dtype)
                    role_audio[key] = np.concatenate([role_audio[key], empty_array,  clip])
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        for key in role_audio.keys():
            clip = role_audio[key]
            # if clip.shape[0] < 10*samplerate:  # 零样本克隆就算了，不用增长时间
            #     clip = np.tile(clip, (2,1))
            filePath = os.path.join(PROMPT_AUDIO_FOLDER, f"{key}_角色干音_{timestamp}.mp3")
            role_audio_path[key] = filePath
            sf.write(filePath, clip, samplerate)

        return role_audio_path


    def trim_silence(self, audio: np.ndarray, sample_rate: int, threshold=0.15, keep_ms=250):  # 大概对应频率为5000，低于人声频率
        abs_audio = np.abs(audio)
        above_th = abs_audio > threshold
        if not np.any(above_th):
            return audio  # all silence
        
        first = np.argmax(above_th)
        last = len(audio) - np.argmax(above_th[::-1]) - 1

        keep_samples = int(sample_rate * keep_ms / 1000)
        start = max(0, first - keep_samples)
        end = min(len(audio), last + keep_samples + 1)
        return audio[start:end]

    def trim_silence_remodify_time_alignments(self, audio: np.ndarray, sample_rate: int, time_alignments: CharacterAlignmentResponseModel, threshold=0.12, keep_ms=250)-> tuple[np.ndarray, CharacterAlignmentResponseModel]:  # 大概对应频率为5000，低于人声频率
        """
        只去除首尾，且更新trim_silence
        """
        characters = copy.deepcopy(time_alignments.characters)
        character_start_times_seconds = copy.deepcopy(time_alignments.character_start_times_seconds)
        character_end_times_seconds = copy.deepcopy(time_alignments.character_end_times_seconds)
        abs_audio = np.abs(audio)
        above_th = abs_audio > threshold
        if not np.any(above_th):
            return audio, time_alignments  # all silence

        first = np.argmax(above_th)
        last = len(audio) - np.argmax(above_th[::-1]) - 1

        keep_samples = int(sample_rate * keep_ms / 1000)  # 最低保留250ms
        start = max(0, first - keep_samples)
        end = min(len(audio), last + keep_samples + 1)  # 最后保留的250ms

        start_time_offset = start / sample_rate
        end_time_offset = end / sample_rate
        # 调整时间对齐信息
        if characters and character_start_times_seconds and character_end_times_seconds:
            # 找到第一个大于start_time_offset的字符开始时间
            new_start_index = 0
            for i, start_time in enumerate(character_start_times_seconds):
                if start_time >= start_time_offset:
                    new_start_index = i
                    # 将该位置的开始时间设为start_time_offset
                    character_start_times_seconds[new_start_index] = start_time_offset
                    break

            # 从后往前找，找到第一个开始时间小于end_time_offset的位置
            new_end_index = len(character_start_times_seconds) - 1
            for i in range(len(character_start_times_seconds) - 1, -1, -1):
                if character_start_times_seconds[i] < end_time_offset:
                    new_end_index = i
                    # 将该位置的结束时间设为end_time_offset
                    if new_end_index <= len(character_end_times_seconds):
                        character_end_times_seconds[new_end_index] = end_time_offset
                    break

            # 裁剪字符和时间数组
            characters = characters[new_start_index:new_end_index + 1]
            character_start_times_seconds = character_start_times_seconds[new_start_index:new_end_index + 1]
            character_end_times_seconds = character_end_times_seconds[new_start_index:new_end_index + 1]

            # 所有时间减去start_time_offset，变为从0开始
            if character_start_times_seconds:
                character_start_times_seconds = [t - start_time_offset for t in character_start_times_seconds]
            if character_end_times_seconds:
                character_end_times_seconds = [t - start_time_offset for t in character_end_times_seconds]
            # 更新time_alignments对象
            time_alignments = CharacterAlignmentResponseModel(characters=characters, character_start_times_seconds=character_start_times_seconds, character_end_times_seconds=character_end_times_seconds)

        return audio[start:end], time_alignments

    def trim_silence_with_time_alignments(self, audio: np.ndarray, time_alignments:CharacterAlignmentResponseModel, samplerate: int=44100, rate: float=0.1):  # 大概对应频率为5000，低于人声频率

        # print(time_alignments)
        characters = time_alignments.characters
        character_start_times_seconds = time_alignments.character_start_times_seconds
        character_end_times_seconds = time_alignments.character_end_times_seconds
        time_seconds = character_start_times_seconds
        time_seconds.append(character_end_times_seconds[-1])

        # 处理开头空格
        if characters and characters[0] == " ":  # 开头是空格
            next_char_start = time_seconds[1]
            space_duration = next_char_start - time_seconds[0]
            start_s = time_seconds[0] + space_duration * (1-rate)  # 保留10%的空格时间
            # 更新字符和时间数组
            characters = characters[1:]
            time_seconds = time_seconds[1:]
            time_seconds[0] = start_s  # 方便后续统一减掉
        else:
            start_s = time_seconds[0]

        # 处理结尾空格
        if characters and characters[-1] == " ":  # 结尾是空格
            prev_char_end = time_seconds[-2]
            space_duration = time_seconds[-1] - prev_char_end
            end_s = prev_char_end + space_duration * rate  # 保留10%的空格时间
            # 更新字符和时间数组
            characters = characters[:-1]
            time_seconds = time_seconds[:-1]
            time_seconds[-1] = end_s
        else:
            end_s = time_seconds[-1]

        # 转换时间并裁剪音频
        start = int(start_s * samplerate)
        end = int(end_s * samplerate)
        new_audio = audio[start:end]
        # 所有时间减去start_s，变为从0开始
        time_seconds = np.array(time_seconds)  # 转换为numpy数组
        time_seconds = time_seconds - start_s
        time_seconds = time_seconds.tolist()
        return new_audio, characters, time_seconds

    def time_str_to_ms(self, time_str: str) -> float:
        """
        将SRT时间格式 (00:00:00,150) 转换为毫秒
        :param time_str: 时间字符串，格式 HH:MM:SS,mmm
        :return: 毫秒数
        """
        # 使用正则表达式解析时间
        match = re.match(r'(\d{2}):(\d{2}):(\d{2}),(\d{3})', time_str)
        if not match:
            raise ValueError(f"无效的时间格式: {time_str}")

        hours, minutes, seconds, milliseconds = map(int, match.groups())
        return (hours * 3600 + minutes * 60 + seconds) * 1000 + milliseconds

    def save_project(self,
                 original_video_path: str = '', 
                 original_bgm_audio_path: str = '', 
                 original_voice_audio_path: str = '',
                     target_voice_audio_path: str = '',
                 target_dubbing_audio_path: str = '',
                 target_video_path: str = '',
                 dubbing_subtitles: list[Subtitle] = None,):
        """
        保存配音项目到数据库
        """
        if not dubbing_subtitles:
            print("***没有字幕数据，无法保存项目!!!")
            return
        video_name = os.path.basename(original_video_path)
        projectname = "{}-配音".format(video_name)
        update_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        dubbingDatasetConn = dubbingDatasetUtils.getInstance()
        project_id = dubbingDatasetConn.insert_project(Project(projectname=projectname, original_video_path=original_video_path, original_bgm_audio_path=original_bgm_audio_path, original_voice_audio_path=original_voice_audio_path, target_voice_audio_path = target_voice_audio_path, target_dubbing_audio_path=target_dubbing_audio_path, target_video_path=target_video_path, update_time=update_time))
        if dubbing_subtitles:
            for subtitle in dubbing_subtitles:
                subtitle.project_id = project_id
            for subtitle in dubbing_subtitles:
                print(subtitle.__dict__)
            dubbingDatasetConn.insert_subtitle_many(dubbing_subtitles)

    def adjust_speed2(self, input_audio: np.ndarray, characters: list, time_seconds: list,
                     target_frames: int, sr=44100, up_tolerance=None, subtitle: dict = None, index: int = 0, target_subtitles: list = None, subtitle_indices: dict = None):
        input_frames = input_audio.shape[0]
        global_speed = input_frames / target_frames
        # 我希望加速倍数在1.1以内并且绝对值不超过12000 大概0.28s
        if global_speed>=0.96 and global_speed<=1.1:
            res_audio = audio_speed(input_audio, global_speed)
            return res_audio
        else:
            split_subtitles_index = list(subtitle_indices.values())[index]
            split_subtitles_a = target_subtitles[split_subtitles_index[0]-1: split_subtitles_index[-1]]
            split_subtitles = []

            print("subtitle:",subtitle)
            print("split_subtitles_a:",split_subtitles_a)
            i = 0
            while i < len(split_subtitles_a):
                start = split_subtitles_a[i]["start"]
                text = split_subtitles_a[i]["text"]

                end = time_str_to_ms(split_subtitles_a[i]["end"])
                while i+1 < len(split_subtitles_a):
                    next_start = time_str_to_ms(split_subtitles_a[i+1]["start"])
                    next_text = split_subtitles_a[i+1]["text"]
                    if next_start-end <= 250 or ends_with_character_or_punctuation(text)!='punctuation':
                        text = " ".join([text, next_text])
                        end = time_str_to_ms(split_subtitles_a[i+1]["end"])
                        i += 1
                        continue
                    break
                end = split_subtitles_a[i]["end"]
                split_subtitles.append({"text": text, "start": start, "end": end})
                i += 1

            print("split_subtitles:",split_subtitles)
            # print("target_frames:", target_frames)
            # print(characters)
            # print(time_seconds)


            # 这里获取的结果是
            # split_subtitles=[{'text': 'You actually dared to hit me!', 'start': '00:00:04,933', 'end': '00:00:05,933'},{'text': 'Make me kneel down and admit my mistake.', 'start': '00:00:06,130', 'end': '00:00:07,130'}]
            # subtitles = [{'text': 'You actually dared to hit me! Make me kneel down and admit my mistake.', 'start': '00:00:04,933', 'end': '00:00:07,130'}]
            string = "".join(characters)
            pointer = 0
            offset_times = int((time_str_to_ms(split_subtitles[0]["start"])*sr)/1000)
            zeros_audio = np.zeros((target_frames+88200, input_audio.shape[1])) # 预留88200个样本，防止加速后超出目标长度
            print(zeros_audio.shape)

            for  index, sub in enumerate(split_subtitles):
                print("==========")
                start, end = find_substring_position(string, sub["text"])
                if start == -1 and end == -1:
                    logging.warning(f"字幕 {sub['text']} 未在文本中找到匹配项")
                    global_speed = min(global_speed, 1.16)
                    global_speed = max(global_speed, 0.95)
                    print("global_speed:", global_speed)
                    res_audio = audio_speed(input_audio, global_speed)
                    return res_audio

                # 这边的方案，是如果>1, 就是加速，我是希望加速因子小于本身的global_speed
                '''
                if global speed>1.1
                    if speed<1   # 就是要减速, 这个情况就是，如果你减速了，那么其他地方就可能会加速
                        speed = max(speed 0.95)  # 你可以减速，但是我减速的阈值就是0.95  减速最好的点就是，它是不会有重叠的
                    if speed>1 and speed <= 1.15:  # 这边需要加速
                        speed
                    if speed > 1.15
                        我重新计算一下前方的阈值
                        speed = new_speed
                if global_speed<0.96:
                    speed = max(speed, 0.96)
                '''


                # print(start, end)
                start = time_seconds[start]*sr
                end = time_seconds[end+1]*sr
                section_audio = input_audio[int(start): int(end)+1]
                # print(start, end)

                align_start = int((time_str_to_ms(sub["start"])*sr)/1000)-offset_times  # 270465
                align_end = int((time_str_to_ms(sub["end"])*sr)/1000)+1-offset_times  # 314565
                speed = section_audio.shape[0] / (align_end - align_start)
                # print(align_start, align_end)
                print(speed)
                print(section_audio.shape)

                # 调整speed和start
                if speed<1:
                    speed = max(speed, 0.95)
                elif speed > 1.15:
                    align_start = min(int((align_start+pointer)/2), pointer+5000)
                    speed = section_audio.shape[0] / (align_end - align_start)
                    if speed <=1.15:
                        speed = max(speed, 1)
                    else:
                        next_end = (int((time_str_to_ms(split_subtitles[index+1]["start"])*sr)/1000)+1-offset_times) if index+1 < len(split_subtitles) else align_end
                        align_end = int((align_end+next_end)/2)
                        speed = section_audio.shape[0] / (align_end - align_start)
                        speed = max(speed, 1.05)

                align_audio = audio_speed(section_audio, speed)
                # print(align_audio.shape)
                zeros_audio[align_start: align_start+align_audio.shape[0]] += align_audio
                pointer = align_start+align_audio.shape[0]


            zeros_audio = zeros_audio[0: pointer]
            return zeros_audio


        # return res_audio