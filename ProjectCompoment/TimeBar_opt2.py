import copy
import re
from PyQt5.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsItem, QGraphicsLineItem, QGraphicsRectItem, QGraphicsSimpleTextItem, QVBoxLayout, QFrame
from PyQt5.QtCore import Qt, QRectF, pyqtSignal, QPointF
from PyQt5.QtGui import QPainter, QColor, QPen, QFont
from ProjectCompoment.TrackBar_opt2 import TrackBarItem

class TimeBarItem(QGraphicsItem):
    def __init__(self, total_ms, scale=100, height=48, offset=5):
        super().__init__()
        self.total_ms = total_ms
        self.scale = scale
        self.height = height
        self.offset = offset
        self.setFlag(QGraphicsItem.ItemUsesExtendedStyleOption)

    def boundingRect(self):
        total_seconds = int(self.total_ms / 1000)
        px_per_sec = self.scale
        total_length = total_seconds * px_per_sec
        w = total_length + self.offset * 2
        h = self.height
        return QRectF(0, 0, w, h)

    def paint(self, painter, option, widget=None):
        painter.fillRect(self.boundingRect(), QColor(245, 245, 245))
        px_per_sec = self.scale
        total_seconds = int(self.total_ms / 1000)
        font = QFont("Microsoft YaHei", 10, QFont.Normal)
        painter.setFont(font)
        sub_ticks = 10
        if px_per_sec <= 100:
            sub_ticks = 5
        if px_per_sec <= 50:
            sub_ticks = 2
        for sec in range(total_seconds + 1):
            x = int(sec * px_per_sec) + self.offset
            painter.setPen(QPen(QColor(80, 80, 80), 2))
            painter.drawLine(x, 0, x, 13)
            if px_per_sec >= 20:
                painter.drawText(x - 4, 25, f"{sec}s")
            if sec < total_seconds:
                for i in range(1, sub_ticks):
                    sub_x = x + int(i * px_per_sec / sub_ticks)
                    painter.setPen(QPen(QColor(160, 160, 160), 1))
                    painter.drawLine(sub_x, 0, sub_x, 8)

class TimeLineItem(QGraphicsLineItem):
    def __init__(self, y_start, y_end, x=0):
        super().__init__(x, y_start, x, y_end)
        self.setPen(QPen(Qt.red, 2))
        self.setZValue(1000)  # 保证在最上层

    def set_x(self, x, y_start, y_end):
        self.setLine(x, y_start, x, y_end)

class TrackWidget(QGraphicsView):
    slider_changed = pyqtSignal(int)

    def __init__(self, total_ms, parent=None, init_scale=100, subtitles=None, project=None):
        scene = QGraphicsScene(parent)
        super().__init__(scene, parent)
        self.setRenderHint(QPainter.Antialiasing)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setFrameShape(QFrame.NoFrame)
        self.setViewportUpdateMode(QGraphicsView.BoundingRectViewportUpdate)
        self.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.total_ms = total_ms
        self.scale = init_scale
        self.offset = 5
        self.trackbars = []
        self.timebar_item = None
        self.timeline_item = None
        self.trackbar_items = []
        self.trackbar_height = 50
        self.timebar_height = 48
        self.subtitles = copy.deepcopy(subtitles) if subtitles else []
        self.project = copy.deepcopy(project) if project else None
        if self.project and self.subtitles:
            role_colors = [
                "#FF6F61", "#FF99C8", "#6BCB77", "#727AE6", "#F8333C", "#FFD93D", "#A66CFF", "#FF922B", "#43C6AC",
            ]
            rolename_to_color = {}
            color_idx = 0
            for subtitle in self.subtitles:
                rolename = subtitle.role_name
                if rolename not in rolename_to_color:
                    rolename_to_color[rolename] = role_colors[color_idx % len(role_colors)]
                    color_idx = (color_idx + 1) % len(role_colors)
            self.original_time_list = [
                [self.time_str_to_ms(subtitle.start_time), self.time_str_to_ms(subtitle.end_time), rolename_to_color[subtitle.role_name]]
                for subtitle in self.subtitles
            ]
            self.target_time_list = [
                [self.time_str_to_ms(subtitle.start_time), self.time_str_to_ms(subtitle.start_time) + subtitle.dubbing_duration, rolename_to_color[subtitle.role_name]]
                for subtitle in self.subtitles
            ]
            # 添加时间轴
            self.timebar_item = TimeBarItem(self.total_ms, scale=self.scale, height=self.timebar_height, offset=self.offset)
            scene.addItem(self.timebar_item)
            # 添加轨道
            y = self.timebar_height
            self.bgm_trackbar_item = TrackBarItem([], audio_path=self.project.original_bgm_audio_path, scale=self.scale, height=self.trackbar_height)
            self.bgm_trackbar_item.setPos(0, y)
            scene.addItem(self.bgm_trackbar_item)
            y += self.trackbar_height
            self.original_voice_trackbar_item = TrackBarItem(self.original_time_list, audio_path=self.project.original_voice_audio_path, scale=self.scale, height=self.trackbar_height)
            self.original_voice_trackbar_item.setPos(0, y)
            scene.addItem(self.original_voice_trackbar_item)
            y += self.trackbar_height
            self.target_voice_trackbar_item = TrackBarItem(self.target_time_list, audio_path=self.project.target_voice_audio_path, scale=self.scale, height=self.trackbar_height)
            self.target_voice_trackbar_item.setPos(0, y)
            scene.addItem(self.target_voice_trackbar_item)
            self.trackbar_items = [self.bgm_trackbar_item, self.original_voice_trackbar_item, self.target_voice_trackbar_item]
            # 添加时间线（最上层）
            self.timeline_item = TimeLineItem(0, y + self.trackbar_height)
            scene.addItem(self.timeline_item)
            self.setSceneRect(0, 0, self.timebar_item.boundingRect().width(), y + self.trackbar_height)
            self.update_timeline(0)

    def update_timeline(self, ms):
        x = int((ms / 1000.0) * self.scale) + self.offset
        y_start = 0
        y_end = self.sceneRect().height()
        if self.timeline_item:
            self.timeline_item.set_x(x, y_start, y_end)

    def on_scale_changed(self, value):
        self.scale = value
        if self.timebar_item:
            self.timebar_item.scale = value
            self.timebar_item.update()
        for item in self.trackbar_items:
            item.set_scale(value)
        self.setSceneRect(0, 0, self.timebar_item.boundingRect().width(), self.sceneRect().height())
        self.update()

    def repaint_wave(self):
        for item in self.trackbar_items:
            item._load_waveform()
            item.update()

    def on_timebar_changed(self, ms):
        self.update_timeline(ms)
        self.update()

    def time_str_to_ms(self, time_str: str) -> float:
        match = re.match(r'(\d{2}):(\d{2}):(\d{2}),(\d{3})', time_str)
        if not match:
            raise ValueError(f"无效的时间格式: {time_str}")
        hours, minutes, seconds, milliseconds = map(int, match.groups())
        return (hours * 3600 + minutes * 60 + seconds) * 1000 + milliseconds
