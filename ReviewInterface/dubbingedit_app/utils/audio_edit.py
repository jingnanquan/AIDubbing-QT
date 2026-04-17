"""音频切片与变速（pydub；需系统安装 ffmpeg 以支持 mp3 等格式）。"""

from __future__ import annotations

from pathlib import Path
import io
import shutil
import time

import librosa
import numpy as np
import pyrubberband
from pydub import AudioSegment



def _export_format_for_path(path: Path) -> str:
    ext = path.suffix.lower()
    mapping = {".mp3": "mp3", ".wav": "wav", ".flac": "flac", ".ogg": "ogg", ".m4a": "mp4", ".aac": "aac"}
    return mapping.get(ext, "wav")


def _change_speed(sound: AudioSegment, speed: float) -> AudioSegment:
    """
    使用 pyrubberband 进行变速处理，保持音调和音量不变。
    
    Args:
        sound: 输入音频 (AudioSegment)
        speed: 播放速度倍数，大于1为加速，小于1为减速
    
    Returns:
        改变速度后的音频 (AudioSegment)
    """
    if abs(speed - 1.0) < 1e-6:
        return sound
    
    # 1. 获取音频参数
    sample_rate = sound.frame_rate
    channels = sound.channels
    samples = np.array(sound.get_array_of_samples())
    original_dtype = samples.dtype
    
    # 2. 预处理：为 pyrubberband 准备数据
    # 如果是立体声，pyrubberband 需要 (n_samples, n_channels) 的形状
    if channels == 2:
        samples = samples.reshape((-1, 2))
    
    # 归一化到 [-1, 1] (float32)
    max_val = np.iinfo(original_dtype).max
    samples_norm = samples.astype(np.float32) / max_val
    
    # 3. 计算原始音量 (RMS) 并进行变速处理
    if channels == 2:
        # 立体声：取左声道计算 RMS
        original_rms = librosa.feature.rms(y=samples_norm[:, 0])[0].mean()
        # 使用 pyrubberband 进行变速处理
        y_stretched = pyrubberband.time_stretch(samples_norm, sample_rate, speed)
        # 恢复原始音量
        stretched_rms = librosa.feature.rms(y=y_stretched[:, 0])[0].mean()
        y_stretched = y_stretched * (original_rms / (stretched_rms + 1e-6))
    else:
        # 单声道
        original_rms = librosa.feature.rms(y=samples_norm)[0].mean()
        # 使用 pyrubberband 进行变速处理
        y_stretched = pyrubberband.time_stretch(samples_norm, sample_rate, speed)
        # 恢复原始音量
        stretched_rms = librosa.feature.rms(y=y_stretched)[0].mean()
        y_stretched = y_stretched * (original_rms / (stretched_rms + 1e-6))
    
    # 4. 后处理：恢复格式
    # 反归一化并裁剪到原始数据类型范围
    y_out = y_stretched * max_val
    y_out = np.clip(y_out, np.iinfo(original_dtype).min, np.iinfo(original_dtype).max)
    y_out = y_out.astype(original_dtype)
    
    # 如果是立体声，展平数组以符合 pydub 输入要求
    if channels == 2:
        y_out = y_out.flatten()
    
    # 5. 重新构建 AudioSegment
    return AudioSegment(
        y_out.tobytes(),
        frame_rate=sample_rate,
        sample_width=sound.sample_width,
        channels=channels
    )


def _safe_export_to_file(out: AudioSegment, dub_audio_path: str, fmt: str) -> None:
    """安全地将 AudioSegment 导出到原文件路径。
    
    1. 将原文件移动到 histmp/ 下作为历史备份（按时间戳命名）
    2. 将处理后的音频导出到原文件路径
    3. 如果导出失败，从 histmp/ 回滚恢复原文件
    
    Args:
        out: 处理后的 AudioSegment
        dub_audio_path: 目标文件路径（即原文件路径）
        fmt: 导出格式（如 "mp3", "wav" 等）
    """
    path = Path(dub_audio_path)
    histmp_dir = path.parent / "histmp"
    histmp_dir.mkdir(parents=True, exist_ok=True)

    timestamp = int(time.time() * 1000)
    backup_name = f"{path.stem}_{timestamp}{path.suffix}"
    backup_path = histmp_dir / backup_name

    shutil.move(str(path), str(backup_path))

    try:
        out.export(dub_audio_path, format=fmt)
    except Exception:
        if path.exists():
            path.unlink()
        shutil.move(str(backup_path), str(path))
        raise


def apply_speed_to_segment(
    dub_audio_path: str,
    start_ms: int,
    end_ms: int,
    speed: float,
) -> None:
    """将 workspace 内整轨配音人声在 [start_ms, end_ms) 的片段按倍速替换后写回原文件。
    
    变速后保持原始片段时长不变：
    - 加速时：变速后音频变短，补充静音到原始时长
    - 减速时：变速后音频变长，覆盖 after 的开头部分
    """
    path = Path(dub_audio_path)
    audio = AudioSegment.from_file(dub_audio_path)
    start_ms = max(0, min(start_ms, len(audio)))
    end_ms = max(start_ms, min(end_ms, len(audio)))
    
    before = audio[:start_ms]
    seg = audio[start_ms:end_ms]
    after = audio[end_ms:]
    
    # 应用速度调整
    seg2 = _change_speed(seg, speed)
    
    # 处理变速后的长度差异
    original_segment_length = end_ms - start_ms
    if len(seg2) < original_segment_length:
        # 加速后音频变短，补充静音到原始时长
        silence = AudioSegment.silent(original_segment_length - len(seg2))
        seg2 = seg2 + silence
    elif len(seg2) > original_segment_length:
        # 减速后音频变长，覆盖 after 的开头部分
        overlap = len(seg2) - original_segment_length
        after = after[overlap:]
    
    out = before + seg2 + after
    _safe_export_to_file(out, dub_audio_path, _export_format_for_path(path))


def export_segment_wav(dub_audio_path: str, start_ms: int, end_ms: int, dest_path: str) -> None:
    """导出纯人声片段为 wav（便于兼容）。"""
    audio = AudioSegment.from_file(dub_audio_path)
    start_ms = max(0, min(start_ms, len(audio)))
    end_ms = max(start_ms, min(end_ms, len(audio)))
    seg = audio[start_ms:end_ms]
    seg.export(dest_path, format="wav")


def replace_segment_with_speed(
    dub_audio_path: str,
    start_ms: int,
    end_ms: int,
    new_audio_bytes: bytes,
    speed: float,
) -> None:
    """将 workspace 内整轨配音人声在 [start_ms, end_ms) 的片段替换为新音频，并应用速度调整后写回原文件。
    
    变速后保持原始片段时长不变：
    - 加速时：变速后音频变短，补充静音到原始时长
    - 减速时：变速后音频变长，覆盖 after 的开头部分
    """
    path = Path(dub_audio_path)
    audio = AudioSegment.from_file(dub_audio_path)
    start_ms = max(0, min(start_ms, len(audio)))
    end_ms = max(start_ms, min(end_ms, len(audio)))

    # 从字节数据加载新音频
    new_audio = AudioSegment.from_file(io.BytesIO(new_audio_bytes), format="mp3")

    # 应用速度调整
    new_audio = _change_speed(new_audio, speed)

    # 替换片段
    before = audio[:start_ms]
    after = audio[end_ms:]

    # 处理变速后的长度差异
    segment_length = end_ms - start_ms
    if len(new_audio) < segment_length:
        # 加速后音频变短，补充静音到原始时长
        silence = AudioSegment.silent(segment_length - len(new_audio))
        new_audio = new_audio + silence
    elif len(new_audio) > segment_length:
        # 减速后音频变长，覆盖 after 的开头部分
        overlap = len(new_audio) - segment_length
        after = after[overlap:]

    out = before + new_audio + after
    _safe_export_to_file(out, dub_audio_path, _export_format_for_path(path))



# ######==========================##########

def _change_speed_cast2(sound: AudioSegment, speed: float) -> AudioSegment:
    """使用相位声码器进行变速处理，保持音调不变。

    Args:
        sound: 输入音频
        speed: 变速倍率（>1 加速，<1 减速）

    Returns:
        变速后的音频
    """
    if abs(speed - 1.0) < 1e-6:
        return sound

    # 获取音频参数
    sample_rate = sound.frame_rate
    channels = sound.channels

    # 将 AudioSegment 转换为 numpy 数组
    samples = np.array(sound.get_array_of_samples())

    # 如果是立体声，分离声道
    if channels == 2:
        samples = samples.reshape((-1, 2))

    # 归一化到 [-1, 1]
    samples = samples.astype(np.float32) / (2 ** (sound.sample_width * 8 - 1))

    # 对每个声道应用相位声码器
    if channels == 2:
        y_left = _phase_vocoder_time_stretch(samples[:, 0], rate=speed)
        y_right = _phase_vocoder_time_stretch(samples[:, 1], rate=speed)
        # 确保两个声道长度一致
        min_len = min(len(y_left), len(y_right))
        y_left = y_left[:min_len]
        y_right = y_right[:min_len]
        y_stretched = np.column_stack([y_left, y_right])
    else:
        y_stretched = _phase_vocoder_time_stretch(samples, rate=speed)

    # 反归一化
    y_stretched = (y_stretched * (2 ** (sound.sample_width * 8 - 1))).astype(np.int16)

    # 重新构建 AudioSegment
    if channels == 2:
        y_stretched = y_stretched.flatten()

    return AudioSegment(
        y_stretched.tobytes(),
        frame_rate=sample_rate,
        sample_width=sound.sample_width,
        channels=channels
    )


def _phase_vocoder_time_stretch(y: np.ndarray, rate: float, n_fft: int = 4096, hop_length: int = 512) -> np.ndarray:
    """使用相位声码器进行时域拉伸。

    Args:
        y: 单声道音频数据
        rate: 变速倍率（>1 加速，<1 减速）
        n_fft: FFT 窗口大小
        hop_length: 跳跃长度

    Returns:
        变速后的音频数据
    """
    # STFT
    stft = librosa.stft(y, n_fft=n_fft, hop_length=hop_length)

    # 相位声码器时域拉伸
    stft_stretched = librosa.phase_vocoder(
        stft,
        rate=rate,
        hop_length=hop_length
    )

    # 逆 STFT 重建
    y_stretched = librosa.istft(
        stft_stretched,
        hop_length=hop_length
    )

    return y_stretched


def _change_speed_cast(sound: AudioSegment, speed: float) -> AudioSegment:
    """保留的兼容性函数，调用 _change_speed。"""
    return _change_speed(sound, speed)