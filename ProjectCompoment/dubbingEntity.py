
# def to_dict(obj):
#     """
#     将任意对象的字段转换为dict
#     """
#     if hasattr(obj, '__dict__'):
#         return {k: to_dict(v) for k, v in obj.__dict__.items()}
#     elif isinstance(obj, list):
#         return [to_dict(item) for item in obj]
#     elif isinstance(obj, dict):
#         return {k: to_dict(v) for k, v in obj.items()}
#     else:
#         return obj


class Project:
    def __init__(self, id: int = None, projectname: str = '', 
                 original_video_path: str = '', 
                 original_bgm_audio_path: str = '', 
                 original_voice_audio_path: str = '',
                 target_voice_audio_path: str = '',
                 target_dubbing_audio_path: str = '',
                 target_video_path: str = '',
                 update_time: str = '',):
        self.id = id  # 自增主键
        self.projectname = projectname  # 项目名称
        self.original_video_path = original_video_path  # 原视频路径（必须）
        self.original_bgm_audio_path = original_bgm_audio_path  # 原背景声音频路径（非必须）
        self.original_voice_audio_path = original_voice_audio_path  # 原人声音频路径（非必须）
        self.target_voice_audio_path = target_voice_audio_path  # 目标人声音频路径（必须）
        self.target_dubbing_audio_path = target_dubbing_audio_path  # 目标配音音频路径（必须）
        self.target_video_path = target_video_path  # 目标视频路径（必须）
        self.update_time = update_time


class Subtitle:
    def __init__(self, id: int = None, project_id: int = '',
                 original_subtitle: str = '',
                 target_subtitle: str = '',
                 start_time: str = '',
                 end_time: str = '',
                 dubbing_duration: int = 0,
                 role_name: str = '',
                 voice_id: str = '',
                 api_id: int = 0):  # 实际上没有0,0作为zeroshot的结果
        """
        1为elevenlab 2为minimax
        """
        self.id = id  # 自增主键
        self.project_id = project_id  # 外键，绑定project主键
        self.original_subtitle = original_subtitle  # 原句配音字幕（非必须）
        self.target_subtitle = target_subtitle  # 目标句配音字幕（必须）
        self.start_time = start_time  # 开始时间（必须，格式00:00:00:120）
        self.end_time = end_time  # 结束时间（非必须）
        self.dubbing_duration = dubbing_duration  # 配音时长（必须，单位毫秒）
        self.role_name = role_name   # 必须
        self.voice_id = voice_id # 非必须
        self.api_id = api_id  # 必须


if __name__ == '__main__':
    subtitle = Subtitle(project_id=1, original_subtitle="Hello", target_subtitle="你好", start_time="00:00:01:000", end_time="00:00:03:000", role_name="角色A")
    print(subtitle) 
    print(subtitle.__dict__)
