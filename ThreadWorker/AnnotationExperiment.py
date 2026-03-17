import os
import re
import traceback
import tempfile
import shutil

from PyQt5.QtCore import QThread, pyqtSignal

from Service.generalUtils import time_str_to_ms, ms_to_time_str
from Service.subtitleUtils import parse_subtitle_uncertain
from Service.videoUtils import get_audio_np_from_video, _probe_video_duration_ms
from Service.mergeVideoUtils import merge_video


def count_subtitle_entries(srt_path):
    """计算SRT文件中的字幕条数"""
    try:
        with open(srt_path, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            blocks = content.split("\n\n")
            return len([block for block in blocks if block.strip()])
    except Exception as e:
        print(f"Error counting subtitle entries: {e}")
        return 0


def merge_srt_files_with_offset(srt_files, output_path):
    """
    合并多个SRT文件，保持时间轴连续

    Args:
        srt_files: [(srt_path, time_offset_ms), ...]
        output_path: 输出文件路径
    """
    merged_lines = []
    current_index = 1

    for srt_path, offset_ms in srt_files:
        with open(srt_path, 'r', encoding='utf-8') as f:
            content = f.read().strip()

        blocks = content.split("\n\n")
        for block in blocks:
            lines = block.strip().split("\n")
            if len(lines) >= 3:
                # 解析时间行
                time_line = lines[1]
                match = re.match(r"(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})", time_line)
                if match:
                    start_time, end_time = match.groups()
                    start_ms = time_str_to_ms(start_time) + offset_ms
                    end_ms = time_str_to_ms(end_time) + offset_ms

                    # 重建块
                    new_block = [str(current_index)]
                    new_block.append(f"{ms_to_time_str(start_ms)} --> {ms_to_time_str(end_ms)}")
                    new_block.extend(lines[2:])  # 文本内容

                    merged_lines.append("\n".join(new_block))
                    current_index += 1

    # 保存合并结果
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("\n\n".join(merged_lines))


def split_merged_srt_back(marked_srt_path, original_srt_files_info, output_dir):
    """
    将标记好的合并字幕拆分回原来的各个文件

    Args:
        marked_srt_path: 标记好的合并字幕文件路径
        original_srt_files_info: [(original_srt_path, time_offset_ms), ...]
        output_dir: 输出目录
    """
    # 读取标记好的合并字幕
    with open(marked_srt_path, 'r', encoding='utf-8') as f:
        content = f.read().strip()

    blocks = content.split("\n\n")
    merged_subs = []

    for block in blocks:
        lines = block.strip().split("\n")
        if len(lines) >= 3:
            index = int(lines[0])
            time_line = lines[1]
            match = re.match(r"(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})", time_line)
            if match:
                start_time, end_time = match.groups()
                text = "\n".join(lines[2:])
                merged_subs.append({
                    'index': index,
                    'start': start_time,
                    'end': end_time,
                    'text': text
                })

    # 按时间偏移量拆分回原文件
    for i, (original_srt_path, offset_ms) in enumerate(original_srt_files_info):
        next_offset = original_srt_files_info[i + 1][1] if i + 1 < len(original_srt_files_info) else float('inf')

        # 筛选出属于当前文件的字幕
        current_subs = []
        for sub in merged_subs:
            sub_start_ms = time_str_to_ms(sub['start'])
            if offset_ms <= sub_start_ms < next_offset:
                # 调整时间轴回到原文件的时间范围
                adjusted_start_ms = sub_start_ms - offset_ms
                adjusted_end_ms = time_str_to_ms(sub['end']) - offset_ms
                current_subs.append({
                    'start': ms_to_time_str(adjusted_start_ms),
                    'end': ms_to_time_str(adjusted_end_ms),
                    'text': sub['text']
                })

        # 保存到新文件
        if current_subs:
            base_name = os.path.splitext(os.path.basename(original_srt_path))[0]
            output_srt_path = os.path.join(output_dir, f"{base_name}_角色标注.srt")

            with open(output_srt_path, 'w', encoding='utf-8') as f:
                for idx, sub in enumerate(current_subs, 1):
                    f.write(f"{idx}\n")
                    f.write(f"{sub['start']} --> {sub['end']}\n")
                    f.write(f"{sub['text']}\n\n")


class BatchAnnotationWorker_with_AudioFeature(QThread):
    """
    QThread worker that uses a ThreadPoolExecutor to annotate roles for each (video, srt) pair in parallel.
    """
    finished = pyqtSignal(dict)
    progress = pyqtSignal(int, str)

    def __init__(self, pairs, role_info_text, output_root_dir, extraOutput=False, max_workers=3,
                 if_translate: bool = False, language: str = ""):
        super().__init__()
        self.pairs = pairs
        self.role_info_text = role_info_text
        self.output_root_dir = output_root_dir
        self.max_workers = max_workers
        self.extraOutput = extraOutput
        self.if_translate = if_translate
        self.language = language
        self.strip = 100

    def run(self):
        try:
            os.makedirs(self.output_root_dir, exist_ok=True)
            self.summary_dir = os.path.join(self.output_root_dir, "剧情简介")
            self.srt_dir = os.path.join(self.output_root_dir, "字幕")
            self.role_dir = os.path.join(self.output_root_dir, "角色表")
            self.processing_dir = os.path.join(self.output_root_dir, "中间结果")
            self.batch_merge_dir = os.path.join(self.output_root_dir, "视频字幕合并中间结果")
            os.makedirs(self.summary_dir, exist_ok=True)
            os.makedirs(self.srt_dir, exist_ok=True)
            os.makedirs(self.role_dir, exist_ok=True)
            os.makedirs(self.processing_dir, exist_ok=True)
            os.makedirs(self.batch_merge_dir, exist_ok=True)

            from Service.dubbingMain.llmAPI import LLMAPI
            LLMAPI.getInstance()  # initialize once

            def process_one_batch(batch_pairs, batch_idx):
                """处理一批视频/字幕对"""
                try:
                    # 如果只有一个文件对，直接处理
                    # if len(batch_pairs) == 1:
                    #     idx, video_path, srt_path = batch_pairs[0]
                    #     return _process_single_pair(idx, video_path, srt_path)

                    # 合并多个视频和字幕
                    print(f"Processing batch {batch_idx}: Merging {len(batch_pairs)} videos/subtitles...")

                    # 1. 合并视频
                    video_paths = [pair[1] for pair in batch_pairs]
                    merge_result = merge_video(video_paths, id = batch_idx, result_dir = self.batch_merge_dir)
                    if not merge_result["result_path"]:
                        raise Exception(f"视频合并失败: {merge_result['msg']}")
                    merged_video_path = merge_result["result_path"]

                    # 2. 合并字幕文件（需要计算时间偏移）
                    srt_files_with_offset = []
                    total_duration = 0

                    # try:
                    for i, (idx, video_path, srt_path) in enumerate(batch_pairs):
                        srt_files_with_offset.append((srt_path, total_duration))
                        # 累加视频时长作为下一个文件的时间偏移
                        if i < len(batch_pairs) - 1:
                            duration_ms = _probe_video_duration_ms(video_path)
                            total_duration += duration_ms
                    # 合并字幕
                    merged_srt_path = os.path.join(self.batch_merge_dir, f"字幕合并_{batch_idx}.srt")
                    merge_srt_files_with_offset(srt_files_with_offset, merged_srt_path)
                    # 3. 处理合并后的视频和字幕
                    translated_srt_path = merged_srt_path
                    with open(merged_srt_path, 'r', encoding='utf-8') as f:
                        original_subtitle_text = f.read().strip()

                    # 翻译字幕（如果需要）
                    if self.if_translate:
                        print(f"Processing batch {batch_idx}: Translating subtitle...")
                        input_subtitles, _ = parse_subtitle_uncertain(merged_srt_path)
                        translated_subtitles = LLMAPI.getInstance().translate_subtitle_with_audio(
                            str(input_subtitles), merged_video_path, language=self.language
                        )
                        # 转换为SRT格式
                        translated_srt_text = ""
                        for i, sub in enumerate(translated_subtitles, 1):
                            translated_srt_text += f"{i}\n{sub['start']} --> {sub['end']}\n{sub['text']}\n\n"
                        working_subtitle_text = translated_srt_text.strip()
                        # 保存翻译后的字幕
                        translated_srt_path = os.path.join(self.processing_dir, f"translated_{batch_idx}_m.srt")
                        with open(translated_srt_path, 'w', encoding='utf-8') as f:
                            f.write(working_subtitle_text)
                    else:
                        working_subtitle_text = original_subtitle_text
                    # 4. 使用音频合并字幕
                    merge_result = LLMAPI.getInstance().merge_subtitle_with_audio_2(
                        working_subtitle_text, merged_video_path, language=self.language
                    )
                    # 创建合并后的字幕文本
                    original_subs, _ = parse_subtitle_uncertain(
                        merged_srt_path if not self.if_translate else translated_srt_path
                    )
                    merged_subtitles = []
                    for merge_idx, original_indices in enumerate(merge_result, 1):
                        first_idx = original_indices[0] - 1
                        last_idx = original_indices[-1] - 1
                        if first_idx < len(original_subs) and last_idx < len(original_subs):
                            start_time = original_subs[first_idx]['start']
                            end_time = original_subs[last_idx]['end']
                            # 合并所有合并字幕的文本
                            combined_text = ""
                            for orig_idx in original_indices:
                                if orig_idx - 1 < len(original_subs):
                                    if combined_text:
                                        combined_text += " "
                                    combined_text += original_subs[orig_idx - 1]['text']
                            merged_subtitles.append({
                                'index': merge_idx,
                                'start': start_time,
                                'end': end_time,
                                'text': combined_text
                            })
                    # 保存合并字幕
                    merged_srt_text = ""
                    for sub in merged_subtitles:
                        merged_srt_text += f"{sub['index']}\n{sub['start']} --> {sub['end']}\n{sub['text']}\n\n"
                    batch_merged_srt_path = os.path.join(self.processing_dir, f"短句合并_{batch_idx}_m.srt")
                    with open(batch_merged_srt_path, 'w', encoding='utf-8') as f:
                        f.write(merged_srt_text.strip())
                    # 5. 匹配合并字幕的角色
                    print(f"Processing batch {batch_idx}: Matching roles for merged subtitles...")
                    merged_role_result = LLMAPI.getInstance().match_role_by_hint(
                        merged_srt_text.strip(), "", self.role_info_text, merged_video_path, language=self.language,
                    )
                    # 匹配角色后，写入合并后的字幕
                    merged_original_text = ""
                    for i, sub in enumerate(merged_subtitles, 1):
                        role = merged_role_result.get(str(i), "未知角色")
                        merged_original_text += f"{i}\n{sub['start']} --> {sub['end']}\n{role}: {sub['text']}\n\n"
                    merged_original_path = os.path.join(self.processing_dir,
                                                        f"first_annotated_短句合并_{batch_idx}_m.srt")
                    with open(merged_original_path, 'w', encoding='utf-8') as f:
                        f.write(merged_original_text.strip())
                    # 6. 将角色映射回原始字幕
                    original_roles = {}
                    for merge_idx, original_indices in enumerate(merge_result, 1):
                        role = merged_role_result.get(str(merge_idx), "未知角色")
                        for orig_idx in original_indices:
                            original_roles[str(orig_idx)] = role
                    # 7. 创建标记的原始字幕
                    annotated_original_text = ""
                    for i, sub in enumerate(original_subs, 1):
                        role = original_roles.get(str(i), "未知角色")
                        annotated_original_text += f"{i}\n{sub['start']} --> {sub['end']}\n{role}: {sub['text']}\n\n"
                    annotated_original_path = os.path.join(self.processing_dir,
                                                           f"first_annotated_{batch_idx}_m.srt")
                    with open(annotated_original_path, 'w', encoding='utf-8') as f:
                        f.write(annotated_original_text.strip())
                    # 8. 仲裁员验证
                    print(f"Processing batch {batch_idx}: Verifying roles with arbitrator...")
                    final_role_result = LLMAPI.getInstance().arbitrator_roles(
                        annotated_original_text.strip(), "", self.role_info_text, merged_video_path,
                        language=self.language
                    )
                    # 9. 生成最终字幕文件
                    final_subtitles = []
                    input_subtitles, _ = parse_subtitle_uncertain(merged_srt_path)
                    for i, sub in enumerate(input_subtitles, 1):
                        final_role = final_role_result.get(str(i), original_roles.get(str(i), "未知角色"))
                        final_subtitles.append({
                            'index': i,
                            'start': sub['start'],
                            'end': sub['end'],
                            'text': sub['text'],
                            'role': final_role
                        })
                    # 10. 保存合并后的最终字幕
                    batch_final_srt_path = os.path.join(self.batch_merge_dir, f"final_annotated_{batch_idx}.srt")
                    with open(batch_final_srt_path, 'w', encoding='utf-8') as f:
                        for sub in final_subtitles:
                            f.write(f"{sub['index']}\n")
                            f.write(f"{sub['start']} --> {sub['end']}\n")
                            f.write(f"{sub['role']}: {sub['text']}\n\n")
                    # 11. 将合并的字幕拆分回原来的各个文件
                    split_merged_srt_back(batch_final_srt_path, srt_files_with_offset, self.srt_dir)
                    # 返回成功的文件数量和总时长
                    duration_ms = _probe_video_duration_ms(merged_video_path)
                    return len(batch_pairs), duration_ms

                except Exception as e:
                    raise Exception(f"批处理失败: {e}")

            # def process_one(idx, video_path, srt_path):
            #     """处理单个视频/字幕对（为了保持接口兼容性）"""
            #     return self._process_single_pair(idx, video_path, srt_path)

            def _process_single_pair(idx, video_path, srt_path):

                """处理单个视频/字幕对的原始逻辑"""
                try:
                    translated_srt_path = srt_path  # 初始化翻译字幕路径
                    # 1) Read original subtitle
                    with open(srt_path, 'r', encoding='utf-8') as f:
                        original_subtitle_text = f.read().strip()

                    # 2) If translation is needed, translate the subtitle
                    if self.if_translate:
                        print(f"Processing {idx}: Translating subtitle...")
                        input_subtitles, _ = parse_subtitle_uncertain(srt_path)
                        translated_subtitles = LLMAPI.getInstance().translate_subtitle_with_audio(str(input_subtitles),
                                                                                                  video_path,
                                                                                                  language=self.language)
                        # Convert to SRT format for further processing
                        translated_srt_text = ""
                        for i, sub in enumerate(translated_subtitles, 1):
                            translated_srt_text += f"{i}\n{sub['start']} --> {sub['end']}\n{sub['text']}\n\n"
                        working_subtitle_text = translated_srt_text.strip()

                        # Save translated subtitle
                        translated_srt_path = os.path.join(self.processing_dir, f"translated_{idx}.srt")
                        with open(translated_srt_path, 'w', encoding='utf-8') as f:
                            f.write(working_subtitle_text)
                    else:
                        working_subtitle_text = original_subtitle_text

                    # 3) Merge subtitles using audio
                    # print(f"Processing {idx}: Merging subtitles with audio...")
                    merge_result = LLMAPI.getInstance().merge_subtitle_with_audio_2(working_subtitle_text, video_path,
                                                                                    language=self.language)

                    # Create merged subtitle text
                    # Parse original subtitles to get time info
                    original_subs, _ = parse_subtitle_uncertain(
                        srt_path if not self.if_translate else translated_srt_path)
                    merged_subtitles = []
                    for merge_idx, original_indices in enumerate(merge_result, 1):
                        # Get the first subtitle's time range
                        first_idx = original_indices[0] - 1  # Convert to 0-based index
                        last_idx = original_indices[-1] - 1

                        if first_idx < len(original_subs) and last_idx < len(original_subs):
                            start_time = original_subs[first_idx]['start']
                            end_time = original_subs[last_idx]['end']

                            # Combine text from all merged subtitles
                            combined_text = ""
                            for orig_idx in original_indices:
                                if orig_idx - 1 < len(original_subs):
                                    if combined_text:
                                        combined_text += " "
                                    combined_text += original_subs[orig_idx - 1]['text']

                            merged_subtitles.append({
                                'index': merge_idx,
                                'start': start_time,
                                'end': end_time,
                                'text': combined_text
                            })

                    # Save merged subtitle
                    merged_srt_text = ""
                    for sub in merged_subtitles:
                        merged_srt_text += f"{sub['index']}\n{sub['start']} --> {sub['end']}\n{sub['text']}\n\n"

                    merged_srt_path = os.path.join(self.processing_dir, f"短句合并_{idx}.srt")
                    with open(merged_srt_path, 'w', encoding='utf-8') as f:
                        f.write(merged_srt_text.strip())

                    # 4) Match roles for merged subtitles
                    print(f"Processing {idx}: Matching roles for merged subtitles...")
                    merged_role_result = LLMAPI.getInstance().match_role_by_hint(
                        merged_srt_text.strip(), "", self.role_info_text, video_path, language=self.language,
                    )

                    # match角色之后，先写入合并后的字幕
                    merged_original_text = ""
                    for i, sub in enumerate(merged_subtitles, 1):
                        role = merged_role_result.get(str(i), "未知角色")
                        merged_original_text += f"{i}\n{sub['start']} --> {sub['end']}\n{role}: {sub['text']}\n\n"
                    merged_original_path = os.path.join(self.processing_dir, f"first_annotated_短句合并_{idx}.srt")
                    with open(merged_original_path, 'w', encoding='utf-8') as f:
                        f.write(merged_original_text.strip())

                    # 5) Map roles back to original subtitles  dict2dict
                    original_roles = {}
                    for merge_idx, original_indices in enumerate(merge_result, 1):
                        role = merged_role_result.get(str(merge_idx), "未知角色")
                        for orig_idx in original_indices:
                            original_roles[str(orig_idx)] = role

                    # 6) Create annotated original subtitle
                    # original_subs, _ = parse_subtitle_uncertain(srt_path if not self.if_translate else translated_srt_path)
                    annotated_original_text = ""
                    for i, sub in enumerate(original_subs, 1):
                        role = original_roles.get(str(i), "未知角色")
                        annotated_original_text += f"{i}\n{sub['start']} --> {sub['end']}\n{role}: {sub['text']}\n\n"
                    annotated_original_path = os.path.join(self.processing_dir, f"first_annotated_原始字幕{idx}.srt")
                    with open(annotated_original_path, 'w', encoding='utf-8') as f:
                        f.write(annotated_original_text.strip())

                    # 7) Arbitrator verification
                    print(f"Processing {idx}: Verifying roles with arbitrator...")
                    final_role_result = LLMAPI.getInstance().arbitrator_roles(
                        annotated_original_text.strip(), "", self.role_info_text, video_path, language=self.language
                    )

                    # 8) Generate final subtitle file

                    final_subtitles = []
                    input_subtitles, _ = parse_subtitle_uncertain(srt_path)
                    for i, sub in enumerate(input_subtitles, 1):
                        final_role = final_role_result.get(str(i), original_roles.get(str(i), "未知角色"))
                        final_subtitles.append({
                            'index': i,
                            'start': sub['start'],
                            'end': sub['end'],
                            'text': sub['text'],
                            'role': final_role
                        })

                    # 9) Write output files
                    base_name = os.path.splitext(os.path.basename(srt_path))[0]
                    output_srt_path = os.path.join(self.srt_dir, f"{base_name}_{idx}_角色标注.srt")
                    role_table_file = os.path.join(self.role_dir, f"角色表{idx}.txt")

                    with open(output_srt_path, 'w', encoding='utf-8') as f:
                        for sub in final_subtitles:
                            f.write(f"{sub['index']}\n")
                            f.write(f"{sub['start']} --> {sub['end']}\n")
                            f.write(f"{sub['role']}: {sub['text']}\n\n")

                    # Write role table
                    roles_list = [sub['role'] for sub in final_subtitles]
                    with open(role_table_file, "w", encoding="utf-8") as f:
                        f.write(";".join(roles_list))

                    duration_ms = _probe_video_duration_ms(video_path)
                    return output_srt_path, duration_ms

                except Exception as e:
                    raise Exception(f"处理失败: {e}")

            total = len(self.pairs)
            completed = 0
            failed = []
            sub_results = [None] * total
            self.progress.emit(0, f"开始处理，共 {total} 组...   ")

            # 创建批次处理队列
            batches = []
            i = 0
            while i < len(self.pairs):
                current_batch = []
                subtitle_count = 0

                # 收集字幕条数少于100的视频/字幕对作为一个批次
                while i < len(self.pairs) and subtitle_count < self.strip:
                    pair = self.pairs[i]
                    v, s = pair
                    count = count_subtitle_entries(s)
                    if count == 0:
                        # 如果无法计算字幕条数，单独处理
                        if current_batch:
                            batches.append(current_batch)
                            current_batch = []
                        batches.append([(i, v, s)])
                        i += 1
                        break
                    else:
                        current_batch.append((i, v, s))
                        subtitle_count += count
                        i += 1

                    if subtitle_count > self.strip and current_batch:
                        # 如果当前总条数超过100条，且已有文件在批次中，则结束当前批次
                        break

                if current_batch:
                    batches.append(current_batch)

            print(f"总共 {len(self.pairs)} 个文件对，分为 {len(batches)} 个批次处理")

            from concurrent.futures import ThreadPoolExecutor, as_completed
            # import ffmpeg
            batch_log_path = os.path.join(self.output_root_dir, "批量日志.txt")
            with open(batch_log_path, 'w', encoding='utf-8') as f:
                for batch_idx, batch_pairs in enumerate(batches):
                    f.write(f"批次 {batch_idx + 1}，共 {len(batch_pairs)} 个文件对，处理文件为：{', '.join([os.path.basename(v) for _, v, _ in batch_pairs])}\n")

            total = len(batches)
            # 存储成功条目的 (导出字幕路径, 视频时长ms)，按原顺序
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                future_to_ctx = {}
                for batch_idx, batch_pairs in enumerate(batches):
                    # 为批次创建一个处理任务
                    fut = executor.submit(process_one_batch, batch_pairs, batch_idx)
                    future_to_ctx[fut] = batch_pairs

                for fut in as_completed(future_to_ctx):
                    batch_pairs = future_to_ctx[fut]
                    try:
                        # 更新完成计数（根据批次中文件的数量）
                        completed += len(batch_pairs)
                        pct = int((completed * 100) / total)
                        self.progress.emit(pct, f"正在处理：{completed}/{total}，失败 {len(failed)}...   ")
                    except Exception as e:
                        for pair in batch_pairs:
                            idx, v, s = pair
                            failed.append((os.path.basename(v), os.path.basename(s), str(e), traceback.format_exc()))
                        completed += len(batch_pairs)
                        pct = int((completed * 100) / total)
                        self.progress.emit(pct, f"正在处理：{completed}/{total}，失败 {len(failed)}...   ")

            # save error log if any
            if failed:
                error_log_path = os.path.join(self.output_root_dir, "error_log.txt")
                with open(error_log_path, 'w', encoding='utf-8') as f:
                    f.write("发生错误的条目如下:\n\n")
                    for vname, sname, err, tb in failed:
                        f.write(f"视频: {vname}  字幕: {sname}\n错误: {err}\n{tb}\n---\n")

            msg = f"批量角色标注完成，成功 {total - len(failed)}，失败 {len(failed)}。"
            self.finished.emit({
                "msg": msg,
                "result_path": self.output_root_dir
            })
        except Exception as e:
            print(e)
            print(traceback.format_exc())
            self.finished.emit({
                "msg": f"发生错误: {e}",
                "result_path": self.output_root_dir if os.path.isdir(self.output_root_dir) else ""
            })


class BatchAnnotationWorker_with_AudioFeature_no_split(QThread):
    """
    QThread worker that uses a ThreadPoolExecutor to annotate roles for each (video, srt) pair in parallel.
    """
    finished = pyqtSignal(dict)
    progress = pyqtSignal(int, str)

    def __init__(self, pairs, role_info_text, output_root_dir, extraOutput=False, max_workers=3,
                 if_translate: bool = False, language: str = ""):
        super().__init__()
        self.pairs = pairs
        self.role_info_text = role_info_text
        self.output_root_dir = output_root_dir
        self.max_workers = max_workers
        self.extraOutput = extraOutput
        self.if_translate = if_translate
        self.language = language
        self.strip = 300

    def run(self):
        try:
            os.makedirs(self.output_root_dir, exist_ok=True)
            self.srt_dir = os.path.join(self.output_root_dir, "单集标注字幕结果")
            self.processing_dir = os.path.join(self.output_root_dir, "中间结果")
            self.batch_merge_dir = os.path.join(self.output_root_dir, "合并的视频与字幕结果")
            os.makedirs(self.srt_dir, exist_ok=True)
            os.makedirs(self.processing_dir, exist_ok=True)
            os.makedirs(self.batch_merge_dir, exist_ok=True)

            from Service.dubbingMain.llmAPI import LLMAPI
            LLMAPI.getInstance()  # initialize once

            def process_one_batch(batch_pairs, batch_idx):
                """处理一批视频/字幕对"""
                try:
                    # 如果只有一个文件对，直接处理
                    # if len(batch_pairs) == 1:
                    #     idx, video_path, srt_path = batch_pairs[0]
                    #     return _process_single_pair(idx, video_path, srt_path)

                    # 合并多个视频和字幕
                    print(f"Processing batch {batch_idx}: Merging {len(batch_pairs)} videos/subtitles...")

                    # 1. 合并视频
                    video_paths = [pair[1] for pair in batch_pairs]
                    output_filename = f"视频合并_{batch_pairs[0][0]+1}-{batch_pairs[-1][0]+1}.mp4"   # 文件名呢能够提供合并的视频索引
                    merge_result = merge_video(video_paths, id = batch_idx, result_dir = self.batch_merge_dir, output_filename=output_filename)
                    if not merge_result["result_path"]:
                        raise Exception(f"视频合并失败: {merge_result['msg']}")
                    merged_video_path = merge_result["result_path"]

                    # 2. 合并字幕文件（需要计算时间偏移）
                    srt_files_with_offset = []
                    total_duration = 0

                    # try:
                    for i, (idx, video_path, srt_path) in enumerate(batch_pairs):
                        srt_files_with_offset.append((srt_path, total_duration))
                        # 累加视频时长作为下一个文件的时间偏移
                        if i < len(batch_pairs) - 1:
                            duration_ms = _probe_video_duration_ms(video_path)
                            total_duration += duration_ms
                    # 合并字幕
                    merged_srt_path = os.path.join(self.batch_merge_dir, f"字幕合并_{batch_pairs[0][0]+1}-{batch_pairs[-1][0]+1}.srt")
                    merge_srt_files_with_offset(srt_files_with_offset, merged_srt_path)
                    # 3. 处理合并后的视频和字幕
                    translated_srt_path = merged_srt_path
                    with open(merged_srt_path, 'r', encoding='utf-8') as f:
                        original_subtitle_text = f.read().strip()

                    # 翻译字幕（如果需要）
                    if self.if_translate:
                        print(f"Processing batch {batch_idx}: Translating subtitle...")
                        input_subtitles, _ = parse_subtitle_uncertain(merged_srt_path)
                        translated_subtitles = LLMAPI.getInstance().translate_subtitle_with_audio(
                            str(input_subtitles), merged_video_path, language=self.language
                        )
                        # 转换为SRT格式
                        translated_srt_text = ""
                        for i, sub in enumerate(translated_subtitles, 1):
                            translated_srt_text += f"{i}\n{sub['start']} --> {sub['end']}\n{sub['text']}\n\n"
                        working_subtitle_text = translated_srt_text.strip()
                        # 保存翻译后的字幕
                        translated_srt_path = os.path.join(self.processing_dir, f"translated_{batch_idx}_m.srt")
                        with open(translated_srt_path, 'w', encoding='utf-8') as f:
                            f.write(working_subtitle_text)
                    else:
                        working_subtitle_text = original_subtitle_text

                    # 4. 使用音频合并字幕， 返回的是索引列表
                    merge_result = LLMAPI.getInstance().merge_subtitle_with_audio_2(
                        working_subtitle_text, merged_video_path, language=self.language
                    )
                    # 根据索引填充字幕
                    original_subs, _ = parse_subtitle_uncertain(
                        merged_srt_path if not self.if_translate else translated_srt_path
                    )
                    merged_subtitles = []
                    for merge_idx, original_indices in enumerate(merge_result, 1):
                        first_idx = original_indices[0] - 1
                        last_idx = original_indices[-1] - 1
                        if first_idx < len(original_subs) and last_idx < len(original_subs):
                            start_time = original_subs[first_idx]['start']
                            end_time = original_subs[last_idx]['end']
                            # 合并所有合并字幕的文本
                            combined_text = ""
                            for orig_idx in original_indices:
                                if orig_idx - 1 < len(original_subs):
                                    if combined_text:
                                        combined_text += " "
                                    combined_text += original_subs[orig_idx - 1]['text']
                            merged_subtitles.append({
                                'index': merge_idx,
                                'start': start_time,
                                'end': end_time,
                                'text': combined_text
                            })
                    # 保存合并字幕
                    merged_srt_text = ""
                    for sub in merged_subtitles:
                        merged_srt_text += f"{sub['index']}\n{sub['start']} --> {sub['end']}\n{sub['text']}\n\n"
                    batch_merged_srt_path = os.path.join(self.processing_dir, f"短句合并_{batch_idx}_m.srt")
                    with open(batch_merged_srt_path, 'w', encoding='utf-8') as f:
                        f.write(merged_srt_text.strip())

                    # 5. 匹配合并字幕的角色
                    print(f"Processing batch {batch_idx}: Matching roles for merged subtitles...")
                    merged_role_result = LLMAPI.getInstance().match_role_by_hint(
                        merged_srt_text.strip(), "", self.role_info_text, merged_video_path, language=self.language,
                    )
                    # 匹配角色后，写入合并后的字幕
                    merged_original_text = ""
                    for i, sub in enumerate(merged_subtitles, 1):
                        role = merged_role_result.get(str(i), "未知角色")
                        merged_original_text += f"{i}\n{sub['start']} --> {sub['end']}\n{role}: {sub['text']}\n\n"
                    merged_original_path = os.path.join(self.processing_dir,
                                                        f"first_annotated_短句合并_{batch_idx}_m.srt")
                    with open(merged_original_path, 'w', encoding='utf-8') as f:
                        f.write(merged_original_text.strip())

                    # 6. 将角色映射回原始字幕条数
                    original_roles = {}
                    for merge_idx, original_indices in enumerate(merge_result, 1):
                        role = merged_role_result.get(str(merge_idx), "未知角色")
                        for orig_idx in original_indices:
                            original_roles[str(orig_idx)] = role

                    # 7. 创建标记的原始字幕
                    annotated_original_text = ""
                    for i, sub in enumerate(original_subs, 1):
                        role = original_roles.get(str(i), "未知角色")
                        annotated_original_text += f"{i}\n{sub['start']} --> {sub['end']}\n{role}: {sub['text']}\n\n"
                    annotated_original_path = os.path.join(self.processing_dir,
                                                           f"first_annotated_{batch_idx}_m.srt")
                    with open(annotated_original_path, 'w', encoding='utf-8') as f:
                        f.write(annotated_original_text.strip())

                    # 8. 仲裁员验证
                    print(f"Processing batch {batch_idx}: Verifying roles with arbitrator...")
                    final_role_result = LLMAPI.getInstance().arbitrator_roles(
                        annotated_original_text.strip(), "", self.role_info_text, merged_video_path,
                        language=self.language
                    )

                    # 9. 生成最终字幕文件，这里需要parse一次，是为了消除翻译的影响，这里需要得到原始的字幕语言
                    final_subtitles = []
                    input_subtitles, _ = parse_subtitle_uncertain(merged_srt_path)
                    for i, sub in enumerate(input_subtitles, 1):
                        final_role = final_role_result.get(str(i), original_roles.get(str(i), "未知角色"))
                        final_subtitles.append({
                            'index': i,
                            'start': sub['start'],
                            'end': sub['end'],
                            'text': sub['text'],
                            'role': final_role
                        })

                    # 10. 保存合并后的最终字幕
                    batch_final_srt_path = os.path.join(self.batch_merge_dir, f"最终标注字幕_{batch_pairs[0][0]+1}-{batch_pairs[-1][0]+1}.srt")
                    with open(batch_final_srt_path, 'w', encoding='utf-8') as f:
                        for sub in final_subtitles:
                            f.write(f"{sub['index']}\n")
                            f.write(f"{sub['start']} --> {sub['end']}\n")
                            f.write(f"{sub['role']}: {sub['text']}\n\n")

                    # 11. 将合并的字幕拆分回原来的各个文件
                    split_merged_srt_back(batch_final_srt_path, srt_files_with_offset, self.srt_dir)
                    # 返回成功的文件数量和总时长
                    duration_ms = _probe_video_duration_ms(merged_video_path)
                    return len(batch_pairs), duration_ms

                except Exception as e:
                    raise Exception(f"批处理失败: {e}")

            total = len(self.pairs)
            completed = 0
            failed = []
            sub_results = [None] * total
            self.progress.emit(0, f"开始处理，共 {total} 组...   ")

            # 创建批次处理队列
            batches = []
            i = 0
            while i < len(self.pairs):
                current_batch = []
                subtitle_count = 0

                # 收集字幕条数少于100的视频/字幕对作为一个批次
                while i < len(self.pairs) and subtitle_count < self.strip:
                    pair = self.pairs[i]
                    v, s = pair
                    count = count_subtitle_entries(s)
                    if count == 0:
                        # 如果无法计算字幕条数，单独处理
                        if current_batch:
                            batches.append(current_batch)
                            current_batch = []
                        batches.append([(i, v, s)])
                        i += 1
                        break
                    else:
                        current_batch.append((i, v, s))
                        subtitle_count += count
                        i += 1

                    if subtitle_count > self.strip and current_batch:
                        # 如果当前总条数超过100条，且已有文件在批次中，则结束当前批次
                        break

                if current_batch:
                    batches.append(current_batch)

            print(f"总共 {len(self.pairs)} 个文件对，合并为 {len(batches)} 个批次处理")

            from concurrent.futures import ThreadPoolExecutor, as_completed
            # import ffmpeg
            batch_log_path = os.path.join(self.output_root_dir, "批量日志.txt")
            with open(batch_log_path, 'w', encoding='utf-8') as f:
                for batch_idx, batch_pairs in enumerate(batches):
                    f.write(f"批次 {batch_idx + 1}，共 {len(batch_pairs)} 个文件对，处理文件为：{', '.join([os.path.basename(v) for _, v, _ in batch_pairs])}\n")

            total = len(batches)
            # 存储成功条目的 (导出字幕路径, 视频时长ms)，按原顺序
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                future_to_ctx = {}
                for batch_idx, batch_pairs in enumerate(batches):
                    # 为批次创建一个处理任务
                    fut = executor.submit(process_one_batch, batch_pairs, batch_idx)
                    future_to_ctx[fut] = batch_pairs

                for fut in as_completed(future_to_ctx):
                    batch_pairs = future_to_ctx[fut]
                    try:
                        # 更新完成计数（根据批次中文件的数量）
                        completed += len(batch_pairs)
                        pct = int((completed * 100) / total)
                        self.progress.emit(pct, f"正在处理：{completed}/{total}，失败 {len(failed)}...   ")
                    except Exception as e:
                        for pair in batch_pairs:
                            idx, v, s = pair
                            failed.append((os.path.basename(v), os.path.basename(s), str(e), traceback.format_exc()))
                        completed += len(batch_pairs)
                        pct = int((completed * 100) / total)
                        self.progress.emit(pct, f"正在处理：{completed}/{total}，失败 {len(failed)}...   ")

            # save error log if any
            if failed:
                error_log_path = os.path.join(self.output_root_dir, "error_log.txt")
                with open(error_log_path, 'w', encoding='utf-8') as f:
                    f.write("发生错误的条目如下:\n\n")
                    for vname, sname, err, tb in failed:
                        f.write(f"视频: {vname}  字幕: {sname}\n错误: {err}\n{tb}\n---\n")

            msg = f"批量角色标注完成，成功 {total - len(failed)}，失败 {len(failed)}。"
            self.finished.emit({
                "msg": msg,
                "result_path": self.output_root_dir
            })
        except Exception as e:
            print(e)
            print(traceback.format_exc())
            self.finished.emit({
                "msg": f"发生错误: {e}",
                "result_path": self.output_root_dir if os.path.isdir(self.output_root_dir) else ""
            })


