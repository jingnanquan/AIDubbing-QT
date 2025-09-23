# 说话人聚类分析 - 高级交互式可视化系统

## 概述

这是一个高级的说话人聚类分析可视化系统，支持在多线程环境下创建交互式界面，可以显示embedding分布并支持点击播放音频。

## 主要功能

### 🎵 交互式可视化
- **散点图显示**: 使用t-SNE或PCA降维显示高维embedding的2D分布
- **聚类中心标记**: 红色X标记显示各说话人的聚类中心
- **颜色编码**: 不同颜色代表不同的说话人
- **实时高亮**: 点击任意点会高亮显示并播放对应音频

### 🎧 音频播放功能
- **点击播放**: 左键点击散点图中的任意点播放对应音频
- **键盘快捷键**: 数字键1-9快速播放对应索引的音频
- **播放控制**: 空格键停止播放，支持实时音频播放
- **音频信息**: 显示音频时长、说话人标签等详细信息

### 📊 统计分析
- **聚类统计**: 显示总音频数、说话人数、未识别数等
- **分布分析**: 各说话人的片段数量和百分比
- **聚类质量**: 评估聚类效果和分离度
- **导出功能**: 支持导出embedding、标签和统计信息

### 🎛️ 高级功能
- **多进程架构**: 在独立进程中运行，避免Qt多线程限制
- **实时交互**: 鼠标悬停显示详细信息
- **图片保存**: 右键保存高质量可视化图片
- **帮助系统**: 内置操作指南和快捷键说明

## 文件结构

```
Service/ERes2NetV2/
├── audiosimilarity.py              # 原始聚类分析类
├── interactive_visualizer.py       # 基础交互式可视化器
├── advanced_visualizer.py          # 高级可视化器（推荐使用）
├── audio_player.py                 # 音频播放器
└── README_visualization.md         # 本文档
```

## 使用方法

### 1. 在AnnotationAudioFeatureWorker中使用

```python
from Service.ERes2NetV2.advanced_visualizer import create_advanced_visualization_process

# 在run方法中，获得embs, labels和vad_separate_audios后
if len(embs) > 0 and len(labels) > 0:
    # 准备字幕信息
    subtitle_info = []
    for i, sub in enumerate(origin_subtitles):
        subtitle_info.append({
            'index': sub['index'],
            'start': sub['start'],
            'end': sub['end'],
            'text': sub['text'],
            'speaker_label': labels[i] if i < len(labels) else -1
        })
    
    # 创建高级可视化进程
    viz_process = mp.Process(
        target=create_advanced_visualization_process,
        args=(embs, labels, vad_separate_audios, samplerate, subtitle_info)
    )
    viz_process.start()
```

### 2. 独立使用

```python
import numpy as np
from Service.ERes2NetV2.advanced_visualizer import create_advanced_visualization_process

# 准备数据
embeddings = np.random.randn(20, 10)  # 20个音频片段的10维embedding
labels = np.random.randint(0, 3, 20)  # 对应的说话人标签
audio_data = [np.random.randn(16000) for _ in range(20)]  # 音频数据
sample_rate = 16000

# 创建可视化
create_advanced_visualization_process(embeddings, labels, audio_data, sample_rate)
```

## 界面操作指南

### 🖱️ 鼠标操作
- **左键点击**: 播放对应音频片段
- **右键点击**: 保存当前可视化图片
- **鼠标悬停**: 查看音频片段详细信息

### ⌨️ 键盘快捷键
- **数字键 1-9**: 快速播放对应索引的音频片段
- **空格键**: 停止当前播放
- **Esc键**: 清除选择

### 🎛️ 界面功能
- **散点图**: 显示音频片段的embedding分布
- **红色X标记**: 表示各说话人的聚类中心
- **统计面板**: 显示详细的聚类分析结果
- **控制面板**: 提供各种操作按钮

## 技术特点

### 🔧 多进程架构
- 使用`multiprocessing.Process`创建独立进程
- 避免Qt多线程限制，确保界面响应性
- 支持进程间通信和状态监控

### 🎨 可视化技术
- **降维算法**: 支持PCA和t-SNE两种降维方法
- **聚类分析**: 基于AgglomerativeClustering的说话人分离
- **交互设计**: 基于matplotlib的交互式散点图

### 🎵 音频处理
- **实时播放**: 支持WAV格式音频的实时播放
- **临时文件管理**: 自动创建和清理临时音频文件
- **跨平台支持**: Windows、macOS、Linux系统兼容

## 依赖库

```python
# 核心依赖
numpy
scipy
scikit-learn
matplotlib
PyQt5
soundfile

# 可选依赖
pygame  # 用于更好的音频播放体验
```

## 注意事项

1. **多进程限制**: 可视化界面必须在独立进程中运行
2. **音频格式**: 目前支持WAV格式，采样率建议16000Hz
3. **内存管理**: 大量音频数据时注意内存使用
4. **临时文件**: 系统会自动清理临时音频文件

## 故障排除

### 常见问题

1. **导入错误**: 确保所有依赖库已正确安装
2. **音频播放失败**: 检查系统音频驱动和权限
3. **界面无响应**: 确保在独立进程中运行可视化
4. **内存不足**: 减少音频数据量或使用更高效的音频格式

### 调试技巧

1. 查看控制台输出的错误信息
2. 检查临时文件是否正确创建
3. 验证embedding和标签数据的维度匹配
4. 确认音频数据的采样率设置

## 更新日志

- **v1.0**: 基础交互式可视化功能
- **v2.0**: 添加高级可视化界面和音频播放
- **v2.1**: 优化多进程架构和错误处理
- **v2.2**: 增加统计分析和导出功能

## 贡献指南

欢迎提交Issue和Pull Request来改进这个可视化系统！

## 许可证

本项目遵循MIT许可证。
