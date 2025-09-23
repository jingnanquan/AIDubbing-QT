import logging

import torch.cuda
from torch import device

from Config import AUDIO_SEPARATION_FOLDER
import os
import shutil

import soundfile as sf
from Service.uvr5.mdxSeparator import MDXSeparator
from Service.videoUtils import get_audio_np_from_video


class AudioSeparator:
    _instance = None

    def __init__(self):
        if AudioSeparator._instance is not None:
            raise Exception("This class is a singleton. Use get_instance() method to get the instance.")

        prefix_path = os.path.dirname(os.path.abspath(__file__))
        self.model_dir = os.path.join(prefix_path, "audio-separator-models")
        self.model_path = os.path.join(self.model_dir, "UVR-MDX-NET-Inst_HQ_2.onnx")

        print(prefix_path)
        logger = logging.getLogger(__name__)
        torch_device = device(type='cuda' if torch.cuda.is_available() else 'cpu')
        if torch_device.type == 'cuda':
            onnx_execution_provider = ["CUDAExecutionProvider"]
        else:
            onnx_execution_provider = ["CPUExecutionProvider"]
        common_params = {'logger': logger, 'log_level': 20, 'torch_device': torch_device, 'torch_device_cpu': device(type='cpu'), 'torch_device_mps': None, 'onnx_execution_provider': onnx_execution_provider,
                         'model_name': 'UVR-MDX-NET-Inst_HQ_2', 'model_path': self.model_path, 'model_data': {'compensate': 1.033, 'mdx_dim_f_set': 3072, 'mdx_dim_t_set': 8, 'mdx_n_fft_scale_set': 6144, 'primary_stem': 'Instrumental'},
                         'output_format': 'mp3', 'output_dir': AUDIO_SEPARATION_FOLDER, 'normalization_threshold': 0.9, 'output_single_stem': None, 'invert_using_spec': False, 'sample_rate': 44100}
        arch_specific_params = {
                "hop_length": 1024,
                "segment_size": 256,
                "overlap": 0.25,
                "batch_size": 2,
                "enable_denoise": False
            }
        print(common_params)
        self.separator = MDXSeparator(common_config=common_params, arch_config=arch_specific_params)

        AudioSeparator._instance = self

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def isolate(self, audio_path: str, result_dir: str):

        try:
            self.separator.primary_source = None
            self.separator.secondary_source = None
            self.separator.audio_file_path = None
            self.separator.audio_file_base = None

            # Perform the separation on specific audio files without reloading the model
            output_files = self.separator.separate(audio_path)
            print(output_files)
            print(f"Separation complete! Output file(s): {' '.join(output_files)}")
            # 将分离后的文件剪切到指定目录
            moved_files = []
            for file in output_files:
                filename = os.path.basename(file)
                print(filename)
                source_path = os.path.join(AUDIO_SEPARATION_FOLDER, filename)
                # 目标路径
                target_path = os.path.join(result_dir, filename)
                # 剪切文件
                shutil.move(source_path, target_path)
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
