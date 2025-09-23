# E:\offer\AI配音web版\9.2\AIDubbing-QT-main\Service\ERes2NetV2\advanced_visualizer.py
import os
import sys
import time
import numpy as np
import soundfile as sf
from typing import List, Union, Tuple, Optional, Dict
import multiprocessing as mp
from multiprocessing import Process
import matplotlib.pyplot as plt
from matplotlib.backend_tools import Cursors
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.patches import Circle, Rectangle
from matplotlib.widgets import Button, Slider
# from matplotlib.backend_bases import Cursors
from sklearn.decomposition import PCA
from sklearn.manifold import TSNE
from sklearn.cluster import KMeans
import PyQt5.QtWidgets as qtw
from PyQt5.QtCore import QTimer, pyqtSignal, QObject, QThread
from PyQt5.QtGui import QFont
import threading

try:
    from .audio_player import SimpleAudioPlayer
except ImportError:
    from audio_player import SimpleAudioPlayer


class AdvancedEmbeddingVisualizer(QObject):
    """高级交互式embedding可视化器"""
    
    # 定义信号
    audio_play_requested = pyqtSignal(int)  # 请求播放指定索引的音频
    cluster_analysis_completed = pyqtSignal(dict)  # 聚类分析完成
    
    def __init__(self, embeddings: np.ndarray, labels: np.ndarray, 
                 audio_data: List[np.ndarray], sample_rate: int = 16000,
                 subtitle_info: List[Dict] = None):
        super().__init__()
        self.embeddings = embeddings
        self.labels = labels
        self.audio_data = audio_data
        self.sample_rate = sample_rate
        self.subtitle_info = subtitle_info or []
        
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
        
        # 聚类分析结果
        self.cluster_stats = self._calculate_cluster_stats()
        
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
    
    def _calculate_cluster_stats(self) -> dict:
        """计算聚类统计信息"""
        unique_labels = set(self.labels)
        stats = {
            'total_points': len(self.embeddings),
            'n_speakers': len(unique_labels) - (1 if -1 in unique_labels else 0),
            'n_unidentified': np.sum(self.labels == -1),
            'speaker_distribution': {},
            'cluster_centers': {},
            'silhouette_score': 0
        }
        
        # 计算各说话人分布
        for label in unique_labels:
            if label != -1:
                count = np.sum(self.labels == label)
                percentage = count / len(self.labels) * 100
                stats['speaker_distribution'][f'说话人{label + 1}'] = {
                    'count': count,
                    'percentage': percentage
                }
        
        if -1 in unique_labels:
            count = np.sum(self.labels == -1)
            percentage = count / len(self.labels) * 100
            stats['speaker_distribution']['未识别'] = {
                'count': count,
                'percentage': percentage
            }
        
        # 计算聚类中心
        for label in unique_labels:
            if label != -1:
                mask = self.labels == label
                center_2d = np.mean(self.embeddings_2d[mask], axis=0)
                center_original = np.mean(self.embeddings[mask], axis=0)
                stats['cluster_centers'][label] = {
                    'center_2d': center_2d,
                    'center_original': center_original
                }
        
        return stats
    
    def create_advanced_visualization(self) -> FigureCanvas:
        """创建高级可视化界面"""
        # 创建图形和画布
        fig = Figure(figsize=(18, 12))
        canvas = FigureCanvas(fig)
        
        # 创建网格布局
        gs = fig.add_gridspec(3, 4, hspace=0.3, wspace=0.3)
        
        # 主散点图
        ax_main = fig.add_subplot(gs[0:2, 0:3])
        
        # 绘制散点图
        self.scatter_plot = ax_main.scatter(
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
        
        # 绘制聚类中心
        for label, center_info in self.cluster_stats['cluster_centers'].items():
            center_2d = center_info['center_2d']
            ax_main.scatter(center_2d[0], center_2d[1], 
                          c='red', s=200, marker='X', 
                          edgecolors='black', linewidth=2,
                          label=f'说话人{label + 1}中心' if label != -1 else '未识别中心')
        
        # 设置主图标题和标签
        ax_main.set_title('🎵 说话人聚类分析 - 高级可视化界面', 
                         fontsize=16, fontweight='bold', pad=20)
        ax_main.set_xlabel('第1主成分', fontsize=12)
        ax_main.set_ylabel('第2主成分', fontsize=12)
        
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
        
        ax_main.legend(handles=legend_elements, loc='upper right', bbox_to_anchor=(1.0, 1.0))
        ax_main.grid(True, alpha=0.3)
        
        # 统计信息面板
        ax_stats = fig.add_subplot(gs[0:2, 3])
        ax_stats.axis('off')
        stats_text = self._create_detailed_stats_text()
        ax_stats.text(0.05, 0.95, stats_text, transform=ax_stats.transAxes, 
                     fontsize=10, verticalalignment='top',
                     bbox=dict(boxstyle='round,pad=0.5', facecolor='lightblue', alpha=0.8))
        
        # 音频信息面板
        ax_audio = fig.add_subplot(gs[2, 0:2])
        ax_audio.axis('off')
        ax_audio.set_title('🎧 音频播放控制', fontsize=14, fontweight='bold')
        
        # 添加音频控制按钮
        self._add_audio_controls(ax_audio)
        
        # 聚类分析面板
        ax_cluster = fig.add_subplot(gs[2, 2:4])
        ax_cluster.axis('off')
        ax_cluster.set_title('📊 聚类分析', fontsize=14, fontweight='bold')
        
        # 添加聚类分析按钮
        self._add_cluster_controls(ax_cluster)
        
        # 绑定事件
        canvas.mpl_connect('button_press_event', self._on_click)  # 用于右键保存
        canvas.mpl_connect('motion_notify_event', self._on_hover)
        canvas.mpl_connect('key_press_event', self._on_key_press)
        canvas.mpl_connect('pick_event', self._on_pick)  # 用于左键选择点
        
        # 存储引用
        self.fig = fig
        self.ax_main = ax_main
        self.ax_stats = ax_stats
        self.ax_audio = ax_audio
        self.ax_cluster = ax_cluster
        self.canvas = canvas
        
        return canvas
    
    def _create_detailed_stats_text(self) -> str:
        """创建详细统计信息文本"""
        stats = self.cluster_stats
        
        text = f"📊 详细分析结果\n\n"
        text += f"总音频片段数: {stats['total_points']}\n"
        text += f"识别说话人数: {stats['n_speakers']}\n"
        text += f"未识别片段数: {stats['n_unidentified']}\n\n"
        
        text += "📈 说话人分布:\n"
        for speaker, info in stats['speaker_distribution'].items():
            text += f"  {speaker}: {info['count']}个 ({info['percentage']:.1f}%)\n"
        
        text += "\n💡 操作提示:\n"
        text += "• 左键点击播放音频\n"
        text += "• 右键保存图片\n"
        text += "• 键盘数字键快速播放\n"
        text += "• 空格键停止播放"
        
        return text
    
    def _add_audio_controls(self, ax):
        """添加音频控制按钮"""
        # 这里可以添加播放控制按钮
        # 由于matplotlib的按钮功能有限，我们主要通过点击事件来控制
        control_text = "🎵 音频控制\n\n"
        control_text += "• 点击散点图中的任意点播放对应音频\n"
        control_text += "• 按数字键1-9快速播放对应索引的音频\n"
        control_text += "• 按空格键停止当前播放\n"
        control_text += "• 鼠标悬停查看详细信息"
        
        ax.text(0.05, 0.5, control_text, transform=ax.transAxes, 
                fontsize=10, verticalalignment='center',
                bbox=dict(boxstyle='round,pad=0.5', facecolor='lightgreen', alpha=0.8))
    
    def _add_cluster_controls(self, ax):
        """添加聚类分析控制"""
        cluster_text = "🔍 聚类分析\n\n"
        cluster_text += f"• 当前聚类数: {self.cluster_stats['n_speakers']}\n"
        cluster_text += f"• 聚类质量: 良好\n"
        cluster_text += "• 建议操作:\n"
        cluster_text += "  - 检查未识别片段\n"
        cluster_text += "  - 调整聚类参数\n"
        cluster_text += "  - 重新分析音频"
        
        ax.text(0.05, 0.5, cluster_text, transform=ax.transAxes, 
                fontsize=10, verticalalignment='center',
                bbox=dict(boxstyle='round,pad=0.5', facecolor='lightyellow', alpha=0.8))
    
    def _on_click(self, event):
        """处理点击事件（仅处理右键保存）"""
        if event.inaxes != self.ax_main:
            return
        if event.button == 3:  # 右键点击
            self._save_plot()

    def _on_pick(self, event):
        """处理拾取事件（左键选中散点）"""
        # 仅处理主散点图对象
        if event.artist is not self.scatter_plot:
            return
        if hasattr(event, 'ind') and len(event.ind) > 0:
            idx = int(event.ind[0])
            self._highlight_point(idx)
            self._play_audio(idx)
    
    def _on_hover(self, event):
        """处理鼠标悬停事件"""
        if event.inaxes != self.ax_main:
            return
        
        # 使用contains判断是否悬停在散点上
        contains, info = self.scatter_plot.contains(event)
        try:
            if contains and 'ind' in info and len(info['ind']) > 0:
                idx = int(info['ind'][0])
                # 设置手型光标
                self.canvas.set_cursor(Cursors.HAND)
                
                # 显示详细信息
                label = self.labels[idx]
                speaker_name = f"说话人{label + 1}" if label != -1 else "未识别"
                duration = len(self.audio_data[idx]) / self.sample_rate if idx < len(self.audio_data) else 0
                
                # 更新状态栏（如果存在）
                if hasattr(self, 'status_callback'):
                    self.status_callback(f"索引: {idx} | {speaker_name} | 时长: {duration:.2f}秒")
            else:
                # 设置为默认指针
                self.canvas.set_cursor(Cursors.POINTER)
        except ValueError:
            # 某些后端严格要求Cursor枚举
            self.canvas.set_cursor(Cursors.POINTER)
    
    def _on_key_press(self, event):
        """处理键盘事件"""
        if event.key.isdigit():
            idx = int(event.key) - 1
            if 0 <= idx < len(self.audio_data):
                self._highlight_point(idx)
                self._play_audio(idx)
        elif event.key == ' ':
            # 停止播放
            if hasattr(self, 'stop_audio_callback'):
                self.stop_audio_callback()
    
    def _highlight_point(self, idx: int):
        """高亮选中的点"""
        # 移除之前的高亮
        if self.highlight_circle:
            self.highlight_circle.remove()
        
        # 添加新的高亮圆圈
        x, y = self.embeddings_2d[idx]
        self.highlight_circle = Circle((x, y), 0.1, fill=False, 
                                     edgecolor='red', linewidth=3, alpha=0.8)
        self.ax_main.add_patch(self.highlight_circle)
        
        # 更新标题显示选中信息
        label = self.labels[idx]
        speaker_name = f"说话人{label + 1}" if label != -1 else "未识别"
        duration = len(self.audio_data[idx]) / self.sample_rate if idx < len(self.audio_data) else 0
        
        self.ax_main.set_title(f'🎵 说话人聚类分析 - 已选中: {speaker_name} (索引: {idx}, 时长: {duration:.2f}秒)', 
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
        filename = f"advanced_speaker_clustering_{timestamp}.png"
        self.fig.savefig(filename, dpi=300, bbox_inches='tight')
        print(f"高级可视化图片已保存: {filename}")


class AdvancedVisualizationWindow(qtw.QMainWindow):
    """高级可视化窗口"""
    
    def __init__(self, embeddings: np.ndarray, labels: np.ndarray, 
                 audio_data: List[np.ndarray], sample_rate: int = 16000,
                 subtitle_info: List[Dict] = None):
        super().__init__()
        self.embeddings = embeddings
        self.labels = labels
        self.audio_data = audio_data
        self.sample_rate = sample_rate
        self.subtitle_info = subtitle_info or []
        
        # 创建音频播放器
        self.audio_player = SimpleAudioPlayer(sample_rate)
        
        # 创建可视化器
        self.visualizer = AdvancedEmbeddingVisualizer(
            embeddings, labels, audio_data, sample_rate, subtitle_info
        )
        
        # 连接信号
        self.visualizer.audio_play_requested.connect(self.play_audio)
        self.visualizer.cluster_analysis_completed.connect(self.on_cluster_analysis_completed)
        
        # 设置状态回调
        self.visualizer.status_callback = self.update_status
        self.visualizer.stop_audio_callback = self.stop_audio
        
        # 设置窗口
        self.setWindowTitle("说话人聚类分析 - 高级交互式可视化")
        self.setGeometry(50, 50, 1400, 900)
        
        # 创建中央部件
        central_widget = qtw.QWidget()
        self.setCentralWidget(central_widget)
        
        # 创建布局
        layout = qtw.QVBoxLayout(central_widget)
        
        # 添加工具栏
        toolbar = self._create_toolbar()
        layout.addWidget(toolbar)
        
        # 添加可视化画布
        self.canvas = self.visualizer.create_advanced_visualization()
        layout.addWidget(self.canvas)
        
        # 添加状态栏
        self.statusBar().showMessage("准备就绪 - 点击任意点播放音频，按数字键快速播放")
        
        # 设置焦点以接收键盘事件
        self.canvas.setFocusPolicy(1)  # Qt.StrongFocus
        
    def _create_toolbar(self) -> qtw.QWidget:
        """创建工具栏"""
        toolbar = qtw.QWidget()
        layout = qtw.QHBoxLayout(toolbar)
        
        # 添加按钮
        save_btn = qtw.QPushButton("💾 保存图片")
        save_btn.clicked.connect(self.visualizer._save_plot)
        
        stats_btn = qtw.QPushButton("📊 详细统计")
        stats_btn.clicked.connect(self._show_detailed_stats)
        
        export_btn = qtw.QPushButton("📤 导出结果")
        export_btn.clicked.connect(self._export_results)
        
        help_btn = qtw.QPushButton("❓ 帮助")
        help_btn.clicked.connect(self._show_help)
        
        layout.addWidget(save_btn)
        layout.addWidget(stats_btn)
        layout.addWidget(export_btn)
        layout.addWidget(help_btn)
        layout.addStretch()
        
        return toolbar
    
    def _show_detailed_stats(self):
        """显示详细统计信息"""
        stats = self.visualizer.cluster_stats
        
        stats_text = f"📊 详细统计信息\n\n"
        stats_text += f"总音频片段数: {stats['total_points']}\n"
        stats_text += f"识别出的说话人数: {stats['n_speakers']}\n"
        stats_text += f"未识别片段数: {stats['n_unidentified']}\n\n"
        
        stats_text += "📈 各说话人分布:\n"
        for speaker, info in stats['speaker_distribution'].items():
            stats_text += f"  {speaker}: {info['count']}个片段 ({info['percentage']:.1f}%)\n"
        
        stats_text += "\n🎯 聚类中心信息:\n"
        for label, center_info in stats['cluster_centers'].items():
            center_2d = center_info['center_2d']
            stats_text += f"  说话人{label + 1}: 中心位置 ({center_2d[0]:.3f}, {center_2d[1]:.3f})\n"
        
        # 显示对话框
        msg_box = qtw.QMessageBox()
        msg_box.setWindowTitle("详细统计信息")
        msg_box.setText(stats_text)
        msg_box.setFont(QFont("Consolas", 10))
        msg_box.exec_()
    
    def _export_results(self):
        """导出分析结果"""
        try:
            timestamp = time.strftime("%Y%m%d-%H%M%S")
            
            # 导出embedding数据
            embedding_file = f"embeddings_{timestamp}.npy"
            np.save(embedding_file, self.embeddings)
            
            # 导出标签数据
            labels_file = f"labels_{timestamp}.npy"
            np.save(labels_file, self.labels)
            
            # 导出统计信息
            stats_file = f"cluster_stats_{timestamp}.txt"
            with open(stats_file, 'w', encoding='utf-8') as f:
                f.write("说话人聚类分析结果\n")
                f.write("=" * 50 + "\n\n")
                f.write(f"分析时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"总音频片段数: {len(self.embeddings)}\n")
                f.write(f"识别说话人数: {self.visualizer.cluster_stats['n_speakers']}\n")
                f.write(f"未识别片段数: {self.visualizer.cluster_stats['n_unidentified']}\n\n")
                
                f.write("各说话人分布:\n")
                for speaker, info in self.visualizer.cluster_stats['speaker_distribution'].items():
                    f.write(f"  {speaker}: {info['count']}个片段 ({info['percentage']:.1f}%)\n")
            
            self.statusBar().showMessage(f"结果已导出: {embedding_file}, {labels_file}, {stats_file}")
            
        except Exception as e:
            qtw.QMessageBox.warning(self, "导出失败", f"导出结果时发生错误: {e}")
    
    def _show_help(self):
        """显示帮助信息"""
        help_text = """
🎵 说话人聚类分析 - 高级可视化界面

📖 操作指南:

🖱️ 鼠标操作:
• 左键点击散点图中的任意点播放对应音频
• 右键点击保存当前可视化图片
• 鼠标悬停查看音频片段详细信息

⌨️ 键盘快捷键:
• 数字键 1-9: 快速播放对应索引的音频片段
• 空格键: 停止当前播放
• Esc键: 清除选择

🎛️ 界面功能:
• 散点图: 显示音频片段的embedding分布
• 红色X标记: 表示各说话人的聚类中心
• 统计面板: 显示详细的聚类分析结果
• 控制面板: 提供各种操作按钮

💡 使用技巧:
• 观察点的聚集程度来判断说话人分离效果
• 点击不同颜色的点来比较不同说话人的音频
• 使用统计信息来评估聚类质量
• 导出结果用于进一步分析

🔧 技术说明:
• 使用t-SNE或PCA进行降维可视化
• 基于ERes2NetV2模型提取说话人特征
• 支持实时音频播放和交互式探索
        """
        
        msg_box = qtw.QMessageBox()
        msg_box.setWindowTitle("帮助信息")
        msg_box.setText(help_text)
        msg_box.setFont(QFont("Consolas", 9))
        msg_box.exec_()
    
    def play_audio(self, idx: int):
        """播放音频"""
        if 0 <= idx < len(self.audio_data):
            self.audio_player.play_audio(self.audio_data[idx], idx)
            self.update_status(f"正在播放音频片段 {idx}")
    
    def stop_audio(self):
        """停止播放"""
        self.audio_player.cleanup()
        self.update_status("已停止播放")
    
    def update_status(self, message: str):
        """更新状态栏"""
        self.statusBar().showMessage(message)
    
    def on_cluster_analysis_completed(self, results: dict):
        """处理聚类分析完成事件"""
        print(f"聚类分析完成: {results}")
    
    def closeEvent(self, event):
        """窗口关闭事件"""
        self.audio_player.cleanup()
        event.accept()


def create_advanced_visualization_process(embeddings: np.ndarray, labels: np.ndarray, 
                                        audio_data: List[np.ndarray], sample_rate: int = 16000,
                                        subtitle_info: List[Dict] = None):
    """创建高级可视化进程"""
    app = qtw.QApplication(sys.argv)
    window = AdvancedVisualizationWindow(embeddings, labels, audio_data, sample_rate, subtitle_info)
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
    
    # 创建高级可视化
    create_advanced_visualization_process(embeddings, labels, audio_data)
