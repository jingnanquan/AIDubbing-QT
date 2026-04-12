from __future__ import annotations

from typing import Optional

from PyQt5.QtCore import QObject, QTimer, QUrl
from PyQt5.QtMultimedia import QMediaContent, QMediaPlayer

from ReviewInterface.dubbingedit_app.core.workspace_paths import WorkspacePaths


class PlaybackController(QObject):
    """主视频（静音）+ 三路辅音轨同步播放。"""

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._paths: Optional[WorkspacePaths] = None

        self.video_player = QMediaPlayer(self, QMediaPlayer.VideoSurface)
        self.video_player.setMuted(True)

        self.bgm_player = QMediaPlayer(self, QMediaPlayer.LowLatency)
        self.vocal_player = QMediaPlayer(self, QMediaPlayer.LowLatency)
        self.dub_player = QMediaPlayer(self, QMediaPlayer.LowLatency)

        self.bgm_enabled = True
        self.vocal_enabled = False
        self.dub_enabled = True

        self._sync_timer = QTimer(self)
        self._sync_timer.setInterval(120)
        self._sync_timer.timeout.connect(self._sync_aux_positions)

        self.video_player.stateChanged.connect(self._on_video_state)

    def set_paths(self, paths: WorkspacePaths) -> None:
        self._paths = paths
        self.stop()

        self.video_player.setMedia(QMediaContent(QUrl.fromLocalFile(paths.dubbed_video)))
        if paths.background:
            self.bgm_player.setMedia(QMediaContent(QUrl.fromLocalFile(paths.background)))
        else:
            self.bgm_player.setMedia(QMediaContent())
        if paths.vocal:
            self.vocal_player.setMedia(QMediaContent(QUrl.fromLocalFile(paths.vocal)))
        else:
            self.vocal_player.setMedia(QMediaContent())
        self.dub_player.setMedia(QMediaContent(QUrl.fromLocalFile(paths.dub_vocal_audio)))

        self.apply_track_mutes()
        self._seek_all(0)

    def clear(self) -> None:
        self._paths = None
        self.stop()
        self.video_player.setMedia(QMediaContent())
        self.bgm_player.setMedia(QMediaContent())
        self.vocal_player.setMedia(QMediaContent())
        self.dub_player.setMedia(QMediaContent())

    def apply_track_mutes(self) -> None:
        if self._paths and self._paths.background:
            self.bgm_player.setMuted(not self.bgm_enabled)
        else:
            self.bgm_player.setMuted(True)
        if self._paths and self._paths.vocal:
            self.vocal_player.setMuted(not self.vocal_enabled)
        else:
            self.vocal_player.setMuted(True)
        self.dub_player.setMuted(not self.dub_enabled)

    def set_bgm_enabled(self, on: bool) -> None:
        self.bgm_enabled = on
        self.apply_track_mutes()
        self._update_aux_player_states()

    def set_vocal_enabled(self, on: bool) -> None:
        self.vocal_enabled = on
        self.apply_track_mutes()
        self._update_aux_player_states()

    def set_dub_enabled(self, on: bool) -> None:
        self.dub_enabled = on
        self.apply_track_mutes()
        self._update_aux_player_states()

    def play(self) -> None:
        pos = self.video_player.position()
        self._seek_all(pos)
        self.video_player.play()
        if self._paths and self._paths.background and self.bgm_enabled:
            self.bgm_player.play()
        if self._paths and self._paths.vocal and self.vocal_enabled:
            self.vocal_player.play()
        if self.dub_enabled:
            self.dub_player.play()
        self._sync_timer.start()

    def pause(self) -> None:
        self.video_player.pause()
        self.bgm_player.pause()
        self.vocal_player.pause()
        self.dub_player.pause()
        self._sync_timer.stop()

    def stop(self) -> None:
        self._sync_timer.stop()
        self.video_player.stop()
        self.bgm_player.stop()
        self.vocal_player.stop()
        self.dub_player.stop()

    def toggle_play(self) -> None:
        if self.video_player.state() == QMediaPlayer.PlayingState:
            self.pause()
        else:
            self.play()

    def seek(self, position_ms: int) -> None:
        self._seek_all(position_ms)

    def duration_ms(self) -> int:
        d = self.video_player.duration()
        return max(0, d)

    def position_ms(self) -> int:
        return self.video_player.position()

    def _seek_all(self, position_ms: int) -> None:
        self.video_player.setPosition(position_ms)
        self.bgm_player.setPosition(position_ms)
        self.vocal_player.setPosition(position_ms)
        self.dub_player.setPosition(position_ms)

    def _on_video_state(self, state: QMediaPlayer.State) -> None:
        if state == QMediaPlayer.PlayingState:
            if self._paths and self._paths.background and self.bgm_enabled and self.bgm_player.state() != QMediaPlayer.PlayingState:
                self.bgm_player.play()
            if self._paths and self._paths.vocal and self.vocal_enabled and self.vocal_player.state() != QMediaPlayer.PlayingState:
                self.vocal_player.play()
            if self.dub_enabled and self.dub_player.state() != QMediaPlayer.PlayingState:
                self.dub_player.play()
            self._sync_timer.start()
        elif state == QMediaPlayer.PausedState:
            self.bgm_player.pause()
            self.vocal_player.pause()
            self.dub_player.pause()
            self._sync_timer.stop()
        elif state == QMediaPlayer.StoppedState:
            self.bgm_player.stop()
            self.vocal_player.stop()
            self.dub_player.stop()
            self._sync_timer.stop()

    def _update_aux_player_states(self) -> None:
        if self.video_player.state() == QMediaPlayer.PlayingState:
            if self._paths and self._paths.background and self.bgm_enabled and self.bgm_player.state() != QMediaPlayer.PlayingState:
                self.bgm_player.play()
            elif not self.bgm_enabled and self.bgm_player.state() == QMediaPlayer.PlayingState:
                self.bgm_player.pause()

            if self._paths and self._paths.vocal and self.vocal_enabled and self.vocal_player.state() != QMediaPlayer.PlayingState:
                self.vocal_player.play()
            elif not self.vocal_enabled and self.vocal_player.state() == QMediaPlayer.PlayingState:
                self.vocal_player.pause()

            if self.dub_enabled and self.dub_player.state() != QMediaPlayer.PlayingState:
                self.dub_player.play()
            elif not self.dub_enabled and self.dub_player.state() == QMediaPlayer.PlayingState:
                self.dub_player.pause()

    def _sync_aux_positions(self) -> None:
        if self.video_player.state() != QMediaPlayer.PlayingState:
            return
        pos = self.video_player.position()
        for p in (self.bgm_player, self.vocal_player, self.dub_player):
            if p.state() != QMediaPlayer.PlayingState:
                continue
            if abs(p.position() - pos) > 180:
                p.setPosition(pos)

    def reload_dub_track(self) -> None:
        if not self._paths:
            return
        from PyQt5.QtMultimedia import QMediaPlayer

        pos = self.video_player.position()
        was_playing = self.video_player.state() == QMediaPlayer.PlayingState
        self.dub_player.setMedia(QMediaContent(QUrl.fromLocalFile(self._paths.dub_vocal_audio)))
        self.dub_player.setPosition(pos)
        self.apply_track_mutes()
        if was_playing and self.dub_enabled:
            self.dub_player.play()

    def shutdown(self) -> None:
        self.stop()
