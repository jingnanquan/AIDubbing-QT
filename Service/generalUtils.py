import os
import re
import time

from PyQt5.QtWidgets import QMessageBox
from pypinyin import lazy_pinyin

from Config import RESULT_OUTPUT_FOLDER


def calculate_time(func):
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        print(f"{func.__name__} 执行时间: {end_time - start_time} 秒")
        return result

    return wrapper

def get_result_path(filename):
    return os.path.join(RESULT_OUTPUT_FOLDER, filename)


def time_str_to_ms(time_str: str) -> int:
    """
    将SRT时间格式 (00:00:00,150) 转换为毫秒
    :param time_str: 时间字符串，格式 HH:MM:SS,mmm
    :return: 毫秒数
    """
    # 使用正则表达式解析时间
    match = re.match(r'(\d{2}):(\d{2}):(\d{2}),(\d{3})', time_str)
    if not match:
        raise ValueError(f"无效的时间格式: {time_str}")
    hours, minutes, seconds, milliseconds = map(int, match.groups())
    return int((hours * 3600 + minutes * 60 + seconds) * 1000 + milliseconds)

def ms_to_time_str(ms: int) -> str:
    """
    ms -> 00:00:01,000
    """
    h = ms // 3600000
    ms = ms % 3600000
    m = ms // 60000
    ms = ms % 60000
    s = ms // 1000
    ms = ms % 1000
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def check_close_permission(cls):
    """
    类装饰器，为窗口类添加关闭检查功能
    """
    original_closeEvent = cls.closeEvent if hasattr(cls, 'closeEvent') else lambda self, event: event.accept()

    def new_closeEvent(self, event):
        print("注解成功")
        if hasattr(self, 'allow_close') and not self.allow_close:
            QMessageBox.information(self, "提示", "任务进行中，请勿关闭窗口。")
            event.ignore()
        else:
            original_closeEvent(self, event)

    cls.closeEvent = new_closeEvent
    return cls

def mixed_sort_key_cast(s):
    parts = []
    for char in s:
        if '\u4e00' <= char <= '\u9fff':  # 中文字符
            parts.append(''.join(lazy_pinyin(char)))
        else:  # 非中文字符（字母、数字等）
            parts.append(char.lower())
    return ''.join(parts)


def mixed_sort_key(s):
    def convert_text(text):
        # 处理中文字符转换为拼音
        converted = []
        for char in text:
            if '\u4e00' <= char <= '\u9fff':  # 中文字符
                converted.append(''.join(lazy_pinyin(char)))
            else:  # 非中文字符
                converted.append(char.lower())
        return ''.join(converted)

    def convert_part(part):
        # 尝试将部分转换为数字，如果不能转换则返回原始字符串
        try:
            return int(part)
        except ValueError:
            return convert_text(part)

    # 将字符串拆分为字母和数字部分
    parts = re.split('([0-9]+)', s)
    # 对每个部分进行适当转换
    return [convert_part(part) for part in parts]



