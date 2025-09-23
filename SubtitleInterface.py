import copy
import sys

from PyQt5.QtCore import Qt, QPropertyAnimation, QPoint, QTimer
from PyQt5.QtGui import QStandardItemModel, QStandardItem
from PyQt5.QtWidgets import QWidget, QFileDialog, QFrame, QVBoxLayout, \
    QInputDialog, QMessageBox, QMenu, QApplication, QSizePolicy
import os

from Compoment.DeleteVoiceParamsWindow import DeleteVoiceParamsWindow
from Compoment.DubbingParamWindows import CosyDubbingParamsWindow, DubbingParamsWindow, DirectedDubbingParamsWindow
from Compoment.DubbingParamWindows2 import ElevenDubbingParamsWindow2
from Compoment.ExtractRolesParamWindows import ExtractRolesParamsWindow

from Compoment.SubtitleListItem import SubtitleListItem
from Service.videoUtils import is_video_file
from ThreadWorker.SubtitleInterfaceWorker import ExportRolesWorker
from Compoment.VideoPlayWidget import VideoPlayerWidget
from Compoment.VoiceChangerParamWindows import VoiceChangerParamsWindow
from Service.generalUtils import time_str_to_ms
from UI.Ui_subtitle2 import Ui_Subtitle
from Service.subtitleUtils import is_srt_file, get_srt_files_in_folder, parse_subtitle_uncertain
from Config import env



class SubtitleInterface(Ui_Subtitle, QFrame):


    def __init__(self, parent=None):
        super().__init__()
        print("配音子界面加载")
        self.setupUi(self)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.subtitlePaths = []
        self.subtitles = []
        self.role_match_list = []
        self.video_player = None
        self.video_file = ""
        self.subtitle_text = ""
        self.subtitle_file_name = ""
        self.roles_model = QStandardItemModel()
        self.roles_model.appendRow(QStandardItem("default"))

        # 初始化字幕滚动列表和角色列表
        self._setup_unfinished_ui()
        self._update_RoleListWidget()
        self.setAcceptDrops(True)

        # 绑定事件
        self.AddSubBtn.clicked.connect(self.select_subtitle_file)      # 上传字幕文件
        self.AddVideoBtn.clicked.connect(self.select_video_file)       # 上传视频文件
        self.AddRoleBtn.clicked.connect(self.add_role_list)            # 添加角色
        self.AutoMarkBtn.clicked.connect(self.set_extract_params)      # 自动标注角色
        self.AIDubbingBtn.clicked.connect(self.set_dubbing_params)     # AI配音
        self.AIDirectedBtn.clicked.connect(self.set_directed_dubbing_params)   # AI直接配音（无需原始字幕，无需克隆）
        self.AIVoiceBtn.clicked.connect(self.set_video_voice_changer_params)  # 视频声线转换
        self.CosyDubbingBtn.clicked.connect(self.set_cosy_dubbing_params)
        self.OutputRoleBtn.clicked.connect(self.export_role_list)      # 导出角色列表
        self.ImportRoleBtn.clicked.connect(self.import_role_list)      # 导入角色列表
        self.PullVoiceBtn.clicked.connect(self.pull_eleven_voice)             # 拉取声音列表
        self.DelVoiceBtn.clicked.connect(self.set_delete_voice_params)
        self.ElevenDubbingBtn.clicked.connect(self.set_eleven_dubbing_params2)  # ElevenLabs端到端配音, 只生成配音，不管视频
        
        self.SubListWidget.itemClicked.connect(self.show_subtitle_list)
        self.RoleListWidget.itemClicked.connect(self.modify_role_list)
        self.RoleListWidget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.RoleListWidget.customContextMenuRequested.connect(self.show_role_context_menu)


        self.now_path = os.path.dirname(os.path.abspath(__file__))
        test_path = os.path.join(self.now_path,"1-中_test.srt")

        try:
            if env=="dev" and os.path.exists(test_path):
                self.subtitlePaths.append(test_path)
                self.SubListWidget.addItem(os.path.basename(self.subtitlePaths[0]))

                self.subtitlePaths.append(os.path.join(self.now_path,"1-英_test.srt"))
                self.SubListWidget.addItem(os.path.basename(self.subtitlePaths[1]))
                self.subtitlePaths.append(os.path.join(self.now_path,"1-中.srt"))
                self.SubListWidget.addItem(os.path.basename(self.subtitlePaths[2]))
                self.subtitlePaths.append(os.path.join(self.now_path,"1-英.srt"))
                self.SubListWidget.addItem(os.path.basename(self.subtitlePaths[3]))
                self.import_role_list(os.path.join(self.now_path,"1-中-角色表-固定.txt"))

                QTimer.singleShot(1000, lambda: self.select_video_file(os.path.join(self.now_path, "a视频_test.mp4")))
        except Exception as e:
            pass

    def _init_video_player(self):
        # 初始化视频播放器
        self.CustomVideoWidget.setLayout(QVBoxLayout())
        self.CustomVideoWidget.layout().setContentsMargins(0, 0, 0, 0)
        self.CustomVideoWidget.layout().setSizeConstraint(QVBoxLayout.SetDefaultConstraint)

        self.video_player = VideoPlayerWidget(self.CustomVideoWidget)
        self.CustomVideoWidget.layout().addWidget(self.video_player)

        self.video_player.bar_slide.connect(self._update_SubScroll)


    def set_video_voice_changer_params(self):
        print(self.subtitlePaths, self.video_file)
        if not self.subtitlePaths or not self.video_file:
            QMessageBox.information(self, "提示", "请先导入字幕和视频！")
            return
        items = self.findChildren(SubtitleListItem)
        if not items:
            QMessageBox.information(self, "提示", "请先标注角色列表！")
            return
        video_duration = self.video_player.mediaPlayer.duration()
        self.video_player.pause()
        subtitle_duration = time_str_to_ms(items[-1].end)
        if subtitle_duration> video_duration:
            QMessageBox.warning(self, "提示", "字幕与视频不匹配！")
            return
        role_match_list = []
        for item in items:
            role_match_list.append(item.roles.currentText())
        # 创建参数窗口, 需要self持有这个窗体，否则会被清除
        self.params_window = VoiceChangerParamsWindow(self.subtitlePaths, role_match_list, self.DubbingSelector.currentIndex() + 1, self.video_file, video_duration)
        self.params_window.setWindowModality(Qt.ApplicationModal)
        self.params_window.show()  # 显示

    def set_cosy_dubbing_params(self):
        print(self.subtitlePaths, self.video_file)
        if not self.subtitlePaths or not self.video_file:
            QMessageBox.information(self, "提示", "请先导入字幕和视频！")
            return
        items = self.findChildren(SubtitleListItem)
        if not items:
            QMessageBox.information(self, "提示", "请先标注角色列表！")
            return
        video_duration = self.video_player.mediaPlayer.duration()
        self.video_player.pause()
        subtitle_duration = time_str_to_ms(items[-1].end)
        if subtitle_duration> video_duration:
            QMessageBox.warning(self, "提示", "字幕与视频不匹配！")
            return
        role_match_list = []
        for item in items:
            role_match_list.append(item.roles.currentText())
        # 创建参数窗口, 需要self持有这个窗体，否则会被清除
        self.params_window = CosyDubbingParamsWindow(self.subtitlePaths, role_match_list, self.DubbingSelector.currentIndex() + 1, self.video_file, video_duration)
        self.params_window.setWindowModality(Qt.ApplicationModal)
        self.params_window.show()  # 显示

    def set_dubbing_params(self):
        print(self.subtitlePaths, self.video_file)
        if not self.subtitlePaths or not self.video_file:
            QMessageBox.information(self, "提示", "请先导入字幕和视频！")
            return
        items = self.findChildren(SubtitleListItem)
        if not items:
            QMessageBox.information(self, "提示", "请先标注角色列表！")
            return
        video_duration = self.video_player.mediaPlayer.duration()
        self.video_player.pause()
        subtitle_duration = time_str_to_ms(items[-1].end)
        if subtitle_duration> video_duration:
            QMessageBox.warning(self, "提示", "字幕与视频不匹配！")
            return

        role_match_list = []
        for item in items:
            role_match_list.append(item.roles.currentText())
        # 创建参数窗口, 需要self持有这个窗体，否则会被清除
        self.params_window = DubbingParamsWindow(self.subtitlePaths, role_match_list, self.DubbingSelector.currentIndex() + 1, self.video_file, video_duration)
        self.params_window.setWindowModality(Qt.ApplicationModal)
        self.params_window.show()  # 显示

    def set_directed_dubbing_params(self):
        print(self.subtitlePaths, self.video_file)
        if not self.subtitlePaths or not self.video_file:
            QMessageBox.information(self, "提示", "请先导入字幕和视频！")
            return
        items = self.findChildren(SubtitleListItem)
        if not items:
            QMessageBox.information(self, "提示", "请先标注角色列表！")
            return
        video_duration = self.video_player.mediaPlayer.duration()
        self.video_player.pause()
        subtitle_duration = time_str_to_ms(items[-1].end)
        if subtitle_duration> video_duration:
            QMessageBox.warning(self, "提示", "字幕与视频不匹配！")
            return
        role_match_list = []
        for item in items:
            role_match_list.append(item.roles.currentText())
        # 创建参数窗口, 需要self持有这个窗体，否则会被清除
        self.params_window = DirectedDubbingParamsWindow(self.subtitlePaths, role_match_list, self.DubbingSelector.currentIndex() + 1,  self.video_file, video_duration)
        self.params_window.setWindowModality(Qt.ApplicationModal)
        self.params_window.show()  # 显示

    def set_extract_params(self):
        print(self.subtitlePaths, self.video_file)
        if not self.subtitlePaths or not self.video_file:
            QMessageBox.information(self, "提示", "请先导入字幕和视频！")
            return
        items = self.findChildren(SubtitleListItem)
        if not items:
            QMessageBox.information(self, "提示", "请先打开待标注字幕！")
            return
        video_duration = self.video_player.mediaPlayer.duration()
        self.video_player.pause()
        subtitle_duration = time_str_to_ms(items[-1].end)
        if subtitle_duration> video_duration:
            QMessageBox.warning(self, "提示", "字幕与视频不匹配！")
            return
        role_match_list = []
        for item in items:
            role_match_list.append(item.roles.currentText())
        # 创建参数窗口, 需要self持有这个窗体，否则会被清除
        self.params_window = ExtractRolesParamsWindow(self.subtitle_file_name,  self.video_file)
        self.params_window.pass_result.connect(self.on_role_match_finished)  # 连接信号
        self.params_window.setWindowModality(Qt.ApplicationModal)
        self.params_window.show()  # 显示

    def set_eleven_dubbing_params2(self):
        print(self.subtitlePaths, self.video_file)
        if not self.subtitlePaths or not self.video_file:
            QMessageBox.information(self, "提示", "请先导入字幕和视频！")
            return
        items = self.findChildren(SubtitleListItem)
        if not items:
            QMessageBox.information(self, "提示", "请先标注角色列表！")
            return
        video_duration = self.video_player.mediaPlayer.duration()
        self.video_player.pause()
        subtitle_duration = time_str_to_ms(items[-1].end)
        if subtitle_duration> video_duration:
            QMessageBox.warning(self, "提示", "字幕与视频不匹配！")
            return
        role_match_list = []
        for item in items:
            role_match_list.append(item.roles.currentText())
        self.params_window = ElevenDubbingParamsWindow2(self.subtitle_file_name, role_match_list, self.video_file)
        self.params_window.setWindowModality(Qt.ApplicationModal)
        self.params_window.show()  # 显示

    def set_delete_voice_params(self):
        self.params_window = DeleteVoiceParamsWindow()
        self.params_window.setWindowModality(Qt.ApplicationModal)
        self.params_window.show()  # 显示


    def on_role_match_finished(self, role_match_list: list):
        self.role_match_list = copy.deepcopy(role_match_list)
        self.role_set = set(self.role_match_list)   # 更新外部角色表
        for role in self.role_set:
            if self._isin_role_list(role):
                continue
            self.roles_model.appendRow(QStandardItem(role))

        self._update_RoleListWidget()
        items = self.findChildren(SubtitleListItem)
        for i in range(len(self.role_match_list)):
            item = items[i]
            if item is not None:
                item.roles.setCurrentText(self.role_match_list[i])

    def select_video_file(self, video_file=""):
        try:
            if not video_file:
                self.video_file, _ = QFileDialog.getOpenFileName(self, "Select File", "", "Video Files (*.mp4 *.avi *.mov *.mkv *.flv *.wmv *.mpeg *.mpg *.webm);;All Files (*)")
            else:
                self.video_file = video_file

            print(self.video_file)
            if self.video_file:
                # 只有再用到的时候，才初始化
                if not self.video_player:
                    self._init_video_player()
                self.video_player.open_file(self.video_file)
        except Exception as e:
            print(e)
            QMessageBox.warning(self, "提示", str(e))

    def _update_RoleListWidget(self):
        self.RoleListWidget.clear()
        for row in range(self.roles_model.rowCount()):
            self.RoleListWidget.addItem(self.roles_model.item(row).text())

    def _setup_unfinished_ui(self):
        self.DubbingAISet =  ['ElevenLabs', 'Minimax', 'ElevenLabs端到端']
        self.DubbingSelector.addItems(self.DubbingAISet)

        self.SubScroll.setWidgetResizable(True)  # 允许内部控件自适应
        self.SubScroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.SubListContainer = QWidget()
        self.SubListContainer.setObjectName("SubtitleCardContainer")

        self.container_layout = QVBoxLayout()
        self.container_layout.setAlignment(Qt.AlignTop)  # 内容顶部对齐
        self.SubListContainer.setLayout(self.container_layout)
        # 将容器添加到滚动区域
        self.SubScroll.setWidget(self.SubListContainer)
        self.SubScroll.setStyleSheet(""" #SubScroll{ border: 1px solid #ccc; background: transparent; } #SubtitleCardContainer{ background: transparent; } """)


    def select_subtitle_file(self):
        # Open file dialog to select a file
        file_names, _ = QFileDialog.getOpenFileNames(self, "Select File", "", "字幕 (*.srt)")  # 限制了只允许srt

        for file_name in file_names:
            self.subtitlePaths.append(file_name)
            self.SubListWidget.addItem(os.path.basename(file_name))
            print(self.subtitlePaths)

    def show_subtitle_list(self, item):
        # 获取被点击项的行号（从 0 开始）
        row = self.SubListWidget.row(item)
        print(f"点击了第 {row} 行，内容: {item.text()}")
        print(self.subtitlePaths[row])
        self.subtitles, new_role_list = parse_subtitle_uncertain(self.subtitlePaths[row])
        if not self.subtitles:
            QMessageBox.warning(self, "错误", "字幕文件内容错误！")
            return
        self.subtitle_file_name = self.subtitlePaths[row]
        items = self.findChildren(SubtitleListItem)

        if new_role_list:
            for item in items:
                item.deleteLater()
            self.role_match_list = copy.deepcopy(new_role_list)
            self.role_set = set(self.role_match_list)  # 更新外部角色表
            for role in self.role_set:
                if self._isin_role_list(role):
                    continue
                self.roles_model.appendRow(QStandardItem(role))
            self._update_RoleListWidget()
        else:
            i = 0
            for item in items:
                self.role_match_list[i] = item.roles.currentText()
                item.deleteLater()
                i += 1
        print(self.subtitles)
        for subtitle in self.subtitles:
            item = SubtitleListItem(subtitle, self.roles_model)
            index = subtitle["index"]-1
            if index< len(self.role_match_list):
                item.roles.setCurrentText(self.role_match_list[index])
            else:
                self.role_match_list.append(self.roles_model.item(0).text())
            self.container_layout.addWidget(item)


    def _update_SubScroll(self, msec: list):
        if self.subtitles:
            index = 0
            items = self.findChildren(SubtitleListItem)
            for item in items:
                if time_str_to_ms(item.start) >= msec[0]:
                    index = items.index(item)+1
                    break
            if index==0:
                index = len(items)
            if index > 3:   # index等于4才会滚动
                vbar = self.SubScroll.verticalScrollBar()
                # 垂直滚动条的范围
                # vmin = vbar.minimum()
                vmax = vbar.maximum()
                offset = int(((len(items)-index)*9)/len(items))
                offset2 = int(offset/2)
                offset -=3
                # print(offset)
                animation = QPropertyAnimation(vbar, b"value", self)
                animation.setDuration(100)  # 动画持续时间（毫秒）
                animation.setStartValue(vbar.value())  # 起始值
                animation.setEndValue(((index-offset2)*vmax)/(len(items)+offset))  # 目标值
                animation.start()
            else:
                vbar = self.SubScroll.verticalScrollBar()
                animation = QPropertyAnimation(vbar, b"value", self)
                animation.setDuration(100)  # 动画持续时间（毫秒）
                animation.setStartValue(vbar.value())  # 起始值
                animation.setEndValue(0)  # 目标值
                animation.start()

    def _isin_role_list(self, role_name: str):
        for row in range(self.roles_model.rowCount()):
            if self.roles_model.item(row).text() == role_name:
                return True
        return False


    def modify_role_list(self, item):
        new_text, ok = QInputDialog.getText(self, "编辑项", "修改文本:", text=item.text())
        row = self.RoleListWidget.row(item)
        if self._isin_role_list(new_text):
            QMessageBox.information(self, "提示", "角色已存在！")
            return
        if ok and new_text:
            item.setText(new_text)
            self.roles_model.item(row).setText(new_text)

    def add_role_list(self):
        new_text, ok = QInputDialog.getText(self, "编辑项", "添加角色:", text="")
        if self._isin_role_list(new_text):
            QMessageBox.information(self, "提示", "角色已存在！")
            return
        if ok and new_text:
            self.roles_model.appendRow(QStandardItem(new_text))
            self._update_RoleListWidget()



    def import_role_list(self, file_name=""):
        if not file_name:
            file_name, _ = QFileDialog.getOpenFileName(self, "Select File", "", "字幕角色表 (*.txt)")
        try:
            if file_name:
                with open(file_name, "r", encoding="utf-8") as f:
                    role_match_list = f.read().split(";")
                    items = self.findChildren(SubtitleListItem)
                    print(len(role_match_list))
                    print(len(items))
                    if len(role_match_list)< len(items):
                        raise Exception("角色表错误！")
                    self.role_match_list = copy.deepcopy(role_match_list)  # 你已经导入了，所以就是这样
                    self.role_set = set(role_match_list)
                    for role in self.role_set:
                        if self._isin_role_list(role):
                            continue
                        self.roles_model.appendRow(QStandardItem(role))
                    self._update_RoleListWidget()
                    for i in range(len(items)):  # 如果有，则直接标注上去，如果无则，则后续选择的时候可以进行标注
                        item = items[i]
                        if item is not None:
                            item.roles.setCurrentText(self.role_match_list[i])
        except  Exception as e:
            print(e)
            QMessageBox.warning(self, "警告", "角色表错误！")

    def export_role_list(self):
        items = self.findChildren(SubtitleListItem)
        if not items:
            QMessageBox.information(self, "提示", "请先标注并校验角色！")
            return
        folder = QFileDialog.getExistingDirectory(
            self,
            "选择导出文件夹",
            "",  # 从当前目录开始
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )
        if folder:
            role_match_list = []
            for item in items:
                role_match_list.append(item.roles.currentText())
            self.worker = ExportRolesWorker(self.subtitle_file_name, folder, role_match_list)
            self.worker.finished.connect(self.on_general_task_finished)
            self.worker.start()

    def show_role_context_menu(self,  pos: QPoint):
        print("右键点击")
        # 将局部坐标转为全局坐标（用于 menu 显示位置）
        global_pos = self.RoleListWidget.viewport().mapToGlobal(pos)

        # 获取右键点击处的 item（可选）
        item = self.RoleListWidget.itemAt(pos)
        if item is None:
            return  # 没有点击到任何 item，直接返回

        # 创建菜单
        menu = QMenu()
        action2 = menu.addAction("删除")

        action = menu.exec_(global_pos)  # 弹出菜单并等待选择

        if action == action2:
            index = self.RoleListWidget.row(item)
            self.RoleListWidget.takeItem(index)
            self.roles_model.removeRow(index)


    def dragEnterEvent(self, event):
        super().dragEnterEvent(event)
        if event.mimeData().hasUrls():
            decide_url = event.mimeData().urls()[0].toLocalFile()
            if is_video_file(decide_url):
                self.CustomVideoWidget.setStyleSheet("""#CustomVideoWidget{
                    background-color: #F8F8F8;
                    border: 2px dashed #a1bbd7;
                }""")
            else:
                self.SubListBox.setStyleSheet("""#SubListBox{
                        background-color: #F8F8F8;
                        border: 2px dashed #a1bbd7;
                }""")
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        super().dragLeaveEvent(event)
        self.SubListBox.setStyleSheet("""#SubListBox{border: 1px solid #ccc;}""")
        self.CustomVideoWidget.setStyleSheet("""#CustomVideoWidget{border: 1px solid #ccc;}""")

    def dropEvent(self, event):
        super().dropEvent(event)
        pos = event.pos()
        self.SubListBox.setStyleSheet("""#SubListBox{border: 1px solid #ccc;}""")
        self.CustomVideoWidget.setStyleSheet("""#CustomVideoWidget{border: 1px solid #ccc;}""")
        if self.SubListBox.geometry().contains(pos):
            print("Drop into srt")

            urls = event.mimeData().urls()
            paths = [url.toLocalFile() for url in urls]
            print(paths)

            srt_paths = []
            for path in paths:
                if os.path.isdir(path):
                    srt_paths.extend(get_srt_files_in_folder(path))
                elif is_srt_file(path):
                    srt_paths.append(path)

            for file_name in srt_paths:
                self.subtitlePaths.append(file_name)
                self.SubListWidget.addItem(os.path.basename(file_name))
                print(self.subtitlePaths)

        if self.CustomVideoWidget.geometry().contains(pos):
            print("Drop into video")
            print(event.mimeData().urls())
            decide_url = event.mimeData().urls()[0].toLocalFile()
            if is_video_file(decide_url):
                print(decide_url)
                self.select_video_file(decide_url)


    def pull_eleven_voice(self):
        from ThreadWorker.SubtitleInterfaceWorker import PullVoiceWorker
        reply = QMessageBox.question(
            self,  # 父窗口
            "拉取提示",  # 标题
            "此操作将拉取并更新elevenlabs上克隆的语音!",  # 提示文本
            QMessageBox.Yes | QMessageBox.Cancel,  # 按钮选项
        )
        print(reply)
        if reply==QMessageBox.Yes:
            print("开始拉取")
            # # 是否根据角色提示列表进行标记
            self.worker = PullVoiceWorker()
            self.worker.finished.connect(self.on_general_task_finished)
            self.worker.start()

    def on_general_task_finished(self, msg):
        print(msg)
        QMessageBox.information(self, "提示", msg)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = SubtitleInterface()
    window.show()
    sys.exit(app.exec_())




