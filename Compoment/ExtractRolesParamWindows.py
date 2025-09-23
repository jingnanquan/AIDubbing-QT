import datetime
import os
import re
import sys
import threading

from PyQt5 import QtWidgets
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QLabel, QTextEdit, QLineEdit, QPushButton,
    QVBoxLayout, QHBoxLayout, QFormLayout, QGridLayout, QSizePolicy, QMessageBox, QProgressBar, QScrollArea,
    QApplication, QFrame
)
from PyQt5.QtCore import Qt, pyqtSignal, QThread
from qfluentwidgets import ComboBox, PushButton, LineEdit,  StrongBodyLabel, TextEdit

from Compoment.DraggableTextEdit import DraggableTextEdit
from Compoment.PathDialog import PrettyPathDialog
from Config import ROLE_ANNO_FOLDER
from Service.dubbingMain.llmAPI import LLMAPI
from Service.subtitleUtils import parse_subtitle, write_subtitles_to_srt


def create_expanding_widget() -> QWidget:
    widget = QWidget()
    size_policy = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
    widget.setSizePolicy(size_policy)
    return widget


class RoleTag(QFrame):
    """角色标签组件"""
    tag_removed = pyqtSignal(str)
    
    def __init__(self, role_name: str, parent=None):
        super().__init__(parent)
        self.role_name = role_name
        self.init_ui()
    
    def init_ui(self):
        layout = QHBoxLayout()
        layout.setContentsMargins(4, 1, 4, 1)
        layout.setSpacing(12)
        self.setFixedHeight(30)
        self.setObjectName("RoleTagFrame")
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        # 角色名称标签
        role_label = QLabel(self.role_name)
        role_label.setFont(QFont("Microsoft YaHei Ui", 9))

        self.setStyleSheet("""
            QFrame#RoleTagFrame {
                background-color: #e1f5fe;
                border: 1px solid #81c784;
                border-radius: 12px;
                padding: 4px 8px;
                color: #2e7d32;
            }
        """)
        
        # 删除按钮
        delete_btn = QPushButton("×")
        delete_btn.setFixedSize(16, 16)

        delete_btn.setStyleSheet("""
            QPushButton {
                background-color: #ffffff;
                border: none;
                border-radius: 8px !important;
                color: black;
            }
            QPushButton:hover {
                background-color: #eeeeee;
            }
        """)
        delete_btn.clicked.connect(lambda: self.tag_removed.emit(self.role_name))


        layout.addWidget(role_label)
        layout.addWidget(delete_btn, Qt.AlignmentFlag.AlignVCenter)
        layout.setAlignment(delete_btn, Qt.AlignmentFlag.AlignVCenter)
        layout.addStretch()
        
        self.setLayout(layout)


class ExtractRolesParamsWindow(QMainWindow):
    pass_result = pyqtSignal(list)

    def closeEvent(self, event):
        if not self.allow_close:
            QMessageBox.information(self, "提示", "当前不允许关闭窗口。")
            event.ignore()
        else:
            event.accept()

    def __init__(self, subtitle_path: str, video_path: str):
        super().__init__()
        self.thread = None
        self.allow_close = True
        self.subtitle_path = subtitle_path
        self.video_path = video_path
        self.role_tags = []  # 存储角色标签组件
        self.role_names = []  # 存储角色名称列表
        self.base_height = 410
        self.setMinimumHeight(self.base_height)
        self.setMinimumWidth(600)
        self.setWindowTitle("角色标注参数设置-已读取字幕和视频")
        
        # 监听窗口大小改变事件
        self.resizeEvent = self.on_resize_event

        # 主体 widget 和布局
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)
        central_widget.setLayout(layout)

        # 1. 剧情概要输入框
        self.create_plot_summary_section(layout)
        # 2. 角色列表组件
        self.create_role_list_section(layout)
        # 3. 开始标注按钮
        self.create_start_button(layout)
        # 4. 进度显示组件
        self.create_progress_section(layout)

    def create_plot_summary_section(self, parent_layout):
        """创建剧情概要输入框"""
        # 标题
        title_label = StrongBodyLabel("剧情概要")
        title_label.setFont(QFont("Microsoft YaHei", 12, QFont.Bold))
        parent_layout.addWidget(title_label)
        
        # 多行输入框
        self.plot_text_edit = DraggableTextEdit()
        self.plot_text_edit.setPlaceholderText("请在这里填写剧名、本集剧情概要、人物介绍、人物关系，可拖动文件自动解析文本。如果为空，系统会自动分析音视频内容生成剧情概要")
        self.plot_text_edit.setFont(QFont("Microsoft YaHei", 10))
        self.plot_text_edit.setFixedHeight(150)  # 固定6行高度
        self.plot_text_edit.setStyleSheet("""
            QTextEdit {
                border: 1px solid #ddd;
                border-radius: 6px;
                padding: 8px;
            }
        """)
        parent_layout.addWidget(self.plot_text_edit)

    def create_role_list_section(self, parent_layout):
        """创建角色列表组件"""
        # 标题
        title_label = StrongBodyLabel("角色列表")
        title_label.setFont(QFont("Microsoft YaHei", 12, QFont.Bold))
        parent_layout.addWidget(title_label)
        
        # 角色标签显示区域
        self.role_tags_widget = QWidget()
        self.role_tags_layout = QVBoxLayout()  # 垂直布局，每行一个水平布局
        self.role_tags_layout.setContentsMargins(0, 0, 0, 0)
        self.role_tags_layout.setSpacing(7)
        self.role_tags_widget.setLayout(self.role_tags_layout)
        self.role_tags_widget.hide()  # 初始隐藏
        parent_layout.addWidget(self.role_tags_widget)
        
        # 角色输入区域
        input_layout = QHBoxLayout()
        input_layout.setSpacing(10)
        
        self.role_input = LineEdit()
        self.role_input.setPlaceholderText("可添加角色名称以辅助ai进行标注，如陈女士-保洁、菜奈-小女孩、男主-成年态")
        self.role_input.setFont(QFont("Microsoft YaHei", 10))
        self.role_input.setFixedHeight(40)
        self.role_input.setStyleSheet("""
            QLineEdit {
                border: 1px solid #ddd;
                border-radius: 6px;
                padding: 8px;
            }
        """)
        
        self.add_role_btn = PushButton("添加")
        self.add_role_btn.setFixedWidth(60)
        self.add_role_btn.clicked.connect(self.add_role)
        
        input_layout.addWidget(self.role_input)
        input_layout.addWidget(self.add_role_btn)
        input_layout.setStretch(0, 1)
        parent_layout.addLayout(input_layout)

    def create_start_button(self, parent_layout):
        """创建开始标注按钮"""
        self.start_button = PushButton()
        self.start_button.setText("开始标注")
        self.start_button.setFixedHeight(40)
        self.start_button.clicked.connect(self.start_extraction)
        parent_layout.addWidget(self.start_button)

    def create_progress_section(self, parent_layout):
        """创建进度显示组件"""
        self.state_label = QLabel()
        self.state_label.setFont(QFont("Microsoft YaHei", 9))
        self.state_label.setStyleSheet("color: #666;")
        
        self.processbar = QProgressBar()
        self.processbar.setRange(0, 100)
        self.processbar.setValue(0)
        
        parent_layout.addWidget(self.state_label)
        parent_layout.addWidget(self.processbar)
        
        self.state_label.hide()
        self.processbar.hide()

    def add_role(self):
        """添加角色标签"""
        role_name = self.role_input.text().strip()
        if not role_name:
            return
        
        # 检查是否已存在
        if role_name in self.role_names:
            QMessageBox.information(self, "提示", "该角色已存在！")
            return
        
        # 创建角色标签
        role_tag = RoleTag(role_name)
        role_tag.tag_removed.connect(self.remove_role)
        
        # 添加到布局并重新排列
        self.role_tags.append(role_tag)
        self.role_names.append(role_name)
        self.rearrange_role_tags()
        
        # 显示角色标签区域
        if not self.role_tags_widget.isVisible():
            self.role_tags_widget.show()
            self.adjust_window_height()
        
        # 清空输入框
        self.role_input.clear()

    def remove_role(self, role_name: str):
        """删除角色标签"""
        if role_name in self.role_names:
            index = self.role_names.index(role_name)
            # 移除标签组件
            tag_widget = self.role_tags[index]
            tag_widget.deleteLater()
            
            # 从列表中移除
            self.role_tags.pop(index)
            self.role_names.pop(index)
            
            # 重新排列标签
            self.rearrange_role_tags()
            
            # 如果没有角色标签了，隐藏区域
            if len(self.role_tags) == 0:
                self.role_tags_widget.hide()
                self.adjust_window_height()

    def rearrange_role_tags(self):
        """重新排列角色标签，支持自动换行（基于实际标签宽度）"""
        # 清除现有布局中的所有组件
        while self.role_tags_layout.count():
            child = self.role_tags_layout.takeAt(0)
            if child.widget():
                child.widget().setParent(None)

        if not self.role_tags:
            return

        # 获取可用宽度（减去布局边距和间距）
        available_width = self.width() - self.role_tags_layout.contentsMargins().left() - self.role_tags_layout.contentsMargins().right()

        current_row_width = 0
        current_row_layout = QHBoxLayout()
        current_row_layout.setAlignment(Qt.AlignLeft)
        current_row_layout.setContentsMargins(0, 0, 0, 0)
        current_row_layout.setSpacing(8)

        for tag in self.role_tags:
            # 确保标签已经显示（否则无法获取正确宽度）
            # tag.show()
            print(tag.width())
            print(tag.sizeHint().width())
            # 获取标签的理想宽度（包括边距和间距）
            tag_width = tag.sizeHint().width() + current_row_layout.spacing()

            # 如果当前行剩余空间不足，则换行
            if current_row_width + tag_width > available_width and current_row_layout.count() > 0:
                self.role_tags_layout.addLayout(current_row_layout)
                current_row_layout = QHBoxLayout()
                current_row_layout.setAlignment(Qt.AlignLeft)
                current_row_layout.setContentsMargins(0, 0, 0, 0)
                current_row_layout.setSpacing(8)
                current_row_width = 0

            # 添加标签到当前行
            current_row_layout.addWidget(tag)
            current_row_width += tag_width

        # 添加最后一行（如果有内容）
        if current_row_layout.count() > 0:
            self.role_tags_layout.addLayout(current_row_layout)
    
    def adjust_window_height(self):
        """调整窗口高度"""
        # 计算所需高度
        base_height = self.base_height  # 基础高度
        
        # 如果角色标签区域可见，添加其高度
        if self.role_tags_widget.isVisible() and len(self.role_tags) > 0:
            # 计算标签行数
            window_width = self.width() - 40
            estimated_tag_width = 120
            tags_per_row = max(1, window_width // estimated_tag_width)
            rows = (len(self.role_tags) + tags_per_row - 1) // tags_per_row
            tags_height = rows * 42  # 每行35px高度
            base_height += tags_height
        
        # 如果进度条可见，添加其高度
        if self.state_label.isVisible() and self.processbar.isVisible():
            base_height += 50  # 进度条和状态标签的高度
        
        self.setMinimumHeight(base_height)
        self.resize(self.width(), base_height)
    
    def on_resize_event(self, event):
        """窗口大小改变事件"""
        super().resizeEvent(event)
        # 重新排列角色标签
        if self.role_tags_widget.isVisible() and len(self.role_tags) > 0:
            self.rearrange_role_tags()
            self.adjust_window_height()

    def start_extraction(self):
        """开始标注"""
        try:
            self.allow_close = False
            self.start_button.setEnabled(False)
            self.start_button.setText("请稍等...")
            self.processbar.setValue(0)
            self.state_label.setText("")
            self.state_label.show()
            self.processbar.show()
            self.adjust_window_height()  # 调整窗口高度

            # 准备参数
            params = {
                "subtitle_path": self.subtitle_path,
                "video_path": self.video_path,
                "plot_summary": self.plot_text_edit.toPlainText().strip(),
                "role_names": self.role_names.copy()
            }

            print("角色标注参数：", params)

            # 创建worker线程
            self.worker = ExtractRolesWorker(self, params)
            self.worker.pass_result.connect(self.pass_result_up)
            self.worker.finished.connect(self.on_task_finished)
            self.worker.progress.connect(self.update_process)
            self.worker.start()

        except Exception as e:
            print(e)
            self.on_task_finished({"error": str(e)})
    def pass_result_up(self, role_match_list: list):
        """更新进度"""
        print("传递标注结果到主界面:", role_match_list)
        self.pass_result.emit(role_match_list)

    def on_task_finished(self, result: dict):
        """任务完成回调"""
        if "error" in result:
            QMessageBox.warning(self, "角色标注出现错误", result["error"])
        elif "annotation_dir" in result:
            dlg = PrettyPathDialog("标注完成", "角色标注已完成，已保存过程文件到文件夹下，退出后会自动更新标记结果到主界面中，请进一步校验核对：", result["annotation_dir"], parent=self)
            dlg.exec_()
            # 可以在这里处理标注结果

        print("on_task_finished thread:", threading.current_thread())
        self.allow_close = True
        self.start_button.setEnabled(True)
        self.start_button.setText("开始标注")


    def update_process(self, value: int, text: str, plot_summary: str = ""):
        """更新进度"""
        if value != -1:
            self.processbar.setValue(value)
        if text:
            self.state_label.setText(text)
        if plot_summary:
            self.plot_text_edit.setPlainText(plot_summary)


class ExtractRolesWorker(QThread):
    """角色标注工作线程"""
    finished = pyqtSignal(dict)
    progress = pyqtSignal(int, str, str)
    pass_result = pyqtSignal(list)

    def on_progress(self, value, msg, plot_summary=""):
        self.progress.emit(value, msg, plot_summary)

    def __init__(self, parent, params):
        super().__init__()
        self.subtitle_path = params["subtitle_path"]
        self.video_path = params["video_path"]
        self.plot_summary = params["plot_summary"]
        self.role_names = params["role_names"]
        self.parent = parent

    def run(self):
        """执行角色标注任务"""
        try:
            self.progress.emit(10, "正在解析字幕文件...","")
            subtitle_text = ""
            with open(self.subtitle_path, 'r', encoding='utf-8') as file:
                subtitle_text = file.read()
                subtitle_text = re.sub(r'\n{2,}', '\n\n', subtitle_text.strip())
            print(subtitle_text)
            if not subtitle_text:
                raise Exception("字幕文件为空")
            subtitle_list = parse_subtitle(self.subtitle_path)

            attempt = 1
            self.progress.emit(30, "正在分析视频内容...","")
            while True:
                # 如果没有提供剧情概要，则调用API生成
                self.plot_summary = LLMAPI.getInstance().video_summary("", self.video_path, str(self.role_names))
                if self.plot_summary:
                    self.progress.emit(40, "正在分析视频内容...", self.plot_summary)
                    break
                attempt += 1
                if attempt >= 3 :
                    break
            print("剧情概要：", self.plot_summary)
            self.progress.emit(60, "正在进行角色标注...","")
            result_dict = LLMAPI.getInstance().extract_role_info_by_hint(subtitle_text, self.plot_summary, str(self.role_names))
            print("结果",result_dict)

            if not result_dict:
                raise Exception("gemini服务端错误")
            print(len(subtitle_list))
            print(len(result_dict))

            if len(subtitle_list) != len(result_dict):
                raise Exception("字幕和角色标注结果数量不一致")
            result_roles_list = list(result_dict.values())
            for i in range(len(subtitle_list)):
                subtitle_list[i]["role"] = result_roles_list[i]
            self.progress.emit(90, "正在生成标注结果...","")

            timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
            annotation_dir = os.path.join(ROLE_ANNO_FOLDER, "{}-角色标注结果-{}".format(os.path.basename(self.video_path).split('.')[0], timestamp))
            plot_summary_file = os.path.join(annotation_dir, "剧情简介.txt")
            anno_srt_file = os.path.join(annotation_dir, "角色标注字幕.srt")
            role_table_file = os.path.join(annotation_dir, "角色表.txt")

            os.makedirs(annotation_dir, exist_ok=True)
            with open(plot_summary_file, 'w', encoding='utf-8') as f:
                f.write(self.plot_summary)
            write_subtitles_to_srt(subtitle_list, anno_srt_file)
            with open(role_table_file, "w", encoding="utf-8") as f:
                f.write(";".join(result_roles_list))

            self.progress.emit(100, "角色标注完成！","")
            
            # 返回结果
            result = {
                "result": "success",
                "message": "角色标注完成",
                "annotation_dir": annotation_dir
            }

            self.pass_result.emit(result_roles_list)
            self.finished.emit(result)
            
        except Exception as e:
            print(e)
            self.finished.emit({"error": str(e)})


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = ExtractRolesParamsWindow("E:\\offer\\AI配音web版\\7.28\\AIDubbing-QT-main\\1-中_test.srt","E:\\offer\\AI配音web版\\7.28\\AIDubbing-QT-main\\a视频_test.mp4")
    window.show()
    sys.exit(app.exec_())
