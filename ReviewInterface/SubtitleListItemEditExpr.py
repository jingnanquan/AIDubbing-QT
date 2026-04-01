from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QEvent
from PyQt5.QtGui import QStandardItemModel, QFont
from PyQt5.QtWidgets import (
    QFrame, QVBoxLayout, QSizePolicy, QHBoxLayout, QComboBox, QLineEdit
)
from qfluentwidgets import PushButton, BodyLabel


# ─────────────────────────────────────────────
#  共享样式常量（避免每个实例重复解析样式字符串）
# ─────────────────────────────────────────────
_FRAME_STYLE = """
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
"""

_DELETE_BTN_STYLE = """
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
"""

# 复用字体对象，避免每个实例重复创建
_FONT_INDEX  = QFont("Microsoft YaHei UI", 11, QFont.Bold)
_FONT_TIME   = QFont("Microsoft YaHei UI", 8)
_FONT_TEXT   = QFont("Microsoft YaHei UI", 11)


class NoScrollComboBox(QComboBox):
    """屏蔽滚轮事件的 ComboBox，防止在列表滚动时意外切换角色"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.installEventFilter(self)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Wheel:
            return True  # 吞掉滚轮事件
        return super().eventFilter(obj, event)


class SubtitleListItemEdit(QFrame):
    """
    可编辑字幕列表项：时间/内容修改 + 插入/删除 + 角色选择

    优化点
    ------
    * 样式字符串、字体对象提升为模块级常量，所有实例共享，减少重复解析/分配。
    * 延迟连接信号：先完成布局，再 `_connect_signals()`，避免构造期间触发无效信号。
    * `_schedule_emit` 保护：row < 0 时直接忽略，避免定时器空转。
    * `blockSignals` 工具方法：供外部批量赋值时使用，防止触发级联更新。
    """

    changed         = pyqtSignal(int, dict)  # (row, subtitle_dict)
    insertAbove     = pyqtSignal(int)         # (row)
    insertBelow     = pyqtSignal(int)         # (row)
    deleteRequested = pyqtSignal(int)         # (row)

    def __init__(self, subtitle: dict, roles_model: QStandardItemModel, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self._row = -1

        # 防抖定时器：300 ms 内连续编辑只触发一次 changed 信号
        self._emit_timer = QTimer(self)
        self._emit_timer.setSingleShot(True)
        self._emit_timer.setInterval(300)
        self._emit_timer.timeout.connect(self._emit_changed)

        self.setStyleSheet(_FRAME_STYLE)

        index = int(subtitle.get("index", 1))
        start = subtitle.get("start", "00:00:00,000")
        end   = subtitle.get("end",   "00:00:00,000")
        text  = subtitle.get("text",  "")

        self.setMaximumHeight(200)
        self._create_widgets(index, start, end, roles_model, text)
        self._setup_layout()
        self._connect_signals()

    # ──────────────────────────────────────────
    #  构建控件
    # ──────────────────────────────────────────

    def _create_widgets(self, index, start, end, roles_model, text):
        # 编号标签
        self.index_label = BodyLabel("")
        self.index_label.setFont(_FONT_INDEX)
        self.set_index(index)

        # 时间输入框
        self.start_edit = QLineEdit(start)
        self.start_edit.setFont(_FONT_TIME)
        self.start_edit.setPlaceholderText("00:00:00,000")

        self.end_edit = QLineEdit(end)
        self.end_edit.setFont(_FONT_TIME)
        self.end_edit.setPlaceholderText("00:00:00,000")

        # 角色选择（共享 model，不复制）
        self.roles = NoScrollComboBox()
        self.roles.setFixedHeight(30)
        self.roles.setModel(roles_model)

        # 操作按钮
        self.insert_above_btn = PushButton("上插")
        self.insert_below_btn = PushButton("下插")
        self.delete_btn = PushButton("删除")
        self.delete_btn.setStyleSheet(_DELETE_BTN_STYLE)

        # 字幕内容编辑框
        self.text_edit = QLineEdit(text)
        self.text_edit.setFont(_FONT_TEXT)
        self.text_edit.setPlaceholderText("输入字幕内容…")
        self.text_edit.setMinimumHeight(36)
        self.text_edit.setMaximumHeight(36)
        self.text_edit.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Minimum)

    def _setup_layout(self):
        # 第一行：编号 + 时间
        time_row = QHBoxLayout()
        time_row.setContentsMargins(0, 0, 0, 0)
        time_row.setSpacing(6)
        time_row.addWidget(self.index_label)
        time_row.addWidget(self.start_edit)
        time_row.addWidget(BodyLabel("->"))
        time_row.addWidget(self.end_edit)
        time_row.addStretch(1)

        # 第二行：角色 + 操作按钮
        control_row = QHBoxLayout()
        control_row.setContentsMargins(0, 0, 0, 0)
        control_row.setSpacing(6)
        control_row.addWidget(BodyLabel("角色"))
        control_row.addWidget(self.roles, 2)
        control_row.addStretch(1)
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
        self.start_edit.textChanged.connect(self._schedule_emit)
        self.end_edit.textChanged.connect(self._schedule_emit)
        self.roles.currentIndexChanged.connect(self._schedule_emit)
        self.text_edit.textChanged.connect(self._schedule_emit)

        self.insert_above_btn.clicked.connect(lambda: self.insertAbove.emit(self._row))
        self.insert_below_btn.clicked.connect(lambda: self.insertBelow.emit(self._row))
        self.delete_btn.clicked.connect(lambda: self.deleteRequested.emit(self._row))

    # ──────────────────────────────────────────
    #  公共接口
    # ──────────────────────────────────────────

    def set_row(self, row: int):
        self._row = int(row)

    def set_index(self, index: int):
        self.index_label.setText(f"编号：{int(index)}")

    def get_subtitle(self) -> dict:
        return {
            "index": int(self.index_label.text().replace("编号：", "").strip() or "1"),
            "start": self.start_edit.text().strip(),
            "end":   self.end_edit.text().strip(),
            "text":  self.text_edit.text().strip(),
            "role":  self.roles.currentText(),
        }

    def set_subtitle_silent(self, subtitle: dict):
        """
        批量写入字幕数据，屏蔽信号避免触发 changed 防抖定时器。
        供外部批量更新时调用，性能更优。
        """
        for w in (self.start_edit, self.end_edit, self.text_edit, self.roles):
            w.blockSignals(True)
        try:
            self.start_edit.setText(subtitle.get("start", self.start_edit.text()))
            self.end_edit.setText(subtitle.get("end",   self.end_edit.text()))
            self.text_edit.setText(subtitle.get("text",  self.text_edit.text()))
            role = subtitle.get("role")
            if role is not None:
                self.roles.setCurrentText(role)
        finally:
            for w in (self.start_edit, self.end_edit, self.text_edit, self.roles):
                w.blockSignals(False)

    # ──────────────────────────────────────────
    #  内部
    # ──────────────────────────────────────────

    def _schedule_emit(self):
        if self._row < 0:
            return
        self._emit_timer.start()

    def _emit_changed(self):
        if self._row < 0:
            return
        self.changed.emit(self._row, self.get_subtitle())