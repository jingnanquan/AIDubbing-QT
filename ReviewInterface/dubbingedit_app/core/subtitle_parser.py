from __future__ import annotations

from typing import Any


# 直接使用此解析函数，不可修改逻辑
def parse_subtitle_uncertain(subtitle_path) -> tuple[list[Any], list[Any]]:
    try:
        with open(subtitle_path, "r", encoding="utf-8-sig") as f:
            content = f.read().strip()
            subtitles = []
            blocks = content.split("\n\n")
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
                    if len(seperate) >= 2:
                        text = seperate[-1].strip()
                        role_match_list.append(seperate[0])
                    else:
                        role_match_list.append("default")
                        uncertain_num += 1
                    subtitles.append(
                        {
                            "index": index,
                            "start": start,
                            "end": end,
                            "text": text,
                        }
                    )
            if uncertain_num > tolerate_num:
                role_match_list = []
            return subtitles, role_match_list
    except Exception as e:
        print(f"Error parsing subtitle: {e}")
        return [], []


def timecode_to_ms(tc: str) -> int:
    """SRT 时间码 HH:MM:SS,mmm -> 毫秒。"""
    tc = tc.strip().replace("\ufeff", "")
    if "," in tc:
        time_part, ms_part = tc.rsplit(",", 1)
    else:
        time_part, ms_part = tc, "0"
    parts = time_part.split(":")
    h, m, s = int(parts[0]), int(parts[1]), int(parts[2])
    ms = int(ms_part.ljust(3, "0")[:3])
    return ((h * 60 + m) * 60 + s) * 1000 + ms


def ms_to_timecode(ms: int) -> str:
    """毫秒 -> HH:MM:SS,mmm"""
    if ms < 0:
        ms = 0
    s, ms_part = divmod(ms, 1000)
    m, sec = divmod(s, 60)
    h, minute = divmod(m, 60)
    return f"{h:02d}:{minute:02d}:{sec:02d},{ms_part:03d}"
