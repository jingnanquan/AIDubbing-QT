import sys

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPixmap, QImage
from PyQt5.QtWidgets import QWidget, QFrame, QVBoxLayout, QMessageBox, QApplication, QLabel, QPushButton, QScrollArea, QGridLayout
import os
from functools import lru_cache
from importlib import import_module

from UI.Ui_project import Ui_Project
from qfluentwidgets import SegmentedWidget

card_width = 240


@lru_cache(maxsize=None)
def _load_module(path: str):
    return import_module(path)


def _get_attr(module_path: str, attr_name: str):
    return getattr(_load_module(module_path), attr_name)



class ProjectInterface(QFrame, Ui_Project):
    def __init__(self, parent=None):
        super().__init__(parent)
        print("项目列表界面加载")
        self.setupUi(self)
        self.verticalLayout.setAlignment(Qt.AlignTop)
        self.container.setStyleSheet("#container { background: #f8f8f8; }")
        self.cards = []
        self.projects = []
        self.subtitleProjects = []
        self.current_project_type = "dubbing"  # 当前项目类型: dubbing 或 subtitle
        
        # --- 新增: 顶部导航栏 ---
        self.segmented_widget = SegmentedWidget(self)
        self.segmented_widget.addItem("配音项目", "配音项目", onClick=self.on_project_type_changed)
        self.segmented_widget.addItem("字幕标注项目", "字幕标注项目", onClick=self.on_project_type_changed)
        self.segmented_widget.setCurrentItem("配音项目")
        # self.segmented_widget.itemClicked.connect(self.on_project_type_changed)
        
        # 将导航栏添加到布局
        self.verticalLayout.insertWidget(2, self.segmented_widget)
        
        # --- 新增: 用 QScrollArea 包裹卡片区域 ---
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.containerLayout.addWidget(self.scroll_area, 1, 0)  # 注意行号改为1，因为导航栏占用了第0行

        # 卡片容器
        self.card_container = QWidget()
        self.card_container.setObjectName("card_container")
        self.grid_layout = QGridLayout(self.card_container)
        self.grid_layout.setContentsMargins(8, 8, 8, 8)
        self.grid_layout.setSpacing(32)
        self.grid_layout.setAlignment(Qt.AlignTop)  #
        self.scroll_area.setWidget(self.card_container)
        self.setStyleSheet("""
            QScrollArea{
                background: transparent;
            }
            #card_container{
                background: transparent;
            }
            """
        )
        self.async_refresh()

    def on_project_type_changed(self, item):
        """项目类型切换回调"""
        key =  self.segmented_widget.currentRouteKey()
        if key == "配音项目":
            self.current_project_type = "dubbing"
        elif key == "字幕标注项目":
            self.current_project_type = "subtitle"
        self.refresh_cache()

    def async_refresh(self):
        QTimer.singleShot(0, lambda: self.refresh())

    def refresh(self):
        """根据当前项目类型刷新显示"""
        # 清空现有卡片
        for i in reversed(range(self.grid_layout.count())):
            item = self.grid_layout.itemAt(i)
            if item:
                w = item.widget()
                self.grid_layout.removeWidget(w)
                if w:
                    w.deleteLater()

        dubbingDatasetUtils = _get_attr("ProjectCompoment.dubbingDatasetUtils", "dubbingDatasetUtils")
        self.projects = dubbingDatasetUtils.getInstance().get_all_projects()
        self.subtitleProjects = dubbingDatasetUtils.getInstance().get_all_subtitle_projects()
        print("刷新显示项目卡片")
        self.projects.reverse()
        self.subtitleProjects.reverse()
        # self.projects = self.projects
        self.cards = []
        if self.current_project_type == "dubbing":
            for project in self.projects:
                card = ProjectCard(project)
                self.cards.append(card)
                self.grid_layout.addWidget(card)
        elif self.current_project_type == "subtitle":
          for project in self.subtitleProjects:
                card = ProjectCard(project)
                self.cards.append(card)
                self.grid_layout.addWidget(card)
        self.relayout_cards()
        
    def refresh_cache(self):
        # 清空现有卡片
        for i in reversed(range(self.grid_layout.count())):
            item = self.grid_layout.itemAt(i)
            if item:
                w = item.widget()
                self.grid_layout.removeWidget(w)
                if w:
                    w.deleteLater()
        self.cards = []
        if self.current_project_type == "dubbing":
            for project in self.projects:
                card = ProjectCard(project)
                self.cards.append(card)
                self.grid_layout.addWidget(card)
        elif self.current_project_type == "subtitle":
            for project in self.subtitleProjects:
                card = ProjectCard(project)
                self.cards.append(card)
                self.grid_layout.addWidget(card)
        self.relayout_cards()


    def show_empty_state(self, message="暂无项目"):
        """显示空状态提示"""
        empty_label = QLabel(message)
        empty_label.setAlignment(Qt.AlignCenter)
        empty_label.setStyleSheet("""
            QLabel {
                color: #999;
                font-size: 16px;
                font-family: "Microsoft YaHei UI";
            }
        """)
        self.grid_layout.addWidget(empty_label, 0, 0, 1, 1, Qt.AlignCenter)


    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.relayout_cards()

    def relayout_cards(self):
        print("触发")
        # 固定卡片宽度
        # card_width = 280
        margin = 26
        viewport = self.scroll_area.viewport()
        if viewport is not None:
            area_width = viewport.width()
            if area_width < 300:
                area_width = self.width()-28
        else:
            area_width = self.width()-28

        print(area_width)
        if area_width < card_width + margin:
            cols = 1
        else:
            cols = max(1, area_width // (card_width + margin))
        # 清空布局
        for i in reversed(range(self.grid_layout.count())):
            item = self.grid_layout.itemAt(i)
            if item:
                w = item.widget()
                self.grid_layout.removeWidget(w)
                # if w:
                #     self.grid_layout.removeWidget(w)
        # 重新布局
        for idx, card in enumerate(self.cards):
            row = idx // cols
            col = idx % cols
            self.grid_layout.addWidget(card, row, col)

class ProjectCard(QFrame):
    def __init__(self, project, project_type="dubbing", parent=None):
        super().__init__(parent)
        self.setObjectName("ProjectCard")
        self.project = project
        self.project_type = project_type
        self.setStyleSheet("""
            ProjectCard {
                border-radius: 12px;
                background: #ffffff;
                border: 1px solid #ccc;
            }
            *{
                font-family: "Microsoft YaHei UI";
            }
        """)
        self.setAutoFillBackground(True)
        self.setFixedSize(card_width, 370)  # 固定卡片大小
        layout = QVBoxLayout(self)
        margin = 12
        layout.setContentsMargins(margin, margin, margin, margin)
        layout.setSpacing(2)
        # Project image
        self.image_label = QLabel(self)
        self.image_label.setFixedHeight(260)
        self.image_label.setScaledContents(True)

        if hasattr(project, "image_path") and project.image_path and os.path.exists(project.image_path):
            pixmap = QPixmap(project.image_path)
        elif hasattr(project, "original_video_path") and project.original_video_path and os.path.exists(project.original_video_path):
            pixmap = get_first_pixmap(project.original_video_path)
        else:
            pixmap = QPixmap(':/qfluentwidgets/images/logo.png')
            # pixmap.fill(Qt.gray)  # 这里后续修正
        
        self.image_label.setPixmap(pixmap)
        layout.addWidget(self.image_label)
        self.name_label = QLabel(getattr(project, "projectname", "未命名项目"), self)
        font = self.name_label.font()
        font.setPointSize(11)
        font.setBold(True)
        self.name_label.setFont(font)
        layout.addWidget(self.name_label)
        
        # 根据项目类型设置不同的按钮文本
        self.detail_btn = QPushButton("查看详情", self)
        if project_type == "subtitle":
            self.detail_btn.setText("标注字幕")
        self.detail_btn.setFixedHeight(28)
        
        # Timestamp
        timestamp = getattr(project, "update_time", "2025/01/01 00:00:00")
        self.time_label = QLabel(str(timestamp), self)
        font2 = self.time_label.font()
        font2.setPointSize(9)
        self.time_label.setFont(font2)
        self.time_label.setStyleSheet("color: #888;")
        layout.addWidget(self.time_label)
        layout.addWidget(self.detail_btn)

        self.detail_btn.clicked.connect(self.open_detail)
        self.detail_page = None

    def open_detail(self):
        """根据项目类型打开不同的详情页面"""
        self.loading_msg = QMessageBox(self)
        self.loading_msg.setWindowTitle("请稍候")
        
        if self.project_type == "dubbing":
            self.loading_msg.setText("正在加载配音室，请稍候...")
            self.loading_msg.show()
            QApplication.processEvents()
            
            from ProjectCompoment.CutStudioPage import CutStudioPage
            self.detail_page = CutStudioPage(self.project)
            self.loading_msg.hide()
            self.loading_msg.deleteLater()
            self.detail_page.show()
            
        elif self.project_type == "subtitle":
            self.loading_msg.setText("正在加载字幕标注界面，请稍候...")
            self.loading_msg.show()
            QApplication.processEvents()
            
            try:
                from AnnotationInterface import AnnotationInterface
                self.detail_page = AnnotationInterface(self.project)
                self.loading_msg.hide()
                self.loading_msg.deleteLater()
                self.detail_page.show()
            except ImportError:
                self.loading_msg.hide()
                self.loading_msg.deleteLater()
                QMessageBox.information(self, "提示", "字幕标注功能开发中...")





def get_first_pixmap(video_url: str):
    """获取视频的第一帧图片"""
    cv2 = _load_module("cv2")
    cap = cv2.VideoCapture(video_url)
    
    if not cap.isOpened():
        print("无法打开视频")
        return
    
    # 读取第一帧
    ret, frame = cap.read()
    cap.release()
    
    if not ret:
        print("无法读取视频帧")
        return
    
    # 将 OpenCV 图像转换为 QImage
    height, width, channel = frame.shape
    bytes_per_line = 3 * width
    q_img = QImage(frame.data, width, height, bytes_per_line, QImage.Format_RGB888).rgbSwapped()
    
    # 转换为 QPixmap 并设置到 QLabel
    return QPixmap.fromImage(q_img)



if __name__ == '__main__':
    app = QApplication(sys.argv)
    ui = ProjectInterface()
    ui.show()
    sys.exit(app.exec_())