import sys

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPixmap, QImage
from PyQt5.QtWidgets import QWidget, QFrame, QVBoxLayout, QMessageBox, QApplication, QLabel, QPushButton, QScrollArea, QGridLayout
import os
from functools import lru_cache
from importlib import import_module

from UI.Ui_project import Ui_Project

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

        # --- 新增: 用 QScrollArea 包裹卡片区域 ---
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.containerLayout.addWidget(self.scroll_area, 0, 0)

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

    def async_refresh(self):
        QTimer.singleShot(0, lambda: self.refresh())

    def refresh(self):
        dubbingDatasetUtils = _get_attr("ProjectCompoment.dubbingDatasetUtils", "dubbingDatasetUtils")
        self.projects = dubbingDatasetUtils.getInstance().get_all_projects()
        print("刷新显示项目卡片")
        self.projects.reverse()
        self.projects = self.projects
        self.cards = []
        for project in self.projects:
            card = ProjectCard(project)
            self.cards.append(card)
            self.grid_layout.addWidget(card)
        self.relayout_cards()


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
    def __init__(self, project, parent=None):
        super().__init__(parent)
        self.setObjectName("ProjectCard")
        self.project = project
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
        self.detail_btn = QPushButton("查看详情", self)
        self.detail_btn.setFixedHeight(28)
        # layout.addLayout(row)
        # Timestamp
        timestamp = getattr(project, "update_time", "2025/01/01 00:00:00")
        self.time_label = QLabel(str(timestamp), self)
        font2 = self.time_label.font()
        font2.setPointSize(9)
        self.time_label.setFont(font2)
        self.time_label.setStyleSheet("color: #888;")
        layout.addWidget(self.time_label)
        layout.addWidget(self.detail_btn)

        self.detail_btn.clicked.connect(self.open_dubbing_cut)
        self.cutStudioPage = None

    def open_dubbing_cut(self):
        self.loading_msg = QMessageBox(self)
        self.loading_msg.setWindowTitle("请稍候")
        self.loading_msg.setText("正在加载配音室，请稍候...")
        self.loading_msg.setStandardButtons(QMessageBox.NoButton)
        self.loading_msg.setModal(False)
        self.loading_msg.show()
        QApplication.processEvents()

        from ProjectCompoment.CutStudioPage import CutStudioPage
        self.cutStudioPage = CutStudioPage(self.project)
        self.loading_msg.hide()
        self.loading_msg.deleteLater()
        self.cutStudioPage.show()



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