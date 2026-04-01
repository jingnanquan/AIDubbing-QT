import copy
import os
import sys

from functools import lru_cache
from importlib import import_module
from typing import Optional

from PyQt5 import sip
from PyQt5.QtCore import (
    Qt, QPropertyAnimation, QPoint, QTimer, QUrl,
    QThread, pyqtSignal, QObject, QSizeF, QEasingCurve
)
from PyQt5.QtGui import QStandardItemModel, QStandardItem, QPainter, QBrush
from PyQt5.QtWidgets import (
    QWidget, QFileDialog, QFrame, QVBoxLayout, QInputDialog, QMessageBox,
    QMenu, QApplication, QSizePolicy, QGraphicsScene, QGraphicsView, QLabel, QDesktopWidget
)
from PyQt5.QtMultimedia import QMediaContent, QMediaPlayer
from PyQt5.QtMultimediaWidgets import QGraphicsVideoItem

from qfluentwidgets.components.widgets.frameless_window import FramelessWindow

from ReviewInterface.SubtitleListItemEditExpr2 import SubtitleListItemEdit
from UI.Ui_subtitleEdit import Ui_SubtitleEdit
from Config import env

# ─────────────────────────────────────────────
#  分批渲染参数
#  CHUNK_SIZE   : 每帧渲染的 widget 数量
#  CHUNK_DELAY  : 每帧间隔（ms），设为 0 则尽快渲染但仍让 Qt 处理事件
# ─────────────────────────────────────────────
_CHUNK_SIZE  = 20
_CHUNK_DELAY = 0


@lru_cache(maxsize=None)
def _load_module(path: str):
    return import_module(path)


def _get_attr(module_path: str, attr_name: str):
    return getattr(_load_module(module_path), attr_name)


# ─────────────────────────────────────────────
#  视频播放相关（未改动）
# ─────────────────────────────────────────────

class GraphicsVideoItem(QGraphicsVideoItem):
    """ Graphics video item """

    def paint(self, painter, option, widget=None):
        painter.setBrush(QBrush(Qt.black))
        painter.drawRect(self.boundingRect())
        painter.setCompositionMode(QPainter.CompositionMode_Difference)
        super().paint(painter, option, widget)


def _format_time(ms: int) -> str:
    if ms is None or ms < 0:
        ms = 0
    hours        = ms // (3600 * 1000)
    minutes      = (ms % (3600 * 1000)) // (60 * 1000)
    seconds      = (ms % (60 * 1000)) // 1000
    milliseconds = ms % 1000
    return f"{hours:02}:{minutes:02}:{seconds:02},{milliseconds:03}"


class _QtMediaBackend(QObject):
    duration_changed = pyqtSignal(int)
    position_changed = pyqtSignal(int)
    state_changed    = pyqtSignal(QMediaPlayer.State)

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self._parent = parent
        self.mediaPlayer = QMediaPlayer(None, QMediaPlayer.VideoSurface)
        self.videoItem   = GraphicsVideoItem()
        self.scene       = QGraphicsScene(self)
        self.view        = QGraphicsView(self.scene)
        self.view.setFrameShape(QFrame.NoFrame)
        self.view.setAlignment(Qt.AlignCenter)
        self.view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.view.setDragMode(QGraphicsView.NoDrag)
        self.view.setAcceptDrops(False)
        self.view.viewport().setAcceptDrops(False)
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.scene.addItem(self.videoItem)
        self.mediaPlayer.setVideoOutput(self.videoItem)

        self._file_path       = ""
        self._position_timer  = QTimer(self)
        self._position_timer.setInterval(100)
        self._position_timer.timeout.connect(self._emit_position)

        self.mediaPlayer.durationChanged.connect(self.duration_changed.emit)
        self.mediaPlayer.stateChanged.connect(self.state_changed.emit)
        self.mediaPlayer.error.connect(self._handle_error)
        try:
            self.videoItem.nativeSizeChanged.connect(self._on_native_size_changed)
        except Exception:
            pass

    def _on_native_size_changed(self, size: QSizeF):
        try:
            if size and size.width() > 0 and size.height() > 0:
                self.videoItem.setSize(size)
                self.scene.setSceneRect(self.videoItem.boundingRect())
                self._fit_video_in_view()
        except Exception:
            pass

    def _fit_video_in_view(self):
        try:
            bounds = self.videoItem.boundingRect()
            if not bounds.isEmpty():
                self.view.resetTransform()
                self.view.fitInView(self.videoItem, Qt.KeepAspectRatio)
        except Exception:
            pass

    def _emit_position(self):
        self.position_changed.emit(self.mediaPlayer.position())

    def _handle_error(self):
        QMessageBox.critical(self._parent, "播放错误", self.mediaPlayer.errorString())

    def set_video_widget(self, widget: QWidget):
        if widget.layout() is None:
            layout = QVBoxLayout(widget)
            layout.setContentsMargins(0, 0, 0, 0)
        else:
            layout = widget.layout()
        for i in reversed(range(layout.count())):
            layout.itemAt(i).widget().deleteLater()
        layout.addWidget(self.view)

    def open(self, file_path: str) -> int:
        self._file_path = file_path
        self.mediaPlayer.stop()
        self.mediaPlayer.setMedia(QMediaContent(QUrl.fromLocalFile(file_path)))
        if not self._position_timer.isActive():
            self._position_timer.start()
        # QTimer.singleShot(500, lambda: self.duration_changed.emit(self.mediaPlayer.duration()))
        # self.play()

        QTimer.singleShot(1000, lambda: self.play())
        return self.mediaPlayer.duration()

    def play(self):
        self.mediaPlayer.play()
        if not self._position_timer.isActive():
            self._position_timer.start()

    def pause(self):
        self.mediaPlayer.pause()

    def stop(self):
        self.mediaPlayer.stop()
        self._position_timer.stop()

    def seek(self, ms: int):
        ms = max(0, int(ms))
        if self.mediaPlayer.duration() > 0:
            ms = min(ms, self.mediaPlayer.duration())
        self.mediaPlayer.setPosition(ms)

    def duration(self) -> int:
        return int(self.mediaPlayer.duration() or 0)

    def position(self) -> int:
        return int(self.mediaPlayer.position() or 0)

    def is_playing(self) -> bool:
        return self.mediaPlayer.state() == QMediaPlayer.PlayingState

    def resize_view(self):
        self._fit_video_in_view()


# ─────────────────────────────────────────────
#  SubtitleItemBuilder —— 已废弃，保留供兼容
#  实际渲染改为主线程分批渲染（见 _rebuild_subtitle_items_batch）
# ─────────────────────────────────────────────

class SubtitleItemBuilder(QThread):
    """
    保留此类以保持向后兼容，但主流程已改用主线程分批渲染。
    Qt 控件必须在主线程创建，子线程创建 widget 是未定义行为。
    """
    finished = pyqtSignal(list)
    progress = pyqtSignal(int)

    def __init__(self, subtitles, role_match_list, roles_model):
        super().__init__()
        self.subtitles      = subtitles
        self.role_match_list = role_match_list
        self.roles_model    = roles_model

    def run(self):
        # 子线程不再创建 widget，仅传回原始数据供主线程渲染
        self.finished.emit([])


# ─────────────────────────────────────────────
#  主界面
# ─────────────────────────────────────────────

class SubtitleEditorInterface(Ui_SubtitleEdit, FramelessWindow):

    def __init__(self, parent=None):
        super().__init__()
        print("字幕编辑界面加载")
        self.setupUi(self)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.subtitlePaths          = []
        self.subtitles              = []
        self.role_match_list        = []
        self._player_backend        = None
        self._position_poll_timer   = None
        self.video_file             = ""
        self.subtitle_text          = ""
        self.subtitle_file_name     = ""
        self.is_dirty               = False
        self._current_subtitle_row  = None
        self.roles_model            = QStandardItemModel()
        self.roles_model.appendRow(QStandardItem("default"))

        self.subtitle_widgets: list = []

        # 字幕跟随状态
        self._follow_enabled   = True   # "跟随"按钮开关
        self._highlighted_row  = -1     # 当前高光的行号，-1 表示无

        # 分批渲染状态
        self._pending_subtitles: list = []   # 待渲染的原始数据切片
        self._chunk_timer: QTimer = QTimer(self)
        self._chunk_timer.setSingleShot(True)
        self._chunk_timer.setInterval(_CHUNK_DELAY)
        self._chunk_timer.timeout.connect(self._render_next_chunk)
        self._loading_label: Optional[QLabel] = None  # 加载中占位提示

        self._del_unused_ui()
        self._setup_unfinished_ui()
        self._update_RoleListWidget()
        self.setAcceptDrops(True)

        self.AddSubBtn.clicked.connect(self.select_subtitle_file)
        self.AddVideoBtn.clicked.connect(self.select_video_file)
        self.AddRoleBtn.clicked.connect(self.add_role_list)
        self.OutputRoleBtn.setText("另存为字幕文件")
        self.SaveBtn.clicked.connect(self.save_subtitle_file)
        self.ExportBtn.clicked.connect(self.export_subtitle_file)
        self.ExportBtn.setText("另存为字幕文件")

        self.BottomPlayBtn.setText("暂停")
        self.BottomPlayBtn.clicked.connect(self.toggle_play_pause)
        self.BottomPositionSlider.sliderMoved.connect(self.on_position_slider_moved)

        # 字幕跟随按钮（动态创建，挂在播放控件旁）,可以不需要
        # from qfluentwidgets import PushButton as _PushButton
        # self._follow_btn = _PushButton("📌 跟随字幕")
        # self._follow_btn.setCheckable(True)
        # self._follow_btn.setChecked(True)
        # self._follow_btn.setFixedHeight(self.BottomPlayBtn.height() or 32)
        # self._follow_btn.clicked.connect(self._on_follow_btn_clicked)
        # self._update_follow_btn_style()
        # self.bottomBarLayout.insertWidget(1, self._follow_btn)

        self.SubListWidget.itemClicked.connect(self.show_subtitle_list)
        self.RoleListWidget.itemClicked.connect(self.modify_role_list)
        self.RoleListWidget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.RoleListWidget.customContextMenuRequested.connect(self.show_role_context_menu)

        self.now_path = os.path.dirname(os.path.abspath(__file__))
        test_path = os.path.join(self.now_path, "1-中_test.srt")

        try:
            if env == "dev" and os.path.exists(test_path):
                self.subtitlePaths.append(test_path)
                self.SubListWidget.addItem(os.path.basename(self.subtitlePaths[0]))
                self.subtitlePaths.append(os.path.join(self.now_path, "1-英_test.srt"))
                self.SubListWidget.addItem(os.path.basename(self.subtitlePaths[1]))
                self.subtitlePaths.append(os.path.join(self.now_path, "1-中.srt"))
                self.SubListWidget.addItem(os.path.basename(self.subtitlePaths[2]))
                self.subtitlePaths.append(os.path.join(self.now_path, "1-英.srt"))
                self.SubListWidget.addItem(os.path.basename(self.subtitlePaths[3]))
                self.import_role_list(os.path.join(self.now_path, "1-中-角色表-固定.txt"))
        except Exception:
            pass

        self._update_drop_hints()

    # ──────────────────────────────────────────
    #  resize / dirty
    # ──────────────────────────────────────────

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._player_backend:
            self._player_backend.resize_view()

    def mark_dirty(self):
        self.is_dirty = True
        try:
            title = os.path.basename(self.subtitle_file_name) if self.subtitle_file_name else "字幕编辑器"
            if not title.endswith("*"):
                self.setWindowTitle(f"{title} *")
        except Exception:
            pass

    def mark_clean(self):
        self.is_dirty = False
        try:
            title = os.path.basename(self.subtitle_file_name) if self.subtitle_file_name else "字幕编辑器"
            self.setWindowTitle(title)
        except Exception:
            pass

    # ──────────────────────────────────────────
    #  视频播放器
    # ──────────────────────────────────────────

    def _init_video_player(self):
        if self.CustomVideoWidget.layout() is None:
            self.CustomVideoWidget.setLayout(QVBoxLayout())
        self.CustomVideoWidget.layout().setContentsMargins(0, 0, 0, 0)
        self._player_backend = _QtMediaBackend(self)
        self._player_backend.set_video_widget(self.CustomVideoWidget)
        self._player_backend.duration_changed.connect(self._sync_duration)
        self._player_backend.position_changed.connect(self._on_position_updated)
        if isinstance(self._position_poll_timer, QTimer):
            self._position_poll_timer.stop()
            self._position_poll_timer.deleteLater()

    def select_video_file(self, video_file=""):
        try:
            if not video_file:
                self.video_file, _ = QFileDialog.getOpenFileName(
                    self, "Select File", "",
                    "Video Files (*.mp4 *.avi *.mov *.mkv *.flv *.wmv *.mpeg *.mpg *.webm);;All Files (*)"
                )
            else:
                self.video_file = video_file
            if self.video_file:
                if not self._player_backend:
                    self._init_video_player()
                self._player_backend.open(self.video_file)
                self.CustomVideoWidget.setStyleSheet("""#CustomVideoWidget{border: 1px solid #ccc;}""")
                self._update_drop_hints()
        except Exception as e:
            print(e)
            QMessageBox.warning(self, "提示", str(e))

    def _sync_duration(self, duration_ms: int):
        duration_ms = int(duration_ms or 0)
        self.BottomPositionSlider.setRange(0, max(0, duration_ms))
        self.BottomTimeLabel.setText(_format_time(0))
        self.BottomTimeLabelMax.setText(_format_time(duration_ms))

    def _on_position_updated(self, pos: int):
        if not self.BottomPositionSlider.isSliderDown():
            self.BottomPositionSlider.setValue(pos)
        self.BottomTimeLabel.setText(_format_time(pos))
        # 只在"播放中"且"跟随开关开启"时才滚动
        if self._follow_enabled and self._player_backend and self._player_backend.is_playing():
            self._update_SubScroll(pos)

    def toggle_play_pause(self):
        if not self._player_backend or not self.video_file:
            QMessageBox.information(self, "提示", "请先导入视频！")
            return
        if self._player_backend.is_playing():
            self._player_backend.pause()
            self.BottomPlayBtn.setText("播放")
        else:
            self._player_backend.play()
            self.BottomPlayBtn.setText("暂停")

    def on_position_slider_moved(self, pos: int):
        pos = int(self.BottomPositionSlider.value())
        if self._player_backend is not None:
            self._player_backend.seek(pos)

    # ──────────────────────────────────────────
    #  UI 初始化
    # ──────────────────────────────────────────

    def _update_RoleListWidget(self):
        self.RoleListWidget.clear()
        for row in range(self.roles_model.rowCount()):
            self.RoleListWidget.addItem(self.roles_model.item(row).text())

    def _setup_unfinished_ui(self):
        self.SubScroll.setWidgetResizable(True)
        self.SubScroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.scrollAreaWidgetContents.deleteLater()
        self.SubListContainer = QFrame()
        self.SubListContainer.setObjectName("SubtitleCardContainer")
        self.container_layout = QVBoxLayout()
        self.container_layout.setAlignment(Qt.AlignTop)
        self.SubListContainer.setLayout(self.container_layout)
        self.SubScroll.setStyleSheet(
            """ #SubScroll{ border: 1px solid #ccc; background: transparent; }
                #SubtitleCardContainer{ background: transparent; } """
        )
        self.SubScroll.setWidget(self.SubListContainer)

    def _del_unused_ui(self):
        self.M3U8Box.hide()
        self.AIDirectedBtn.hide()
        self.AIDubbingBtn.hide()
        self.AIVoiceBtn.hide()
        self.CosyDubbingBtn.hide()
        self.AutoMarkBtn.hide()
        self.ImportRoleBtn.hide()
        self.OutputRoleBtn.hide()

    def select_subtitle_file(self):
        file_names, _ = QFileDialog.getOpenFileNames(self, "Select File", "", "字幕 (*.srt)")
        for file_name in file_names:
            self.subtitlePaths.append(file_name)
            self.SubListWidget.addItem(os.path.basename(file_name))
        self._update_drop_hints()

    def _update_drop_hints(self):
        try:
            if hasattr(self, "SubListDropHint"):
                self.SubListDropHint.setAttribute(Qt.WA_TransparentForMouseEvents, True)
                self.SubListDropHint.setVisible(self.SubListWidget.count() == 0)
        except Exception:
            pass
        try:
            if hasattr(self, "VideoDropHint"):
                if isinstance(self.VideoDropHint, QLabel) and not sip.isdeleted(self.VideoDropHint):
                    self.VideoDropHint.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        except Exception:
            pass

    # ──────────────────────────────────────────
    #  字幕列表加载（核心优化区域）
    # ──────────────────────────────────────────

    def show_subtitle_list(self, item):
        parse_subtitle_uncertain = _get_attr("Service.subtitleUtils", "parse_subtitle_uncertain")
        row = self.SubListWidget.row(item)
        print(f"点击了第 {row} 行，内容: {item.text()}")

        if self._current_subtitle_row is not None and row != self._current_subtitle_row:
            if not self.maybe_save():
                try:
                    self.SubListWidget.setCurrentRow(self._current_subtitle_row)
                except Exception:
                    pass
                return

        self.subtitles, new_role_list = parse_subtitle_uncertain(self.subtitlePaths[row])
        if not self.subtitles:
            QMessageBox.warning(self, "错误", "字幕文件内容错误！")
            return

        self.subtitle_file_name    = self.subtitlePaths[row]
        self._current_subtitle_row = row
        self.mark_clean()

        if new_role_list:
            self.role_match_list = copy.deepcopy(new_role_list)
            self.role_set        = set(self.role_match_list)
            for role in self.role_set:
                if self._isin_role_list(role):
                    continue
                self.roles_model.appendRow(QStandardItem(role))
            self._update_RoleListWidget()

        self._clear_subtitle_items()
        self._rebuild_subtitle_items_batch()

    def _clear_subtitle_items(self):
        """
        快速清空所有字幕控件。

        优化：先停止分批定时器，再批量移除 widget。
        直接调用 deleteLater 即可；不必逐个从 layout 中 removeWidget，
        因为 layout 会在 widget 析构时自动处理。
        """
        # 停止可能正在进行的上一轮分批渲染
        self._chunk_timer.stop()
        self._pending_subtitles.clear()

        # 隐藏 loading 标签（如果存在）
        self._hide_loading_label()

        # 重置高光状态（无需调用 clear_highlight，widget 即将销毁）
        self._highlighted_row = -1

        for w in self.subtitle_widgets:
            # 先从布局摘除再销毁，避免 layout 频繁计算
            self.container_layout.removeWidget(w)
            w.deleteLater()
        self.subtitle_widgets.clear()

    def _rebuild_subtitle_items_batch(self):
        """
        分批渲染字幕控件（主线程，非阻塞）。

        流程
        ----
        1. 对齐 role_match_list 长度
        2. 显示"加载中…"占位 Label（立即反馈给用户）
        3. 将所有字幕数据保存到 _pending_subtitles 队列
        4. 立即渲染首批（_CHUNK_SIZE 条），让用户最快看到内容
        5. 通过 QTimer 每帧渲染后续批次，保持 UI 响应
        """
        self._reindex_subtitles()
        if self.subtitles is None:
            self.subtitles = []

        # role_match_list 长度对齐
        default_role = self.roles_model.item(0).text()
        while len(self.role_match_list) < len(self.subtitles):
            self.role_match_list.append(default_role)
        if len(self.role_match_list) > len(self.subtitles):
            self.role_match_list = self.role_match_list[: len(self.subtitles)]

        total = len(self.subtitles)
        if total == 0:
            return

        # ① 立即显示 loading 占位，消除用户感知的空白等待
        self._show_loading_label(loaded=0, total=total)

        # ② 准备分批队列（带上 role 信息，打包成 tuple 避免重复索引）
        self._pending_subtitles = list(enumerate(self.subtitles))

        # ③ 立即触发首批渲染（不等定时器），让内容尽快出现
        self._render_next_chunk()

    def _render_next_chunk(self):
        """
        从 _pending_subtitles 取出一批，创建并挂载控件，
        然后若队列非空则启动定时器继续渲染下一批。
        """
        if not self._pending_subtitles:
            self._hide_loading_label()
            return

        total   = len(self.subtitles)
        chunk   = self._pending_subtitles[:_CHUNK_SIZE]
        self._pending_subtitles = self._pending_subtitles[_CHUNK_SIZE:]

        for i, subtitle in chunk:
            w = SubtitleListItemEdit(subtitle, self.roles_model)
            w.set_row(i)
            w.set_index(i + 1)
            try:
                w.roles.setCurrentText(self.role_match_list[i])
            except Exception:
                pass
            w.changed.connect(self.on_subtitle_item_changed)
            w.insertAbove.connect(self.on_subtitle_insert_above)
            w.insertBelow.connect(self.on_subtitle_insert_below)
            w.deleteRequested.connect(self.on_subtitle_delete)
            self.container_layout.addWidget(w)
            self.subtitle_widgets.append(w)

        loaded = len(self.subtitle_widgets)

        if self._pending_subtitles:
            # 更新进度提示
            self._update_loading_label(loaded=loaded, total=total)
            # 调度下一批（interval=0 表示下一个事件循环周期，UI 不阻塞）
            self._chunk_timer.start()
        else:
            # 全部渲染完毕
            self._hide_loading_label()

    # ── Loading 占位 Label 辅助方法 ──────────────

    def _show_loading_label(self, loaded: int, total: int):
        """在 container_layout 顶部插入一个加载提示标签"""
        if self._loading_label is None:
            self._loading_label = QLabel()
            self._loading_label.setAlignment(Qt.AlignCenter)
            self._loading_label.setStyleSheet(
                "color: #888; font-size: 13px; padding: 8px;"
            )
        self._loading_label.setText(f"加载中… 0 / {total} 条")
        # 插入到布局最前面（index 0），保持其始终在列表顶部可见
        self.container_layout.insertWidget(0, self._loading_label)
        self._loading_label.show()

    def _update_loading_label(self, loaded: int, total: int):
        if self._loading_label is not None:
            self._loading_label.setText(f"加载中… {loaded} / {total} 条")

    def _hide_loading_label(self):
        if self._loading_label is not None:
            self.container_layout.removeWidget(self._loading_label)
            self._loading_label.hide()

    # ──────────────────────────────────────────
    #  字幕项增删改（增量更新，不重建全列表）
    # ──────────────────────────────────────────

    def _reindex_subtitles(self):
        for i, sub in enumerate(self.subtitles):
            sub["index"] = i + 1

    def on_subtitle_item_changed(self, row: int, data: dict):
        """修改字幕项（增量更新）"""
        row = int(row)
        if row < 0 or row >= len(self.subtitles):
            return

        data["index"] = row + 1
        self.subtitles[row].update({
            "index": data.get("index", row + 1),
            "start": data.get("start", self.subtitles[row].get("start", "00:00:00,000")),
            "end":   data.get("end",   self.subtitles[row].get("end",   "00:00:00,000")),
            "text":  data.get("text",  self.subtitles[row].get("text",  "")),
        })
        self.role_match_list[row] = data.get("role", self.role_match_list[row])

        # 用 set_subtitle_silent 批量写入，屏蔽信号防止级联触发
        if 0 <= row < len(self.subtitle_widgets):
            self.subtitle_widgets[row].set_subtitle_silent(data)

        self.mark_dirty()

    def on_subtitle_insert_above(self, row: int):
        """插入字幕到指定行上方（增量更新）"""
        row = int(row)
        row = max(0, min(row, len(self.subtitles)))

        base = self.subtitles[row] if row < len(self.subtitles) else (
            self.subtitles[-1] if self.subtitles else {}
        )
        new_sub = {
            "index": row + 1,
            "start": base.get("start", "00:00:00,000"),
            "end":   base.get("end",   "00:00:00,000"),
            "text":  "",
        }
        self.subtitles.insert(row, new_sub)
        self.role_match_list.insert(row, self.roles_model.item(0).text())

        w = self._make_widget(new_sub, row)
        self.container_layout.insertWidget(row, w)
        self.subtitle_widgets.insert(row, w)

        for i in range(row + 1, len(self.subtitle_widgets)):
            self.subtitle_widgets[i].set_row(i)
            self.subtitle_widgets[i].set_index(i + 1)
            self.subtitles[i]["index"] = i + 1

        self.mark_dirty()

    def on_subtitle_insert_below(self, row: int):
        """插入字幕到指定行下方（增量更新）"""
        row       = int(row)
        insert_at = max(0, min(row + 1, len(self.subtitles)))

        base = self.subtitles[row] if (0 <= row < len(self.subtitles)) else (
            self.subtitles[-1] if self.subtitles else {}
        )
        new_sub = {
            "index": insert_at + 1,
            "start": base.get("end",   "00:00:00,000"),
            "end":   base.get("end",   "00:00:00,000"),
            "text":  "",
        }
        self.subtitles.insert(insert_at, new_sub)
        self.role_match_list.insert(insert_at, self.roles_model.item(0).text())

        w = self._make_widget(new_sub, insert_at)
        self.container_layout.insertWidget(insert_at, w)
        self.subtitle_widgets.insert(insert_at, w)

        for i in range(insert_at + 1, len(self.subtitle_widgets)):
            self.subtitle_widgets[i].set_row(i)
            self.subtitle_widgets[i].set_index(i + 1)
            self.subtitles[i]["index"] = i + 1

        self.mark_dirty()

    def on_subtitle_delete(self, row: int):
        """删除指定行字幕（增量更新）"""
        row = int(row)
        if row < 0 or row >= len(self.subtitles):
            return

        self.subtitles.pop(row)
        if 0 <= row < len(self.role_match_list):
            self.role_match_list.pop(row)

        self.container_layout.removeWidget(self.subtitle_widgets[row])
        self.subtitle_widgets[row].deleteLater()
        self.subtitle_widgets.pop(row)

        for i in range(row, len(self.subtitle_widgets)):
            self.subtitle_widgets[i].set_row(i)
            self.subtitle_widgets[i].set_index(i + 1)
            self.subtitles[i]["index"] = i + 1

        self.mark_dirty()

    def _make_widget(self, subtitle: dict, row: int) -> SubtitleListItemEdit:
        """构建并连接单个 SubtitleListItemEdit 控件"""
        w = SubtitleListItemEdit(subtitle, self.roles_model)
        w.set_row(row)
        w.set_index(row + 1)
        try:
            w.roles.setCurrentText(self.role_match_list[row])
        except Exception:
            pass
        w.changed.connect(self.on_subtitle_item_changed)
        w.insertAbove.connect(self.on_subtitle_insert_above)
        w.insertBelow.connect(self.on_subtitle_insert_below)
        w.deleteRequested.connect(self.on_subtitle_delete)
        return w

    # ──────────────────────────────────────────
    #  保存 / 导出
    # ──────────────────────────────────────────

    def _collect_subtitles_for_write(self) -> list:
        out = []
        for i, sub in enumerate(self.subtitles):
            out.append({
                "index": i + 1,
                "start": sub.get("start", "00:00:00,000"),
                "end":   sub.get("end",   "00:00:00,000"),
                "text":  sub.get("text",  ""),
                "role":  self.role_match_list[i] if i < len(self.role_match_list) else "default",
            })
        return out

    def save_subtitle_file(self):
        if not self.subtitle_file_name:
            QMessageBox.information(self, "提示", "请先打开一个字幕文件！")
            return False
        write_subtitles_to_srt = _get_attr("Service.subtitleUtils", "write_subtitles_to_srt")
        ok = write_subtitles_to_srt(self._collect_subtitles_for_write(), self.subtitle_file_name)
        if ok:
            self.mark_clean()
            QMessageBox.information(self, "提示", "保存成功！")
            return True
        QMessageBox.warning(self, "提示", "保存失败！")
        return False

    def export_subtitle_file(self):
        if not self.subtitle_file_name:
            QMessageBox.information(self, "提示", "请先打开一个字幕文件！")
            return False
        default_name = os.path.basename(self.subtitle_file_name)
        out_path, _ = QFileDialog.getSaveFileName(self, "导出字幕", default_name, "字幕 (*.srt)")
        if not out_path:
            return False
        write_subtitles_to_srt = _get_attr("Service.subtitleUtils", "write_subtitles_to_srt")
        ok = write_subtitles_to_srt(self._collect_subtitles_for_write(), out_path)
        if ok:
            QMessageBox.information(self, "提示", "导出成功！")
            return True
        QMessageBox.warning(self, "提示", "导出失败！")
        return False

    def maybe_save(self) -> bool:
        if not self.is_dirty:
            return True
        reply = QMessageBox.question(
            self, "未保存的修改", "当前字幕有未保存的修改，是否保存？",
            QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
        )
        if reply == QMessageBox.Yes:
            return bool(self.save_subtitle_file())
        if reply == QMessageBox.No:
            self.mark_clean()
            return True
        return False

    def closeEvent(self, event):
        if not self.maybe_save():
            event.ignore()
            return
        self._chunk_timer.stop()
        try:
            if self._player_backend:
                self._player_backend.stop()
        except Exception:
            pass
        super().closeEvent(event)

    # ──────────────────────────────────────────
    #  视频同步滚动字幕
    # ──────────────────────────────────────────

    def _update_SubScroll(self, pos_ms: int):
        """
        二分查找当前播放位置对应的字幕，滚动列表并高光显示。

        复杂度 O(log N)，替代原来的 O(N) 线性遍历，
        100 ms 调用一次也不会有性能压力。
        """
        widgets = self.subtitle_widgets
        if not widgets:
            return

        time_str_to_ms = _get_attr("Service.generalUtils", "time_str_to_ms")

        # 二分查找：找到最后一个 start_ms <= pos_ms 的索引
        lo, hi, found = 0, len(widgets) - 1, -1
        while lo <= hi:
            mid = (lo + hi) // 2
            try:
                start_ms = time_str_to_ms(widgets[mid].start_edit.text().strip())
            except Exception:
                start_ms = 0
            if start_ms <= pos_ms:
                found = mid
                lo = mid + 1
            else:
                hi = mid - 1

        # 更新高光
        if found != self._highlighted_row:
            # 清除上一条高光
            if 0 <= self._highlighted_row < len(widgets):
                widgets[self._highlighted_row].clear_highlight()
            # 设置新高光
            if found >= 0:
                widgets[found].set_highlight()
            self._highlighted_row = found

        if found < 0:
            return

        # 滚动到目标位置（保持目标项在可视区中段）
        vbar  = self.SubScroll.verticalScrollBar()
        vmin  = vbar.minimum()
        vmax  = vbar.maximum()
        total = len(widgets)
        if total <= 1 or vmax == 0:
            return

        # 将目标行映射到滚动条位置，使其出现在视口约 1/3 处
        target_ratio  = max(0.0, (found - 1) / max(total - 1, 1))
        target_value  = int(vmin + target_ratio * (vmax - vmin))

        animation = QPropertyAnimation(vbar, b"value", self)
        animation.setDuration(150)
        animation.setEasingCurve(QEasingCurve.OutCubic)
        animation.setStartValue(vbar.value())
        animation.setEndValue(target_value)
        animation.start()

    def _on_follow_btn_clicked(self):
        self._follow_enabled = self._follow_btn.isChecked()
        self._update_follow_btn_style()
        # 关闭跟随时清除当前高光
        if not self._follow_enabled:
            self._clear_highlight()

    def _update_follow_btn_style(self):
        if self._follow_enabled:
            self._follow_btn.setText("📌 跟随字幕：开")
            self._follow_btn.setStyleSheet("""
                QPushButton {
                    background-color: #3a9ad9;
                    color: white;
                    border: 1px solid #2980b9;
                    border-radius: 4px;
                    padding: 4px 10px;
                    font-weight: bold;
                }
                QPushButton:hover { background-color: #2980b9; }
                QPushButton:pressed { background-color: #1f6fa0; }
            """)
        else:
            self._follow_btn.setText("📌 跟随字幕：关")
            self._follow_btn.setStyleSheet("""
                QPushButton {
                    background-color: #bdc3c7;
                    color: #555;
                    border: 1px solid #aaa;
                    border-radius: 4px;
                    padding: 4px 10px;
                }
                QPushButton:hover { background-color: #aab0b4; }
            """)

    def _clear_highlight(self):
        """清除所有字幕高光"""
        widgets = self.subtitle_widgets
        if 0 <= self._highlighted_row < len(widgets):
            widgets[self._highlighted_row].clear_highlight()
        self._highlighted_row = -1

    # ──────────────────────────────────────────
    #  角色管理
    # ──────────────────────────────────────────

    def _isin_role_list(self, role_name: str):
        for row in range(self.roles_model.rowCount()):
            if self.roles_model.item(row).text() == role_name:
                return True
        return False

    def modify_role_list(self, item):
        new_text, ok = QInputDialog.getText(self, "编辑项", "修改角色名称:", text=item.text())
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
                items = self.subtitle_widgets
                if len(role_match_list) < len(items):
                    raise Exception("角色表错误！")
                self.role_match_list = copy.deepcopy(role_match_list)
                self.role_set        = set(role_match_list)
                for role in self.role_set:
                    if self._isin_role_list(role):
                        continue
                    self.roles_model.appendRow(QStandardItem(role))
                self._update_RoleListWidget()
                for i in range(len(items)):
                    item = items[i]
                    if item is not None:
                        item.roles.setCurrentText(self.role_match_list[i])
        except Exception as e:
            print(e)
            QMessageBox.warning(self, "警告", "角色表错误！")

    def export_role_list(self):
        ExportRolesWorker = _get_attr("ThreadWorker.SubtitleInterfaceWorker", "ExportRolesWorker")
        items = self.subtitle_widgets
        if not items:
            QMessageBox.information(self, "提示", "请先标注并校验角色！")
            return
        folder = QFileDialog.getExistingDirectory(
            self, "选择导出文件夹", "",
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )
        if folder:
            role_match_list = [item.roles.currentText() for item in items]
            self.worker = ExportRolesWorker(self.subtitle_file_name, folder, role_match_list)
            self.worker.finished.connect(self.on_general_task_finished)
            self.worker.start()

    def show_role_context_menu(self, pos: QPoint):
        global_pos = self.RoleListWidget.viewport().mapToGlobal(pos)
        item = self.RoleListWidget.itemAt(pos)
        if item is None:
            return
        menu    = QMenu()
        action2 = menu.addAction("删除")
        action  = menu.exec_(global_pos)
        if action == action2:
            index = self.RoleListWidget.row(item)
            self.RoleListWidget.takeItem(index)
            self.roles_model.removeRow(index)

    # ──────────────────────────────────────────
    #  拖放
    # ──────────────────────────────────────────

    def dragEnterEvent(self, event):
        is_video_file = _get_attr("Service.videoUtils", "is_video_file")
        super().dragEnterEvent(event)
        if event.mimeData().hasUrls():
            decide_url = event.mimeData().urls()[0].toLocalFile()
            if is_video_file(decide_url):
                self.CustomVideoWidget.setStyleSheet("""#CustomVideoWidget{
                    background-color: #F8F8F8;
                    border: 2px dashed #a1bbd7;
                }""")
                if hasattr(self, "VideoDropHint"):
                    if isinstance(self.VideoDropHint, QLabel) and not sip.isdeleted(self.VideoDropHint):
                        self.VideoDropHint.setText("松开即可上传视频")
                        self.VideoDropHint.show()
            else:
                self.SubListBox.setStyleSheet("""#SubListBox{
                    background-color: #F8F8F8;
                    border: 2px dashed #a1bbd7;
                }""")
                if hasattr(self, "SubListDropHint"):
                    self.SubListDropHint.setText("松开即可上传字幕")
                    self.SubListDropHint.show()
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        super().dragLeaveEvent(event)
        self.SubListBox.setStyleSheet("""#SubListBox{border: 1px solid #ccc;}""")
        self.CustomVideoWidget.setStyleSheet("""#CustomVideoWidget{border: 1px solid #ccc;}""")
        if hasattr(self, "SubListDropHint"):
            self.SubListDropHint.setText("拖拽上传字幕")
        if hasattr(self, "VideoDropHint"):
            if isinstance(self.VideoDropHint, QLabel) and not sip.isdeleted(self.VideoDropHint):
                self.VideoDropHint.setText("拖拽视频文件到此处上传")
        self._update_drop_hints()

    def dropEvent(self, event):
        utils                    = _load_module("Service.subtitleUtils")
        get_srt_files_in_folder  = getattr(utils, "get_srt_files_in_folder")
        is_srt_file              = getattr(utils, "is_srt_file")
        is_video_file            = _get_attr("Service.videoUtils", "is_video_file")
        super().dropEvent(event)
        pos = event.pos()
        self.SubListBox.setStyleSheet("""#SubListBox{border: 1px solid #ccc;}""")
        self.CustomVideoWidget.setStyleSheet("""#CustomVideoWidget{border: 1px solid #ccc;}""")

        if self.SubListBox.geometry().contains(pos):
            urls      = event.mimeData().urls()
            paths     = [url.toLocalFile() for url in urls]
            srt_paths = []
            for path in paths:
                if os.path.isdir(path):
                    srt_paths.extend(get_srt_files_in_folder(path))
                elif is_srt_file(path):
                    srt_paths.append(path)
            for file_name in srt_paths:
                self.subtitlePaths.append(file_name)
                self.SubListWidget.addItem(os.path.basename(file_name))
            self._update_drop_hints()

        if self.CustomVideoWidget.geometry().contains(pos):
            decide_url = event.mimeData().urls()[0].toLocalFile()
            if is_video_file(decide_url):
                self.select_video_file(decide_url)
            self._update_drop_hints()

    def set_srt_paths(self, paths: list):
        utils                   = _load_module("Service.subtitleUtils")
        get_srt_files_in_folder = getattr(utils, "get_srt_files_in_folder")
        is_srt_file             = getattr(utils, "is_srt_file")
        srt_paths = []
        for path in paths:
            if os.path.isdir(path):
                srt_paths.extend(get_srt_files_in_folder(path))
            elif is_srt_file(path):
                srt_paths.append(path)
        for file_name in srt_paths:
            self.subtitlePaths.append(file_name)
            self.SubListWidget.addItem(os.path.basename(file_name))
        self._update_drop_hints()

    def on_general_task_finished(self, msg):
        print(msg)
        QMessageBox.information(self, "提示", msg)

    # ──────────────────────────────────────────
    #  窗口动画
    # ──────────────────────────────────────────

    def show(self):
        width  = 1600
        height = 980
        screen = QDesktopWidget().screenGeometry()
        x = (screen.width()  - width)  // 2
        y = (screen.height() - height) // 2
        self.setGeometry(x, y, width, height)
        self.setWindowOpacity(0)
        self.animation = QPropertyAnimation(self, b"windowOpacity")
        self.animation.setDuration(300)
        self.animation.setStartValue(0)
        self.animation.setEndValue(1)
        self.animation.setEasingCurve(QEasingCurve.InOutQuad)
        self.animation.start()
        super().show()


if __name__ == '__main__':
    app    = QApplication(sys.argv)
    window = SubtitleEditorInterface()
    window.show()
    sys.exit(app.exec_())