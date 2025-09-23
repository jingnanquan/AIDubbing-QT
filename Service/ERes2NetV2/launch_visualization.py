# E:\offer\AI配音web版\9.2\AIDubbing-QT-main\Service\ERes2NetV2\launch_visualization.py
"""
在多线程环境下启动可视化的启动脚本
"""
import os
import sys
import multiprocessing as mp
from typing import List, Dict, Optional
import numpy as np

# 设置多进程启动方法
mp.set_start_method('spawn', force=True)

def launch_visualization_safely(embeddings: np.ndarray, 
                               labels: np.ndarray, 
                               audio_data: List[np.ndarray], 
                               sample_rate: int = 16000,
                               subtitle_info: Optional[List[Dict]] = None):
    """
    安全地启动可视化进程
    
    Args:
        embeddings: 音频embedding数组
        labels: 说话人标签数组
        audio_data: 音频数据列表
        sample_rate: 采样率
        subtitle_info: 字幕信息列表
    """
    try:
        print(f"🚀 启动可视化进程...")
        print(f"📊 数据统计: {len(embeddings)} 个音频片段, {len(set(labels))} 个说话人")
        
        # 导入可视化函数
        from Service.ERes2NetV2.advanced_visualizer import create_advanced_visualization_process
        
        # 创建新进程
        process = mp.Process(
            target=create_advanced_visualization_process,
            args=(embeddings, labels, audio_data, sample_rate, subtitle_info or [])
        )
        
        # 启动进程
        process.start()
        print(f"✅ 可视化进程已启动，PID: {process.pid}")
        
        # 等待进程完成（可选）
        # process.join()
        
        return process
        
    except Exception as e:
        print(f"❌ 启动可视化失败: {e}")
        import traceback
        traceback.print_exc()
        return None


def launch_simple_visualization(embeddings: np.ndarray, 
                               labels: np.ndarray, 
                               audio_data: List[np.ndarray], 
                               sample_rate: int = 16000):
    """
    启动简化版可视化（不依赖字幕信息）
    """
    try:
        print(f"🚀 启动简化可视化进程...")
        
        from Service.ERes2NetV2.interactive_visualizer import create_visualization_process
        
        process = mp.Process(
            target=create_visualization_process,
            args=(embeddings, labels, audio_data, sample_rate)
        )
        
        process.start()
        print(f"✅ 简化可视化进程已启动，PID: {process.pid}")
        
        return process
        
    except Exception as e:
        print(f"❌ 启动简化可视化失败: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    # 测试代码
    print("🎵 可视化启动器测试")
    
    # 创建测试数据
    np.random.seed(42)
    embeddings = np.random.randn(10, 8)
    labels = np.random.randint(0, 3, 10)
    audio_data = [np.random.randn(16000) for _ in range(10)]
    
    # 启动可视化
    process = launch_visualization_safely(embeddings, labels, audio_data)
    
    if process:
        print("✅ 测试完成")
    else:
        print("❌ 测试失败")
