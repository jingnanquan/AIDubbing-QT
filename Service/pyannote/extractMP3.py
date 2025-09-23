from moviepy import VideoFileClip
import os


def extract_audio_from_video(video_path, output_audio_path=None):
    """
    从视频文件中提取音频并保存

    参数:
        video_path (str): 视频文件路径
        output_audio_path (str, 可选): 输出音频文件路径。如果为None，则使用视频文件同目录

    返回:
        str: 保存的音频文件路径
    """
    # 检查视频文件是否存在
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"视频文件不存在: {video_path}")

    # 如果未指定输出路径，则使用视频文件同目录
    if output_audio_path is None:
        video_dir = os.path.dirname(video_path)
        video_name = os.path.splitext(os.path.basename(video_path))[0]
        output_audio_path = os.path.join(video_dir, f"{video_name}_audio.mp3")

    # 读取视频文件
    video = VideoFileClip(video_path)

    # 提取音频
    audio = video.audio

    # 保存音频文件
    audio.write_audiofile(output_audio_path)

    # 关闭视频和音频对象
    audio.close()
    video.close()

    print(f"音频已成功保存到: {output_audio_path}")
    return output_audio_path


# 使用示例
if __name__ == "__main__":
    video_file = "video.mp4"  # 替换为你的视频文件路径
    audio_output = "audio.mp3"  # 可选，指定输出路径

    try:
        saved_audio_path = extract_audio_from_video(video_file, audio_output)
    except Exception as e:
        print(f"发生错误: {e}")