import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# ffmpeg_dir = os.path.join(BASE_DIR, "Service\\ffmpeg-7.1.1-essentials_build\\bin")
# os.environ['PATH'] = ffmpeg_dir + os.pathsep + os.environ.get('PATH', '')

# 延迟设置PATH，避免启动时的环境变量操作
def _setup_ffmpeg_path():
    pass
    # if ffmpeg_dir not in os.environ.get('PATH', ''):
    #     os.environ['PATH'] = ffmpeg_dir + os.pathsep + os.environ.get('PATH', '')

# 基础路径定义
VIDEO_UPLOAD_FOLDER = os.path.join(BASE_DIR, "OutputFolder\\project_video")
SUBTITLE_UPLOAD_FOLDER = os.path.join(BASE_DIR, "OutputFolder\\project_subtitle")
RESULT_OUTPUT_FOLDER = os.path.join(BASE_DIR, "OutputFolder\\project_result")
AUDIO_SEPARATION_FOLDER = os.path.join(BASE_DIR, "OutputFolder\\audio_separation")
CHANGER_RESULT_OUTPUT_FOLDER = os.path.join(BASE_DIR, "OutputFolder\\changer_result")
PROMPT_AUDIO_FOLDER = os.path.join(BASE_DIR, "OutputFolder\\prompt_audio")
LOG_FOLDER = os.path.join(BASE_DIR, "OutputFolder\\LOG")
ROLE_ANNO_FOLDER = os.path.join(BASE_DIR, "OutputFolder\\role_annotation")
resource_path = os.path.join(BASE_DIR, "Resource")

# 延迟创建文件夹的函数
def _ensure_folders_exist():
    """延迟创建必要的文件夹，只在需要时调用"""
    folders = [
        VIDEO_UPLOAD_FOLDER,
        SUBTITLE_UPLOAD_FOLDER,
        RESULT_OUTPUT_FOLDER,
        AUDIO_SEPARATION_FOLDER,
        CHANGER_RESULT_OUTPUT_FOLDER,
        PROMPT_AUDIO_FOLDER,
        LOG_FOLDER,
        ROLE_ANNO_FOLDER
    ]
    
    for folder in folders:
        if not os.path.exists(folder):
            os.makedirs(folder, exist_ok=True)

# 配置常量
tolerate_factor = [250, 1.2]
env = "dev"
http_url = "http://119.28.203.239:8081/"
cosyvoice_url = "http://127.0.0.1:8081/"

# 初始化函数，在需要时调用
def initialize_config():
    """初始化配置，包括ffmpeg路径和文件夹创建"""
    _setup_ffmpeg_path()
    _ensure_folders_exist()



