import Config
import os
import shutil

from audio_separator.separator import Separator
from audio_separator.separator.architectures.mdx_separator import MDXSeparator
import soundfile as sf

from Service.videoUtils import get_audio_np_from_video


class AudioSeparator:
    _instance = None

    def __init__(self):
        if AudioSeparator._instance is not None:
            raise Exception("This class is a singleton. Use get_instance() method to get the instance.")

        prefix_path = os.path.dirname(os.path.abspath(__file__))
        self.model_dir = os.path.join(prefix_path, "audio-separator-models")
        print(self.model_dir)
        # Initialize the Separator class (with optional configuration properties, below)
        self.separator = Separator(
            model_file_dir=self.model_dir,
            output_format="mp3",
            mdx_params={
                "hop_length": 1024,
                "segment_size": 256,
                "overlap": 0.25,
                "batch_size": 2,
                "enable_denoise": False
            }
        )

        # Load a machine learning model (if unspecified, defaults to 'model_mel_band_roformer_ep_3005_sdr_11.4360.ckpt')
        self.separator.load_model("UVR-MDX-NET-Inst_HQ_2.onnx")
        AudioSeparator._instance = self

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def isolate(self, audio_path: str, result_dir: str):

        try:
            # Perform the separation on specific audio files without reloading the model
            output_files = self.separator.separate(audio_path)
            print(f"Separation complete! Output file(s): {' '.join(output_files)}")
            # 将分离后的文件剪切到指定目录
            moved_files = []
            for file in output_files:
                filename = os.path.basename(file)
                # 目标路径
                target_path = os.path.join(result_dir, filename)
                # 剪切文件
                shutil.move(file, target_path)
                moved_files.append(target_path)
            return moved_files[0]
        except Exception as e:
            print(f"发生错误: {e}")
            return ""



# 以下代码仅为测试用途，实际使用时可以删除
if __name__ == "__main__":
    # 测试代码
    video = r"E:\offer\配音任务2\伤心者联盟\video\伤心者同盟（英）-1.mp4"
    out_dir = r"E:\offer\AI配音web版\8.20\AIDubbing-QT-main\Service"

    audio, samplerate = get_audio_np_from_video(video)
    audio_path = os.path.join(out_dir, "audio.wav")
    sf.write(audio_path, audio, samplerate)

    # 使用单例模式
    separator_instance = AudioSeparator.get_instance()
    output_files = separator_instance.isolate(audio_path, out_dir)
