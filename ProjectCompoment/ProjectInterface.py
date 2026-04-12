import sys
import time
import os
from functools import lru_cache
from importlib import import_module

from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal, QUrl
from PyQt5.QtGui import QPixmap, QImage, QDesktopServices
from PyQt5.QtWidgets import (QWidget, QFrame, QVBoxLayout, QMessageBox,
                             QApplication, QLabel, QPushButton, QScrollArea,
                             QGridLayout, QHBoxLayout)
from qfluentwidgets import SegmentedWidget, ProgressRing, HyperlinkButton

from UI.Ui_project import Ui_Project

card_width = 240


@lru_cache(maxsize=None)
def _load_module(path: str):
    return import_module(path)


def _get_attr(module_path: str, attr_name: str):
    return getattr(_load_module(module_path), attr_name)


class LoadProjectsThread(QThread):
    """后台加载项目数据的线程"""
    dubbing_loaded = pyqtSignal(list, str)  # 信号：配音项目加载完成
    subtitle_loaded = pyqtSignal(list, str)  # 信号：字幕项目加载完成
    error_occurred = pyqtSignal(str)  # 信号：错误信息

    def __init__(self, project_type="dubbing"):
        super().__init__()
        self.project_type = project_type
        self.should_stop = False

    def run(self):
        """在后台线程中执行耗时的数据加载"""
        try:
            # 短暂延迟，防止频繁切换
            time.sleep(0.05)

            if self.should_stop:
                return

            dubbingDatasetUtils = _get_attr("ProjectCompoment.dubbingDatasetUtils", "dubbingDatasetUtils")

            if self.project_type == "dubbing":
                projects = dubbingDatasetUtils.getInstance().get_all_projects()
                projects.reverse()  # 在后台线程中反转
                if not self.should_stop:
                    self.dubbing_loaded.emit(projects, self.project_type)
            else:  # subtitle
                projects = dubbingDatasetUtils.getInstance().get_all_subtitle_projects()
                projects.reverse()
                if not self.should_stop:
                    self.subtitle_loaded.emit(projects, self.project_type)

        except Exception as e:
            if not self.should_stop:
                self.error_occurred.emit(str(e))

    def stop(self):
        """安全停止线程"""
        self.should_stop = True
        if self.isRunning():
            self.terminate()
            self.wait()


@lru_cache(maxsize=20)
def get_first_pixmap(video_url: str):
    """获取视频的第一帧图片（带缓存）"""
    try:
        cv2 = _load_module("cv2")
        cap = cv2.VideoCapture(video_url)

        if not cap.isOpened():
            return QPixmap(':/qfluentwidgets/images/logo.png')

        # 读取第一帧
        ret, frame = cap.read()
        cap.release()

        if not ret:
            return QPixmap(':/qfluentwidgets/images/logo.png')

        # 将 OpenCV 图像转换为 QImage
        height, width, channel = frame.shape
        bytes_per_line = 3 * width
        q_img = QImage(frame.data, width, height, bytes_per_line, QImage.Format_RGB888).rgbSwapped()

        # 转换为 QPixmap
        return QPixmap.fromImage(q_img)

    except Exception as e:
        print(f"获取视频帧失败: {e}")
        return QPixmap(':/qfluentwidgets/images/logo.png')


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

        # 缓存标志
        self.dubbing_data_loaded = False
        self.subtitle_data_loaded = False

        # 加载线程
        self.load_thread = None
        self.last_switch_time = 0

        # 防抖定时器
        self.switch_debounce_timer = QTimer()
        self.switch_debounce_timer.setSingleShot(True)
        self.switch_debounce_timer.timeout.connect(self._perform_switch)

        # --- 顶部导航栏 ---
        self.segmented_widget = SegmentedWidget(self)
        self.segmented_widget.addItem("配音项目", "配音项目", onClick=self.on_project_type_changed)
        self.segmented_widget.addItem("字幕标注项目", "字幕标注项目", onClick=self.on_project_type_changed)
        self.segmented_widget.setCurrentItem("配音项目")

        # 将导航栏添加到布局
        self.verticalLayout.insertWidget(2, self.segmented_widget)

        # --- 用 QScrollArea 包裹卡片区域 ---
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.containerLayout.addWidget(self.scroll_area, 1, 0)

        # 卡片容器
        self.card_container = QWidget()
        self.card_container.setObjectName("card_container")
        self.grid_layout = QGridLayout(self.card_container)
        self.grid_layout.setContentsMargins(8, 8, 8, 8)
        self.grid_layout.setSpacing(32)
        self.grid_layout.setAlignment(Qt.AlignTop)
        self.scroll_area.setWidget(self.card_container)

        # 加载动画
        self.loading_widget = QWidget(self.card_container)
        self.loading_widget.hide()
        loading_layout = QVBoxLayout(self.loading_widget)
        loading_layout.setAlignment(Qt.AlignCenter)

        self.loading_label = QLabel("加载中...")
        self.loading_label.setAlignment(Qt.AlignCenter)
        self.loading_label.setStyleSheet("font-size: 14px; color: #666; margin-bottom: 10px;")

        self.progress_ring = ProgressRing(self.loading_widget)
        self.progress_ring.setFixedSize(40, 40)

        loading_layout.addWidget(self.progress_ring)
        loading_layout.addWidget(self.loading_label)

        self.setStyleSheet("""
            QScrollArea{
                background: transparent;
            }
            #card_container{
                background: transparent;
            }
            #loading_widget {
                background: rgba(255, 255, 255, 0.9);
                border-radius: 8px;
            }
        """)

        # 调整定时器
        self._resize_timer = QTimer()
        self._resize_timer.setSingleShot(True)

        # 异步加载初始数据
        QTimer.singleShot(100, self.load_initial_data)

    def load_initial_data(self):
        """异步加载初始数据"""
        self.show_loading_animation(True, "加载配音项目...")
        self.load_projects_in_background("dubbing")

    def on_project_type_changed(self, item):
        """项目类型切换回调（防抖处理）"""
        current_time = int(time.time() * 1000)  # 毫秒时间戳

        # 300ms内只处理最后一次点击
        if current_time - self.last_switch_time < 300:
            self.switch_debounce_timer.stop()

        self.last_switch_time = current_time
        self.switch_debounce_timer.start(300)  # 300ms防抖

    def _perform_switch(self):
        """实际执行切换操作"""
        key = self.segmented_widget.currentRouteKey()
        project_type = "dubbing" if key == "配音项目" else "subtitle"

        print("触发重加载")

        if self.current_project_type == project_type:
            return

        self.current_project_type = project_type
        self.show_loading_animation(True, f"加载{self.get_project_type_name()}...")

        # 检查缓存
        if (project_type == "dubbing" and self.dubbing_data_loaded) or \
                (project_type == "subtitle" and self.subtitle_data_loaded):
            # 有缓存，短暂延迟后显示
            QTimer.singleShot(50, self.display_cached_projects)
        else:
            # 无缓存，后台加载
            self.load_projects_in_background(project_type)

    def get_project_type_name(self):
        """获取项目类型名称"""
        return "配音项目" if self.current_project_type == "dubbing" else "字幕标注项目"

    def show_loading_animation(self, show=True, message="加载中..."):
        """显示/隐藏加载动画"""
        if show:
            self.loading_label.setText(message)
            # self.progress_ring.start()

            # 设置加载动画位置和大小
            container_rect = self.card_container.rect()
            self.loading_widget.setGeometry(
                container_rect.center().x() - 100,
                container_rect.center().y() - 100,
                200, 120
            )
            self.loading_widget.raise_()
            self.loading_widget.show()
        else:
            # self.progress_ring.stop()
            self.loading_widget.hide()

    def load_projects_in_background(self, project_type):
        """后台加载项目数据"""
        # 停止之前的线程
        if self.load_thread and self.load_thread.isRunning():
            self.load_thread.stop()

        # 创建新线程
        self.load_thread = LoadProjectsThread(project_type)

        if project_type == "dubbing":
            self.load_thread.dubbing_loaded.connect(self.on_dubbing_loaded)
        else:
            self.load_thread.subtitle_loaded.connect(self.on_subtitle_loaded)

        self.load_thread.error_occurred.connect(self.on_load_error)
        self.load_thread.start()

    def on_dubbing_loaded(self, projects, project_type):
        """配音项目加载完成"""
        if self.current_project_type != "dubbing":
            return

        self.projects = projects
        self.dubbing_data_loaded = True
        self.display_cards(projects, project_type)

    def on_subtitle_loaded(self, projects, project_type):
        """字幕项目加载完成"""
        if self.current_project_type != "subtitle":
            return

        self.subtitleProjects = projects
        self.subtitle_data_loaded = True
        self.display_cards(projects, project_type)

    def on_load_error(self, error_msg):
        """加载错误处理"""
        self.show_loading_animation(False)
        QMessageBox.warning(self, "加载失败", f"加载项目失败:\n{error_msg}")

    def display_cached_projects(self):
        """显示缓存的项目"""
        if self.current_project_type == "dubbing":
            projects = self.projects
        else:
            projects = self.subtitleProjects

        if not projects:
            self.clear_cards()
            self.show_empty_state("暂无项目")
            self.show_loading_animation(False)
            return

        self.display_cards(projects, self.current_project_type)

    def display_cards(self, projects, project_type):
        """显示项目卡片"""
        # 清空现有卡片
        self.clear_cards()

        if not projects:
            self.show_empty_state("暂无项目")
            self.show_loading_animation(False)
            return

        # 分批创建卡片
        self.create_cards_batch(projects, project_type, batch_size=8)

    def clear_cards(self):
        """清空卡片（优化版）"""
        # 隐藏所有卡片
        for card in self.cards:
            card.hide()
            card.deleteLater()

        self.cards.clear()

        # 清空布局
        for i in reversed(range(self.grid_layout.count())):
            item = self.grid_layout.itemAt(i)
            if item and item.widget():
                widget = item.widget()
                widget.hide()
                self.grid_layout.removeWidget(widget)
                widget.deleteLater()

        QApplication.processEvents()  # 处理事件队列

    def create_cards_batch(self, projects, project_type, batch_size=8, start_index=0):
        """分批创建卡片"""
        if start_index >= len(projects):
            # 所有卡片创建完成
            self.relayout_cards()
            self.show_loading_animation(False)
            return

        end_index = min(start_index + batch_size, len(projects))

        def create_current_batch():
            for i in range(start_index, end_index):
                project = projects[i]
                card = ProjectCard(project, project_type)
                self.cards.append(card)
                self.grid_layout.addWidget(card)
                card.setVisible(True)

            # 短暂延时后创建下一批
            if end_index < len(projects):
                QTimer.singleShot(20, lambda: self.create_cards_batch(
                    projects, project_type, batch_size, end_index
                ))
            else:
                # 所有卡片创建完成
                self.relayout_cards()
                self.show_loading_animation(False)

        # 创建当前批次
        create_current_batch()

    def show_empty_state(self, message="暂无项目"):
        """显示空状态提示"""
        empty_widget = QWidget(self.card_container)
        empty_widget.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(empty_widget)
        layout.setAlignment(Qt.AlignCenter)

        empty_label = QLabel(message)
        empty_label.setAlignment(Qt.AlignCenter)
        empty_label.setStyleSheet("""
            QLabel {
                color: #999;
                font-size: 16px;
                font-family: "Microsoft YaHei UI";
                padding: 20px;
            }
        """)

        layout.addWidget(empty_label)
        self.grid_layout.addWidget(empty_widget, 0, 0, 1, 1, Qt.AlignCenter)

    def refresh(self):
        """刷新数据"""
        if self.current_project_type == "dubbing":
            self.dubbing_data_loaded = False
        else:
            self.subtitle_data_loaded = False

        self.show_loading_animation(True, f"刷新{self.get_project_type_name()}...")
        self.load_projects_in_background(self.current_project_type)

    def refresh_cache(self):
        """刷新缓存显示"""
        if self.current_project_type == "dubbing":
            projects = self.projects
        else:
            projects = self.subtitleProjects

        if projects:
            self.display_cards(projects, self.current_project_type)
        else:
            self.show_empty_state("暂无项目")
            self.show_loading_animation(False)

    def resizeEvent(self, event):
        super().resizeEvent(event)

        # 更新加载动画位置
        if self.loading_widget.isVisible():
            container_rect = self.card_container.rect()
            self.loading_widget.setGeometry(
                container_rect.center().x() - 100,
                container_rect.center().y() - 100,
                200, 120
            )

        # 延迟重布局
        self._resize_timer.stop()
        self._resize_timer.timeout.connect(self.relayout_cards)
        self._resize_timer.start(150)

    def relayout_cards(self):
        """重新布局卡片"""
        if not self.cards:
            return

        # 计算列数
        margin = 26
        viewport = self.scroll_area.viewport()

        if viewport is not None:
            area_width = viewport.width()
            if area_width < 300:
                area_width = self.width() - 28
        else:
            area_width = self.width() - 28

        if area_width < card_width + margin:
            cols = 1
        else:
            cols = max(1, (area_width + margin) // (card_width + margin))

        # 清空布局但不删除widget
        for i in reversed(range(self.grid_layout.count())):
            item = self.grid_layout.itemAt(i)
            if item and item.widget():
                self.grid_layout.removeWidget(item.widget())

        # 重新布局
        for idx, card in enumerate(self.cards):
            if card.isVisible():
                row = idx // cols
                col = idx % cols
                self.grid_layout.addWidget(card, row, col, Qt.AlignTop)


class ProjectCard(QFrame):
    def __init__(self, project, project_type="dubbing", parent=None):
        super().__init__(parent)
        self.setObjectName("ProjectCard")
        self.project = project
        self.project_type = project_type
        self.image_loaded = False

        self.setStyleSheet("""
            ProjectCard {
                border-radius: 12px;
                background: #ffffff;
                border: 1px solid #e0e0e0;
            }
            *{
                font-family: "Microsoft YaHei UI";
            }
            #detail_btn {
                background: #0078d4;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 6px 12px;
            }
            #detail_btn:hover {
                background: #106ebe;
            }
            #detail_btn:pressed {
                background: #005a9e;
            }
            #open_folder_btn {
                background: #f0f0f0;
                color: #666;
                border: 1px solid #ddd;
                border-radius: 6px;
                padding: 6px 12px;
            }
            #open_folder_btn:hover {
                background: #e8e8e8;
                border-color: #ccc;
            }
            #open_folder_btn:pressed {
                background: #e0e0e0;
            }
        """)

        self.setAutoFillBackground(True)
        self.setFixedSize(card_width, 370)

        layout = QVBoxLayout(self)
        margin = 12
        layout.setContentsMargins(margin, margin, margin, margin)
        layout.setSpacing(8)

        # 项目图片
        self.image_label = QLabel(self)
        self.image_label.setFixedHeight(260)
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setStyleSheet("""
            QLabel {
                background: #f5f5f5;
                border-radius: 8px;
            }
        """)

        # 设置占位图
        placeholder_pixmap = QPixmap(':/qfluentwidgets/images/logo.png')
        if not placeholder_pixmap.isNull():
            self.image_label.setPixmap(placeholder_pixmap.scaled(
                200, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation
            ))

        layout.addWidget(self.image_label)

        # 项目名称
        self.name_label = QLabel(getattr(project, "projectname", "未命名项目"), self)
        font = self.name_label.font()
        font.setPointSize(11)
        font.setBold(True)
        self.name_label.setFont(font)
        self.name_label.setStyleSheet("color: #333;")
        layout.addWidget(self.name_label)

        # 时间戳
        timestamp = getattr(project, "update_time", "2025/01/01 00:00:00")
        self.time_label = QLabel(str(timestamp), self)
        font2 = self.time_label.font()
        font2.setPointSize(9)
        self.time_label.setFont(font2)
        self.time_label.setStyleSheet("color: #888;")
        layout.addWidget(self.time_label)

        # 按钮布局
        button_layout = QHBoxLayout()
        button_layout.setSpacing(8)

        # 打开文件夹按钮
        self.open_folder_btn = QPushButton("📁", self)
        self.open_folder_btn.setObjectName("open_folder_btn")
        self.open_folder_btn.setFixedSize(48, 32)  # 设置固定大小，比detail_btn小
        self.open_folder_btn.setToolTip("打开文件夹")
        self.open_folder_btn.clicked.connect(self.open_folder)

        # 详情按钮
        self.detail_btn = QPushButton("查看详情", self)
        self.detail_btn.setObjectName("detail_btn")
        if project_type == "subtitle":
            self.detail_btn.setText("标注字幕")
        self.detail_btn.setFixedHeight(32)

        # 将按钮添加到布局，打开文件夹按钮在左侧

        button_layout.addWidget(self.detail_btn)
        button_layout.addWidget(self.open_folder_btn)

        layout.addLayout(button_layout)

        self.detail_btn.clicked.connect(self.open_detail)
        self.detail_page = None

        # 延迟加载图片
        QTimer.singleShot(20, self.load_project_image)

    def open_folder(self):
        """打开项目文件夹"""
        try:
            if self.project_type == "dubbing":
                path = getattr(self.project, "target_video_path", None)
            else:  # subtitle
                path = getattr(self.project, "subtitle_path", None)

            if not path:
                QMessageBox.warning(self, "提示", "找不到文件路径")
                return

            if not os.path.exists(path):
                QMessageBox.warning(self, "提示", f"路径不存在:\n{path}")
                return


            if os.path.exists(path):
                if os.path.isdir(path):
                    # 如果是文件夹，直接打开
                    QDesktopServices.openUrl(QUrl.fromLocalFile(path))
                elif os.path.isfile(path):
                    # 如果是文件，打开文件所在文件夹并定位到该文件
                    # folder_path = os.path.dirname(path)
                    # QDesktopServices.openUrl(QUrl.fromLocalFile(folder_path))
                    # 在 Windows 上，可以使用 explorer.exe 来定位文件
                    print(sys.platform)
                    if sys.platform == "win32":
                        os.system(f'explorer /select,"{path}"')
            else:
                print("Path does not exist")

        except Exception as e:
            print(f"打开文件夹时出错: {e}")
            QMessageBox.warning(self, "错误", f"打开文件夹失败:\n{str(e)}")

    def load_project_image(self):
        """延迟加载项目图片"""
        if self.image_loaded:
            return

        try:
            pixmap = None

            # 尝试从图片路径加载
            if hasattr(self.project, "image_path") and self.project.image_path:
                if os.path.exists(self.project.image_path):
                    pixmap = QPixmap(self.project.image_path)

            # 如果图片不存在，尝试从视频加载第一帧
            if (pixmap is None or pixmap.isNull()) and hasattr(self.project, "original_video_path"):
                if self.project.original_video_path and os.path.exists(self.project.original_video_path):
                    pixmap = get_first_pixmap(self.project.original_video_path)

            # 如果都没有，使用默认图片
            if pixmap is None or pixmap.isNull():
                pixmap = QPixmap(':/qfluentwidgets/images/logo.png')

            if not pixmap.isNull():
                # 缩放并设置图片
                scaled_pixmap = pixmap.scaled(
                    self.image_label.width() - 4,  # 留出边距
                    self.image_label.height() - 4,
                    Qt.KeepAspectRatioByExpanding,
                    Qt.SmoothTransformation
                )
                self.image_label.setPixmap(scaled_pixmap)
                self.image_loaded = True

        except Exception as e:
            print(f"加载项目图片失败: {e}")

    def open_detail(self):
        """打开项目详情"""
        loading_msg = QMessageBox(self)
        loading_msg.setWindowTitle("请稍候")

        if self.project_type == "dubbing":
            loading_msg.setText("正在加载配音室，请稍候...")
            loading_msg.show()
            QApplication.processEvents()

            DubbingEditorInterface = _get_attr("ReviewInterface.DubbingEditorInterface", "DubbingEditorInterface")
            self.dubbing_editor = DubbingEditorInterface()
            self.dubbing_editor.setWindowModality(Qt.ApplicationModal)
            print(os.path.dirname(self.project.original_video_path))

            self.dubbing_editor.show_animation()
            loading_msg.hide()

            self.dubbing_editor._on_import_project(os.path.dirname(self.project.original_video_path))

        elif self.project_type == "subtitle":
            loading_msg.setText("正在加载字幕标注界面，请稍候...")
            loading_msg.show()
            QApplication.processEvents()

            try:
                SubtitleInterface = _get_attr("ReviewInterface.SubtitleEditorInterfaceExpr2", "SubtitleEditorInterface")
                self.subtitle_editor = SubtitleInterface()
                self.subtitle_editor.setWindowModality(Qt.ApplicationModal)
                self.subtitle_editor.set_srt_paths([self.project.subtitle_path])
                self.subtitle_editor.show()  # 显示
                # from AnnotationInterface import AnnotationInterface
                # self.detail_page = AnnotationInterface(self.project)
                loading_msg.hide()

            except ImportError:
                loading_msg.hide()
                QMessageBox.information(self, "提示", "字幕标注功能开发中...")

    def resizeEvent(self, event):
        """重设大小事件"""
        super().resizeEvent(event)

        # 如果图片已加载，重新缩放
        if self.image_loaded and hasattr(self, 'original_pixmap'):
            scaled_pixmap = self.original_pixmap.scaled(
                self.image_label.width() - 4,
                self.image_label.height() - 4,
                Qt.KeepAspectRatioByExpanding,
                Qt.SmoothTransformation
            )
            self.image_label.setPixmap(scaled_pixmap)

class ProjectCard_cast(QFrame):
    def __init__(self, project, project_type="dubbing", parent=None):
        super().__init__(parent)
        self.setObjectName("ProjectCard")
        self.project = project
        self.project_type = project_type
        self.image_loaded = False

        self.setStyleSheet("""
            ProjectCard {
                border-radius: 12px;
                background: #ffffff;
                border: 1px solid #e0e0e0;
            }
            *{
                font-family: "Microsoft YaHei UI";
            }
            #detail_btn {
                background: #0078d4;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 6px 12px;
            }
            #detail_btn:hover {
                background: #106ebe;
            }
            #detail_btn:pressed {
                background: #005a9e;
            }
        """)

        self.setAutoFillBackground(True)
        self.setFixedSize(card_width, 370)

        layout = QVBoxLayout(self)
        margin = 12
        layout.setContentsMargins(margin, margin, margin, margin)
        layout.setSpacing(8)

        # 项目图片
        self.image_label = QLabel(self)
        self.image_label.setFixedHeight(260)
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setStyleSheet("""
            QLabel {
                background: #f5f5f5;
                border-radius: 8px;
            }
        """)

        # 设置占位图
        placeholder_pixmap = QPixmap(':/qfluentwidgets/images/logo.png')
        if not placeholder_pixmap.isNull():
            self.image_label.setPixmap(placeholder_pixmap.scaled(
                200, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation
            ))

        layout.addWidget(self.image_label)

        # 项目名称
        self.name_label = QLabel(getattr(project, "projectname", "未命名项目"), self)
        font = self.name_label.font()
        font.setPointSize(11)
        font.setBold(True)
        self.name_label.setFont(font)
        self.name_label.setStyleSheet("color: #333;")
        layout.addWidget(self.name_label)

        # 时间戳
        timestamp = getattr(project, "update_time", "2025/01/01 00:00:00")
        self.time_label = QLabel(str(timestamp), self)
        font2 = self.time_label.font()
        font2.setPointSize(9)
        self.time_label.setFont(font2)
        self.time_label.setStyleSheet("color: #888;")
        layout.addWidget(self.time_label)

        # 详情按钮
        self.detail_btn = QPushButton("查看详情", self)
        self.detail_btn.setObjectName("detail_btn")
        if project_type == "subtitle":
            self.detail_btn.setText("标注字幕")
        self.detail_btn.setFixedHeight(32)
        layout.addWidget(self.detail_btn)

        self.detail_btn.clicked.connect(self.open_detail)
        self.detail_page = None

        # 延迟加载图片
        QTimer.singleShot(20, self.load_project_image)

    def load_project_image(self):
        """延迟加载项目图片"""
        if self.image_loaded:
            return

        try:
            pixmap = None

            # 尝试从图片路径加载
            if hasattr(self.project, "image_path") and self.project.image_path:
                if os.path.exists(self.project.image_path):
                    pixmap = QPixmap(self.project.image_path)

            # 如果图片不存在，尝试从视频加载第一帧
            if (pixmap is None or pixmap.isNull()) and hasattr(self.project, "original_video_path"):
                if self.project.original_video_path and os.path.exists(self.project.original_video_path):
                    pixmap = get_first_pixmap(self.project.original_video_path)

            # 如果都没有，使用默认图片
            if pixmap is None or pixmap.isNull():
                pixmap = QPixmap(':/qfluentwidgets/images/logo.png')

            if not pixmap.isNull():
                # 缩放并设置图片
                scaled_pixmap = pixmap.scaled(
                    self.image_label.width() - 4,  # 留出边距
                    self.image_label.height() - 4,
                    Qt.KeepAspectRatioByExpanding,
                    Qt.SmoothTransformation
                )
                self.image_label.setPixmap(scaled_pixmap)
                self.image_loaded = True

        except Exception as e:
            print(f"加载项目图片失败: {e}")

    def open_detail(self):
        """打开项目详情"""
        loading_msg = QMessageBox(self)
        loading_msg.setWindowTitle("请稍候")

        if self.project_type == "dubbing":
            loading_msg.setText("正在加载配音室，请稍候...")
            loading_msg.show()
            QApplication.processEvents()

            from ProjectCompoment.CutStudioPage import CutStudioPage
            self.detail_page = CutStudioPage(self.project)
            loading_msg.hide()
            self.detail_page.show()

        elif self.project_type == "subtitle":
            loading_msg.setText("正在加载字幕标注界面，请稍候...")
            loading_msg.show()
            QApplication.processEvents()

            try:
                SubtitleInterface = _get_attr("ReviewInterface.SubtitleEditorInterfaceExpr2", "SubtitleEditorInterface")
                self.subtitle_editor = SubtitleInterface()
                self.subtitle_editor.setWindowModality(Qt.ApplicationModal)
                self.subtitle_editor.set_srt_paths([self.project.subtitle_path])
                self.subtitle_editor.show()  # 显示
                # from AnnotationInterface import AnnotationInterface
                # self.detail_page = AnnotationInterface(self.project)
                loading_msg.hide()

            except ImportError:
                loading_msg.hide()
                QMessageBox.information(self, "提示", "字幕标注功能开发中...")

    def resizeEvent(self, event):
        """重设大小事件"""
        super().resizeEvent(event)

        # 如果图片已加载，重新缩放
        if self.image_loaded and hasattr(self, 'original_pixmap'):
            scaled_pixmap = self.original_pixmap.scaled(
                self.image_label.width() - 4,
                self.image_label.height() - 4,
                Qt.KeepAspectRatioByExpanding,
                Qt.SmoothTransformation
            )
            self.image_label.setPixmap(scaled_pixmap)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    ui = ProjectInterface()
    ui.show()
    sys.exit(app.exec_())