import os

from Service.dubbingMain.llmAPI import LLMAPI
from Service.generalUtils import time_str_to_ms


def parse_subtitle(subtitle_path) -> list:
    try:
        with open(subtitle_path, "r", encoding="utf-8-sig") as f:
            content = f.read().strip()
            subtitles = []
            blocks = content.split("\n\n")  # SRT 以空行分隔字幕块
            for block in blocks:
                lines = block.split("\n")
                if len(lines) >= 3:
                    index = int(lines[0])
                    start, end = lines[1].split(" --> ")
                    text = " ".join(lines[2:])
                    subtitles.append({
                        "index": index,
                        "start": start,
                        "end": end,
                        "text": text,
                    })
            return subtitles
    except Exception as e:
        print(f"Error parsing subtitle: {e}")
        return []


def parse_subtitle_uncertain(subtitle_path) -> [list, list]:
    try:
        with open(subtitle_path, "r", encoding="utf-8-sig") as f:
            content = f.read().strip()
            subtitles = []
            blocks = content.split("\n\n")  # SRT 以空行分隔字幕块
            role_match_list = []
            tolerate_num = 3
            uncertain_num = 0
            for block in blocks:
                lines = block.split("\n")
                if len(lines) >= 3:
                    index = int(lines[0])
                    start, end = lines[1].split(" --> ")
                    text = " ".join(lines[2:])
                    seperate = text.split(":")
                    if len(seperate)>=2:
                        text = seperate[-1].strip()
                        role_match_list.append(seperate[0])
                    else:
                        role_match_list.append("default")
                        uncertain_num+=1
                    subtitles.append({
                        "index": index,
                        "start": start,
                        "end": end,
                        "text": text,
                    })
            if uncertain_num>tolerate_num:
                role_match_list = []
            return subtitles, role_match_list
    except Exception as e:
        print(f"Error parsing subtitle: {e}")
        return [],[]



def parse_subtitle_with_role(subtitle_path) -> list:
    try:
        with open(subtitle_path, "r", encoding="utf-8-sig") as f:
            content = f.read().strip()
            subtitles = []
            blocks = content.split("\n\n")  # SRT 以空行分隔字幕块
            for block in blocks:
                lines = block.split("\n")
                if len(lines) >= 3:
                    index = int(lines[0])
                    start, end = lines[1].split(" --> ")
                    text = " ".join(lines[2:])
                    role, text = text.split(": :")
                    subtitles.append({
                        "index": index,
                        "start": start,
                        "end": end,
                        "role": role,
                        "text": text,
                    })
            return subtitles
    except Exception as e:
        print(f"Error parsing subtitle: {e}")
        return []

def is_srt_file(path):
    return path.lower().endswith(('.srt'))

def write_subtitles_to_srt(subtitles: list, output_path: str):
    """
    将字幕列表写入SRT文件

    参数:
        subtitles: 字幕列表，每个元素格式为:
            {
                "index": int,       # 字幕序号
                "start": str,       # 开始时间(格式: 00:00:00,000)
                "end": str,         # 结束时间(格式: 00:00:00,000)
                "text": str,        # 字幕文本
                "role": str         # 角色名称
            }
        output_path: 输出SRT文件路径
    """
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            for sub in subtitles:
                # 写入序号
                f.write(f"{sub['index']}\n")
                # 写入时间轴
                f.write(f"{sub['start']} --> {sub['end']}\n")
                # 写入角色和文本(格式: role: text)
                f.write(f"{sub['role']}: {sub['text']}\n\n")  # 注意两个换行分隔字幕块
            return True
    except Exception as e:
        print(f"Error write subtitle: {e}")
        return False



def adjust_subtitles_cps(target_subs, cps: int, tolerate_factor: list):
    adjust_list = []  # 需要压缩的字幕内容
    adjust_indices = []  # 对应在 target_subs 中的索引
    max_char_lens = []  # 每个字幕对应的最大字符数限制
    compressed_texts = []  # 压缩后的字幕内容

    for i, sub in enumerate(target_subs):
        start_ms = time_str_to_ms(sub['start'])
        end_ms = time_str_to_ms(sub['end'])
        duration_ms = end_ms - start_ms
        text = sub['text']
        text2 = text.replace(" ", "")
        char_count = len(text2)

        # 容忍时间上限（毫秒）
        tolerate_ms = min(duration_ms + tolerate_factor[0], duration_ms * tolerate_factor[1])
        tolerate_cps = char_count / (tolerate_ms / 1000.0)

        if tolerate_cps > cps:
            # 计算合理最大字符数
            adjust = int(cps * (tolerate_ms / 1000.0))
            adjust_list.append(text)
            adjust_indices.append(i)
            max_char_lens.append(adjust)

    print(adjust_list)
    print(max_char_lens)
    print(adjust_indices)
    # 调用 LLM API 进行字幕压缩

    if adjust_list:
        compressed_texts = LLMAPI.getInstance().compress_subtitles(adjust_list, max_char_lens)

        print(compressed_texts)
        # 替换原始字幕内容
        for i, new_text in zip(adjust_indices, compressed_texts):
            target_subs[i]['text'] = new_text

    return target_subs, adjust_list, compressed_texts, adjust_indices

def get_srt_files_in_folder(folder):
    audio_exts = ('.srt')
    return [
        os.path.join(root, file)
        for root, _, files in os.walk(folder)
        for file in files
        if file.lower().endswith(audio_exts)
    ]




