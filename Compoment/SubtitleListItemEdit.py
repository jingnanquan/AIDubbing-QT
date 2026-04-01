from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QStandardItemModel, QFont, QRegExpValidator, QFontMetrics
from PyQt5.QtWidgets import QFrame, QVBoxLayout, QSizePolicy, QHBoxLayout, QComboBox, QLineEdit
from qfluentwidgets import PushButton, BodyLabel

from PyQt5.QtCore import Qt, QEvent
from PyQt5.QtWidgets import QComboBox


class NoScrollComboBox(QComboBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        # 安装事件过滤器
        self.installEventFilter(self)

    def eventFilter(self, obj, event):
        # 拦截鼠标滚轮事件
        if event.type() == QEvent.Wheel:
            return True  # 拦截事件，不再传递

        # 拦截鼠标按下事件（可选，防止在展开时滚动）
        if event.type() == QEvent.MouseButtonPress:
            return super().eventFilter(obj, event)

        return super().eventFilter(obj, event)


class SubtitleListItemEdit(QFrame):
    """可编辑字幕列表项：时间/内容修改 + 插入/删除 + 角色选择"""

    changed = pyqtSignal(int, dict)  # (row, subtitle_dict)
    insertAbove = pyqtSignal(int)  # (row)
    insertBelow = pyqtSignal(int)  # (row)
    deleteRequested = pyqtSignal(int)  # (row)

    def __init__(self, subtitle: dict, roles_model: QStandardItemModel, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self._row = -1
        self._emit_timer = QTimer(self)
        self._emit_timer.setSingleShot(True)
        self._emit_timer.setInterval(300)
        self._emit_timer.timeout.connect(self._emit_changed)

        # margin: 1
        # px
        # 1
        # px;
        self.setStyleSheet("""
            SubtitleListItemEdit {
                border: 1px solid #ccc;
                border-radius: 6px;
                padding: 1px;
                background: #f9f9f9;
            }
            
            QComboBox {
                font-size: 12px;
                font-family: "Microsoft YaHei UI";
            }
        """)

        index = int(subtitle.get("index", 1))
        start = subtitle.get("start", "00:00:00,000")
        end = subtitle.get("end", "00:00:00,000")
        text = subtitle.get("text", "")

        self.setMaximumHeight(200)
        # 创建控件
        self._create_widgets(index, start, end, roles_model, text)
        # 设置布局
        self._setup_layout()
        # 连接信号
        self._connect_signals()

    def _create_widgets(self, index, start, end, roles_model, text):
        """创建所有控件"""
        # 编号标签
        self.index_label = BodyLabel("")
        self.index_label.setFont(QFont("Microsoft YaHei UI", 11, QFont.Bold))
        self.set_index(index)

        # 时间输入框
        # time_re = QRegExp(r"^\d{2}:\d{2}:\d{2},\d{3}$")
        # validator = QRegExpValidator(time_re, self)

        self.start_edit = QLineEdit()
        self.start_edit.setFont(QFont("Microsoft YaHei UI", 8))
        self.start_edit.setText(start)
        # self.start_edit.setValidator(validator)
        self.start_edit.setPlaceholderText("00:00:00,000")

        self.end_edit = QLineEdit()
        self.end_edit.setFont(QFont("Microsoft YaHei UI", 8))
        self.end_edit.setText(end)
        # self.end_edit.setValidator(validator)
        self.end_edit.setPlaceholderText("00:00:00,000")

        # 角色选择
        self.roles = NoScrollComboBox()
        self.roles.setFixedHeight(30)
        self.roles.setModel(roles_model)

        # 操作按钮
        self.insert_above_btn = PushButton("上插")
        self.insert_below_btn = PushButton("下插")
        self.delete_btn = PushButton("删除")
        self.delete_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #e74c3c;
                        color: white;
                        border: 1px solid #c0392b;
                        border-radius: 4px;
                        padding: 4px 8px;
                        font-weight: bold;
                    }
                    QPushButton:hover {
                        background-color: #c0392b;
                        border: 1px solid #a93226;
                    }
                    QPushButton:pressed {
                        background-color: #a93226;
                        border: 1px solid #922b21;
                    }
                    QPushButton:disabled {
                        background-color: #e0e0e0;
                        color: #999;
                        border: 1px solid #ccc;
                    }
                """)

        # 字幕内容编辑框
        self.text_edit = QLineEdit()
        self.text_edit.setText(text)
        # self.text_edit.setAcceptRichText(False)
        self.text_edit.setPlaceholderText("输入字幕内容…")

        # 设置字体（通过setFont）
        text_font = QFont("Microsoft YaHei UI", 11)
        self.text_edit.setFont(text_font)

        # 设置高度策略
        # self.text_edit.setMaximumHeight(40)
        self.text_edit.setMinimumHeight(36)
        self.text_edit.setMaximumHeight(36)

        self.text_edit.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Minimum)


    def _setup_layout(self):
        """设置布局"""
        # 第一行：编号和时间
        time_row = QHBoxLayout()
        time_row.setContentsMargins(0, 0, 0, 0)
        time_row.setSpacing(6)
        time_row.addWidget(self.index_label)
        # time_row.addWidget(BodyLabel("开始"))
        time_row.addWidget(self.start_edit)
        time_row.addWidget(BodyLabel("->"))
        time_row.addWidget(self.end_edit)
        time_row.addStretch(1)  # 添加弹性空间

        # 第二行：角色和操作按钮
        control_row = QHBoxLayout()
        control_row.setContentsMargins(0, 0, 0, 0)
        control_row.setSpacing(6)
        control_row.addWidget(BodyLabel("角色"))
        control_row.addWidget(self.roles, 2)  # 角色选择框占更多空间
        control_row.addStretch(1)  # 弹性空间
        control_row.addWidget(self.insert_above_btn)
        control_row.addWidget(self.insert_below_btn)
        control_row.addWidget(self.delete_btn)

        # 主布局
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        layout.addLayout(time_row)
        layout.addLayout(control_row)
        layout.addWidget(self.text_edit)

    def _connect_signals(self):
        """连接信号与槽"""
        self.start_edit.textChanged.connect(self._schedule_emit)
        self.end_edit.textChanged.connect(self._schedule_emit)
        self.roles.currentIndexChanged.connect(self._schedule_emit)
        self.text_edit.textChanged.connect(self._schedule_emit)

        self.insert_above_btn.clicked.connect(lambda: self.insertAbove.emit(self._row))
        self.insert_below_btn.clicked.connect(lambda: self.insertBelow.emit(self._row))
        self.delete_btn.clicked.connect(lambda: self.deleteRequested.emit(self._row))

    def set_row(self, row: int):
        self._row = int(row)

    def set_index(self, index: int):
        self.index_label.setText(f"编号：{int(index)}")

    def get_subtitle(self) -> dict:
        return {
            "index": int(self.index_label.text().replace("编号：", "").strip() or "1"),
            "start": self.start_edit.text().strip(),
            "end": self.end_edit.text().strip(),
            "text": self.text_edit.text().strip(),
            "role": self.roles.currentText(),
        }

    def _schedule_emit(self):
        if self._row < 0:
            return
        self._emit_timer.start()

    # 当出现修改时，触发changed信号。用于更新外部的列表项
    def _emit_changed(self):
        if self._row < 0:
            return
        self.changed.emit(self._row, self.get_subtitle())
