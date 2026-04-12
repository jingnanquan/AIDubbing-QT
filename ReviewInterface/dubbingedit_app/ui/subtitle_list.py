from __future__ import annotations

from typing import Any, Callable, Optional

from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QVBoxLayout, QWidget

from qfluentwidgets import BodyLabel, CardWidget, CaptionLabel, ScrollArea, StrongBodyLabel, SubtitleLabel


class _SubtitleCard(CardWidget):
    clicked_index = pyqtSignal(int)

    def __init__(self, list_index: int, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.list_index = list_index
        self._title = StrongBodyLabel("", self)
        self._meta = CaptionLabel("", self)
        self._body = BodyLabel("", self)
        self._body.setWordWrap(True)
        self._meta.setFont(QFont("Microsoft YaHei", 11))
        self._body.setFont(QFont("Microsoft YaHei", 13))


        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.addWidget(self._title)
        lay.addWidget(self._meta)
        lay.addWidget(self._body)

        self.original_style = """
                CardWidget {
                    background-color: rgba(200, 200, 200, 0.6);
                    border: 1px solid rgba(200, 200, 200, 0.8);
                    border-radius: 8px;
                }
            """
        self.setStyleSheet(self.original_style)
        self.setCursor(Qt.PointingHandCursor)
        self._setup_hover_effect()

    def enterEvent(self, event) -> None:
        self._set_hover_style(True)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._set_hover_style(False)
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._flash_effect()
            self.clicked_index.emit(self.list_index)
        super().mousePressEvent(event)

    def _setup_hover_effect(self) -> None:
        self._is_hovering = False

    def _set_hover_style(self, hover: bool) -> None:
        self._is_hovering = hover
        if hover:
            self.setStyleSheet("""
                CardWidget {
                    background-color: rgba(74, 144, 217, 0.1);
                    border: 1px solid rgba(74, 144, 217, 0.4);
                    border-radius: 8px;
                }
            """)
        else:
            self.setStyleSheet(self.original_style)

    def _flash_effect(self) -> None:
        original_style = self.original_style
        self.setStyleSheet("""
            CardWidget {
                background-color: rgba(74, 144, 217, 0.4);
                border: 2px solid #4A90D9;
                border-radius: 8px;
            }
        """)

        QTimer.singleShot(150, lambda: self._restore_style(original_style))

    def _restore_style(self, original_style: str) -> None:
        if self._is_hovering:
            self._set_hover_style(True)
        else:
            self.setStyleSheet(original_style)

    def set_content(self, index: int, start: str, end: str, role: str, text: str) -> None:
        self._title.setText(f"#{index}")
        self._meta.setText(f"{start} → {end}  ·  <b>{role}</b>")
        self._body.setText(text)

    def set_highlight(self, on: bool) -> None:
        if on:
            self.setStyleSheet(
                "CardWidget { background-color: rgba(200, 200, 200, 0.6);border: 2px solid #4A90D9; border-radius: 8px; font-weight: bold; }"
            )
        else:
            self.setStyleSheet(self.original_style)


class SubtitleListPanel(QWidget):
    """右侧字幕列表：卡片展示，点击发出索引；高亮当前时间所在条。"""

    block_selected = pyqtSignal(int)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._cards: list[_SubtitleCard] = []
        self._current_highlight: int = -1
        self._time_ms_fn: Optional[Callable[[], int]] = None
        self._subtitles: list[dict[str, Any]] = []
        self._roles: list[str] = []

        self._container = QWidget(self)
        self._container.setObjectName("SubtitleListContainer")
        self._vbox = QVBoxLayout(self._container)
        self._vbox.setContentsMargins(8, 8, 8, 8)
        self._vbox.setSpacing(10)

        self._scroll = ScrollArea(self)
        self._scroll.setObjectName("SubtitleListScroll")
        self._scroll.setWidget(self._container)
        self._scroll.setWidgetResizable(True)
        self._scroll.setStyleSheet("""
            #SubtitleListScroll {
                background-color: rgba(248, 248, 248, 0.5);
                border: 1px solid rgba(0, 0, 0, 0.1);
                border-radius: 8px;
                padding: 4px;
            }
            #SubtitleListContainer {
                background: transparent;
            }
        """)



        title = SubtitleLabel("字幕列表", self)
        root = QVBoxLayout(self)
        root.addWidget(title)
        root.addWidget(self._scroll, 1)

        self.setMinimumWidth(400)

    def set_time_provider(self, fn: Callable[[], int]) -> None:
        self._time_ms_fn = fn

    def set_subtitles(self, subtitles: list[dict[str, Any]], roles: list[str]) -> None:
        self.clear_highlight()
        self._subtitles = subtitles
        self._roles = roles
        for c in self._cards:
            c.deleteLater()
        self._cards.clear()

        while self._vbox.count():
            item = self._vbox.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

        for i, sub in enumerate(subtitles):
            role = roles[i] if i < len(roles) and roles else "default"
            card = _SubtitleCard(i, self._container)
            card.set_content(sub["index"], sub["start"], sub["end"], role, sub["text"])
            card.clicked_index.connect(self._on_card_clicked)
            self._vbox.addWidget(card)
            self._cards.append(card)
        self._vbox.addStretch(1)

    def _on_card_clicked(self, idx: int) -> None:
        self.block_selected.emit(idx)

    def clear_highlight(self) -> None:
        if 0 <= self._current_highlight < len(self._cards):
            self._cards[self._current_highlight].set_highlight(False)
        self._current_highlight = -1

    def refresh_card_text(self, idx: int, text: str) -> None:
        if 0 <= idx < len(self._cards) and 0 <= idx < len(self._subtitles):
            sub = self._subtitles[idx]
            role = self._roles[idx] if idx < len(self._roles) and self._roles else "default"
            self._cards[idx].set_content(sub["index"], sub["start"], sub["end"], role, text)

    def update_playhead(self, position_ms: int) -> None:
        if not self._subtitles:
            return
        from ReviewInterface.dubbingedit_app.core.subtitle_parser import timecode_to_ms

        active = -1
        for i, sub in enumerate(self._subtitles):
            s = timecode_to_ms(sub["start"])
            e = timecode_to_ms(sub["end"])
            if s <= position_ms < e:
                active = i
                break
        if active == self._current_highlight:
            if active >= 0 and active < len(self._cards):
                self._scroll.ensureWidgetVisible(self._cards[active])
            return
        self.clear_highlight()
        if active >= 0:
            self._cards[active].set_highlight(True)
            self._current_highlight = active
            self._scroll.ensureWidgetVisible(self._cards[active])
