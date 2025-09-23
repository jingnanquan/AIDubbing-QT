# E:\offer\AI配音web版\9.2\AIDubbing-QT-main\Service\ERes2NetV2\interactive_visualizer.py
import os
import sys
import time
import numpy as np
import soundfile as sf
from typing import List, Union, Tuple, Optional
import multiprocessing as mp
from multiprocessing import Process, Queue, Event
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.patches import Circle
from sklearn.decomposition import PCA
from sklearn.manifold import TSNE
import PyQt5.QtWidgets as qtw
from PyQt5.QtCore import QTimer, pyqtSignal, QObject
import threading

try:
    from .audio_player import SimpleAudioPlayer
except ImportError:
    from audio_player import SimpleAudioPlayer


class InteractiveEmbeddingVisualizer(QObject):
    """交互式embedding可视化器，支持点击播放音频"""
    
    # 定义信号
    audio_play_requested = pyqtSignal(int)  # 请求播放指定索引的音频
    
    def __init__(self, embeddings: np.ndarray, labels: np.ndarray, 
                 audio_data: List[np.ndarray], sample_rate: int = 16000):
        super().__init__()
        self.embeddings = embeddings
        self.labels = labels
        self.audio_data = audio_data
        self.sample_rate = sample_rate
        
        # 设置中文字体
        plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']
        plt.rcParams['axes.unicode_minus'] = False
        
        # 降维处理
        self.embeddings_2d = self._reduce_dimensions()
        
        # 创建颜色映射
        self.colors = self._create_color_map()
        
        # 当前选中的点
        self.selected_point = None
        self.highlight_circle = None
        
    def _reduce_dimensions(self) -> np.ndarray:
        """降维处理"""
        if len(self.embeddings) <= 2:
            return self.embeddings[:, :2] if self.embeddings.shape[1] >= 2 else np.column_stack([self.embeddings[:, 0], np.zeros(len(self.embeddings))])
        
        # 使用PCA降维
        if len(self.embeddings) <= 30:
            reducer = PCA(n_components=2, random_state=42)
        else:
            reducer = TSNE(n_components=2, random_state=42, 
                          perplexity=min(30, len(self.embeddings) - 1))
        
        return reducer.fit_transform(self.embeddings)
    
    def _create_color_map(self) -> dict:
        """创建颜色映射"""
        unique_labels = sorted(set(self.labels))
        colors = plt.cm.Set3(np.linspace(0, 1, len(unique_labels)))
        return {label: colors[i] for i, label in enumerate(unique_labels)}
    
    def create_visualization(self) -> FigureCanvas:
        """创建可视化界面"""
        # 创建图形和画布
        fig = Figure(figsize=(15, 10))
        canvas = FigureCanvas(fig)
        
        # 创建子图
        ax = fig.add_subplot(111)
        
        # 绘制散点图
        self.scatter_plot = ax.scatter(
            self.embeddings_2d[:, 0], 
            self.embeddings_2d[:, 1],
            c=[self.colors[label] for label in self.labels],
            s=120, 
            alpha=0.8, 
            edgecolors='black',
            linewidth=0.5,
            picker=True,
            pickradius=10
        )
        
        # 设置标题和标签
        ax.set_title('🎵 说话人聚类分析 - 点击任意点播放对应音频', 
                    fontsize=16, fontweight='bold', pad=20)
        ax.set_xlabel('第1主成分', fontsize=12)
        ax.set_ylabel('第2主成分', fontsize=12)
        
        # 添加图例
        unique_labels = sorted(set(self.labels))
        legend_elements = []
        for label in unique_labels:
            if label != -1:
                count = np.sum(self.labels == label)
                legend_elements.append(
                    plt.Line2D([0], [0], marker='o', color='w', 
                              markerfacecolor=self.colors[label], markersize=10,
                              label=f'说话人{label + 1} ({count}个)')
                )
        
        if -1 in unique_labels:
            count = np.sum(self.labels == -1)
            legend_elements.append(
                plt.Line2D([0], [0], marker='o', color='w', 
                          markerfacecolor=self.colors[-1], markersize=10,
                          label=f'未识别 ({count}个)')
            )
        
        ax.legend(handles=legend_elements, loc='upper right', bbox_to_anchor=(1.0, 1.0))
        ax.grid(True, alpha=0.3)
        
        # 添加统计信息文本框
        stats_text = self._create_stats_text()
        ax.text(0.02, 0.98, stats_text, transform=ax.transAxes, 
                fontsize=10, verticalalignment='top',
                bbox=dict(boxstyle='round,pad=0.5', facecolor='lightblue', alpha=0.8))
        
        # 绑定点击事件
        canvas.mpl_connect('button_press_event', self._on_click)
        canvas.mpl_connect('motion_notify_event', self._on_hover)
        
        # 存储引用
        self.fig = fig
        self.ax = ax
        self.canvas = canvas
        
        return canvas
    
    def _create_stats_text(self) -> str:
        """创建统计信息文本"""
        unique_labels = set(self.labels)
        n_speakers = len(unique_labels) - (1 if -1 in unique_labels else 0)
        n_unidentified = np.sum(self.labels == -1)
        
        stats = f"📊 分析结果\n"
        stats += f"总音频数: {len(self.embeddings)}\n"
        stats += f"说话人数: {n_speakers}\n"
        stats += f"未识别数: {n_unidentified}\n\n"
        stats += "💡 操作提示:\n"
        stats += "• 点击任意点播放音频\n"
        stats += "• 鼠标悬停查看详情\n"
        stats += "• 右键可保存图片"
        
        return stats
    
    def _on_click(self, event):
        """处理点击事件"""
        if event.inaxes != self.ax:
            return
        
        if event.button == 1:  # 左键点击
            # 找到最近的点
            if hasattr(event, 'ind') and len(event.ind) > 0:
                idx = event.ind[0]
                self._highlight_point(idx)
                self._play_audio(idx)
        elif event.button == 3:  # 右键点击
            self._save_plot()
    
    def _on_hover(self, event):
        """处理鼠标悬停事件"""
        if event.inaxes != self.ax:
            return
        
        # 更新鼠标样式
        if hasattr(event, 'ind') and len(event.ind) > 0:
            self.canvas.set_cursor(1)  # 手型光标
        else:
            self.canvas.set_cursor(0)  # 默认光标
    
    def _highlight_point(self, idx: int):
        """高亮选中的点"""
        # 移除之前的高亮
        if self.highlight_circle:
            self.highlight_circle.remove()
        
        # 添加新的高亮圆圈
        x, y = self.embeddings_2d[idx]
        self.highlight_circle = Circle((x, y), 0.1, fill=False, 
                                     edgecolor='red', linewidth=3, alpha=0.8)
        self.ax.add_patch(self.highlight_circle)
        
        # 更新标题显示选中信息
        label = self.labels[idx]
        speaker_name = f"说话人{label + 1}" if label != -1 else "未识别"
        self.ax.set_title(f'🎵 说话人聚类分析 - 已选中: {speaker_name} (索引: {idx})', 
                         fontsize=16, fontweight='bold', pad=20)
        
        self.canvas.draw()
        self.selected_point = idx
    
    def _play_audio(self, idx: int):
        """播放指定索引的音频"""
        if 0 <= idx < len(self.audio_data):
            self.audio_play_requested.emit(idx)
            print(f"播放音频 {idx}: 说话人{self.labels[idx] + 1 if self.labels[idx] != -1 else '未识别'}")
    
    def _save_plot(self):
        """保存图片"""
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        filename = f"speaker_clustering_{timestamp}.png"
        self.fig.savefig(filename, dpi=300, bbox_inches='tight')
        print(f"图片已保存: {filename}")


# AudioPlayer类已移动到audio_player.py文件中


class VisualizationWindow(qtw.QMainWindow):
    """可视化窗口"""
    
    def __init__(self, embeddings: np.ndarray, labels: np.ndarray, 
                 audio_data: List[np.ndarray], sample_rate: int = 16000):
        super().__init__()
        self.embeddings = embeddings
        self.labels = labels
        self.audio_data = audio_data
        self.sample_rate = sample_rate
        
        # 创建音频播放器
        self.audio_player = SimpleAudioPlayer(sample_rate)
        
        # 创建可视化器
        self.visualizer = InteractiveEmbeddingVisualizer(
            embeddings, labels, audio_data, sample_rate
        )
        
        # 连接信号
        self.visualizer.audio_play_requested.connect(self.play_audio)
        
        # 设置窗口
        self.setWindowTitle("说话人聚类分析 - 交互式可视化")
        self.setGeometry(100, 100, 1200, 800)
        
        # 创建中央部件
        central_widget = qtw.QWidget()
        self.setCentralWidget(central_widget)
        
        # 创建布局
        layout = qtw.QVBoxLayout(central_widget)
        
        # 添加控制面板
        control_panel = self._create_control_panel()
        layout.addWidget(control_panel)
        
        # 添加可视化画布
        self.canvas = self.visualizer.create_visualization()
        layout.addWidget(self.canvas)
        
        # 添加状态栏
        self.statusBar().showMessage("准备就绪 - 点击任意点播放音频")
        
    def _create_control_panel(self) -> qtw.QWidget:
        """创建控制面板"""
        panel = qtw.QWidget()
        layout = qtw.QHBoxLayout(panel)
        
        # 添加按钮
        save_btn = qtw.QPushButton("保存图片")
        save_btn.clicked.connect(self.visualizer._save_plot)
        
        info_btn = qtw.QPushButton("显示统计信息")
        info_btn.clicked.connect(self._show_stats)
        
        layout.addWidget(save_btn)
        layout.addWidget(info_btn)
        layout.addStretch()
        
        return panel
    
    def _show_stats(self):
        """显示详细统计信息"""
        unique_labels = set(self.labels)
        n_speakers = len(unique_labels) - (1 if -1 in unique_labels else 0)
        
        stats_text = f"📊 详细统计信息\n\n"
        stats_text += f"总音频片段数: {len(self.embeddings)}\n"
        stats_text += f"识别出的说话人数: {n_speakers}\n"
        stats_text += f"未识别片段数: {np.sum(self.labels == -1)}\n\n"
        
        stats_text += "📈 各说话人分布:\n"
        for label in sorted(unique_labels):
            if label != -1:
                count = np.sum(self.labels == label)
                percentage = count / len(self.labels) * 100
                stats_text += f"  说话人{label + 1}: {count}个片段 ({percentage:.1f}%)\n"
        
        if -1 in unique_labels:
            count = np.sum(self.labels == -1)
            percentage = count / len(self.labels) * 100
            stats_text += f"  未识别: {count}个片段 ({percentage:.1f}%)\n"
        
        # 显示对话框
        msg_box = qtw.QMessageBox()
        msg_box.setWindowTitle("统计信息")
        msg_box.setText(stats_text)
        msg_box.exec_()
    
    def play_audio(self, idx: int):
        """播放音频"""
        if 0 <= idx < len(self.audio_data):
            self.audio_player.play_audio(self.audio_data[idx], idx)
            self.statusBar().showMessage(f"正在播放音频片段 {idx}")


def create_visualization_process(embeddings: np.ndarray, labels: np.ndarray, 
                                audio_data: List[np.ndarray], sample_rate: int = 16000):
    """创建可视化进程"""
    app = qtw.QApplication(sys.argv)
    window = VisualizationWindow(embeddings, labels, audio_data, sample_rate)
    window.show()
    app.exec_()


if __name__ == "__main__":
    # 测试代码
    import numpy as np
    
    # 创建测试数据
    np.random.seed(42)
    embeddings = np.random.randn(20, 10)
    labels = np.random.randint(0, 3, 20)
    audio_data = [np.random.randn(16000) for _ in range(20)]
    
    # 创建可视化
    create_visualization_process(embeddings, labels, audio_data)
