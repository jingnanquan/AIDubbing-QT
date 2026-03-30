import copy
import os
import sys

from functools import lru_cache
from importlib import import_module

from PyQt5 import sip
from PyQt5.QtCore import (
    Qt, QPropertyAnimation, QPoint, QTimer, QUrl,
    QThread, pyqtSignal, QObject, QSizeF, QEasingCurve
)
from PyQt5.QtGui import QStandardItemModel, QStandardItem, QPainter, QBrush
from PyQt5.QtWidgets import (
    QWidget, QFileDialog, QFrame, QVBoxLayout, QInputDialog, QMessageBox,
    QMenu, QApplication, QSizePolicy, QGraphicsScene, QGraphicsView, QPushButton,
    QStyle, QHBoxLayout, QLabel, QDesktopWidget
)
from PyQt5.QtMultimedia import QMediaContent, QMediaPlayer
from PyQt5.QtMultimediaWidgets import QGraphicsVideoItem

from qfluentwidgets.components.widgets.frameless_window import FramelessWindow
# from qfluentwidgets import BodyLabel, Slider

from Compoment.SubtitleListItemEdit import SubtitleListItemEdit
from UI.Ui_subtitleEdit import Ui_SubtitleEdit
from Config import env

@lru_cache(maxsize=None)
def _load_module(path: str):
    return import_module(path)


def _get_attr(module_path: str, attr_name: str):
    return getattr(_load_module(module_path), attr_name)

# 参考 VideoPlayWidget 实现的 GraphicsVideoItem
class GraphicsVideoItem(QGraphicsVideoItem):
    """ Graphics video item """

    def paint(self, painter, option, widget=None):
        painter.setBrush(QBrush(Qt.black))
        # 填充整个视频项区域
        painter.drawRect(self.boundingRect())

        painter.setCompositionMode(QPainter.CompositionMode_Difference)
        # 先调用基类方法绘制原始视频
        super().paint(painter, option, widget)


# 格式化时间工具函数
def _format_time(ms: int) -> str:
    if ms is None or ms < 0:
        ms = 0
    hours = ms // (3600 * 1000)
    minutes = (ms % (3600 * 1000)) // (60 * 1000)
    seconds = (ms % (60 * 1000)) // 1000
    milliseconds = ms % 1000
    return f"{hours:02}:{minutes:02}:{seconds:02},{milliseconds:03}"


# 统一的 QtMedia 播放后端（参考 VideoPlayerWidget）
class _QtMediaBackend(QObject):
    duration_changed = pyqtSignal(int)
    position_changed = pyqtSignal(int)
    state_changed = pyqtSignal(QMediaPlayer.State)

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self._parent = parent
        self.mediaPlayer = QMediaPlayer(None, QMediaPlayer.VideoSurface)
        self.videoItem = GraphicsVideoItem()
        self.scene = QGraphicsScene(self)
        self.view = QGraphicsView(self.scene)
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

        self._file_path = ""
        self._position_timer = QTimer(self)
        self._position_timer.setInterval(100)
        self._position_timer.timeout.connect(self._emit_position)

        # 绑定信号
        self.mediaPlayer.durationChanged.connect(self.duration_changed.emit)
        self.mediaPlayer.stateChanged.connect(self.state_changed.emit)
        self.mediaPlayer.error.connect(self._handle_error)
        try:
            self.videoItem.nativeSizeChanged.connect(self._on_native_size_changed)
        except Exception:
            pass

    def _on_native_size_changed(self, size: QSizeF):
        """适配视频原生尺寸"""
        try:
            if size and size.width() > 0 and size.height() > 0:
                self.videoItem.setSize(size)
                self.scene.setSceneRect(self.videoItem.boundingRect())
                self._fit_video_in_view()
        except Exception:
            pass

    def _fit_video_in_view(self):
        """保持宽高比适配视频"""
        try:
            bounds = self.videoItem.boundingRect()
            if not bounds.isEmpty():
                self.view.resetTransform()
                self.view.fitInView(self.videoItem, Qt.KeepAspectRatio)
        except Exception:
            pass

    def _emit_position(self):
        """发射当前播放位置信号"""
        self.position_changed.emit(self.mediaPlayer.position())

    def _handle_error(self):
        """处理播放错误"""
        QMessageBox.critical(self._parent, "播放错误", self.mediaPlayer.errorString())

    def set_video_widget(self, widget: QWidget):
        """将视频视图嵌入到指定控件"""
        if widget.layout() is None:
            layout = QVBoxLayout(widget)
            layout.setContentsMargins(0, 0, 0, 0)
        else:
            layout = widget.layout()

        # 清空原有布局
        for i in reversed(range(layout.count())):
            layout.itemAt(i).widget().deleteLater()

        layout.addWidget(self.view)

    def open(self, file_path: str) -> int:
        """打开视频文件"""
        self._file_path = file_path
        self.mediaPlayer.stop()
        self.mediaPlayer.setMedia(QMediaContent(QUrl.fromLocalFile(file_path)))

        # 启动位置轮询定时器
        if not self._position_timer.isActive():
            self._position_timer.start()

        # 等待时长加载（简易等待，实际可通过信号异步处理）
        QTimer.singleShot(500, lambda: self.duration_changed.emit(self.mediaPlayer.duration()))
        self.play()
        return self.mediaPlayer.duration()

    def play(self):
        """播放"""
        self.mediaPlayer.play()
        if not self._position_timer.isActive():
            self._position_timer.start()

    def pause(self):
        """暂停"""
        self.mediaPlayer.pause()

    def stop(self):
        """停止"""
        self.mediaPlayer.stop()
        self._position_timer.stop()

    def seek(self, ms: int):
        """跳转到指定时间"""
        ms = max(0, int(ms))
        if self.mediaPlayer.duration() > 0:
            ms = min(ms, self.mediaPlayer.duration())
        self.mediaPlayer.setPosition(ms)

    def duration(self) -> int:
        """获取视频时长"""
        return int(self.mediaPlayer.duration() or 0)

    def position(self) -> int:
        """获取当前播放位置"""
        return int(self.mediaPlayer.position() or 0)

    def is_playing(self) -> bool:
        """是否正在播放"""
        return self.mediaPlayer.state() == QMediaPlayer.PlayingState

    def resize_view(self):
        """调整视频视图大小"""
        self._fit_video_in_view()


# 字幕项构建线程
class SubtitleItemBuilder(QThread):
    finished = pyqtSignal(list)  # 传递构建好的控件列表
    progress = pyqtSignal(int)  # 进度信号

    def __init__(self, subtitles, role_match_list, roles_model):
        super().__init__()
        self.subtitles = subtitles
        self.role_match_list = role_match_list
        self.roles_model = roles_model

    def run(self):
        widgets = []
        total = len(self.subtitles)
        for i, subtitle in enumerate(self.subtitles):
            # 构建字幕项控件
            w = SubtitleListItemEdit(subtitle, self.roles_model)
            w.set_row(i)
            w.set_index(i + 1)
            try:
                w.roles.setCurrentText(self.role_match_list[i] if i < len(self.role_match_list) else "default")
            except Exception:
                pass
            widgets.append(w)
            # 发送进度更新
            self.progress.emit(int((i + 1) / total * 100))
        # 发送构建完成的控件列表
        self.finished.emit(widgets)


class SubtitleEditorInterface(Ui_SubtitleEdit, FramelessWindow):

    def __init__(self, parent=None):
        super().__init__()
        print("字幕编辑界面加载")
        self.setupUi(self)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.subtitlePaths = []
        self.subtitles = []
        self.role_match_list = []
        self._player_backend = None
        self._position_poll_timer = None
        self.video_file = ""
        self.subtitle_text = ""
        self.subtitle_file_name = ""
        self.is_dirty = False
        self._current_subtitle_row = None
        self.roles_model = QStandardItemModel()
        self.roles_model.appendRow(QStandardItem("default"))

        # 新增：缓存字幕控件列表，便于增量更新
        self.subtitle_widgets = []

        # 初始化字幕滚动列表和角色列表
        self._del_unused_ui()
        self._setup_unfinished_ui()
        self._update_RoleListWidget()
        self.setAcceptDrops(True)

        # 绑定事件
        self.AddSubBtn.clicked.connect(self.select_subtitle_file)  # 上传字幕文件
        self.AddVideoBtn.clicked.connect(self.select_video_file)  # 上传视频文件
        self.AddRoleBtn.clicked.connect(self.add_role_list)  # 添加角色
        self.OutputRoleBtn.setText("另存为字幕文件")
        self.SaveBtn.clicked.connect(self.save_subtitle_file)  # 保存覆盖
        self.ExportBtn.clicked.connect(self.export_subtitle_file)  # 导出另存为
        self.ExportBtn.setText("另存为字幕文件")

        self.BottomPlayBtn.setText("暂停")
        self.BottomPlayBtn.clicked.connect(self.toggle_play_pause)
        self.BottomPositionSlider.sliderMoved.connect(self.on_position_slider_moved)
        # self.BottomPositionSlider.sliderReleased.connect(self.on_position_slider_released)

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

        except Exception as e:
            pass

        self._update_drop_hints()

    # def _reposition_video_hint(self):
    #     try:
    #         if self.VideoDropHint is None:
    #             return
    #         self.VideoDropHint.setGeometry(0, 0, self.CustomVideoWidget.width(), self.CustomVideoWidget.height())
    #         self.VideoDropHint.raise_()
    #     except Exception:
    #         pass

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # self._reposition_video_hint()
        # 调整视频视图大小
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

    def _init_video_player(self):
        """初始化视频播放器（参考 VideoPlayerWidget）"""
        if self.CustomVideoWidget.layout() is None:
            self.CustomVideoWidget.setLayout(QVBoxLayout())
        self.CustomVideoWidget.layout().setContentsMargins(0, 0, 0, 0)

        # 初始化 Qt 媒体后端
        self._player_backend = _QtMediaBackend(self)
        self._player_backend.set_video_widget(self.CustomVideoWidget)
        self._player_backend.duration_changed.connect(self._sync_duration)
        self._player_backend.position_changed.connect(self._on_position_updated)

        # 停止旧的轮询定时器（如果存在）
        if isinstance(self._position_poll_timer, QTimer):
            self._position_poll_timer.stop()
            self._position_poll_timer.deleteLater()

    def select_video_file(self, video_file=""):
        try:
            if not video_file:
                self.video_file, _ = QFileDialog.getOpenFileName(self, "Select File", "",
                                                                 "Video Files (*.mp4 *.avi *.mov *.mkv *.flv *.wmv *.mpeg *.mpg *.webm);;All Files (*)")
            else:
                self.video_file = video_file

            print(self.video_file)
            if self.video_file:
                # 初始化播放器
                if not self._player_backend:
                    self._init_video_player()

                # 打开视频文件
                self._player_backend.open(self.video_file)
                self.CustomVideoWidget.setStyleSheet("""#CustomVideoWidget{border: 1px solid #ccc;}""")
                self._update_drop_hints()
        except Exception as e:
            print(e)
            QMessageBox.warning(self, "提示", str(e))

    def _sync_duration(self, duration_ms: int):
        """同步视频时长到进度条"""
        duration_ms = int(duration_ms or 0)
        self.BottomPositionSlider.setRange(0, max(0, duration_ms))
        self.BottomTimeLabel.setText(_format_time(0))
        self.BottomTimeLabelMax.setText(_format_time(duration_ms))

    def _on_position_updated(self, pos: int):
        """更新播放位置和字幕滚动"""
        # 避免滑块拖动时更新
        if not self.BottomPositionSlider.isSliderDown():
            self.BottomPositionSlider.setValue(pos)
        self.BottomTimeLabel.setText(_format_time(pos))
        self._update_SubScroll([pos])

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
        """滑块拖动时更新时间显示"""
        pos = int(self.BottomPositionSlider.value())
        self._player_backend.seek(pos)
        # self.BottomTimeLabel.setText(_format_time(int(pos)))

    # def on_position_slider_released(self):
    #     """滑块释放时跳转到指定位置"""
    #     if not self._player_backend:
    #         return
    #     pos = int(self.BottomPositionSlider.value())
    #     self._player_backend.seek(pos)
    #     # 如果是暂停状态，点击滑块后自动播放
    #     if not self._player_backend.is_playing():
    #         self._player_backend.play()
    #         self.BottomPlayBtn.setText("暂停")

    def _update_RoleListWidget(self):
        self.RoleListWidget.clear()
        for row in range(self.roles_model.rowCount()):
            self.RoleListWidget.addItem(self.roles_model.item(row).text())

    def _setup_unfinished_ui(self):
        self.SubScroll.setWidgetResizable(True)  # 允许内部控件自适应
        self.SubScroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.scrollAreaWidgetContents.deleteLater()
        self.SubListContainer = QFrame()
        self.SubListContainer.setObjectName("SubtitleCardContainer")

        self.container_layout = QVBoxLayout()
        self.container_layout.setAlignment(Qt.AlignTop)  # 内容顶部对齐
        self.SubListContainer.setLayout(self.container_layout)
        self.SubScroll.setStyleSheet(
            """ #SubScroll{ border: 1px solid #ccc; background: transparent; } #SubtitleCardContainer{ background: transparent; } """)

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
        # Open file dialog to select a file
        file_names, _ = QFileDialog.getOpenFileNames(self, "Select File", "", "字幕 (*.srt)")  # 限制了只允许srt

        for file_name in file_names:
            self.subtitlePaths.append(file_name)
            self.SubListWidget.addItem(os.path.basename(file_name))
            print(self.subtitlePaths)
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
                # self.VideoDropHint.setVisible(not bool(self.video_file))
                # self._reposition_video_hint()
        except Exception:
            pass

    def show_subtitle_list(self, item):
        parse_subtitle_uncertain = _get_attr("Service.subtitleUtils", "parse_subtitle_uncertain")
        # 获取被点击项的行号（从 0 开始）
        row = self.SubListWidget.row(item)
        print(f"点击了第 {row} 行，内容: {item.text()}")
        print(self.subtitlePaths[row])

        # 切换前拦截未保存
        if self._current_subtitle_row is not None and row != self._current_subtitle_row:
            if not self.maybe_save():
                # 取消切换：还原选中项
                try:
                    self.SubListWidget.setCurrentRow(self._current_subtitle_row)
                except Exception:
                    pass
                return

        self.subtitles, new_role_list = parse_subtitle_uncertain(self.subtitlePaths[row])
        if not self.subtitles:
            QMessageBox.warning(self, "错误", "字幕文件内容错误！")
            return
        self.subtitle_file_name = self.subtitlePaths[row]
        self._current_subtitle_row = row
        self.mark_clean()

        if new_role_list:
            self.role_match_list = copy.deepcopy(new_role_list)
            self.role_set = set(self.role_match_list)  # 更新外部角色表
            for role in self.role_set:
                if self._isin_role_list(role):
                    continue
                self.roles_model.appendRow(QStandardItem(role))
            self._update_RoleListWidget()
        else:
            # 保留原有角色匹配
            pass

        # 全量重建（仅切换文件时）
        self._clear_subtitle_items()
        self._rebuild_subtitle_items_batch()

    def _clear_subtitle_items(self):
        """清空字幕控件"""
        for w in self.subtitle_widgets:
            w.deleteLater()
        self.subtitle_widgets.clear()

    def _reindex_subtitles(self):
        for i, sub in enumerate(self.subtitles):
            sub["index"] = i + 1

    def _rebuild_subtitle_items_batch(self):
        """批量重建字幕项"""
        self._reindex_subtitles()
        if self.subtitles is None:
            self.subtitles = []

        # role_match_list 长度对齐
        while len(self.role_match_list) < len(self.subtitles):
            self.role_match_list.append(self.roles_model.item(0).text())
        if len(self.role_match_list) > len(self.subtitles):
            self.role_match_list = self.role_match_list[: len(self.subtitles)]

        for i, subtitle in enumerate(self.subtitles):
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

    def on_subtitle_item_changed(self, row: int, data: dict):
        """修改字幕项（增量更新）"""
        row = int(row)
        if row < 0 or row >= len(self.subtitles):
            return

        # 更新数据
        data["index"] = row + 1
        self.subtitles[row].update({
            "index": data.get("index", row + 1),
            "start": data.get("start", self.subtitles[row].get("start", "00:00:00,000")),
            "end": data.get("end", self.subtitles[row].get("end", "00:00:00,000")),
            "text": data.get("text", self.subtitles[row].get("text", "")),
        })
        self.role_match_list[row] = data.get("role", self.role_match_list[row])

        # 直接更新控件内容（无需重建）
        if 0 <= row < len(self.subtitle_widgets):
            w = self.subtitle_widgets[row]
            w.start_edit.setText(data.get("start", w.start_edit.text()))
            w.end_edit.setText(data.get("end", w.end_edit.text()))
            w.text_edit.setPlainText(data.get("text", w.text_edit.toPlainText()))
            w.roles.setCurrentText(data.get("role", w.roles.currentText()))

        self.mark_dirty()

    def on_subtitle_insert_above(self, row: int):
        """插入字幕到指定行上方（增量更新）"""
        row = int(row)
        row = max(0, min(row, len(self.subtitles)))

        # 插入数据
        base = self.subtitles[row] if row < len(self.subtitles) else (self.subtitles[-1] if self.subtitles else {})
        new_sub = {
            "index": row + 1,
            "start": base.get("start", "00:00:00,000"),
            "end": base.get("end", "00:00:00,000"),
            "text": "",
        }
        self.subtitles.insert(row, new_sub)
        self.role_match_list.insert(row, self.roles_model.item(0).text())

        # 构建新控件
        w = SubtitleListItemEdit(new_sub, self.roles_model)
        w.set_row(row)
        w.set_index(row + 1)
        w.roles.setCurrentText(self.roles_model.item(0).text())
        w.changed.connect(self.on_subtitle_item_changed)
        w.insertAbove.connect(self.on_subtitle_insert_above)
        w.insertBelow.connect(self.on_subtitle_insert_below)
        w.deleteRequested.connect(self.on_subtitle_delete)

        # 插入控件到布局
        self.container_layout.insertWidget(row, w)
        self.subtitle_widgets.insert(row, w)

        # 更新后续控件的索引
        for i in range(row + 1, len(self.subtitle_widgets)):
            self.subtitle_widgets[i].set_row(i)
            self.subtitle_widgets[i].set_index(i + 1)
            self.subtitles[i]["index"] = i + 1

        self.mark_dirty()

    def on_subtitle_insert_below(self, row: int):
        """插入字幕到指定行下方（增量更新）"""
        row = int(row)
        insert_at = row + 1
        insert_at = max(0, min(insert_at, len(self.subtitles)))

        # 插入数据
        base = self.subtitles[row] if (0 <= row < len(self.subtitles)) else (
            self.subtitles[-1] if self.subtitles else {})
        new_sub = {
            "index": insert_at + 1,
            "start": base.get("end", "00:00:00,000"),
            "end": base.get("end", "00:00:00,000"),
            "text": "",
        }
        self.subtitles.insert(insert_at, new_sub)
        self.role_match_list.insert(insert_at, self.roles_model.item(0).text())

        # 构建新控件
        w = SubtitleListItemEdit(new_sub, self.roles_model)
        w.set_row(insert_at)
        w.set_index(insert_at + 1)
        w.roles.setCurrentText(self.roles_model.item(0).text())
        w.changed.connect(self.on_subtitle_item_changed)
        w.insertAbove.connect(self.on_subtitle_insert_above)
        w.insertBelow.connect(self.on_subtitle_insert_below)
        w.deleteRequested.connect(self.on_subtitle_delete)

        # 插入控件到布局
        self.container_layout.insertWidget(insert_at, w)
        self.subtitle_widgets.insert(insert_at, w)

        # 更新后续控件的索引
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

        # 删除数据
        self.subtitles.pop(row)
        if 0 <= row < len(self.role_match_list):
            self.role_match_list.pop(row)

        # 删除控件
        self.subtitle_widgets[row].deleteLater()
        self.subtitle_widgets.pop(row)

        # 更新后续控件的索引
        for i in range(row, len(self.subtitle_widgets)):
            self.subtitle_widgets[i].set_row(i)
            self.subtitle_widgets[i].set_index(i + 1)
            self.subtitles[i]["index"] = i + 1

        self.mark_dirty()

    def _collect_subtitles_for_write(self) -> list:
        # 以 self.subtitles 为准（已在 changed 回写），并附带 role
        out = []
        for i, sub in enumerate(self.subtitles):
            out.append({
                "index": i + 1,
                "start": sub.get("start", "00:00:00,000"),
                "end": sub.get("end", "00:00:00,000"),
                "text": sub.get("text", ""),
                "role": self.role_match_list[i] if i < len(self.role_match_list) else "default",
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
            self,
            "未保存的修改",
            "当前字幕有未保存的修改，是否保存？",
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
        try:
            if self._player_backend:
                self._player_backend.stop()
        except Exception:
            pass
        super().closeEvent(event)

    def _update_SubScroll(self, msec: list):
        time_str_to_ms = _get_attr("Service.generalUtils", "time_str_to_ms")
        if self.subtitles:
            index = 0
            items = self.subtitle_widgets
            for item in items:
                try:
                    start_text = item.start_edit.text().strip()
                except Exception:
                    start_text = "00:00:00,000"
                if time_str_to_ms(start_text) >= msec[0]:
                    index = items.index(item) + 1
                    break
            if index == 0:
                index = len(items)
            if index > 3:  # index等于4才会滚动
                vbar = self.SubScroll.verticalScrollBar()
                vmax = vbar.maximum()
                offset = int(((len(items) - index) * 9) / len(items))
                offset2 = int(offset / 2)
                offset -= 3
                animation = QPropertyAnimation(vbar, b"value", self)
                animation.setDuration(100)  # 动画持续时间（毫秒）
                animation.setStartValue(vbar.value())  # 起始值
                animation.setEndValue(((index - offset2) * vmax) / (len(items) + offset))  # 目标值
                animation.start()
            else:
                vbar = self.SubScroll.verticalScrollBar()
                animation = QPropertyAnimation(vbar, b"value", self)
                animation.setDuration(100)  # 动画持续时间（毫秒）
                animation.setStartValue(vbar.value())  # 起始值
                animation.setEndValue(0)  # 目标值
                animation.start()

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
                    print(len(role_match_list))
                    print(len(items))
                    if len(role_match_list) < len(items):
                        raise Exception("角色表错误！")
                    self.role_match_list = copy.deepcopy(role_match_list)
                    self.role_set = set(role_match_list)
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
            self,
            "选择导出文件夹",
            "",
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )
        if folder:
            role_match_list = []
            for item in items:
                role_match_list.append(item.roles.currentText())
            self.worker = ExportRolesWorker(self.subtitle_file_name, folder, role_match_list)
            self.worker.finished.connect(self.on_general_task_finished)
            self.worker.start()

    def show_role_context_menu(self, pos: QPoint):
        print("右键点击")
        # 将局部坐标转为全局坐标（用于 menu 显示位置）
        global_pos = self.RoleListWidget.viewport().mapToGlobal(pos)

        # 获取右键点击处的 item（可选）
        item = self.RoleListWidget.itemAt(pos)
        if item is None:
            return  # 没有点击到任何 item，直接返回

        # 创建菜单
        menu = QMenu()
        action2 = menu.addAction("删除")

        action = menu.exec_(global_pos)  # 弹出菜单并等待选择

        if action == action2:
            index = self.RoleListWidget.row(item)
            self.RoleListWidget.takeItem(index)
            self.roles_model.removeRow(index)

    def dragEnterEvent(self, event):
        is_video_file = _get_attr("Service.videoUtils", "is_video_file")
        super().dragEnterEvent(event)
        print("aaa")
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
        utils = _load_module("Service.subtitleUtils")
        get_srt_files_in_folder = getattr(utils, "get_srt_files_in_folder")
        is_srt_file = getattr(utils, "is_srt_file")
        is_video_file = _get_attr("Service.videoUtils", "is_video_file")
        super().dropEvent(event)
        pos = event.pos()
        self.SubListBox.setStyleSheet("""#SubListBox{border: 1px solid #ccc;}""")
        self.CustomVideoWidget.setStyleSheet("""#CustomVideoWidget{border: 1px solid #ccc;}""")
        if self.SubListBox.geometry().contains(pos):
            print("Drop into srt")

            urls = event.mimeData().urls()
            paths = [url.toLocalFile() for url in urls]
            print(paths)

            srt_paths = []
            for path in paths:
                if os.path.isdir(path):
                    srt_paths.extend(get_srt_files_in_folder(path))
                elif is_srt_file(path):
                    srt_paths.append(path)

            for file_name in srt_paths:
                self.subtitlePaths.append(file_name)
                self.SubListWidget.addItem(os.path.basename(file_name))
                print(self.subtitlePaths)
            self._update_drop_hints()

        if self.CustomVideoWidget.geometry().contains(pos):
            print("Drop into video")
            print(event.mimeData().urls())
            decide_url = event.mimeData().urls()[0].toLocalFile()
            if is_video_file(decide_url):
                print(decide_url)
                self.select_video_file(decide_url)
            self._update_drop_hints()

    def set_srt_paths(self, paths:list):
        utils = _load_module("Service.subtitleUtils")
        get_srt_files_in_folder = getattr(utils, "get_srt_files_in_folder")
        is_srt_file = getattr(utils, "is_srt_file")
        is_video_file = _get_attr("Service.videoUtils", "is_video_file")
        # paths = [url.toLocalFile() for url in urls]
        print(paths)

        srt_paths = []
        for path in paths:
            if os.path.isdir(path):
                srt_paths.extend(get_srt_files_in_folder(path))
            elif is_srt_file(path):
                srt_paths.append(path)

        for file_name in srt_paths:
            self.subtitlePaths.append(file_name)
            self.SubListWidget.addItem(os.path.basename(file_name))
            print(self.subtitlePaths)
        self._update_drop_hints()

    def on_general_task_finished(self, msg):
        print(msg)
        QMessageBox.information(self, "提示", msg)

    def show(self):
        # 创建淡入动画
        width = 1600
        height = 980
        screen = QDesktopWidget().screenGeometry()
        x = (screen.width() - width) // 2
        y = (screen.height() - height) // 2
        self.setGeometry(x, y, width, height)
        self.setWindowOpacity(0)  # 初始透明
        self.animation = QPropertyAnimation(self, b"windowOpacity")
        self.animation.setDuration(300)  # 动画时长（毫秒）
        self.animation.setStartValue(0)  # 起始透明度
        self.animation.setEndValue(1)  # 结束透明度
        self.animation.setEasingCurve(QEasingCurve.InOutQuad)  # 缓动曲线
        self.animation.start()
        super().show()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = SubtitleEditorInterface()
    window.show()
    sys.exit(app.exec_())