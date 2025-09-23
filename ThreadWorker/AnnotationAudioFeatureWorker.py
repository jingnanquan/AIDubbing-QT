import os
import re
import traceback

# import ffmpeg
from PyQt5.QtCore import QThread, pyqtSignal
# import soundfile as sf
# from pyparsing import originalTextFor, original_text_for
# from scipy import signal
# from shapely.ops import orient

# from Service.ERes2NetV2.audiosimilarity import SpeakerEmbeddingCluster
# from Service.ERes2NetV2.launch_visualization import launch_visualization_safely
# from Service.dubbingMain.llmAPI import LLMAPI
from Service.generalUtils import time_str_to_ms, ms_to_time_str
from Service.subtitleUtils import parse_subtitle_uncertain
from Service.videoUtils import get_audio_np_from_video, _probe_video_duration_ms


class BatchAnnotationWorker_with_AudioFeature(QThread):
    """
    QThread worker that uses a ThreadPoolExecutor to annotate roles for each (video, srt) pair in parallel.
    """
    finished = pyqtSignal(dict)
    progress = pyqtSignal(int, str)

    def __init__(self, pairs, role_info_text, output_root_dir, extraOutput=False, max_workers=3, if_translate: bool = False, language: str = ""):
        super().__init__()
        self.pairs = pairs
        self.role_info_text = role_info_text
        self.output_root_dir = output_root_dir
        self.max_workers = max_workers
        self.extraOutput = extraOutput
        self.if_translate = if_translate
        self.language = language
        # if self.if_translate:
        #     self.max_workers = 3

    def run(self):
        try:
            os.makedirs(self.output_root_dir, exist_ok=True)
            self.summary_dir = os.path.join(self.output_root_dir, "剧情简介")
            self.srt_dir = os.path.join(self.output_root_dir, "字幕")
            self.role_dir = os.path.join(self.output_root_dir, "角色表")
            self.processing_dir = os.path.join(self.output_root_dir, "中间结果")
            os.makedirs(self.summary_dir, exist_ok=True)
            os.makedirs(self.srt_dir, exist_ok=True)
            os.makedirs(self.role_dir, exist_ok=True)
            os.makedirs(self.processing_dir, exist_ok=True)

            from Service.dubbingMain.llmAPI import LLMAPI
            LLMAPI.getInstance()  # initialize once

            def process_one(idx, video_path, srt_path):
                try:
                    translated_srt_path = srt_path  # 初始化翻译字幕路径
                    # 1) Read original subtitle
                    with open(srt_path, 'r', encoding='utf-8') as f:
                        original_subtitle_text = f.read().strip()
                    
                    # 2) If translation is needed, translate the subtitle
                    if self.if_translate:
                        print(f"Processing {idx}: Translating subtitle...")
                        input_subtitles, _ = parse_subtitle_uncertain(srt_path)
                        translated_subtitles = LLMAPI.getInstance().translate_subtitle_with_audio(str(input_subtitles), video_path, language=self.language)
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
                    merge_result = LLMAPI.getInstance().merge_subtitle_with_audio_2(working_subtitle_text, video_path, language=self.language)
                    
                    # Create merged subtitle text
                    # Parse original subtitles to get time info
                    original_subs, _ = parse_subtitle_uncertain(srt_path if not self.if_translate else translated_srt_path)
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
                    
                    merged_srt_path = os.path.join(self.processing_dir, f"merged_{idx}.srt")
                    with open(merged_srt_path, 'w', encoding='utf-8') as f:
                        f.write(merged_srt_text.strip())
                    
                    # 4) Match roles for merged subtitles
                    print(f"Processing {idx}: Matching roles for merged subtitles...")
                    merged_role_result = LLMAPI.getInstance().match_role_by_hint(
                        merged_srt_text.strip(), "", self.role_info_text, video_path, language=self.language,
                    )
                    
                    # 5) Map roles back to original subtitles
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
                    
                    annotated_original_path = os.path.join(self.processing_dir, f"first_annotated_original_{idx}.srt")
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

            from concurrent.futures import ThreadPoolExecutor, as_completed
            import ffmpeg

            # 存储成功条目的 (导出字幕路径, 视频时长ms)，按原顺序
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                future_to_ctx = {}
                for i, (v, s) in enumerate(self.pairs):
                    fut = executor.submit(process_one, i, v, s)
                    future_to_ctx[fut] = (i, v, s)
                for fut in as_completed(future_to_ctx):
                    i, v, s = future_to_ctx[fut]
                    try:
                        out_srt, dur_ms = fut.result()
                        sub_results[i] = (out_srt, dur_ms)
                    except Exception as e:
                        failed.append((os.path.basename(v), os.path.basename(s), str(e), traceback.format_exc()))
                    finally:
                        completed += 1
                        pct = int(completed / total * 100)
                        self.progress.emit(pct, f"正在处理：{completed}/{total}，失败 {len(failed)}...   ")

            failed2 = []
            # save error log if any
            if failed:
                error_log_path = os.path.join(self.output_root_dir, "error_log.txt")
                with open(error_log_path, 'w', encoding='utf-8') as f:
                    f.write("发生错误的条目如下:\n\n")
                    for vname, sname, err, tb in failed:
                        f.write(f"视频: {vname}  字幕: {sname}\n错误: {err}\n{tb}\n---\n")
            elif self.extraOutput:
                # 先合并字幕：使用成功项，按原顺序叠加 offset（累计时长）
                try:
                    self.progress.emit(1, "  合并字幕中...  ")
                    merged_subtitle_path = os.path.join(self.output_root_dir, "merged_subtitle.srt")
                    current_index = 1
                    merged_lines = []
                    cumulative_offset = 0
                    for res in sub_results:
                        if res is None:
                            continue
                        path, duration_ms = res
                        with open(path, "r", encoding="utf-8") as f:
                            content = f.read()
                        blocks = re.split(r"\n\s*\n", content.strip(), flags=re.MULTILINE)
                        i_block = 1
                        for block in blocks:
                            lines = block.strip().split("\n")
                            if len(lines) < 2:
                                raise Exception(f"字幕文件{path}第{i_block}块格式错误")
                            time_line = lines[1] if "-->" in lines[1] else lines[0]
                            m = re.match(r"(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})", time_line)
                            if not m:
                                raise Exception(f"字幕文件{path}第{i_block}块格式错误")
                            start_time, end_time = m.groups()
                            start_ms = int(time_str_to_ms(start_time) + cumulative_offset)
                            end_ms = int(time_str_to_ms(end_time) + cumulative_offset)
                            new_block = [str(current_index)]
                            new_block.append(f"{ms_to_time_str(start_ms)} --> {ms_to_time_str(end_ms)}")
                            if "-->" in lines[1]:
                                new_block.extend(lines[2:])
                            else:
                                raise Exception(f"字幕文件{path}第{i_block}块格式错误")
                            merged_lines.append("\n".join(new_block))
                            current_index += 1
                            i_block += 1
                        cumulative_offset += max(0, duration_ms)

                    with open(merged_subtitle_path, "w", encoding="utf-8") as f:
                        f.write("\n\n".join(merged_lines))
                except Exception:
                    failed2.append(("MERGE", "SUBTITLE", "合并字幕失败", traceback.format_exc()))

                try:
                    merged_video_path = os.path.join(self.output_root_dir, "merged_video.mp4")
                    video_files_ok = [v for (res, (v, s)) in zip(sub_results, self.pairs) if res is not None]
                    self.progress.emit(2, "  合并视频中...  ")
                    streams = []
                    for fpath in video_files_ok:
                        inp = ffmpeg.input(fpath)
                        v = inp.video
                        a = inp.audio.filter('aresample', **{'async': 1, 'first_pts': 0})
                        streams += [v, a]
                    concat = ffmpeg.concat(*streams, v=1, a=1, n=len(video_files_ok)).node
                    vcat, acat = concat[0], concat[1]
                    (
                        ffmpeg
                        .output(vcat, acat, merged_video_path, vcodec='libx264', acodec='aac')
                        .global_args('-fflags', '+genpts')
                        .overwrite_output()
                        .run()
                    )
                except Exception:
                    failed2.append(("MERGE", "VIDEO", "合并视频失败", traceback.format_exc()))


            msg = f"批量角色标注完成，成功 {total - len(failed)}，失败 {len(failed)}。"
            if failed2:
                msg2 = {info[2] for info in failed2}
                msg += str(msg2)
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

