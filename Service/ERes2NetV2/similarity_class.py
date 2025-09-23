# <class 'modelscope.models.audio.sv.ERes2NetV2.SpeakerVerificationERes2NetV2'>
import time
from typing import Union
import hdbscan

from matplotlib import pyplot as plt
import torch

time1 = time.time()
print(time1)
from modelscope.models.audio.sv.ERes2NetV2 import SpeakerVerificationERes2NetV2
from modelscope.pipelines.audio.speaker_verification_eres2netv2_pipeline import ERes2NetV2_Pipeline
import numpy as np
import soundfile as sf
from scipy import signal

import os
time2 = time.time()
print("import时间", time2 - time1)

os.environ["JOBLIB_TEMP_FOLDER"] = "C:/temp"  # 指定一个纯英文路径的临时目录

path = os.path.dirname(os.path.abspath(__file__))
args = {'model_config': {'sample_rate': 16000, 'embed_dim': 192, 'baseWidth': 26, 'scale': 2, 'expansion': 2},
        'pretrained_model': 'pretrained_eres2netv2.ckpt',
        'yesOrno_thr': 0.36,
        'model_dir': os.path.join(path, 'model'),
        'device_map': None,
        'device': 'cuda'
        }





path = os.path.dirname(os.path.abspath(__file__))
# os.path.join(path, 'model')
model_instance = SpeakerVerificationERes2NetV2(**args)
sv_pipeline = ERes2NetV2_Pipeline(
    model=model_instance,
)
time3 = time.time()
print("创建模型时间", time3 - time2)



speaker1_a_wav = r'E:\offer\AI配音web版\9.2\AIDubbing-QT-main\OutputFolder\audio_separation\a视频_test-分离人声结果-20250902-211709\elevenlab\角色干音_陈女士_20250902_211803.mp3'
speaker1_b_wav = r'E:\offer\AI配音web版\9.2\AIDubbing-QT-main\OutputFolder\audio_separation\伤心者同盟（英）-3-分离人声结果-20250827-162624\mdxnet\角色干音_路辰_20250827_162918.mp3'
speaker2_a_wav = r'E:\offer\AI配音web版\9.2\AIDubbing-QT-main\OutputFolder\audio_separation\a视频_test-分离人声结果-20250902-211709\mdxnet\角色干音_陈女士_20250902_211755.mp3'

def read_and_resample_audio(file_path, target_sr=16000, sr=44100):
    # 使用soundfile读取音频文件
    if isinstance(file_path, str):
        data, sr = sf.read(file_path)
    elif isinstance(file_path, np.ndarray):
        data = file_path
    else:
        return np.zeros(10000)

    # 如果是立体声，转换为单声道
    if len(data.shape) > 1:
        data = np.mean(data, axis=1)

    # 如果采样率不是目标采样率，则进行重采样
    if sr != target_sr:
        # 计算重采样后的长度
        new_length = int(len(data) * target_sr / sr)
        # 重采样
        data = signal.resample(data, new_length)

    return data


# 读取并重采样音频文件
speaker1_a_wav = read_and_resample_audio(speaker1_a_wav)
speaker1_b_wav = read_and_resample_audio(speaker1_b_wav)
speaker2_a_wav = read_and_resample_audio(speaker2_a_wav)

sf.write("speaker1_a_wav.wav", speaker1_a_wav, 16000)
sf.write("speaker1_b_wav.wav", speaker1_b_wav, 16000)
sf.write("speaker2_a_wav.wav", speaker2_a_wav, 16000)


# 相同说话人语音
result = sv_pipeline([speaker1_a_wav, speaker1_b_wav])
print(result)
# 不同说话人语音
result = sv_pipeline([speaker1_a_wav, speaker2_a_wav])
print(result)
# 可以自定义得分阈值来进行识别
result = sv_pipeline([speaker1_a_wav, speaker2_a_wav], thr=0.365)
print(result)



def get_embeddings(in_audios: Union[np.ndarray, list],
             thr: float = None):
    in_audios = [read_and_resample_audio(audio) for audio in in_audios]
    if thr is not None:
        sv_pipeline.thr = thr
    if sv_pipeline.thr < -1 or sv_pipeline.thr > 1:
        raise ValueError(
            'modelscope error: the thr value should be in [-1, 1], but found to be %f.'
            % sv_pipeline.thr)
    wavs = sv_pipeline.preprocess(in_audios)
    embs = sv_pipeline.forward(wavs)
    return embs


result = get_embeddings([speaker1_a_wav, speaker1_b_wav, speaker2_a_wav])
print(result)

result = np.array(result)
print(result)
clusterer = hdbscan.HDBSCAN(min_cluster_size=2, branch_detection_data=True)


cluster_labels = clusterer.fit_predict(result)

print("cluster_labels", cluster_labels)
# 可视化聚类结果
plt.figure(figsize=(10, 8))

# # 获取所有簇的标签（排除噪声点）
unique_labels = set(cluster_labels)

# 为每个簇生成颜色
colors = [plt.cm.Spectral(each) for each in np.linspace(0, 1, len(unique_labels))]

# 绘制每个簇的点
for k, col in zip(unique_labels, colors):
    if k == -1:
        # 噪声点用红色
        col = [1, 0, 0, 1]
    
    class_member_mask = (cluster_labels == k)
    xy = result[class_member_mask]
    plt.scatter(xy[:, 0], xy[:, 1], c=[col], s=50, edgecolors='k', label=f'Cluster {k}')


plt.title('HDBSCAN Clustering Result')
plt.xlabel('Feature 1')
plt.ylabel('Feature 2')
plt.legend()
plt.grid(True)
plt.show()



