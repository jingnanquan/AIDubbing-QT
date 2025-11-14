import os

import numpy as np
import soundfile as sf
from scipy import signal

# import umap
# 尝试导入UMAP，如果不可用则使用PCA作为备选
try:
    import umap

    UMAP_AVAILABLE = True
except ImportError:
    from sklearn.decomposition import PCA

    UMAP_AVAILABLE = False
    print("UMAP库未安装，使用PCA作为备选降维方法")

# 导入可视化相关库
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from matplotlib.widgets import Button
import matplotlib.patches as mpatches

# 导入音频播放器
try:
    from Service.ERes2NetV2.audio_player import SimpleAudioPlayer
except ImportError:
    from Service.ERes2NetV2.audio_player import SimpleAudioPlayer

from Service.ERes2NetV2.audiosimilarity import SpeakerEmbeddingCluster
from Service.generalUtils import time_str_to_ms
from Service.subtitleUtils import parse_subtitle_uncertain

origin_subtitles1, roles1 = parse_subtitle_uncertain(r"E:\offer\配音任务2\伤心者联盟\__测试声纹校验\1_2_merged.srt")
# origin_subtitles2, roles2 = parse_subtitle_uncertain(r"E:\offer\配音任务2\伤心者联盟\__测试声纹校验\3_4_merged.srt")

pure_vocal_audio1, samplerate1 = sf.read(r"E:\offer\配音任务2\伤心者联盟\__测试声纹校验\vocal_1_2.wav")
# pure_vocal_audio2, samplerate2 = sf.read(r"E:\offer\配音任务2\伤心者联盟\__测试声纹校验\vocal_3_4.wav")

processing_dir = r"E:\offer\配音任务2\伤心者联盟\__测试声纹校验\vad"


def get_embs(vad_subtitles: list, pure_vocal_audio: np.ndarray, samplerate: int, srt_name: str):
    vad_separate_audios = []
    vad_separate_names = []
    for idx, sub in enumerate(vad_subtitles):
        start = time_str_to_ms(sub["start"])
        end = time_str_to_ms(sub["end"])
        start_frame = int((start * samplerate) / 1000)
        end_frame = int((end * samplerate) / 1000)
        audio = pure_vocal_audio[start_frame: end_frame]

        new_length = int(len(audio) * 16000 / samplerate)
        name = f"{srt_name}_{idx}_{sub['text']}"
        sf.write(os.path.join(processing_dir, f"{srt_name}_{idx}_{sub['text']}_src.wav"),audio, samplerate)
        audio_data = signal.resample(audio, new_length)
        sf.write(os.path.join(processing_dir, f"{srt_name}_{idx}_{sub['text']}.wav"), audio_data, 16000)
        vad_separate_audios.append(audio_data)
        vad_separate_names.append(name)
        # print(vad_separate_audios)

    embs, _ = SpeakerEmbeddingCluster.get_instance().analyze_speakers_embs(vad_separate_audios, visualize=False)
    return embs,  vad_separate_audios, vad_separate_names


embs1, vad_separate_audios1, vad_separate_names1 = get_embs(origin_subtitles1, pure_vocal_audio1, samplerate1,
                                                                     "vad_1_2")


# get_embs(origin_subtitles2, pure_vocal_audio2, samplerate2, "vad_3_4")


def visualize_embeddings_3d(embeddings, labels, audio_data, names, sample_rate=16000):
    """
    使用UMAP将向量降至三维并可视化，同一角色的点颜色相同
    实现鼠标移入显示vad_separate_name和点击播放对应音频段的交互功能
    """
    # 创建音频播放器
    audio_player = SimpleAudioPlayer(sample_rate)

    # 降维到3D
    if UMAP_AVAILABLE:
        print("使用UMAP进行降维...")
        reducer = umap.UMAP(n_components=3, random_state=42)
        embeddings_3d = reducer.fit_transform(embeddings)
    else:
        print("使用PCA进行降维...")
        reducer = PCA(n_components=3, random_state=42)
        embeddings_3d = reducer.fit_transform(embeddings)

    plt.rcParams['font.sans-serif'] = ['SimHei', 'FangSong', 'Microsoft YaHei', 'KaiTi','Arial Unicode MS']  # 用来正常显示中文标签
    plt.rcParams['axes.unicode_minus'] = False  # 用来正常显示负号
    # 创建3D图形
    fig = plt.figure(figsize=(12, 9))
    ax = fig.add_subplot(111, projection='3d')

    # 为不同标签创建颜色映射
    unique_labels = np.unique(labels)
    colors = plt.cm.Set3(np.linspace(0, 1, len(unique_labels)))
    color_map = {label: colors[i] for i, label in enumerate(unique_labels)}

    # 绘制散点图
    sc = ax.scatter(embeddings_3d[:, 0], embeddings_3d[:, 1], embeddings_3d[:, 2],
                    c=[color_map[label] for label in labels],
                    s=100, alpha=0.8, picker=True, pickradius=10)

    # 设置标题和标签
    ax.set_title('3D 音频特征向量可视化' + (' (UMAP)' if UMAP_AVAILABLE else ' (PCA)'),
                 fontsize=16, fontweight='bold')
    ax.set_xlabel('第1主成分')
    ax.set_ylabel('第2主成分')
    ax.set_zlabel('第3主成分')

    # 创建图例
    legend_elements = []
    for label in unique_labels:
        if label == -1:
            legend_elements.append(mpatches.Patch(color=color_map[label], label='未识别'))
        else:
            legend_elements.append(mpatches.Patch(color=color_map[label], label=f'角色 {label}'))
    ax.legend(handles=legend_elements, loc='upper right')

    # 添加信息文本
    info_text = fig.text(0.02, 0.02, '鼠标悬停查看详细信息，点击播放音频',
                         fontsize=10, style='italic')

    # 当前选中点的信息
    selected_text = fig.text(0.02, 0.95, '', fontsize=12, fontweight='bold')

    # 事件处理函数
    def on_pick(event):
        """处理点击事件"""
        if event.artist == sc:
            # 获取被点击的点的索引
            ind = event.ind[0] if len(event.ind) > 0 else None
            if ind is not None and 0 <= ind < len(audio_data):
                sf.write(os.path.join(r"E:\offer\配音任务2\伤心者联盟\__测试声纹校验\click", f"{ind}.wav"),
                         audio_data[ind], 16000)
                # 播放对应的音频
                audio_player.play_audio(audio_data[ind], ind)
                # 更新选中文本
                label = labels[ind]
                name = names[ind] if ind < len(names) else f"音频片段 {ind}"
                selected_text.set_text(f'正在播放: {name} (角色: {label})')
                fig.canvas.draw()

    def on_hover(event):
        """处理鼠标悬停事件"""
        if event.inaxes == ax:
            # 获取最近的点
            cont, ind = sc.contains(event)
            if cont and len(ind["ind"]) > 0:
                idx = ind["ind"][0]
                if 0 <= idx < len(names):
                    name = names[idx]
                    label = labels[idx]
                    info_text.set_text(f'悬停信息: {name} (角色: {label})')
                    fig.canvas.draw()
            else:
                info_text.set_text('鼠标悬停查看详细信息，点击播放音频')
                fig.canvas.draw()

    # 连接事件
    fig.canvas.mpl_connect('pick_event', on_pick)
    fig.canvas.mpl_connect('motion_notify_event', on_hover)

    # 添加播放控制按钮
    ax_button = plt.axes([0.02, 0.90, 0.1, 0.04])
    button = Button(ax_button, '停止播放')

    def stop_audio(event):
        """停止音频播放"""
        audio_player.cleanup()
        selected_text.set_text('播放已停止')
        fig.canvas.draw()

    button.on_clicked(stop_audio)

    # 显示图形
    plt.tight_layout()
    plt.show()

    return fig, ax


# 执行可视化
if __name__ == "__main__":
    # 合并两个数据集进行可视化
    # if 'embs1' in locals() and 'embs2' in locals():
    #     all_embeddings = np.vstack([embs1, embs2])
    #     all_labels = np.hstack([labels1, labels2])
    #     all_audios = vad_separate_audios1 + vad_separate_audios2
    #     all_names = vad_separate_names1 + vad_separate_names2
    # else:
    # 只使用第一个数据集
    all_embeddings = embs1
    # all_labels = labels1
    all_labels = roles1
    all_audios = vad_separate_audios1
    all_names = vad_separate_names1

    # 执行3D可视化
    visualize_embeddings_3d(all_embeddings, all_labels, all_audios, all_names, 16000)