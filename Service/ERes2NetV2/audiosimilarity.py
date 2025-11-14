# E:\offer\AI配音web版\9.2\AIDubbing-QT-main\Service\ERes2NetV2\similarity_class.py
import os
import time
import logging
from typing import List, Union, Tuple, Optional

import numpy as np
import soundfile as sf
from scipy import signal
import hdbscan
from matplotlib import pyplot as plt
from sklearn.cluster import AgglomerativeClustering
from sklearn.decomposition import PCA
from sklearn.manifold import TSNE
import torch
from modelscope.models.audio.sv.ERes2NetV2 import SpeakerVerificationERes2NetV2
from modelscope.pipelines.audio.speaker_verification_eres2netv2_pipeline import ERes2NetV2_Pipeline
from sklearn.metrics import pairwise_distances
from sklearn.preprocessing import normalize


class SpeakerEmbeddingCluster:
    """单例模式的说话人embedding提取和聚类分析类
    """

    _instance = None

    def __init__(self):
        """私有构造函数，确保单例模式"""
        if SpeakerEmbeddingCluster._instance is not None:
            raise Exception("此类为单例模式，请使用get_instance()方法获取实例")

        # 初始化日志
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)

        # 初始化模型
        self._initialize_model()

        # 标记实例已创建
        SpeakerEmbeddingCluster._instance = self

    def _initialize_model(self):
        """初始化ERes2NetV2模型"""
        start_time = time.time()

        # 设置临时目录
        os.environ["JOBLIB_TEMP_FOLDER"] = "C:/temp"

        # 获取当前目录
        current_path = os.path.dirname(os.path.abspath(__file__))

        # 模型配置
        self.model_config = {
            'model_config': {
                'sample_rate': 16000,
                'embed_dim': 192,
                'baseWidth': 26,
                'scale': 2,
                'expansion': 2
            },
            'pretrained_model': 'pretrained_eres2netv2.ckpt',
            'yesOrno_thr': 0.36,
            'model_dir': os.path.join(current_path, 'model'),
            'device_map': None,
            'device': 'cuda' if torch.cuda.is_available() else 'cpu'
        }

        # 创建模型实例
        self.model_instance = SpeakerVerificationERes2NetV2(**self.model_config)
        self.sv_pipeline = ERes2NetV2_Pipeline(model=self.model_instance)

        init_time = time.time() - start_time
        self.logger.info(f"模型初始化完成，耗时: {init_time:.2f}秒")

    @classmethod
    def get_instance(cls) -> 'SpeakerEmbeddingCluster':
        """获取单例实例"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def read_audio(self, audio_input: Union[str, np.ndarray],
                   target_sr: int = 16000) -> np.ndarray:
        """读取并预处理音频文件

        Args:
            audio_input: 音频文件路径或numpy数组
            target_sr: 目标采样率
            sr: 原始采样率

        Returns:
            预处理后的音频数据
        """
        try:
            if isinstance(audio_input, str):
                # 从文件读取
                data, sr = sf.read(audio_input)
            elif isinstance(audio_input, np.ndarray):
                # 直接使用numpy数组
                data = audio_input
                sr = target_sr
            else:
                raise ValueError("输入必须是文件路径或numpy数组")

            # 转换为单声道
            if len(data.shape) > 1:
                data = np.mean(data, axis=1)

            # 重采样到目标采样率
            if sr != target_sr:
                new_length = int(len(data) * target_sr / sr)
                data = signal.resample(data, new_length)

            return data

        except Exception as e:
            self.logger.error(f"音频读取失败 {audio_input}: {e}")
            return np.zeros(10000)

    def extract_embeddings(self, audio_files: List[Union[str, np.ndarray]],
                           thr: Optional[float] = None) -> np.ndarray:
        """提取音频文件的说话人embedding

        Args:
            audio_files: 音频文件列表或numpy数组列表
            thr: 阈值参数

        Returns:
            embedding数组，形状为(n_samples, embed_dim)
        """
        try:
            self.logger.info(f"开始提取{len(audio_files)}个音频的embedding...")

            # 读取音频数据
            audio_data = [self.read_audio(audio) for audio in audio_files]

            # 设置阈值
            if thr is not None:
                self.sv_pipeline.thr = thr

            # 提取embedding
            wavs = self.sv_pipeline.preprocess(audio_data)
            embeddings = self.sv_pipeline.forward(wavs)

            self.logger.info(f"embedding提取完成，形状: {embeddings.shape}")
            return np.array(embeddings)

        except Exception as e:
            self.logger.error(f"embedding提取失败: {e}")
            return np.array([])

    def cluster_speakers(self, embeddings: np.ndarray,
                         min_cluster_size: int = 5) -> np.ndarray:
        """对说话人embedding进行聚类

        Args:
            embeddings: embedding数组
            min_cluster_size: 最小聚类大小

        Returns:
            聚类标签数组，-1表示噪声
        """
        try:
            if len(embeddings) == 0:
                return np.array([])

            embeddings = embeddings.astype(np.float64)
            embeddings = normalize(embeddings, norm='l2')

            clusterer = hdbscan.HDBSCAN(
                min_cluster_size=3,
                min_samples=3,
                metric='euclidean'  # 可省略
            )
            labels = clusterer.fit_predict(embeddings)

            # embeddings = normalize(embeddings, norm='l2')
            # # 使用HDBSCAN进行聚类
            # # 计算 cosine 距离矩阵
            # distance_matrix = pairwise_distances(embeddings, metric='cosine')
            # # HDBSCAN 聚类
            # clusterer = hdbscan.HDBSCAN(
            #     min_cluster_size=min_cluster_size,
            #     metric='precomputed'
            # )
            # labels = clusterer.fit_predict(distance_matrix)


            # clustering_model = AgglomerativeClustering(
            #     n_clusters=None,  # 不预设簇的数量
            #     distance_threshold=0.7,  # 设置簇合并的距离阈值
            #     metric='cosine',
            #     linkage='average'
            # )

            # 拟合数据并获取标签
            # labels = clustering_model.fit_predict(embeddings)

            n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
            self.logger.info(f"聚类完成，发现{n_clusters}个说话人")

            return labels

        except Exception as e:
            self.logger.error(f"聚类失败: {e}")
            return np.array([])

    def visualize_clusters(self, embeddings: np.ndarray,
                           labels: np.ndarray,
                           method: str = 'tsne',
                           figsize: Tuple[int, int] = (15, 8)) -> None:
        """可视化高维embedding的聚类结果

        Args:
            embeddings: 原始embedding数组
            labels: 聚类标签
            method: 降维方法 ('pca' 或 'tsne')
            figsize: 图形大小
        """
        try:
            plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']  # 黑体，如果找不到用默认
            plt.rcParams['axes.unicode_minus'] = False  # 解决负号显示问题

            if len(embeddings) == 0 or len(labels) == 0:
                self.logger.warning("没有数据可供可视化")
                return

            # 降维处理
            if method.lower() == 'pca':
                reducer = PCA(n_components=2, random_state=42)
                title = "PCA降维 - 说话人聚类结果"
            else:  # tsne
                reducer = TSNE(n_components=2, random_state=42,
                               perplexity=min(30, len(embeddings) - 1))
                title = "t-SNE降维 - 说话人聚类结果"

            embeddings_2d = reducer.fit_transform(embeddings)

            # 创建图形
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=figsize)

            # 左侧：聚类可视化
            unique_labels = set(labels)
            colors = plt.cm.Set3(np.linspace(0, 1, len(unique_labels)))

            for label, color in zip(unique_labels, colors):
                mask = labels == label
                if label == -1:
                    # 噪声点
                    color = [1, 0, 0, 1]
                    label_name = "未识别"
                else:
                    label_name = f"说话人{label + 1}"

                ax1.scatter(embeddings_2d[mask, 0], embeddings_2d[mask, 1],
                            c=[color], s=120, alpha=0.8, edgecolors='black',
                            linewidth=0.5, label=label_name)

            ax1.set_title(title, fontsize=14, fontweight='bold')
            ax1.set_xlabel('第1主成分', fontsize=12)
            ax1.set_ylabel('第2主成分', fontsize=12)
            ax1.legend()
            ax1.grid(True, alpha=0.3)

            # 右侧：统计信息
            ax2.axis('off')

            stats_text = f"📊 聚类分析结果\n\n"
            stats_text += f"总音频数: {len(embeddings)}\n"
            stats_text += f"说话人数: {len(unique_labels) - (1 if -1 in unique_labels else 0)}\n"
            stats_text += f"未识别数: {np.sum(labels == -1)}\n\n"
            stats_text += "📈 分布详情:\n"

            for label in sorted(unique_labels):
                if label != -1:
                    count = np.sum(labels == label)
                    percentage = count / len(labels) * 100
                    stats_text += f"  说话人{label + 1}: {count}个 ({percentage:.1f}%)\n"

            ax2.text(0.05, 0.95, stats_text, transform=ax2.transAxes,
                     fontsize=11, verticalalignment='top',
                     bbox=dict(boxstyle='round,pad=0.5',
                               facecolor='lightblue', alpha=0.8))

            plt.tight_layout()
            save_path = time.strftime("%Y%m%d-%H%M%S") + ".pdf"
            plt.savefig(save_path, format='pdf', bbox_inches='tight')
            plt.close()  # 关闭图形以释放内存
            self.logger.info(f"聚类可视化已保存至 {save_path}")

        except Exception as e:
            self.logger.error(f"可视化失败: {e}")


    def analyze_speakers(self, audio_files: List[Union[str, np.ndarray]],
                         min_cluster_size: int = 2,
                         visualize: bool = True) -> Tuple[np.ndarray, np.ndarray]:
        """完整的说话人分析流程

        Args:
            audio_files: 音频文件列表
            min_cluster_size: 最小聚类大小
            visualize: 是否显示可视化结果

        Returns:
            (embeddings, labels) 元组
        """
        try:
            self.logger.info(f"开始分析{len(audio_files)}个音频文件的说话人...")

            # 提取embedding
            embeddings = self.extract_embeddings(audio_files)
            if len(embeddings) == 0:
                return np.array([]), np.array([])

            # 聚类
            labels = self.cluster_speakers(embeddings, min_cluster_size)

            # 可视化
            if visualize:
                self.visualize_clusters(embeddings, labels)

            return embeddings, labels

        except Exception as e:
            self.logger.error(f"说话人分析失败: {e}")
            return np.array([]), np.array([])

    def analyze_speakers_embs(self, audio_files: List[Union[str, np.ndarray]],
                         min_cluster_size: int = 2,
                         visualize: bool = True) -> Tuple[np.ndarray, np.ndarray]:
        """完整的说话人分析流程
        只获取embs
        """
        try:
            self.logger.info(f"开始分析{len(audio_files)}个音频文件的说话人...")

            # 提取embedding
            embeddings = self.extract_embeddings(audio_files)
            if len(embeddings) == 0:
                return np.array([]), np.array([])

            return embeddings, np.array([])

        except Exception as e:
            self.logger.error(f"说话人分析失败: {e}")
            return np.array([]), np.array([])


# 使用示例
if __name__ == "__main__":
    # 获取单例实例
    analyzer = SpeakerEmbeddingCluster.get_instance()

    # 示例音频文件
    example_audio_files = [
        r'E:\offer\AI配音web版\9.2\AIDubbing-QT-main\OutputFolder\audio_separation\a视频_test-分离人声结果-20250902-211709\elevenlab\角色干音_陈女士_20250902_211803.mp3',
        r'E:\offer\AI配音web版\9.2\AIDubbing-QT-main\OutputFolder\audio_separation\伤心者同盟（英）-3-分离人声结果-20250827-162624\mdxnet\角色干音_路辰_20250827_162918.mp3',
        r'E:\offer\AI配音web版\9.2\AIDubbing-QT-main\OutputFolder\audio_separation\a视频_test-分离人声结果-20250902-211709\mdxnet\角色干音_陈女士_20250902_211755.mp3',
        r"E:\offer\AI配音web版\9.2\AIDubbing-QT-main\OutputFolder\audio_separation\伤心者同盟（英）-1-分离人声结果-20250827-150716\mdxnet\角色干音_陆辰_20250827_151215.mp3",
        r"E:\offer\AI配音web版\9.2\AIDubbing-QT-main\OutputFolder\audio_separation\伤心者同盟（英）-1-分离人声结果-20250827-150716\mdxnet\角色干音_江皓辰_20250827_151215.mp3",
        r"E:\offer\AI配音web版\9.2\AIDubbing-QT-main\OutputFolder\audio_separation\伤心者同盟（英）-2-分离人声结果-20250827-145713\mdxnet\角色干音_路辰_20250827_150019.mp3",
        r"E:\offer\AI配音web版\9.2\AIDubbing-QT-main\OutputFolder\audio_separation\a视频_test-分离人声结果-20250828-180524\2HP\角色干音_陈女士_20250828_180708.mp3"
        r"E:\offer\AI配音web版\9.2\AIDubbing-QT-main\OutputFolder\audio_separation\a视频_test-分离人声结果-20250828-180524\2HP\角色干音_医生_20250828_180708.mp3"
        r"E:\offer\AI配音web版\9.2\AIDubbing-QT-main\OutputFolder\audio_separation\a视频_test-分离人声结果-20250828-180524\elevenlab\角色干音_陈女士_20250828_180626.mp3"
    ]

    # 执行分析
    embeddings, labels = analyzer.analyze_speakers(example_audio_files, visualize=True)

    print(f"✅ 分析完成!")
    print(f"说话人数量: {len(set(labels)) - (1 if -1 in labels else 0)}")
