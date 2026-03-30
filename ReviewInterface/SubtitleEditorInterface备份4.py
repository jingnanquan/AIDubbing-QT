import copy
import os
import sys
from functools import lru_cache
from importlib import import_module
from threading import Thread
from queue import Queue

import qfluentwidgets
from PyQt5.QtCore import (
    Qt, QPropertyAnimation, QPoint, QTimer, QProcess, QUrl, QElapsedTimer,
    QThread, pyqtSignal, QObject
)
from PyQt5.QtGui import QStandardItemModel, QStandardItem
from PyQt5.QtWidgets import (
    QWidget, QFileDialog, QFrame, QVBoxLayout, QInputDialog, QMessageBox,
    QMenu, QApplication, QSizePolicy
)

from qfluentwidgets.components.widgets.frameless_window import FramelessWindow

from Compoment.SubtitleListItemEdit import SubtitleListItemEdit
from UI.Ui_subtitleEdit import Ui_SubtitleEdit
from Config import env

if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes
    # Windows API 声明
    user32 = ctypes.WinDLL('user32', use_last_error=True)
    user32.SetParent.argtypes = [wintypes.HWND, wintypes.HWND]
    user32.SetParent.restype = wintypes.HWND
    user32.MoveWindow.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.BOOL]
    user32.MoveWindow.restype = wintypes.BOOL
elif sys.platform == "linux":
    import subprocess
    import re


def _format_time(ms: int) -> str:
    if ms is None or ms < 0:
        ms = 0
    hours = ms // (3600 * 1000)
    minutes = (ms % (3600 * 1000)) // (60 * 1000)
    seconds = (ms % (60 * 1000)) // 1000
    milliseconds = ms % 1000
    return f"{hours:02}:{minutes:02}:{seconds:02},{milliseconds:03}"


class _PlayerBase:
    def set_video_widget(self, widget: QWidget):
        self._video_widget = widget

    def open(self, file_path: str) -> int:
        raise NotImplementedError()

    def play(self):
        raise NotImplementedError()

    def pause(self):
        raise NotImplementedError()

    def stop(self):
        raise NotImplementedError()

    def seek(self, ms: int):
        raise NotImplementedError()

    def duration(self) -> int:
        return 0

    def position(self) -> int:
        return 0

    def is_playing(self) -> bool:
        return False


class _QtMediaBackend(_PlayerBase):
    def __init__(self, parent: QWidget):
        from PyQt5.QtMultimedia import QMediaContent, QMediaPlayer
        from PyQt5.QtMultimediaWidgets import QVideoWidget

        self._parent = parent
        self._QMediaContent = QMediaContent
        self._QMediaPlayer = QMediaPlayer
        self._QVideoWidget = QVideoWidget

        self.mediaPlayer = QMediaPlayer(None, QMediaPlayer.VideoSurface)
        self.videoWidget = QVideoWidget(parent)
        self.videoWidget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.mediaPlayer.setVideoOutput(self.videoWidget)
        self._file_path = ""

    def set_video_widget(self, widget: QWidget):
        super().set_video_widget(widget)
        layout = widget.layout()
        if layout is None:
            layout = QVBoxLayout(widget)
            layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.videoWidget)

    def open(self, file_path: str) -> int:
        self._file_path = file_path
        self.mediaPlayer.stop()
        self.mediaPlayer.setMedia(self._QMediaContent(QUrl.fromLocalFile(file_path)))
        return self.duration()

    def play(self):
        self.mediaPlayer.play()

    def pause(self):
        self.mediaPlayer.pause()

    def stop(self):
        self.mediaPlayer.stop()

    def seek(self, ms: int):
        self.mediaPlayer.setPosition(int(ms))

    def duration(self) -> int:
        try:
            return int(self.mediaPlayer.duration())
        except Exception:
            return 0

    def position(self) -> int:
        try:
            return int(self.mediaPlayer.position())
        except Exception:
            return 0

    def is_playing(self) -> bool:
        try:
            return self.mediaPlayer.state() == self._QMediaPlayer.PlayingState
        except Exception:
            return False


class _FfplayBackend(_PlayerBase):
    """
    ffplay 播放后端（Windows 优先尝试嵌入到 Qt 容器）。
    由于 ffplay 没有稳定的运行时控制 API，这里采用“seek 即重启进程从指定时间播放”的策略，
    用 QElapsedTimer 近似刷新 position，驱动底部进度条与字幕滚动。
    """

    def __init__(self, parent: QWidget):
        self._parent = parent
        self._proc = QProcess(parent)
        self._proc.setProcessChannelMode(QProcess.MergedChannels)
        self._ffplay_path = self._find_ffplay()
        self._file_path = ""
        self._duration_ms = 0
        self._playing = False
        self._base_ms = 0
        self._timer = QElapsedTimer()

    @staticmethod
    def _find_ffplay() -> str:
        candidates = [
            "ffplay.exe",
            os.path.join(os.getcwd(), "ffmpeg", "bin", "ffplay.exe"),
            os.path.join(os.getcwd(), "bin", "ffplay.exe"),
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ffmpeg", "bin", "ffplay.exe"),
        ]
        for p in candidates:
            try:
                if os.path.isabs(p) and os.path.exists(p):
                    return os.path.normpath(p)
            except Exception:
                pass
        # 交给系统 PATH
        return "ffplay.exe"

    def _probe_duration_ms(self, file_path: str) -> int:
        try:
            from Service.videoUtils import _probe_video_duration_ms
            return int(_probe_video_duration_ms(file_path))
        except Exception:
            return 0

    def open(self, file_path: str) -> int:
        self._file_path = file_path
        self._duration_ms = self._probe_duration_ms(file_path)
        self.stop()
        return self._duration_ms

    def play(self):
        if not self._file_path:
            return
        if self._playing:
            return
        self._start_from(self.position())

    def pause(self):
        # ffplay 无稳定 pause 控制，这里用 stop 模拟
        self.stop()

    def stop(self):
        try:
            if self._proc.state() != QProcess.NotRunning:
                self._proc.kill()
                self._proc.waitForFinished(1000)
        except Exception:
            pass
        self._playing = False

    def seek(self, ms: int):
        if not self._file_path:
            return
        ms = max(0, int(ms))
        if self._duration_ms > 0:
            ms = min(ms, self._duration_ms)
        self._start_from(ms)

    def _start_from(self, ms: int):
        self.stop()
        self._base_ms = int(ms)
        self._timer.restart()
        self._playing = True

        ss = f"{ms / 1000.0:.3f}"
        args = [
            "-hide_banner",
            "-autoexit",
            "-loglevel", "error",
            "-ss", ss,
            "-i", self._file_path,
        ]
        # 不强制嵌入时也能用：默认显示窗口；后续会尝试嵌入（失败则忽略）
        self._proc.start(self._ffplay_path, args)

    def duration(self) -> int:
        return int(self._duration_ms or 0)

    def position(self) -> int:
        if not self._playing:
            return int(self._base_ms)
        try:
            return int(self._base_ms + self._timer.elapsed())
        except Exception:
            return int(self._base_ms)

    def is_playing(self) -> bool:
        return bool(self._playing)


@lru_cache(maxsize=None)
def _load_module(path: str):
    return import_module(path)


def _get_attr(module_path: str, attr_name: str):
    return getattr(_load_module(module_path), attr_name)


# 新增：字幕项构建线程
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
        self.video_player = None
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

        self.BottomPlayBtn.clicked.connect(self.toggle_play_pause)
        self.BottomPositionSlider.sliderMoved.connect(self.on_position_slider_moved)
        self.BottomPositionSlider.sliderReleased.connect(self.on_position_slider_released)

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

    def _reposition_video_hint(self):
        try:
            if self.VideoDropHint is None:
                return
            self.VideoDropHint.setGeometry(0, 0, self.CustomVideoWidget.width(), self.CustomVideoWidget.height())
            self.VideoDropHint.raise_()
        except Exception:
            pass

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._reposition_video_hint()

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
        # 内联播放器：优先 ffplay，失败则回退 QtMultimedia
        if self.CustomVideoWidget.layout() is None:
            self.CustomVideoWidget.setLayout(QVBoxLayout())
        self.CustomVideoWidget.layout().setContentsMargins(0, 0, 0, 0)

        try:
            self._player_backend = _FfplayBackend(self)
        except Exception:
            self._player_backend = None

        if self._player_backend is None:
            self._player_backend = _QtMediaBackend(self)

        self._player_backend.set_video_widget(self.CustomVideoWidget)

        if isinstance(self._position_poll_timer, QTimer):
            self._position_poll_timer.stop()
            self._position_poll_timer.deleteLater()
            self._position_poll_timer = None

        self._position_poll_timer = QTimer(self)
        self._position_poll_timer.setInterval(50)  # 高精度刷新
        self._position_poll_timer.timeout.connect(self._poll_position)
        self._position_poll_timer.start()

    def select_video_file(self, video_file=""):
        try:
            if not video_file:
                self.video_file, _ = QFileDialog.getOpenFileName(self, "Select File", "",
                                                                 "Video Files (*.mp4 *.avi *.mov *.mkv *.flv *.wmv *.mpeg *.mpg *.webm);;All Files (*)")
            else:
                self.video_file = video_file

            print(self.video_file)
            if self.video_file:
                # 只有再用到的时候，才初始化
                if not self._player_backend:
                    self._init_video_player()
                duration = self._player_backend.open(self.video_file)
                self._sync_duration(duration)
                self.CustomVideoWidget.setStyleSheet("""#CustomVideoWidget{border: 1px solid #ccc;}""")
                self._update_drop_hints()
        except Exception as e:
            print(e)
            QMessageBox.warning(self, "提示", str(e))

    def _sync_duration(self, duration_ms: int):
        duration_ms = int(duration_ms or 0)
        self.BottomPositionSlider.setRange(0, max(0, duration_ms))
        if duration_ms == 0:
            self.BottomTimeLabel.setText("00:00:00,000")
        else:
            self.BottomTimeLabel.setText(_format_time(0))

    def _poll_position(self):
        if not self._player_backend:
            return
        pos = int(self._player_backend.position() or 0)
        # 避免 sliderMoved 时抢焦点
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
        self.BottomTimeLabel.setText(_format_time(int(pos)))

    def on_position_slider_released(self):
        if not self._player_backend:
            return
        pos = int(self.BottomPositionSlider.value())
        self._player_backend.seek(pos)
        self.BottomPlayBtn.setText("暂停")

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
            if getattr(self, "VideoDropHint", None) is not None:
                self.VideoDropHint.setVisible(not bool(self.video_file))
                self._reposition_video_hint()
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

        # 全量重建（仅切换文件时），使用线程批量构建
        self._clear_subtitle_items()
        self._rebuild_subtitle_items_batch()

    def _clear_subtitle_items(self):
        """清空字幕控件"""
        # 禁用容器以提升性能
        # self.SubListContainer.setUpdatesEnabled(False)
        # 批量删除控件
        for w in self.subtitle_widgets:
            w.deleteLater()
        self.subtitle_widgets.clear()
        # 重新启用更新
        # self.SubListContainer.setUpdatesEnabled(True)

    def _reindex_subtitles(self):
        for i, sub in enumerate(self.subtitles):
            sub["index"] = i + 1

    def _rebuild_subtitle_items_batch(self):
        """批量重建字幕项（线程化）"""
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

        # self._reindex_subtitles()
        #
        # # 对齐角色列表长度
        # while len(self.role_match_list) < len(self.subtitles):
        #     self.role_match_list.append(self.roles_model.item(0).text())
        # if len(self.role_match_list) > len(self.subtitles):
        #     self.role_match_list = self.role_match_list[: len(self.subtitles)]
        #
        # # 创建构建线程
        # self.builder = SubtitleItemBuilder(
        #     self.subtitles,
        #     self.role_match_list,
        #     self.roles_model
        # )
        # # 绑定线程信号
        # self.builder.finished.connect(self._on_items_built)
        # self.builder.start()

    # def _on_items_built(self, widgets):
    #     """线程构建完成后的UI处理"""
    #     # 禁用容器以提升性能
    #     # self.SubListContainer.setUpdatesEnabled(False)
    #
    #     # 批量添加控件并绑定事件
    #     for i, w in enumerate(widgets):
    #         w.changed.connect(self.on_subtitle_item_changed)
    #         w.insertAbove.connect(self.on_subtitle_insert_above)
    #         w.insertBelow.connect(self.on_subtitle_insert_below)
    #         w.deleteRequested.connect(self.on_subtitle_delete)
    #         self.container_layout.addWidget(w)
    #         self.subtitle_widgets.append(w)

        # 恢复容器更新
        # self.SubListContainer.setUpdatesEnabled(True)
        # self.SubListContainer.update()

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
        if isinstance(self._position_poll_timer, QTimer):
            self._position_poll_timer.stop()
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
                if getattr(self, "VideoDropHint", None) is not None:
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
        if getattr(self, "VideoDropHint", None) is not None:
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

    def on_general_task_finished(self, msg):
        print(msg)
        QMessageBox.information(self, "提示", msg)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = SubtitleEditorInterface()
    window.show()
    sys.exit(app.exec_())