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

from PyQt5.QtCore import QPropertyAnimation, QEasingCurve, Qt, QThread, pyqtSignal
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QApplication, QDesktopWidget, QSizePolicy, QFrame, QVBoxLayout, QLabel
from qfluentwidgets import SplitFluentWindow
from qfluentwidgets import FluentIcon as FIF

# 延迟导入重量级组件
# from Compoment.VideoPlayWidget import VideoPlayerWidget
# from ProjectCompoment.ProjectInterface import ProjectInterface
# from Service.dubbingMain.dubbingElevenLabs import dubbingElevenLabs
from Service.generalUtils import calculate_time
# from SubtitleInterface import SubtitleInterface
# from ToolsInterface import ToolsInterface
# from VoiceChangerInterface import VoiceChangerInterface

class LazyLoadThread(QThread):
    finished = pyqtSignal(bool)  # 信号，传递加载完成的widget

    def __init__(self, index):
        super().__init__()
        self.index = index

    def run(self):
        """在子线程中执行加载操作"""
        print("开始导入模块", time.time())
        if self.index == 1:
            from SubtitleInterface import SubtitleInterface
        elif self.index == 2:
            from VoiceChangerInterface import VoiceChangerInterface
        elif self.index == 3:
            from ToolsInterface import ToolsInterface
        elif self.index == 4:
            from ProjectCompoment.ProjectInterface import ProjectInterface
        elif self.index == 5:
            from AnnotationInterface import AnnotationInterface
        elif self.index == 6:
            from DubbingInterface import DubbingInterface
        self.finished.emit(True)

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
        if self.main_widget is None and self.loading_thread is None:
            print("触发延迟加载", self.objectName())
            self.loading_thread = LazyLoadThread(self.index)
            self.loading_thread.finished.connect(self.on_load_finished)
            self.loading_thread.start()

    def on_load_finished(self):
        """加载完成后的回调"""
        print("导入模块完成", time.time())
        if self.index == 1:
            from SubtitleInterface import SubtitleInterface
            self.main_widget = SubtitleInterface()
        elif self.index == 2:
            from VoiceChangerInterface import VoiceChangerInterface
            self.main_widget = VoiceChangerInterface()
        elif self.index == 3:
            from ToolsInterface import ToolsInterface
            self.main_widget = ToolsInterface()
        elif self.index == 4:
            from ProjectCompoment.ProjectInterface import ProjectInterface
            self.main_widget = ProjectInterface()
        elif self.index == 5:
            from AnnotationInterface import AnnotationInterface
            self.main_widget = AnnotationInterface()
        elif self.index == 6:
            from DubbingInterface import DubbingInterface
            self.main_widget = DubbingInterface()

        self.label.hide()
        self.layout().addWidget(self.main_widget)

    # def lazy_load(self):
    #     if self.main_widget is None:
    #         print("触发延迟加载", self.objectName())
    #         if self.index == 1:
    #             from SubtitleInterface import SubtitleInterface
    #             self.main_widget = SubtitleInterface()
    #         elif self.index == 2:
    #             from VoiceChangerInterface import VoiceChangerInterface
    #             self.main_widget = VoiceChangerInterface()
    #         elif self.index == 3:
    #             from ToolsInterface import ToolsInterface
    #             self.main_widget = ToolsInterface()
    #         elif self.index == 4:
    #             from ProjectCompoment.ProjectInterface import ProjectInterface
    #             self.main_widget = ProjectInterface()
    #         self.label.hide()
    #         self.layout().addWidget(self.main_widget)


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
        self.SubtitleInterface = placeholder_widget("subtitle",1)
        self.ProjectInterface = placeholder_widget("project",4)
        self.VoiceChangerInterface = placeholder_widget("changer",2)
        self.ToolsInterface = placeholder_widget("tools",3)
        self.AnnotationInterface = placeholder_widget("annotation",5)
        self.DubbingInterface = placeholder_widget("dubbing",6)

        # 先添加占位符，实际组件延迟创建
        self.addSubInterface(self.AnnotationInterface, FIF.TILES, '批量标注')
        self.addSubInterface(self.DubbingInterface, FIF.VIDEO, '批量配音')
        self.addSubInterface(self.SubtitleInterface, FIF.HOME, 'AI配音')
        self.addSubInterface(self.VoiceChangerInterface, FIF.MUSIC_FOLDER, 'AI声线转换')


        self.addSubInterface(self.ToolsInterface, FIF.CLIPPING_TOOL, '工具箱')
        self.navigationInterface.addSeparator()
        self.addSubInterface(self.ProjectInterface, FIF.HOME, '我的项目')
        self.stackedWidget.currentChanged.connect(self.pageSignal)
        self.stackedWidget.currentWidget().lazy_load()

    def _create_placeholder_widget(self, name=""):
        """创建占位符组件"""
        from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout
        from PyQt5.QtCore import Qt
        
        widget = QWidget()
        widget.setObjectName(name)
        layout = QVBoxLayout()
        label = QLabel("正在加载...")
        label.setAlignment(Qt.AlignCenter)
        layout.addWidget(label)
        widget.setLayout(layout)
        return widget

    def pageSignal(self):
        print(self.stackedWidget.currentWidget())

        assert isinstance(self.stackedWidget.currentWidget(), placeholder_widget)
        # 延迟初始化组件
        self.stackedWidget.currentWidget().lazy_load()
        
        if self.SubtitleInterface.main_widget and hasattr(self.SubtitleInterface.main_widget, 'video_player'):
            if self.SubtitleInterface.main_widget.video_player is not None:
                self.SubtitleInterface.main_widget.video_player.pause()
            # from Compoment.VideoPlayWidget import VideoPlayerWidget
            # if isinstance(self.SubtitleInterface.main_widget.video_player, VideoPlayerWidget):
            #     self.SubtitleInterface.main_widget.video_player.pause()

        # 回到该界面时，进行一次刷新
        if self.ProjectInterface.main_widget and self.stackedWidget.currentWidget() == self.ProjectInterface:
            self.ProjectInterface.main_widget.async_refresh()

        # 刷新voicedict
        if self.DubbingInterface.main_widget and self.stackedWidget.currentWidget() == self.DubbingInterface:
            self.DubbingInterface.main_widget.update_voice_dict()

    def initWindow(self):
        self.setWindowIcon(QIcon(':/qfluentwidgets/images/logo.png'))
        self.setWindowTitle('AI-DubbingBox')
        
        # 延迟初始化ElevenLabs实例
        thread = threading.Thread(target=self._init_elevenlabs)
        thread.daemon = True  # 设置为守护线程
        thread.start()

    def _init_elevenlabs(self):
        """在后台线程中初始化ElevenLabs"""
        try:
            from Service.dubbingMain.dubbingElevenLabs import dubbingElevenLabs
            from SubtitleInterface import SubtitleInterface
            # dubbingElevenLabs.getInstance()
            print("ElevenLabs初始化完成")
        except Exception as e:
            print(f"ElevenLabs初始化失败: {e}")

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



def run1():
    w = None
    try:
        print(time.time())

        myCapturer = StreamCapturer()
        sys.stdout = myCapturer
        sys.stderr = myCapturer

        profiler = cProfile.Profile()
        profiler.enable()
        print("app start")
        # setTheme(Theme.DARK)

        app = QApplication(sys.argv)
        w = Window(capturer=myCapturer)
        w.show()

        profiler.disable()
        stats = pstats.Stats(profiler)
        stats.sort_stats("cumulative")  # 按总耗时排序
        stats.print_stats(20)  # 打印前20个耗时最多的函
        app.exec()
    except Exception as e:
        print(f"发生错误: {str(e)}")
        traceback.print_exc()  # 打印完整的错误堆栈
        if w is not None:
            w.close()
        input("按 Enter 键退出...")  # 暂停等待用户输入
        sys.exit(1)

if __name__ == '__main__':
    w = None
    try:
        print(time.time())
        
        myCapturer = StreamCapturer()
        sys.stdout = myCapturer
        sys.stderr = myCapturer

        profiler = cProfile.Profile()
        profiler.enable()
        print("app start")
        # setTheme(Theme.DARK)

        app = QApplication(sys.argv)
        w = Window(capturer=myCapturer)
        w.show()
        
        profiler.disable()
        stats = pstats.Stats(profiler)
        stats.sort_stats("cumulative")  # 按总耗时排序
        stats.print_stats(20)  # 打印前20个耗时最多的函
        app.exec()
    except Exception as e:
        print(f"发生错误: {str(e)}")
        traceback.print_exc()  # 打印完整的错误堆栈
        if w is not None:
            w.close()
        input("按 Enter 键退出...")  # 暂停等待用户输入
        sys.exit(1)
