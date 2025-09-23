import copy
import datetime
import re
import sys
from threading import Thread
import traceback

from PyQt5.QtCore import Qt, QPropertyAnimation, QThread, QPoint, QTimer, QTimeLine
from PyQt5.QtGui import QPixmap, QStandardItemModel, QStandardItem, QImage, QIcon
from PyQt5.QtWidgets import QWidget, QFileDialog, QFrame, QVBoxLayout, \
    QInputDialog, QMessageBox, QSizePolicy, QMenu, QApplication, QMainWindow, QTableWidget, QTableWidgetItem, \
    QHeaderView, QScrollArea
import os

from Compoment.VideoPlayWidget import VideoPlayerWidget
from ProjectCompoment.hiscode.QTimeBarArea3 import TimeBarArea
from ProjectCompoment.hiscode.TrackWidget3 import TrackWidget
from ProjectCompoment.dubbingDatasetUtils import dubbingDatasetUtils
from ProjectCompoment.dubbingEntity import Project
from Service.generalUtils import time_str_to_ms
from UI.Ui_cut2 import Ui_Cut
from PyQt5.QtGui import QFont


class CutStudioPage(QMainWindow, Ui_Cut):


    def __init__(self, project: Project , parent=None ):
        super().__init__(parent)
        print("配音演播室加载")
        self.setupUi(self)
        self.AutoMarkBtn.clicked.connect(lambda: print("自动标注角色"))
        self.project = copy.deepcopy(project)
        print(self.project.__dict__)
        self.setWindowTitle(self.project.projectname+"演播室")
        self.setWindowIcon(QIcon(':/qfluentwidgets/images/logo.png'))
        self.subtitles = dubbingDatasetUtils.getInstance().get_subtitles_by_project_id(self.project.id)

        # self.subtitles = self.subtitles
        for item in self.subtitles:
            print(item.__dict__)

        self.video_player = None
        self.table = None
        if self.project.target_video_path:
            self.select_video_file(self.project.target_video_path)
        self.setup_unfinished_ui()
        QTimer.singleShot(10, lambda: self.fill_SubScroll())


    def setup_unfinished_ui(self):
        self.trackFrame.setFixedHeight(250)

        # 字幕滚动区域
        self.SubScroll.setWidgetResizable(True)  # 允许内部控件自适应
        self.SubScroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.SubListContainer = QWidget()
        self.SubListContainer.setObjectName("SubtitleCardContainer")
        # self.container.setFixedWidth(280)  # 宽度略小于滚动区域以避免水平滚动条
        self.SubListLayout = QVBoxLayout()
        self.SubListLayout.setAlignment(Qt.AlignTop)  # 内容顶部对齐
        self.SubListContainer.setLayout(self.SubListLayout)
        # 将容器添加到滚动区域
        self.SubScroll.setWidget(self.SubListContainer)
        self.SubScroll.setStyleSheet(
            """ #SubScroll{ border: 1px solid #ccc; background: transparent; } #SubtitleCardContainer{ background: transparent; } """)

        # 初始化轨道时间轴
        self.trackFrameLayout = QVBoxLayout()
        self.trackFrameLayout.setContentsMargins(0, 0, 0, 0)
        self.trackFrameLayout.setSpacing(0)
        self.trackFrame.setLayout(self.trackFrameLayout)
        self.TrackScroll = QScrollArea()
        self.TrackScroll.setFrameShape(QFrame.NoFrame)
        self.TrackScroll.setStyleSheet("")
        self.TrackScroll.setWidgetResizable(True)
        self.TrackScroll.setObjectName("TrackScroll")
        self.TrackContainer = QWidget()
        self.TrackContainer.setObjectName("TrackContainer")
        self.TrackScroll.setWidget(self.TrackContainer)
        self.trackFrameLayout.addWidget(self.TrackScroll)
        self.TrackContainerLayout = QVBoxLayout(self.TrackContainer)
        self.TrackContainerLayout.setContentsMargins(0, 0, 0, 0)
        self.TrackContainerLayout.setSpacing(0)
        self.TrackScroll.installEventFilter(self)

    def eventFilter(self, obj, event):
        if obj == self.TrackScroll and event.type() == event.Wheel:
            print("滚动")
            delta = event.angleDelta().y()
            scroll_bar = self.TrackScroll.horizontalScrollBar()
            step = scroll_bar.singleStep() * 5  # 可调整步长
            if delta < 0:
                scroll_bar.setValue(scroll_bar.value() + step)
            else:
                scroll_bar.setValue(scroll_bar.value() - step)
            return True
        return super().eventFilter(obj, event)


    def init_track_compoment(self, total_ms: int):
        init_scale = 80
        self.total_ms = total_ms
        print("时间轴长度：", self.total_ms)
        self.trackScaleSlider.setValue(init_scale)
        if self.project:  # self.subtitle没有就当是[]
            self.TrackWidget = TrackWidget(self.total_ms, init_scale=init_scale, subtitles=self.subtitles,
                                           project=self.project)
            self.TrackWidget = TimeBarArea(300, init_scale)
            self.TrackContainerLayout.addWidget(self.TrackWidget)

            self.trackScaleSlider.valueChanged.connect(self.TrackWidget.on_scale_changed)
            # self.trackScaleSlider.sliderReleased.connect(self.TrackWidget.repaint_wave)
            self.TrackWidget.positionChanged.connect(self.change_position)


    def change_position(self, pos: int):
        # # 获取当前缩放比例和总时长
        # scale = self.TrackWidget.timebar.scale if hasattr(self.TrackWidget.timebar, "scale") else 100
        # total_ms = self.TrackWidget.timebar.total_ms if hasattr(self.TrackWidget.timebar, "total_ms") else 30000
        # # 计算总宽度
        # total_width = self.TrackWidget.timebar.width() if hasattr(self.TrackWidget.timebar,
        #                                                           "width") else self.TrackWidget.width()
        # 计算当前指针在track上的像素位置
        pointer_x = pos
        # 获取可见区域宽度
        viewport_width = self.TrackScroll.viewport().width()
        # 计算指针相对可见区域的位置
        scroll_x = self.TrackScroll.horizontalScrollBar().value()
        pointer_in_view = pointer_x - scroll_x
        # 判断是否需要滚动
        if pointer_in_view > viewport_width * 0.75:
            # 向后滚动
            new_scroll = pointer_x - int(viewport_width * 0.75)
            self.TrackScroll.horizontalScrollBar().setValue(new_scroll)
        elif pointer_in_view < viewport_width * 0.25:
            # 向前滚动
            new_scroll = pointer_x - int(viewport_width * 0.25)
            if new_scroll < 0:
                new_scroll = 0
            self.TrackScroll.horizontalScrollBar().setValue(new_scroll)


    def fill_SubScroll(self):
        """
        self.subtitles为Subtitle类的对象列表
        在SubListLayout中添加一个QTableWidget。
        QTableWidget的每列字段需要从Subtitle这个实体的属性中动态加载，即Subtitle字段可能会增加或减少。
        设置origin_subtitle和target_subtitle的列宽分别占layoutview宽度的25%，支持换行显示
        """
        if self.table:
            self.SubListLayout.removeWidget(self.table)
            self.table.deleteLater()
            self.table = None
            print("删除旧的table")
        if not self.subtitles or len(self.subtitles) == 0:
            return

        subtitle_obj = self.subtitles[0]
        columns = [k for k in vars(subtitle_obj).keys() if not k.startswith('__') and not callable(getattr(subtitle_obj, k))]
        columns = columns[2:]  # 不需要id和project
        columns.remove("api_id")
        columns.remove("voice_id")
        print(columns)

        self.table = QTableWidget()
        self.table.setColumnCount(len(columns))
        self.table.setRowCount(len(self.subtitles))
        self.table.setHorizontalHeaderLabels(columns)

        font = QFont()
        font.setPointSize(10)
        bold_font = QFont()
        bold_font.setPointSize(10)
        bold_font.setBold(True)

        self.table.setFont(font)
        self.table.verticalHeader().setFixedWidth(30)

        self.table.setStyleSheet("""
            QTableWidget::item {
                padding-left: 8px;
            }
        """)

        for row, subtitle in enumerate(self.subtitles):
            for col, field in enumerate(columns):
                value = getattr(subtitle, field, "")
                item = QTableWidgetItem(str(value))
                # 支持换行显示
                item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                item.setData(Qt.DisplayRole, str(value))
                item.setToolTip(str(value))
                item.setWhatsThis(str(value))
                item.setText(str(value))
                if field == "start_time" or field == "end_time":
                    item.setFont(bold_font)
                self.table.setItem(row, col, item)

        self.table.resizeColumnsToContents()
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)  # 不可编辑


        # 设置origin_subtitle和target_subtitle的列宽分别占layoutview宽度的25%，支持换行显示
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table.setWordWrap(True)

        # 获取父容器宽度
        parent_width = self.SubScroll.viewport().width() if self.SubScroll.viewport() else 800
        print(parent_width)
        if parent_width<200:
            parent_width = self.MP4Box_2.width()
            print("重新计算", parent_width)
        print(self.width())
        parent_width = parent_width - 30
        origin_idx = columns.index("original_subtitle") if "original_subtitle" in columns else -1
        target_idx = columns.index("target_subtitle") if "target_subtitle" in columns else -1

        for idx in range(len(columns)):
            if idx == origin_idx or idx == target_idx:
                self.table.setColumnWidth(idx, int(parent_width * 0.25))
            # else:
            #     self.table.setColumnWidth(idx, int((parent_width * 0.5) / (len(columns) - 2)) if len(columns) > 2 else int(parent_width * 0.5))
        # 让表格高度自适应内容
        self.table.resizeRowsToContents()
        self.SubListLayout.addWidget(self.table)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.fill_SubScroll()

    def init_video_player(self):
        # 初始化视频播放器
        self.CustomVideoLayout.setLayout(QVBoxLayout())
        self.CustomVideoLayout.layout().setContentsMargins(0, 0, 0, 0)
        self.video_player = VideoPlayerWidget(self.CustomVideoLayout)
        self.CustomVideoLayout.layout().addWidget(self.video_player)
        self.video_player.bar_slide.connect(self.update_SubScroll)
        self.video_player.duration_get.connect(self.init_track_compoment)

    def select_video_file(self, video_file=""):
        try:
            if not video_file:
                self.video_file, _ = QFileDialog.getOpenFileName(self, "Select File", self.subtitleLastDir,
                                                                 "Video Files (*.mp4 *.avi *.mov *.mkv *.flv *.wmv *.mpeg *.mpg *.webm);;All Files (*)")
            else:
                self.video_file = video_file
            print(self.video_file)
            if self.video_file:
                # 只有再用到的时候，才初始化
                if not self.video_player:
                    self.init_video_player()
                self.video_player.open_file(self.video_file)
        except Exception as e:
            print(e)
            QMessageBox.warning(self, "提示", str(e))

    def update_SubScroll(self, msec: list):
        pass



if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = CutStudioPage(dubbingDatasetUtils.getInstance().get_project_by_id(9))
    window.show()
    sys.exit(app.exec_())

