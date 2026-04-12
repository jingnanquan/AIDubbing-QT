"""音频切片与变速（pydub；需系统安装 ffmpeg 以支持 mp3 等格式）。"""

from __future__ import annotations

from pathlib import Path

from pydub import AudioSegment


def _export_format_for_path(path: Path) -> str:
    ext = path.suffix.lower()
    mapping = {".mp3": "mp3", ".wav": "wav", ".flac": "flac", ".ogg": "ogg", ".m4a": "mp4", ".aac": "aac"}
    return mapping.get(ext, "wav")


def _change_speed(sound: AudioSegment, speed: float) -> AudioSegment:
    if abs(speed - 1.0) < 1e-6:
        return sound
    new_frame_rate = int(sound.frame_rate * speed)
    stretched = sound._spawn(sound.raw_data, overrides={"frame_rate": new_frame_rate})
    return stretched.set_frame_rate(sound.frame_rate)


def apply_speed_to_segment(
    dub_audio_path: str,
    start_ms: int,
    end_ms: int,
    speed: float,
) -> None:
    """将 workspace 内整轨配音人声在 [start_ms, end_ms) 的片段按倍速替换后写回原文件。"""
    path = Path(dub_audio_path)
    audio = AudioSegment.from_file(dub_audio_path)
    start_ms = max(0, min(start_ms, len(audio)))
    end_ms = max(start_ms, min(end_ms, len(audio)))
    before = audio[:start_ms]
    seg = audio[start_ms:end_ms]
    seg2 = _change_speed(seg, speed)
    after = audio[end_ms:]
    out = before + seg2 + after
    out.export(dub_audio_path, format=_export_format_for_path(path))


def export_segment_wav(dub_audio_path: str, start_ms: int, end_ms: int, dest_path: str) -> None:
    """导出纯人声片段为 wav（便于兼容）。"""
    audio = AudioSegment.from_file(dub_audio_path)
    start_ms = max(0, min(start_ms, len(audio)))
    end_ms = max(start_ms, min(end_ms, len(audio)))
    seg = audio[start_ms:end_ms]
    seg.export(dest_path, format="wav")
