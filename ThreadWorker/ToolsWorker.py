import datetime
import io
import math
import os
import re
import time
from collections import Counter

import ffmpeg
import numpy as np
import soundfile as sf
from PyQt5.QtCore import QThread, pyqtSignal
from Service.datasetUtils import datasetUtils
from Service.dubbingMain.dubbingElevenLabs import dubbingElevenLabs
from Service.generalUtils import time_str_to_ms, ms_to_time_str
from Service.subtitleUtils import parse_subtitle_uncertain
from Service.videoUtils import compress_video, get_audio_np_from_video, merge_audio_video2


class ClearBGMWorker(QThread):
    # 定义一个信号，用于在任务完成后更新 GUI
    finished = pyqtSignal(dict)
    item_finished = pyqtSignal(int)

    def __init__(self, video_files: list):
        super().__init__()
        self.video_files = video_files

    def run(self):
        print("enter: 视频背景声清除")
        dir = os.path.dirname(self.video_files[0])
        result_dir = os.path.join(dir, "clearBGM")
        os.makedirs(result_dir, exist_ok=True)
        from Service.uvr5.audioseperate import AudioSeparator

        error_files = []
        try:
            Separator = AudioSeparator.get_instance()
        except Exception as e:
            self.finished.emit({"msg": f"视频背景声清除模型出错: {e}",
                                "result_path":"" })
            return

        for file_path in self.video_files:
            if os.path.isfile(file_path):
                print(f"▶️ 正在处理视频: {file_path}")

                video_audio, samplerate = get_audio_np_from_video(file_path)
                assert isinstance(video_audio, np.ndarray)


                output_filename = f"clearBGM_{os.path.splitext(os.path.basename(file_path))[0]}.mp4"
                output_path = os.path.join(result_dir, output_filename)
                video_audio_path = os.path.join(result_dir, f"原音频_{os.path.splitext(os.path.basename(file_path))[0]}.mp3")
                sf.write(video_audio_path, video_audio, samplerate)

                try:
                    print(video_audio_path)
                    vocal_path = Separator.isolate(video_audio_path, result_dir)
                    merge_audio_video2(file_path, vocal_path, output_path)

                    print(f"✅ 已保存清除视频: {output_path}")
                except Exception as e:
                    print(f"❌ 处理 {file_path} 出错: {e}")
                    error_files.append(file_path)
        if error_files:
            self.finished.emit({"msg": f"视频背景声清除完成! 未完成的视频路径{error_files}, 其他视频保存路径如下：",
                                "result_path": result_dir})
        else:
            self.finished.emit({"msg": "视频背景声清除完成! 保存路径如下：", "result_path": result_dir})


class CompressVideoWorker(QThread):
    # 定义一个信号，用于在任务完成后更新 GUI
    finished = pyqtSignal(dict)
    item_finished = pyqtSignal(int)

    def __init__(self, video_files: list):
        super().__init__()
        self.video_files = video_files
        self.target_height = 1080
        self.crf = 28
        self.preset = "fast"

    def run(self):
        print("enter: 视频压缩")
        dir = os.path.dirname(self.video_files[0])
        result_dir = os.path.join(dir, "compressed")
        os.makedirs(result_dir, exist_ok=True)

        error_files = []
        for file_path in self.video_files:
            if os.path.isfile(file_path):
                print(f"▶️ 正在处理视频: {file_path}")

                output_filename = f"compressed_{os.path.splitext(os.path.basename(file_path))[0]}.mp4"
                output_path = os.path.join(result_dir, output_filename)

                try:
                    compress_video(str(file_path), str(output_path), self.target_height, self.crf, self.preset)
                    print(f"✅ 已保存压缩视频: {output_path}")
                except Exception as e:
                    print(f"❌ 处理 {file_path} 出错: {e}")
                    error_files.append(file_path)
        if error_files:
            self.finished.emit({"msg": f"视频压缩完成! 未完成的视频路径{error_files}, 其他视频保存路径如下：", "result_path": result_dir})
        else:
            self.finished.emit({"msg": "视频压缩完成! 保存路径如下：",  "result_path": result_dir})


class MergeVideoWorker_origin1(QThread):
    # 定义一个信号，用于在任务完成后更新 GUI
    finished = pyqtSignal(dict)
    item_finished = pyqtSignal(int)

    def __init__(self, video_files: []):
        super().__init__()
        self.video_files = video_files
        self.target_height = 1080
        self.crf = 28
        self.preset = "fast"

    def run(self):
        print("enter: 视频合并")
        dir = os.path.dirname(self.video_files[0])
        result_dir = os.path.join(dir, "merged")
        os.makedirs(result_dir, exist_ok=True)

        output_filename = f"merged_video_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}.mp4"
        output_path = os.path.join(result_dir, output_filename)

        try:
            streams = []
            for f in self.video_files:
                inp = ffmpeg.input(f)
                v = inp.video
                # 通过 aresample 做“时间轴对齐/补偿”，避免拼接边界音频错位
                a = inp.audio.filter('aresample', **{'async': 1, 'first_pts': 0})
                streams += [v, a]

            # n=片段数量；v=1, a=1 表示输出 1 路视频 + 1 路音频
            concat = ffmpeg.concat(*streams, v=1, a=1, n=len(self.video_files)).node
            vcat = concat[0]
            acat = concat[1]

            (
                ffmpeg
                .output(vcat, acat, output_path,
                        vcodec='libx264', acodec='aac',
                        preset=self.preset, crf=self.crf)
                .global_args('-fflags', '+genpts')  # 重新生成连续 PTS
                .overwrite_output()
                .run()
            )

            print(f"✅ 视频合并完成: {output_path}")
            self.finished.emit({"msg": f"视频合并完成!保存路径如下：", "result_path": result_dir})
        except Exception as e:
            print(f"❌ 视频合并出错: {e}")
            self.finished.emit({"msg": f"视频合并失败: {str(e)}", "result_path": ""})

class MergeVideoWorker(QThread):
    finished = pyqtSignal(dict)
    item_finished = pyqtSignal(int)

    def __init__(self, video_files: list):
        super().__init__()
        self.video_files = video_files
        self.crf = 28
        self.preset = "fast"

    def _probe_video(self, path):
        """获取视频的元信息"""
        try:
            info = ffmpeg.probe(path)
            video_stream = next((s for s in info['streams'] if s['codec_type'] == 'video'), None)
            audio_stream = next((s for s in info['streams'] if s['codec_type'] == 'audio'), None)
            if not video_stream:
                raise ValueError("No video stream found")
            return {
                'width': int(video_stream.get('width', 0)),
                'height': int(video_stream.get('height', 0)),
                'fps': eval(video_stream.get('r_frame_rate', '0/1')),
                'v_codec': video_stream.get('codec_name', ''),
                'a_codec': audio_stream.get('codec_name', '') if audio_stream else '',
                'sample_rate': int(audio_stream.get('sample_rate', 0)) if audio_stream else 0,
            }
        except Exception as e:
            raise ValueError(f"Failed to probe {path}: {e}")

    def _can_copy_merge(self, base_info, other_info):
        """判断是否可以无损合并（所有视频格式一致）"""
        return (
            base_info['v_codec'] == other_info['v_codec'] and
            base_info['a_codec'] == other_info['a_codec'] and
            base_info['width'] == other_info['width'] and
            base_info['height'] == other_info['height'] and
            abs(base_info['fps'] - other_info['fps']) < 0.01 and
            base_info['sample_rate'] == other_info['sample_rate']
        )

    def run(self):
        print("enter: 视频合并")
        if not self.video_files:
            self.finished.emit({"msg": "视频文件列表为空", "result_path": ""})
            return

        dir = os.path.dirname(self.video_files[0])
        result_dir = os.path.join(dir, "merged")
        os.makedirs(result_dir, exist_ok=True)
        output_filename = f"merged_video_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}.mp4"
        output_path = os.path.join(result_dir, output_filename)

        try:
            # 1. 探测第一个视频作为基准
            base_info = self._probe_video(self.video_files[0])
            print(f"基准视频格式: {base_info}")

            # 2. 检查是否所有视频都兼容 copy 合并
            use_copy = True
            for f in self.video_files[1:]:
                info = self._probe_video(f)
                if not self._can_copy_merge(base_info, info):
                    use_copy = False
                    break

            if use_copy:
                print("✅ 所有视频格式一致，使用无损快速合并（-c copy）")
                # 构建 concat 输入列表文件（避免命令行过长）
                list_file = os.path.join(result_dir, "input_files.txt")
                with open(list_file, 'w', encoding='utf-8') as f:
                    for vf in self.video_files:
                        f.write(f"file '{vf}'\n")

                (
                    ffmpeg
                    .input(list_file, format='concat', safe=0)
                    .output(output_path, c='copy')
                    .overwrite_output()
                    .run()
                )
                os.remove(list_file)  # 清理临时文件
            else:
                print("⚠️ 视频格式不一致，启用重编码合并（统一到基准格式）")
                streams = []
                has_audio = False

                for idx, f in enumerate(self.video_files):
                    inp = ffmpeg.input(f)
                    v = inp.video
                    a = inp.audio if any(s['codec_type'] == 'audio' for s in ffmpeg.probe(f)['streams']) else None

                    # 统一视频：缩放+帧率对齐（以第一个视频为准）
                    if idx > 0:
                        v = v.filter('scale', base_info['width'], base_info['height'])
                        # 可选：强制帧率（如果差异大）
                        # v = v.filter('fps', base_info['fps'])

                    # 统一音频：重采样 + aresample 对齐
                    if a is not None:
                        a = a.filter('aresample', **{
                            'async': 1,
                            'first_pts': 0,
                            'sample_rate': base_info['sample_rate'] or 44100
                        })
                    else:
                        a = ffmpeg.input('anullsrc', sample_rate=base_info['sample_rate'] or 44100,
                                         duration=ffmpeg.probe(f)['format']['duration']).audio

                    streams += [v, a]

                concat = ffmpeg.concat(*streams, v=1, a=1, n=len(self.video_files)).node
                vcat = concat[0]
                acat = concat[1]


                out = ffmpeg.output(
                    vcat, acat, output_path,
                    vcodec='libx264',
                    acodec='aac',
                    preset=self.preset,
                    crf=self.crf
                ).global_args('-fflags', '+genpts').overwrite_output()

                out.run()

            print(f"✅ 视频合并完成: {output_path}")
            self.finished.emit({
                "msg": f"视频合并完成！保存路径如下：",
                "result_path": result_dir
            })

        except Exception as e:
            print(f"❌ 视频合并出错: {e}")
            self.finished.emit({
                "msg": f"视频合并失败: {str(e)}",
                "result_path": ""
            })


class MergeSubtitleWorker(QThread):
    finished = pyqtSignal(dict)

    def __init__(self, subtitle_params: dict, parent=None):
        super().__init__(parent)
        self.subtitle_params = subtitle_params  # {path: offset_ms}
        dir = os.path.dirname(list(self.subtitle_params.keys())[0])
        self.output_dir = os.path.join(dir, "merged_subtitle")
        os.makedirs(self.output_dir, exist_ok=True)

    def run(self):
        try:
            merged_lines = []
            current_index = 1  # 字幕编号递增
            error_files = []

            output_filename = f"merged_subtitle_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}.srt"
            output_path = os.path.join(self.output_dir, output_filename)
            for path, offset in self.subtitle_params.items():
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                # 按 SRT 块切分
                blocks = re.split(r"\n\s*\n", content.strip(), flags=re.MULTILINE)
                i = 1
                for block in blocks:
                    lines = block.strip().split("\n")
                    if len(lines) < 2:
                        raise Exception(f"字幕文件{path}第{i}块格式错误")
                    # 时间行
                    time_line = lines[1] if "-->" in lines[1] else lines[0]
                    m = re.match(r"(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})", time_line)
                    if not m:
                        raise Exception(f"字幕文件{path}第{i}块格式错误")
                    start_time, end_time = m.groups()
                    start_ms = int(time_str_to_ms(start_time) + offset)
                    end_ms = int(time_str_to_ms(end_time) + offset)
                    # 重建块
                    new_block = [str(current_index)]
                    new_block.append(f"{ms_to_time_str(start_ms)} --> {ms_to_time_str(end_ms)}")
                    # 其余行 = 文本
                    if "-->" in lines[1]:
                        new_block.extend(lines[2:])  # 跳过原编号和时间行
                    else:
                        raise Exception(f"字幕文件{path}第{i}块格式错误")
                    merged_lines.append("\n".join(new_block))
                    current_index += 1
                    i += 1


            # 保存合并结果
            with open(output_path, "w", encoding="utf-8") as f:
                f.write("\n\n".join(merged_lines))

            self.finished.emit({
                "msg": f"字幕合并完成! 出错文件: {error_files}" if error_files else "字幕合并完成!",
                "result_path": self.output_dir
            })

        except Exception as e:
            self.finished.emit({
                "msg": f"字幕合并失败: {e}",
                "result_path": ""
            })



class SplitSubtitleWorker(QThread):
    finished = pyqtSignal(dict)

    def __init__(self, subtitle_params: dict, subtitle_path: str, parent=None):
        super().__init__(parent)
        self.subtitle_params = subtitle_params  # {path: offset_ms}
        self.subtitle_path = subtitle_path
        dir = os.path.dirname(self.subtitle_path)
        self.output_dir = os.path.join(dir, "split_subtitles")
        os.makedirs(self.output_dir, exist_ok=True)

    def run(self):
        try:
            # 准备拆分时间点
            print(self.subtitle_params)
            split_points = sorted(self.subtitle_params.values())
            print(split_points)
            # split_points.insert(0, 0)  # 添加起始点0

            # 读取原始字幕
            with open(self.subtitle_path, "r", encoding="utf-8") as f:
                content = f.read()

            # 解析字幕块
            blocks = re.split(r"\n\s*\n", content.strip(), flags=re.MULTILINE)
            subtitle_blocks = []

            for block in blocks:
                lines = block.strip().split("\n")
                if len(lines) < 2:
                    continue

                # 解析时间行
                time_line = lines[1] if "-->" in lines[1] else lines[0]
                m = re.match(r"(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})", time_line)
                if not m:
                    continue

                start_time, end_time = m.groups()
                start_ms = time_str_to_ms(start_time)
                end_ms = time_str_to_ms(end_time)

                # 文本内容
                text_lines = lines[2:] if "-->" in lines[1] else lines[1:]
                subtitle_blocks.append({
                    'start_ms': start_ms,
                    'end_ms': end_ms,
                    'text': "\n".join(text_lines)
                })

            # 按时间区间拆分字幕
            output_files = {}
            for i in range(len(split_points)):
                start_point = split_points[i]
                end_point = split_points[i + 1] if i < len(split_points) - 1 else math.inf

                part_blocks = []
                for block in subtitle_blocks:
                    if block['start_ms'] >= start_point and block['end_ms'] < end_point:
                        # 调整时间并添加到当前部分
                        adjusted_start = block['start_ms'] - start_point
                        adjusted_end = block['end_ms'] - start_point
                        part_blocks.append({
                            'start': adjusted_start,
                            'end': adjusted_end,
                            'text': block['text']
                        })

                # 如果当前时间段有字幕，则创建文件
                if part_blocks:
                    # 按时间排序并重新编号
                    part_blocks.sort(key=lambda x: x['start'])
                    output_lines = []
                    for idx, block in enumerate(part_blocks, start=1):
                        start_str = ms_to_time_str(block['start'])
                        end_str = ms_to_time_str(block['end'])
                        output_lines.append(f"{idx}\n{start_str} --> {end_str}\n{block['text']}")

                    # 保存文件
                    output_filename = f"part_{i + 1}.srt"
                    output_path = os.path.join(self.output_dir, output_filename)
                    with open(output_path, "w", encoding="utf-8") as f:
                        f.write("\n\n".join(output_lines))

                    output_files[i + 1] = output_path

            self.finished.emit({
                "msg": f"字幕拆分完成，共生成{len(output_files)}个文件",
                "result_path": self.output_dir,
                "output_files": output_files
            })

        except Exception as e:
            self.finished.emit({
                "msg": f"字幕拆分失败: {e}",
                "result_path": "",
                "output_files": {}
            })

class CloneVoiceWorker(QThread):
    # 定义一个信号，用于在任务完成后更新 GUI
    finished = pyqtSignal(dict)
    item_finished = pyqtSignal(int)

    def __init__(self, voice_files: []):
        super().__init__()
        self.voice_files = voice_files

    def run(self):
        print("enter: 语音克隆")
        timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        error_files = []
        connect = dubbingElevenLabs.getInstance()
        db_connect = datasetUtils.getInstance()
        for file_path in self.voice_files:
            if os.path.isfile(file_path):
                name = os.path.splitext(os.path.basename(file_path))[0]
                voice_name = "{}-{}".format(name, timestamp)
                try:
                    voice = connect.elevenlabs.voices.ivc.create(
                        name=voice_name,
                        # Replace with the paths to your audio files.
                        # The more files you add, the better the clone will be.
                        files=[io.BytesIO(open(file_path, "rb").read())]
                    )
                    print(voice)
                    db_connect.save_voice_id(api_id=1, voice_name=voice_name, voice_id=voice.voice_id)
                    print(f"克隆成功{file_path}")
                except Exception as e:
                    print(f"❌ 处理 {file_path} 出错: {e}")
                    error_files.append(file_path)
        if error_files:
            print("未完成语音克隆文件:", error_files)
            self.finished.emit({"msg": f"语音克隆完成! 未完成的语音{error_files}", "result_path": ""})
        else:
            self.finished.emit({"msg": "语音克隆完成!",  "result_path": ""})
        return



class SyncSubtitleWorker(QThread):
    finished = pyqtSignal(dict)

    def __init__(self, src_subtitle_paths: list, dst_subtitle_paths: list, parent=None):
        super().__init__(parent)
        self.src_subtitle_paths = src_subtitle_paths
        self.dst_subtitle_paths = dst_subtitle_paths
        dir = os.path.dirname(self.dst_subtitle_paths[0])
        print(dir)
        self.output_dir = os.path.join(dir, "sync_subtitle")
        os.makedirs(self.output_dir, exist_ok=True)

    def run(self):
        print("enter: 字幕同步")
        output_files = []
        error_files = []
        total_files = len(self.dst_subtitle_paths)

        self.output_subtitle_dir = os.path.join(self.output_dir, "subtitle")
        self.output_role_list_dir = os.path.join(self.output_dir, "role_list")
        os.makedirs(self.output_role_list_dir, exist_ok=True)
        os.makedirs(self.output_subtitle_dir, exist_ok=True)

        # TODO: 字幕同步
        for i, (src_path, dst_path) in enumerate(zip(self.src_subtitle_paths, self.dst_subtitle_paths)):
            try:
                base_name = os.path.basename(dst_path)
                print(f"开始处理: {src_path} -> {dst_path}")

                src_subs, src_roles = parse_subtitle_uncertain(src_path)
                dst_subs, _ = parse_subtitle_uncertain(dst_path)

                if not src_subs or not dst_subs or not src_roles:
                    print(
                        f"警告: 解析失败或内容为空. Src: {len(src_subs)}, Dst: {len(dst_subs)}, Roles: {len(src_roles)}. 跳过文件 {dst_path}")
                    error_files.append(dst_path)
                    continue

                # 1. 预处理：转换时间为秒
                for sub in src_subs:
                    sub['start_sec'] = time_str_to_ms(sub['start'])
                    sub['end_sec'] = time_str_to_ms(sub['end'])

                for sub in dst_subs:
                    sub['start_sec'] = time_str_to_ms(sub['start'])
                    sub['end_sec'] = time_str_to_ms(sub['end'])
                    sub['duration_sec'] = sub['end_sec'] - sub['start_sec']

                # 2. 核心同步算法
                new_dst_subs = []
                role_match_list = []
                src_ptr = 0

                for dst_sub in dst_subs:
                    overlapping_src = []

                    # 使用双指针优化查找
                    # 向前移动src_ptr，跳过所有在dst_sub开始前就已经结束的src字幕
                    while src_ptr < len(src_subs) and src_subs[src_ptr]['end_sec'] < dst_sub['start_sec']:
                        src_ptr += 1

                    # 从当前src_ptr开始，查找所有与dst_sub重叠的src字幕
                    temp_ptr = src_ptr
                    while temp_ptr < len(src_subs) and src_subs[temp_ptr]['start_sec'] < dst_sub['end_sec']:
                        # 计算重叠时间
                        overlap_start = max(dst_sub['start_sec'], src_subs[temp_ptr]['start_sec'])
                        overlap_end = min(dst_sub['end_sec'], src_subs[temp_ptr]['end_sec'])
                        overlap_duration = overlap_end - overlap_start

                        if overlap_duration > 0:
                            overlapping_src.append({
                                "index": temp_ptr,
                                'role': src_roles[temp_ptr],
                                'overlap_duration': overlap_duration,
                                'src_duration': src_subs[temp_ptr]['end_sec'] - src_subs[temp_ptr]['start_sec']
                            })
                        temp_ptr += 1

                    assigned_role = "未知"  # 默认角色

                    if overlapping_src:
                        # 规则 1: 检查是否存在90%以上的覆盖
                        strong_match_found = False
                        for overlap_info in overlapping_src:
                            # 如果dst字幕的90%被某一个src字幕覆盖
                            if overlap_info['overlap_duration'] / dst_sub['duration_sec'] > 0.85:
                                assigned_role = overlap_info['role']  #  找到role了
                                strong_match_found = True
                                # print(src_subs[overlap_info['index']], overlap_info['role'])
                                # print(dst_sub)
                                break

                        if not strong_match_found:
                            print("未找到85%以上的覆盖")
                            for overlap_info in overlapping_src:
                                print(src_subs[overlap_info['index']], overlap_info['role'])
                            print("-====-")
                            print(dst_sub)
                            # 规则 2: 投票和时长判断
                            # 投票
                            role_votes = Counter(info['role'] for info in overlapping_src)
                            winners = []
                            if role_votes:
                                max_vote = max(role_votes.values())
                                winners = [role for role, count in role_votes.items() if count == max_vote]

                            if len(winners) == 1:
                                # 只有一个胜出者
                                assigned_role = winners[0]
                            elif len(winners) > 1:
                                # 票数相同，进行时长判断
                                max_duration = -1
                                duration_winner = assigned_role
                                for role in winners:
                                    total_duration = sum(
                                        info['overlap_duration'] for info in overlapping_src if info['role'] == role)
                                    if total_duration > max_duration:
                                        max_duration = total_duration
                                        duration_winner = role
                                assigned_role = duration_winner

                    # 更新字幕文本
                    dst_sub['text'] = f"{assigned_role}: {dst_sub['text']}"
                    new_dst_subs.append(dst_sub)
                    role_match_list.append(assigned_role)

                # 3. 生成并保存新的SRT文件
                output_path = os.path.join(self.output_subtitle_dir, base_name)
                with open(output_path, 'w', encoding='utf-8') as f:
                    for sub in new_dst_subs:
                        f.write(f"{sub['index']}\n")
                        f.write(f"{sub['start']} --> {sub['end']}\n")
                        f.write(f"{sub['text']}\n\n")
                # 4. 生成并保存角色列表
                role_list_path = os.path.join(self.output_role_list_dir, base_name.replace(".srt", "_role_list.txt"))
                with open(role_list_path, 'w', encoding='utf-8') as f:
                    for role in set(role_match_list):
                        f.write(f"{role}\n")

                output_files.append(output_path)
                print(f"处理完成: {output_path}")

            except Exception as e:
                print(f"处理文件 {dst_path} 时发生严重错误: {e}")
                error_files.append(dst_path)

        # 完成所有任务
        if error_files:
            print("未完成字幕同步文件:", error_files)
            msg = f"同步任务完成，成功 {len(output_files)} 个文件，未完成的字幕文件{error_files} 个。"
        else:
            msg = f"字幕同步全部完成，共生成 {len(output_files)} 个文件。"
        self.finished.emit({
            "msg": msg,
            "result_path": self.output_dir,
            "output_files": output_files,
            "error_files": error_files  # 建议也返回错误文件列表
        })

class SplitVideoWorker(QThread):
    finished = pyqtSignal(dict)

    def __init__(self, src_video_path: str, dst_video_paths: list, parent=None):
        super().__init__(parent)
        self.src_video_path = src_video_path
        self.dst_video_paths = dst_video_paths

    def run(self):
        print("enter: 视频分割")

        # 获取源视频所在目录作为输出目录
        dir = os.path.dirname(self.src_video_path)
        result_dir = os.path.join(dir, "split_videos")
        os.makedirs(result_dir, exist_ok=True)

        try:
            # 获取每个目标视频的时长
            durations = []
            for dst_path in self.dst_video_paths:
                info = ffmpeg.probe(dst_path)
                duration = float(info['format']['duration'])
                durations.append(duration)

            # 计算分割点（累积时长）
            split_points = [0]  # 起始点
            for duration in durations:
                split_points.append(split_points[-1] + duration)

            # 分割源视频
            output_files = []
            src_filename = os.path.splitext(os.path.basename(self.src_video_path))[0]

            for i in range(len(durations)):
                start_time = split_points[i]
                end_time = split_points[i + 1]
                duration = durations[i]

                output_filename = f"{src_filename}_part_{i + 1:02d}.mp4"
                output_path = os.path.join(result_dir, output_filename)

                # 使用 ffmpeg 进行分割，不能使用copy啊，copy不会找到精确的start_time，前几秒会压缩卡顿
                # (
                #     ffmpeg
                #     .input(self.src_video_path, ss=start_time, t=duration)
                #     .output(output_path, c='copy')  # 使用 copy 以加快速度并保持质量
                #     .overwrite_output()
                #     .run()
                # )
                (
                    ffmpeg
                    .input(self.src_video_path, ss=start_time, t=duration)
                    .output(
                        output_path,
                        vcodec='libx264',
                        acodec='aac',
                        preset='ultrafast',
                        crf=28,
                        pix_fmt='yuv420p'
                    )
                    .overwrite_output()
                    .run()
                )

                output_files.append(output_path)
                print(f"✅ 已保存分割视频: {output_path}")

            self.finished.emit({
                "msg": f"视频分割完成! 共生成 {len(output_files)} 个文件",
                "result_path": result_dir,
                "output_files": output_files
            })

        except Exception as e:
            print(f"❌ 视频分割出错: {e}")
            self.finished.emit({
                "msg": f"视频分割失败: {str(e)}",
                "result_path": ""
            })

class GetVideoAudioWorker(QThread):
    finished = pyqtSignal(dict)

    def __init__(self, video_path: list[str], parent=None):
        super().__init__(parent)
        self.video_paths = video_path

    def run(self):
        print("enter: 获取视频音频")
        try:
            dir = os.path.dirname(self.video_paths[0])
            result_dir = os.path.join(dir, "audio")
            os.makedirs(result_dir, exist_ok=True)

            for video_path in self.video_paths:

                audio_path = os.path.join(result_dir, os.path.splitext(os.path.basename(video_path))[0] + ".wav")

                audio, sr = get_audio_np_from_video(video_path)

                sf.write(audio_path, audio, sr)

            self.finished.emit({
                "msg": f"获取音频完成! 共生成 {len(self.video_paths)} 个文件",
                "result_path": result_dir,
            })

        except Exception as e:
            print(f"❌ 获取音频出错: {e}")
            self.finished.emit({
                "msg": f"获取音频失败: {str(e)}",
                "result_path": ""
            })

            # (
            #     ffmpeg
            #     .input(video_path)
            #     .output(audio_path, acodec='pcm_s16le', ac=1, ar='16k')
            #     .overwrite_output()
            #     .run()
            # )
            # print(f"✅ 已保存音频: {audio_path}")



