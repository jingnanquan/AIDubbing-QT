import os
import sys
from pathlib import Path
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel, QGroupBox, QTextEdit, QApplication, QScrollArea
from qfluentwidgets import (CardWidget, PushButton, LineEdit, StrongBodyLabel, BodyLabel,
                            InfoBar, InfoBarPosition, PrimaryPushButton, HyperlinkButton,
                            ScrollArea, TextEdit)

from AnnotationInterface import _load_module


def _get_attr(module_path: str, attr_name: str):
    return getattr(_load_module(module_path), attr_name)

class APIKeyCard(CardWidget):
    """单个API密钥配置卡片"""

    def __init__(self, title, description, current_key="", placeholder="", config_key="", parent=None):
        super().__init__(parent)
        self.title = title
        self.description = description
        self.current_key = current_key
        self.placeholder = placeholder
        self.config_key = config_key
        self.original_key = current_key  # 保存原始密钥

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        # 标题和描述
        title_label = StrongBodyLabel(self.title)
        title_label.setFont(QFont("Microsoft YaHei", 12, QFont.Bold))
        layout.addWidget(title_label)

        desc_label = BodyLabel(self.description)
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)

        # 密钥输入框
        self.key_input = LineEdit()
        self.key_input.setPlaceholderText(self.placeholder)
        self.key_input.setClearButtonEnabled(True)

        # 如果是已有密钥，显示部分字符
        if self.current_key:
            masked_key = self.mask_key(self.current_key)
            self.key_input.setText(self.current_key)

        layout.addWidget(self.key_input)

    def mask_key(self, key):
        """掩码显示密钥"""
        if not key:
            return ""
        if len(key) <= 8:
            return "*" * len(key)
        return key[:4] + "*" * (len(key) - 8) + key[-4:]

    def get_key(self):
        """获取当前输入的密钥"""
        current_text = self.key_input.text().strip()
        # 如果显示的是掩码格式，返回原始密钥
        if "*" in current_text and current_text == self.mask_key(self.original_key):
            return self.original_key
        return current_text

    def set_key(self, key):
        """设置密钥并更新显示"""
        self.current_key = key
        self.original_key = key
        if key:
            masked_key = self.mask_key(key)
            self.key_input.setText(self.current_key)
        else:
            self.key_input.clear()

    def is_modified(self):
        """检查是否被修改"""
        current_text = self.key_input.text().strip()
        # 如果显示的是掩码格式，认为未被修改
        if "*" in current_text and current_text == self.mask_key(self.original_key):
            return False
        return current_text != self.original_key


class SettingInterface(QFrame):
    """设置界面主类"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SettingInterface")
        ConfigManager = _get_attr("Service.readConfig", "ConfigManager")
        self.config_manager = ConfigManager()
        self.api_cards = {}  # 存储API卡片引用
        self.original_config = {}  # 存储原始配置
        self.init_ui()
        self.load_settings()

    def init_ui(self):
        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(30, 30, 30, 30)
        main_layout.setSpacing(20)

        # 标题
        title_label = StrongBodyLabel("设置")
        title_label.setFont(QFont("Microsoft YaHei", 18, QFont.Bold))
        main_layout.addWidget(title_label)

        # 创建滚动区域
        # scroll_area = ScrollArea()
        scroll_area = QScrollArea()
        scroll_area.setObjectName("scroll_area")

        scroll_widget = QFrame()
        scroll_widget.setObjectName("scroll_widget")
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setSpacing(20)

        scroll_area.setStyleSheet(
            """ #scroll_area{ border: None; background: transparent; } #scroll_widget{ background: transparent; } """)

        # API配置组
        api_group = self.create_api_group()
        scroll_layout.addWidget(api_group)

        # 关于信息组
        about_group = self.create_about_group()
        scroll_layout.addWidget(about_group)

        scroll_layout.addStretch()

        scroll_area.setWidget(scroll_widget)
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        main_layout.addWidget(scroll_area)

        # 按钮组
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)

        self.save_btn = PrimaryPushButton("保存")
        self.save_btn.clicked.connect(self.save_settings)

        self.cancel_btn = PushButton("取消")
        self.cancel_btn.clicked.connect(self.cancel_settings)

        # self.reset_btn = PushButton("重置")
        # self.reset_btn.clicked.connect(self.reset_settings)

        button_layout.addWidget(self.save_btn)
        button_layout.addWidget(self.cancel_btn)
        # button_layout.addWidget(self.reset_btn)
        button_layout.addStretch()

        main_layout.addLayout(button_layout)

    def create_api_group(self):
        """创建API配置组"""
        group = QGroupBox("API 配置")
        group.setStyleSheet("""
            QGroupBox {
                font-size: 18px;
                font-weight: bold;
                font-family: "Microsoft YaHei";
                border: 2px solid #e0e0e0;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 20px;
                padding: 0 5px 0 5px;
            }
        """)

        layout = QVBoxLayout(group)
        layout.setSpacing(15)

        # Gemini API配置
        gemini_card = APIKeyCard(
            title="Google Gemini API",
            description="用于AI配音和文本处理功能，请从 Google AI Studio 获取 API 密钥",
            current_key="",
            placeholder="请输入 Gemini API 密钥",
            config_key="API_KEY_GEMINI"
        )
        self.api_cards["API_KEY_GEMINI"] = gemini_card
        layout.addWidget(gemini_card)

        # JSON配置
        json_gemini_card = APIKeyCard(
            title="Gemini vertex_credentials JSON",
            description="Gemini API的JSON配置文件，包含认证信息和其他设置",
            current_key="",
            placeholder="请输入 JSON 配置内容",
            config_key="API_G"
        )
        self.api_cards["API_G"] = json_gemini_card
        layout.addWidget(json_gemini_card)

        # ElevenLabs API配置
        elevenlabs_card = APIKeyCard(
            title="ElevenLabs API",
            description="用于高质量的AI语音合成，请从 ElevenLabs 官网获取 API 密钥",
            current_key="",
            placeholder="请输入 ElevenLabs API 密钥",
            config_key="API_KEY_ElevenLabs"
        )
        self.api_cards["API_KEY_ElevenLabs"] = elevenlabs_card
        layout.addWidget(elevenlabs_card)

        return group

    def create_about_group(self):
        """创建关于信息组"""
        group = QGroupBox("关于")
        group.setStyleSheet("""
            QGroupBox {
                font-size: 18px;
                font-weight: bold;
                font-family: "Microsoft YaHei";
                border: 2px solid #e0e0e0;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 20px;
                padding: 0 5px 0 5px;
            }
        """)

        layout = QVBoxLayout(group)
        layout.setSpacing(10)

        # 应用信息
        app_info = BodyLabel("   AI配音工具箱 - 专业的AI配音和音频处理工具")
        app_info.setWordWrap(True)
        layout.addWidget(app_info)

        # 版本信息
        version_info = BodyLabel("   版本: v1.0.0")
        layout.addWidget(version_info)

        # 开发者信息
        dev_info = BodyLabel("   开发者: 境南泉")
        layout.addWidget(dev_info)

        # 链接按钮
        link_layout = QHBoxLayout()
        link_layout.setSpacing(10)

        github_btn = HyperlinkButton(
            url="https://github.com/jingnanquan/AIDubbing-QT",
            text="GitHub"
        )
        link_layout.addWidget(github_btn)

        docs_btn = HyperlinkButton(
            url="https://qfluentwidgets.com/",
            text="QFluentWidgets文档"
        )
        link_layout.addWidget(docs_btn)

        link_layout.addStretch()
        layout.addLayout(link_layout)

        return group

    def load_settings(self):
        """加载设置"""
        self.original_config = self.config_manager.load_config()

        # 更新各个卡片
        for config_key, card in self.api_cards.items():
            if config_key in self.original_config:
                card.set_key(self.original_config[config_key])

    def save_settings(self):
        """保存设置"""
        new_config = {}

        # 收集所有卡片的值
        for config_key, card in self.api_cards.items():
            new_config[config_key] = card.get_key()

        # 保存到文件
        if self.config_manager.save_config(new_config):
            self.original_config = new_config.copy()

            InfoBar.success(
                title="保存成功",
                content="所有配置已保存到 setting.env 文件",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2000,
                parent=self
            )
        else:
            InfoBar.error(
                title="保存失败",
                content="配置文件保存失败，请检查文件权限",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )

    def cancel_settings(self):
        """取消设置，恢复到原始值"""
        # 重新加载原始配置
        self.load_settings()

        InfoBar.info(
            title="已取消",
            content="配置已恢复到保存前的状态",
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=2000,
            parent=self
        )

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = SettingInterface()

    window.show()
    sys.exit(app.exec_())

