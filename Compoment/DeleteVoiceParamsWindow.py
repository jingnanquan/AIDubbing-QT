import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QGridLayout, QScrollArea, QCheckBox, QPushButton,
                             QLabel, QFrame, QMessageBox, QApplication)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from qfluentwidgets import CheckBox

from Service.datasetUtils import datasetUtils
from Service.dubbingMain.dubbingElevenLabs import dubbingElevenLabs
import traceback


class DeleteVoiceWorker(QThread):
    """删除声音的工作线程"""
    finished = pyqtSignal(bool, str)  # (成功与否, 消息)

    def __init__(self, voice_dict: dict):
        super().__init__()
        self.voice_dict = voice_dict

    def run(self):
        try:
            print(self.voice_dict.values())
            datasetUtils.getInstance().delete_voice_by_id(list(self.voice_dict.values()))
            eleven = dubbingElevenLabs.getInstance()
            success_count = 0
            fail_count = 0

            # 使用线程池并发删除声音，最大并发数为5
            with ThreadPoolExecutor(max_workers=5) as executor:
                # 提交所有删除任务
                future_to_name = {
                    executor.submit(self.delete_single_voice, eleven, name, voice_id): name
                    for name, voice_id in self.voice_dict.items()
                }

                # 等待所有任务完成
                for future in as_completed(future_to_name):
                    name = future_to_name[future]
                    try:
                        if future.result():
                            success_count += 1
                        else:
                            fail_count += 1
                    except Exception as e:
                        print(f"删除声音 {name} 失败: {e}")
                        fail_count += 1

            # for name, voice_id in self.voice_dict.items():
            #     try:
            #         eleven.elevenlabs.voices.delete(voice_id=voice_id)
            #         success_count += 1
            #     except Exception as e:
            #         print(f"删除声音 {name} 失败: {e}")
            #         fail_count += 1

            self.finished.emit(True, f"删除成功: {success_count}个, 失败: {fail_count}个")
        except Exception as e:
            print("出现错误：", e)
            self.finished.emit(False, f"删除过程中发生错误: {str(e)}")

    def delete_single_voice(self, eleven, name, voice_id):
        """删除单个声音的函数"""
        try:
            eleven.elevenlabs.voices.delete(voice_id=voice_id)
            return True
        except Exception as e:
            print(f"删除声音 {name} 失败: {e}")
            return False


class DeleteVoiceParamsWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.allow_close=True
        self.voice_checkboxes = []
        self.voice_dict = {}
        self.init_ui()
        self.load_voices()

    def closeEvent(self, event):
        if not self.allow_close:
            QMessageBox.information(self, "提示", "当前不允许关闭窗口。")
            event.ignore()
        else:
            event.accept()

    def init_ui(self):
        self.setWindowTitle("删除声音参数")
        # self.setGeometry(300, 300, 750, 450)
        self.setMinimumWidth(750)

        # self.setMinimumWidth(500)
        # self.setMaximumHeight(600)

        # 主窗口部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # 主布局
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(10)


        # 顶部布局 - 标题和全选按钮
        top_layout = QHBoxLayout()
        title_label = QLabel("选择要删除的声音:")
        title_label.setFont(QFont("Microsoft YaHei", 14))

        self.select_all_btn = QPushButton("全选")
        self.select_all_btn.clicked.connect(self.toggle_select_all)

        top_layout.addWidget(title_label)
        top_layout.addStretch()
        top_layout.addWidget(self.select_all_btn)

        main_layout.addLayout(top_layout)

        # 滚动区域
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                border: 1px solid #ccc;
                border-radius: 5px;
            }
        """)

        # 滚动内容容器
        self.scroll_content = QWidget()
        self.scroll_layout = QGridLayout(self.scroll_content)
        self.scroll_layout.setAlignment(Qt.AlignTop)  # 内容顶部对齐
        self.scroll_layout.setSpacing(10)
        self.scroll_layout.setContentsMargins(10, 10, 10, 10)

        self.scroll_area.setWidget(self.scroll_content)
        main_layout.addWidget(self.scroll_area)

        # 底部按钮布局
        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch()

        self.delete_btn = QPushButton("确认删除")
        self.delete_btn.setStyleSheet("""
            QPushButton {
                background-color: #ff4d4d;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #ff3333;
            }
            QPushButton:pressed {
                background-color: #cc0000;
            }
        """)
        self.delete_btn.clicked.connect(self.delete_selected_voices)

        bottom_layout.addWidget(self.delete_btn)
        main_layout.addLayout(bottom_layout)

    def load_voices(self):
        """加载声音列表"""
        try:
            self.voice_dict = datasetUtils.getInstance().query_voice_id(1)
            self.create_voice_checkboxes()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"加载声音列表失败: {str(e)}")

    def create_voice_checkboxes(self):
        """创建声音选择框"""
        # 清除之前的复选框
        for checkbox in self.voice_checkboxes:
            checkbox.deleteLater()
        self.voice_checkboxes.clear()

        # 创建新的复选框
        row, col = 0, 0
        for name in self.voice_dict.keys():
            checkbox = CheckBox(name)

            self.scroll_layout.addWidget(checkbox, row, col)
            self.voice_checkboxes.append(checkbox)

            col += 1
            if col >= 3:  # 每行3列
                col = 0
                row += 1

    def toggle_select_all(self):
        """切换全选/取消全选"""
        all_selected = all(cb.isChecked() for cb in self.voice_checkboxes)

        for checkbox in self.voice_checkboxes:
            checkbox.setChecked(not all_selected)

        self.select_all_btn.setText("取消全选" if not all_selected else "全选")

    def delete_selected_voices(self):
        """删除选中的声音"""
        selected_voices = {}
        for checkbox in self.voice_checkboxes:
            if checkbox.isChecked():
                name = checkbox.text()
                if name in self.voice_dict:
                    selected_voices[name] = self.voice_dict[name]

        if not selected_voices:
            QMessageBox.information(self, "提示", "请至少选择一个声音")
            return

        # 确认删除
        reply = QMessageBox.question(
            self,
            "确认删除",
            f"确定要删除选中的 {len(selected_voices)} 个声音吗？此操作不可撤销。",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self.delete_btn.setEnabled(False)
            self.delete_btn.setText("删除中...")
            self.allow_close = False

            # 启动删除线程
            self.worker = DeleteVoiceWorker(selected_voices)
            self.worker.finished.connect(self.on_delete_finished)
            self.worker.start()

    def on_delete_finished(self, success, message):
        """删除完成回调"""
        self.delete_btn.setEnabled(True)
        self.delete_btn.setText("确认删除")
        self.allow_close = True

        if success:
            QMessageBox.information(self, "成功", message)
            self.load_voices()
        else:
            QMessageBox.warning(self, "出现错误", message)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = DeleteVoiceParamsWindow()
    # window = VoiceSelectorWindow()
    window.show()
    sys.exit(app.exec_())


