from Config import LOG_FOLDER, initialize_config
import cProfile
import datetime
import io
import os
import pstats
import sys
import threading
import time
import traceback
from importlib import import_module

from PyQt5.QtCore import QPropertyAnimation, QEasingCurve, Qt, QThread, pyqtSignal
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QApplication, QDesktopWidget, QSizePolicy, QFrame, QVBoxLayout, QLabel
from qfluentwidgets import SplitFluentWindow, NavigationItemPosition
from qfluentwidgets import FluentIcon as FIF

from Service.ccTest import read_config
# 延迟导入重量级组件
# from Compoment.VideoPlayWidget import VideoPlayerWidget
# from ProjectCompoment.ProjectInterface import ProjectInterface
# from Service.dubbingMain.dubbingElevenLabs import dubbingElevenLabs
from Service.generalUtils import calculate_time
# from SubtitleInterface import SubtitleInterface
# from ToolsInterface import ToolsInterface
# from VoiceChangerInterface import VoiceChangerInterface

WIDGET_DEFINITIONS = {
    # 1: ("SubtitleInterface", "SubtitleInterface"),
    2: ("VoiceChangerInterface", "VoiceChangerInterface"),
    3: ("ToolsInterface", "ToolsInterface"),
    4: ("ProjectCompoment.ProjectInterface", "ProjectInterface"),
    5: ("AnnotationInterface", "AnnotationInterface"),
    6: ("DubbingInterface", "DubbingInterface"),
    7: ("SettingInterface", "SettingInterface"),
}

class WidgetRegistry:
    """Load-once registry for expensive widget modules."""
    _cache = {}
    _lock = threading.Lock()

    @classmethod
    def preload(cls, index):
        with cls._lock:
            if index in cls._cache:
                return cls._cache[index]
        module_path, attr_name = WIDGET_DEFINITIONS[index]
        module = import_module(module_path)
        widget_cls = getattr(module, attr_name)
        with cls._lock:
            cls._cache[index] = widget_cls
        return widget_cls

    @classmethod
    def ensure(cls, index):
        return cls.preload(index)

    @classmethod
    def is_ready(cls, index):
        with cls._lock:
            return index in cls._cache

    @classmethod
    def create_widget(cls, index):
        widget_cls = cls.ensure(index)
        return widget_cls()

class ModulePreloader(threading.Thread):
    """Background preloader that warms up heavy modules once."""
    def __init__(self, plan):
        super().__init__(daemon=True)
        self.plan = plan

    def run(self):
        for index in self.plan:
            try:
                WidgetRegistry.preload(index)
            except Exception as exc:
                print(f"模块预加载失败({index}): {exc}")

class LazyLoadThread(QThread):
    finished = pyqtSignal(int)

    def __init__(self, index):
        super().__init__()
        self.index = index

    def run(self):
        """在子线程中执行加载操作"""
        print("开始导入模块", time.time())
        WidgetRegistry.preload(self.index)
        self.finished.emit(self.index)

class placeholder_widget(QFrame):
    def __init__(self, name="", index=0, ):
        super().__init__()
        self.setObjectName(name)
        self.index = index
        layout = QVBoxLayout()
        self.label = QLabel("正在加载...")
        self.label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.label)
        layout.setContentsMargins(0,0,0,0)
        layout.setSpacing(0)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setLayout(layout)
        self.main_widget = None
        self.loading_thread = None

    def lazy_load(self):
        """启动异步加载"""
        if self.main_widget is not None:
            return
        if WidgetRegistry.is_ready(self.index):
            self._hydrate()
            return
        if self.loading_thread is not None:
            return
        print("触发延迟加载", self.objectName())
        self.loading_thread = LazyLoadThread(self.index)
        self.loading_thread.finished.connect(self.on_load_finished)
        self.loading_thread.start()

    def on_load_finished(self, index):
        """加载完成后的回调"""
        if index != self.index:
            return
        print("导入模块完成", time.time())
        self.loading_thread = None
        self._hydrate()

    def _hydrate(self):
        """将真实界面实例化并挂载到占位符上"""
        if self.main_widget is not None:
            return
        self.main_widget = WidgetRegistry.create_widget(self.index)
        self.label.hide()
        self.layout().addWidget(self.main_widget)


class Window(SplitFluentWindow):
    """ 主界面 """
    @calculate_time
    def __init__(self, capturer=None):
        super().__init__()
        
        print("进入")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.capturer = capturer
        
        # 延迟初始化配置
        initialize_config()
        
        self.initNavigation()
        self.initWindow()

    def initNavigation(self):
        self.navigationInterface.setExpandWidth(200)
        self.navigationInterface.setCollapsible(False)

        # 延迟初始化界面组件
        # self.SubtitleInterface = placeholder_widget("subtitle",1)
        self.ProjectInterface = placeholder_widget("project",4)
        # self.VoiceChangerInterface = placeholder_widget("changer",2)
        self.ToolsInterface = placeholder_widget("tools",3)
        self.AnnotationInterface = placeholder_widget("annotation",5)
        self.DubbingInterface = placeholder_widget("dubbing",6)
        self.SettingInterface = placeholder_widget("setting",7)

        # 先添加占位符，实际组件延迟创建
        self.addSubInterface(self.AnnotationInterface, FIF.TILES, '批量标注')
        self.addSubInterface(self.DubbingInterface, FIF.VIDEO, '批量配音')
        # self.addSubInterface(self.SubtitleInterface, FIF.HOME, 'AI配音')
        # self.addSubInterface(self.VoiceChangerInterface, FIF.MUSIC_FOLDER, 'AI声线转换')


        self.addSubInterface(self.ToolsInterface, FIF.CLIPPING_TOOL, '工具箱')
        self.navigationInterface.addSeparator()
        self.addSubInterface(self.ProjectInterface, FIF.HOME, '我的项目')

        self.addSubInterface(self.SettingInterface, FIF.SETTING, '设置', NavigationItemPosition.BOTTOM)

        self.stackedWidget.currentChanged.connect(self.pageSignal)
        self.stackedWidget.currentWidget().lazy_load()
        self._start_background_preload()

    def _start_background_preload(self):
        current = getattr(self.stackedWidget.currentWidget(), "index", None)
        plan = [idx for idx in WIDGET_DEFINITIONS if idx != current]
        if not plan:
            return
        self._module_preloader = ModulePreloader(plan)
        self._module_preloader.start()

    def pageSignal(self):
        print(self.stackedWidget.currentWidget())

        assert isinstance(self.stackedWidget.currentWidget(), placeholder_widget)
        # 延迟初始化组件
        self.stackedWidget.currentWidget().lazy_load()
        
        # if self.SubtitleInterface.main_widget and hasattr(self.SubtitleInterface.main_widget, 'video_player'):
        #     if self.SubtitleInterface.main_widget.video_player is not None:
        #         self.SubtitleInterface.main_widget.video_player.pause()

        # 回到该界面时，进行一次刷新
        if self.ProjectInterface.main_widget and self.stackedWidget.currentWidget() == self.ProjectInterface:
            self.ProjectInterface.main_widget.async_refresh()

        # 刷新voicedict
        # if self.DubbingInterface.main_widget and self.stackedWidget.currentWidget() == self.DubbingInterface:
        #     self.DubbingInterface.main_widget.update_voice_dict()

    def initWindow(self):
        self.setWindowIcon(QIcon(':/qfluentwidgets/images/logo.png'))
        self.setWindowTitle('AI-DubbingBox')
        
    #     # 延迟初始化ElevenLabs实例
    #     thread = threading.Thread(target=self._init_elevenlabs)
    #     thread.daemon = True  # 设置为守护线程
    #     thread.start()
    #
    # def _init_elevenlabs(self):
    #     """在后台线程中初始化ElevenLabs"""
    #     try:
    #         from Service.dubbingMain.dubbingElevenLabs import dubbingElevenLabs
    #         # dubbingElevenLabs.getInstance()
    #         print("ElevenLabs初始化完成")
    #     except Exception as e:
    #         print(f"ElevenLabs初始化失败: {e}")

    def show(self):
        # 创建淡入动画
        width = 1400
        height = 920
        screen = QDesktopWidget().screenGeometry()
        x = (screen.width() - width) // 2
        y = (screen.height() - height) // 2
        self.setGeometry(x, y, width, height)
        self.setWindowOpacity(0)  # 初始透明
        self.animation = QPropertyAnimation(self, b"windowOpacity")
        self.animation.setDuration(300)  # 动画时长（毫秒）
        self.animation.setStartValue(0)  # 起始透明度
        self.animation.setEndValue(1)  # 结束透明度
        self.animation.setEasingCurve(QEasingCurve.InOutQuad)  # 缓动曲线
        self.animation.start()
        super().show()

    def closeEvent(self, event):
        print("日志关闭流程")
        if self.capturer:
            filename = "output_"+datetime.datetime.now().strftime("%Y%m%d_%H%M%S")+".log"
            log_path = os.path.join(LOG_FOLDER, filename)
            with open(log_path, "w", encoding="utf-8") as f:
                f.write(self.capturer.get_log())
        super().closeEvent(event)



class StreamCapturer(io.StringIO):
    """捕获 print 输出的类"""
    def __init__(self, stream=sys.__stdout__):
        super().__init__()
        self.content = []
        self.terminal = stream

    def write(self, txt):
        self.content.append(txt)
        self.terminal.write(txt)
        super().write(txt)

    def flush(self):
        self.terminal.flush()

    def get_log(self):
        return ''.join(self.content)

def launch(enable_profiler=False):
    """启动主界面，可选启用性能分析。"""
    window = None
    profiler = cProfile.Profile() if enable_profiler else None
    try:
        print(time.time())

        my_capturer = StreamCapturer()
        sys.stdout = my_capturer
        sys.stderr = my_capturer

        if profiler:
            profiler.enable()
        print("app start")

        read_config()

        app = QApplication(sys.argv)
        window = Window(capturer=my_capturer)
        window.show()

        if profiler:
            profiler.disable()
            stats = pstats.Stats(profiler)
            stats.sort_stats("cumulative")
            stats.print_stats(20)
        app.exec()
        return 0
    except Exception as exc:
        print(f"发生错误: {str(exc)}")
        traceback.print_exc()
        if window is not None:
            window.close()
        input("按 Enter 键退出...")
        return 1


if __name__ == '__main__':
    sys.exit(launch(enable_profiler=True))
