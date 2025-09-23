# E:\offer\AI配音web版\9.2\AIDubbing-QT-main\Service\ERes2NetV2\audio_player.py
import os
import tempfile
import threading
import time
from typing import Optional
import numpy as np
import soundfile as sf
from PyQt5.QtCore import QObject, pyqtSignal, QTimer
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtCore import QUrl


class AudioPlayer(QObject):
    """增强版音频播放器，支持实时播放和进度控制"""
    
    # 定义信号
    playback_started = pyqtSignal(int)  # 开始播放指定索引的音频
    playback_finished = pyqtSignal(int)  # 播放完成
    playback_error = pyqtSignal(str)  # 播放错误
    
    def __init__(self, sample_rate: int = 16000):
        super().__init__()
        self.sample_rate = sample_rate
        self.current_audio_index = -1
        self.is_playing = False
        self.temp_files = {}  # 存储临时文件路径
        self.media_player = None
        self._init_media_player()
        
    def _init_media_player(self):
        """初始化媒体播放器"""
        try:
            self.media_player = QMediaPlayer()
            self.media_player.stateChanged.connect(self._on_state_changed)
            self.media_player.error.connect(self._on_error)
        except Exception as e:
            print(f"初始化媒体播放器失败: {e}")
            self.media_player = None
    
    def _on_state_changed(self, state):
        """处理播放状态变化"""
        if state == QMediaPlayer.StoppedState and self.is_playing:
            self.is_playing = False
            self.playback_finished.emit(self.current_audio_index)
    
    def _on_error(self, error):
        """处理播放错误"""
        error_msg = f"音频播放错误: {error}"
        self.playback_error.emit(error_msg)
        self.is_playing = False
    
    def prepare_audio(self, audio_data: np.ndarray, index: int) -> str:
        """准备音频文件"""
        try:
            # 创建临时文件
            temp_fd, temp_path = tempfile.mkstemp(suffix='.wav', prefix=f'audio_{index}_')
            os.close(temp_fd)  # 关闭文件描述符
            
            # 保存音频数据
            sf.write(temp_path, audio_data, self.sample_rate)
            
            # 存储临时文件路径
            self.temp_files[index] = temp_path
            
            return temp_path
            
        except Exception as e:
            self.playback_error.emit(f"准备音频失败: {e}")
            return None
    
    def play_audio(self, audio_data: np.ndarray, index: int):
        """播放音频数据"""
        try:
            # 停止当前播放
            self.stop_audio()
            
            # 准备音频文件
            temp_path = self.prepare_audio(audio_data, index)
            if not temp_path:
                return
            
            # 使用媒体播放器播放
            if self.media_player:
                media_content = QMediaContent(QUrl.fromLocalFile(temp_path))
                self.media_player.setMedia(media_content)
                self.media_player.play()
                
                self.current_audio_index = index
                self.is_playing = True
                self.playback_started.emit(index)
                
                print(f"正在播放音频片段 {index}，长度: {len(audio_data)/self.sample_rate:.2f}秒")
            else:
                # 备用方案：使用系统播放器
                self._play_with_system_player(temp_path, index)
                
        except Exception as e:
            self.playback_error.emit(f"播放音频失败: {e}")
    
    def _play_with_system_player(self, file_path: str, index: int):
        """使用系统播放器播放音频（备用方案）"""
        try:
            import subprocess
            import platform
            
            if platform.system() == "Windows":
                subprocess.Popen(['start', file_path], shell=True)
            elif platform.system() == "Darwin":  # macOS
                subprocess.Popen(['open', file_path])
            else:  # Linux
                subprocess.Popen(['xdg-open', file_path])
            
            self.current_audio_index = index
            self.is_playing = True
            self.playback_started.emit(index)
            
        except Exception as e:
            self.playback_error.emit(f"系统播放器播放失败: {e}")
    
    def stop_audio(self):
        """停止播放"""
        if self.media_player and self.is_playing:
            self.media_player.stop()
        self.is_playing = False
        self.current_audio_index = -1
    
    def pause_audio(self):
        """暂停播放"""
        if self.media_player and self.is_playing:
            self.media_player.pause()
    
    def resume_audio(self):
        """恢复播放"""
        if self.media_player and not self.is_playing:
            self.media_player.play()
            self.is_playing = True
    
    def cleanup(self):
        """清理临时文件"""
        try:
            # 停止播放
            self.stop_audio()
            
            # 删除临时文件
            for temp_path in self.temp_files.values():
                if os.path.exists(temp_path):
                    os.remove(temp_path)
            
            self.temp_files.clear()
            
        except Exception as e:
            print(f"清理临时文件失败: {e}")


class SimpleAudioPlayer:
    """简化版音频播放器，不依赖Qt多媒体"""
    
    def __init__(self, sample_rate: int = 16000):
        self.sample_rate = sample_rate
        self.temp_files = {}
        
    def play_audio(self, audio_data: np.ndarray, index: int):
        """播放音频数据"""
        try:
            # 创建临时文件
            temp_fd, temp_path = tempfile.mkstemp(suffix='.wav', prefix=f'audio_{index}_')
            os.close(temp_fd)
            
            # 保存音频数据
            sf.write(temp_path, audio_data, self.sample_rate)
            
            # 使用系统播放器播放
            import subprocess
            import platform
            
            if platform.system() == "Windows":
                subprocess.Popen(['start', temp_path], shell=True)
            elif platform.system() == "Darwin":  # macOS
                subprocess.Popen(['open', temp_path])
            else:  # Linux
                subprocess.Popen(['xdg-open', temp_path])
            
            # 存储临时文件路径
            self.temp_files[index] = temp_path
            
            print(f"正在播放音频片段 {index}，长度: {len(audio_data)/self.sample_rate:.2f}秒")
            
            # 延迟删除临时文件
            threading.Timer(30.0, self._cleanup_file, args=[temp_path]).start()
            
        except Exception as e:
            print(f"播放音频失败: {e}")
    
    def _cleanup_file(self, file_path: str):
        """清理单个文件"""
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception as e:
            print(f"清理文件失败: {e}")
    
    def cleanup(self):
        """清理所有临时文件"""
        for temp_path in self.temp_files.values():
            self._cleanup_file(temp_path)
        self.temp_files.clear()
