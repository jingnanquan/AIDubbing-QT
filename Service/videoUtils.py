import io

import ffmpeg
import numpy as np
from moviepy import VideoFileClip
from pydub import AudioSegment


def is_video_file(path):
    return path.lower().endswith(('.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm'))


def get_audio_zeronp_from_video(video_path, fallback_sr=44100):
    """
    只生成静音片段
    """
    clip = VideoFileClip(video_path)

    duration_sec = clip.duration

    sample_rate = fallback_sr
    num_samples = int(duration_sec * sample_rate)
    silent_audio = np.zeros((num_samples, 2), dtype=np.float64)
    return silent_audio, sample_rate

def get_audio_np_from_video(video_path, fallback_sr=44100):
    try:
        # 使用ffmpeg直接从视频提取音频到内存
        out, _ = (
            ffmpeg.input(video_path)
            .output('-', format='f32le', acodec='pcm_f32le', ac=2, ar=44100)
            .run(capture_stdout=True, capture_stderr=True)
        )
        samples = np.frombuffer(out, dtype=np.float32).reshape(-1, 2)
        return samples, 44100
    except:
        # 处理失败或没有音频的情况
        clip = VideoFileClip(video_path)
        duration_sec = clip.duration
        num_samples = int(duration_sec * fallback_sr)
        silent_audio = np.zeros((num_samples, 2), dtype=np.float64)
        return silent_audio, fallback_sr


def compress_video(input_path, output_path, target_height=720, crf=28, preset="fast"):
    """
    使用 ffmpeg-python 压缩视频到指定高度 (如 720p)，保持宽高比，控制码率/质量

    Args:
        input_path: 输入视频路径
        output_path: 输出视频路径
        target_height: 输出视频高度（默认 720p）
        crf: 压缩质量（0-51，值越大压缩越狠，推荐 23-30）
        preset: 压缩速度（ultrafast, superfast, veryfast, faster, fast, medium, slow, slower, veryslow）
    """
    try:
        (
            ffmpeg
            .input(input_path)
            .output(
                output_path,
                vf=f'scale=-2:{target_height}',  # 高度缩放到 target_height，宽度自动计算为偶数
                vcodec='libx264',
                preset=preset,
                crf=crf,
                acodec='aac',
                audio_bitrate='128k'
            )
            .overwrite_output()
            .run(quiet=True)  # 设置 quiet=True 不打印 ffmpeg 的日志
        )
    except ffmpeg.Error as e:
        print(f"❌ 压缩 {input_path} 出错: {e.stderr.decode('utf-8') if e.stderr else e}")
        raise


def _probe_video_duration_ms(video_path):
    try:
        info = ffmpeg.probe(video_path)
        if 'format' in info and 'duration' in info['format']:
            return int(float(info['format']['duration']) * 1000)
        for stream in info.get('streams', []):
            if 'duration' in stream:
                return int(float(stream['duration']) * 1000)
    except Exception:
        pass
    return 0


def merge_audio_video2(video_path: str, audio_path: str, output_path: str):
    # 加载视频（自动丢弃原音频）
    video_stream = ffmpeg.input(video_path)
    audio_stream = ffmpeg.input(audio_path)
    # 合成并输出
    ffmpeg.output(video_stream.video, audio_stream.audio, output_path,
                  vcodec='copy', acodec='aac', shortest=None).run()