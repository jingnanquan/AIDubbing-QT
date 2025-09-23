# E:\offer\AI配音web版\9.2\AIDubbing-QT-main\Service\ERes2NetV2\test_visualization.py
"""
测试可视化功能的脚本
"""
import os
import sys
import numpy as np
import soundfile as sf
from typing import List, Dict

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from Service.ERes2NetV2.advanced_visualizer import create_advanced_visualization_process


def create_test_data(n_samples: int = 20, n_features: int = 10, n_speakers: int = 3):
    """创建测试数据"""
    np.random.seed(42)
    
    # 创建embedding数据
    embeddings = []
    labels = []
    audio_data = []
    subtitle_info = []
    
    for i in range(n_samples):
        # 生成不同说话人的embedding（添加一些聚类结构）
        speaker_id = i % n_speakers
        base_embedding = np.random.randn(n_features)
        
        # 为每个说话人添加特征偏移
        speaker_offset = np.array([speaker_id * 2.0] * n_features)
        embedding = base_embedding + speaker_offset + np.random.normal(0, 0.5, n_features)
        
        embeddings.append(embedding)
        labels.append(speaker_id)
        
        # 生成测试音频数据（1-3秒的随机音频）
        duration = np.random.uniform(1.0, 3.0)
        sample_rate = 16000
        n_samples_audio = int(duration * sample_rate)
        audio = np.random.randn(n_samples_audio) * 0.1  # 降低音量避免过响
        audio_data.append(audio)
        
        # 创建字幕信息
        subtitle_info.append({
            'index': i + 1,
            'start': f"00:00:{i:02d},000",
            'end': f"00:00:{i+1:02d},000",
            'text': f"这是第{i+1}个音频片段的测试文本，说话人{speaker_id + 1}",
            'speaker_label': speaker_id
        })
    
    return np.array(embeddings), np.array(labels), audio_data, subtitle_info


def test_basic_visualization():
    """测试基础可视化功能"""
    print("🎵 创建测试数据...")
    embeddings, labels, audio_data, subtitle_info = create_test_data(15, 8, 3)
    
    print(f"📊 数据统计:")
    print(f"  - 音频片段数: {len(embeddings)}")
    print(f"  - 说话人数: {len(set(labels))}")
    print(f"  - Embedding维度: {embeddings.shape[1]}")
    
    print("🚀 启动高级可视化界面...")
    try:
        create_advanced_visualization_process(
            embeddings, labels, audio_data, 16000, subtitle_info
        )
        print("✅ 可视化测试完成")
    except Exception as e:
        print(f"❌ 可视化测试失败: {e}")
        import traceback
        traceback.print_exc()


def test_with_real_audio():
    """使用真实音频文件进行测试"""
    print("🎵 使用真实音频文件测试...")
    
    # 查找项目中的音频文件
    audio_files = []
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    # 搜索可能的音频文件
    for root, dirs, files in os.walk(project_root):
        for file in files:
            if file.endswith(('.mp3', '.wav', '.m4a')):
                audio_files.append(os.path.join(root, file))
                if len(audio_files) >= 5:  # 限制测试文件数量
                    break
        if len(audio_files) >= 5:
            break
    
    if not audio_files:
        print("⚠️ 未找到音频文件，使用模拟数据")
        test_basic_visualization()
        return
    
    print(f"📁 找到 {len(audio_files)} 个音频文件")
    
    # 读取音频文件
    embeddings = []
    labels = []
    audio_data = []
    subtitle_info = []
    
    for i, audio_file in enumerate(audio_files[:5]):  # 只使用前5个文件
        try:
            # 读取音频
            audio, sample_rate = sf.read(audio_file)
            
            # 转换为单声道
            if len(audio.shape) > 1:
                audio = np.mean(audio, axis=1)
            
            # 重采样到16000Hz
            if sample_rate != 16000:
                from scipy import signal
                new_length = int(len(audio) * 16000 / sample_rate)
                audio = signal.resample(audio, new_length)
                sample_rate = 16000
            
            # 截取前3秒
            max_length = 3 * sample_rate
            if len(audio) > max_length:
                audio = audio[:max_length]
            
            audio_data.append(audio)
            
            # 生成模拟的embedding（实际应用中这里会调用模型）
            embedding = np.random.randn(10)
            embeddings.append(embedding)
            labels.append(i % 3)  # 模拟3个说话人
            
            # 创建字幕信息
            subtitle_info.append({
                'index': i + 1,
                'start': f"00:00:{i:02d},000",
                'end': f"00:00:{i+1:02d},000",
                'text': f"音频文件 {os.path.basename(audio_file)}",
                'speaker_label': i % 3
            })
            
            print(f"  ✅ 处理完成: {os.path.basename(audio_file)}")
            
        except Exception as e:
            print(f"  ❌ 处理失败: {audio_file} - {e}")
            continue
    
    if len(embeddings) > 0:
        print(f"🚀 启动可视化界面，共 {len(embeddings)} 个音频片段...")
        try:
            create_advanced_visualization_process(
                np.array(embeddings), np.array(labels), audio_data, 16000, subtitle_info
            )
            print("✅ 真实音频测试完成")
        except Exception as e:
            print(f"❌ 真实音频测试失败: {e}")
            import traceback
            traceback.print_exc()
    else:
        print("❌ 没有成功处理任何音频文件")


if __name__ == "__main__":
    print("🎵 说话人聚类分析 - 可视化测试")
    print("=" * 50)
    
    # 选择测试模式
    test_mode = input("选择测试模式 (1: 模拟数据, 2: 真实音频, 默认: 1): ").strip()
    
    if test_mode == "2":
        test_with_real_audio()
    else:
        test_basic_visualization()
    
    print("\n🎉 测试完成！")
