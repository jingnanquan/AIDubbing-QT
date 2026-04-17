import logging
import os
import sys

from PyQt5.QtCore import pyqtSignal, Qt, QUrl, QThread, QTimer
from PyQt5.QtWidgets import QWidget, QMainWindow, QVBoxLayout, QScrollArea, QGridLayout, QHBoxLayout, QSizePolicy, \
    QApplication
from qfluentwidgets.multimedia import SimpleMediaPlayBar
from qfluentwidgets import IndeterminateProgressRing, ToolButton, FluentIcon, BodyLabel, InfoBar, InfoBarPosition

from Compoment.DubbingParamParams import prepared_voices, spare_voices
from Compoment.HistoryCard import VoiceCardItem
from Config import resource_path


# # 需要区分欧美和亚洲
# language_region = {
#     "English": "en",
#     "Chinese (Simplified)": "zh",
#     "Chinese (Traditional)": "zh-TW",
#     "Japanese": "jp",
#     "Korean": "ko",
#     "French": "fr",
#     "German": "de",
#     "Spanish": "es",
#     "Portuguese": "pt",
#     "Russian": "ru",
#     "Italian": "it",
#     "Dutch": "nl",
#     "Polish": "pl",
#     "Turkish": "tr",
#     "Arabic": "ar",
#     "Hindi": "hi",
#     "Vietnamese": "vi",
#     "Thai": "th",
#     "Indonesian": "id",
#     "Czech": "cs",
#     "Swedish": "sv",
#     "Danish": "da",
#     "Finnish": "fi",
#     "Greek": "el"
# }
#
# language_cps = {
#     "英语": 23,
#     "汉语": 15,
#     "日语": 17,
#     "韩语": 16,
#     "法语": 21,
#     "葡萄牙语": 20,
#     "俄罗斯语": 18,
#     "越南语": 22,
#     "泰语": 22,
#     "印尼语": 18
# }
#
# language_code = {
#     "英语": "en",
#     "汉语": "zh",
#     "日语": "ja",
#     "韩语": "ko",
#     "法语": "fr",
#     "葡萄牙语": "pt",
#     "俄罗斯语": "ru",
#     "越南语": "vi",
#     "泰语": "th",
#     "印尼语": "id"
# }
#
# # 幼年、少年、青中年、中老年、老年   os.path.join(resource_path, "prepared_voices","default.mp3"
# prepared_voices = {
#     # "默认声音":                   ["uju3wxzG5OhpWcoi3SMy", os.path.join(resource_path, "prepared_voices","default.mp3")],
#     "小孩-女-Daniela":            [  "tTdCI0IDTgFa2iLQiWu4", os.path.join(resource_path, "prepared_voices","小孩-女-Daniela.mp3")],
#     "青年-女-Lily-Wolff":        [  "qBDvhofpxp92JgXJxDjB", os.path.join(resource_path, "prepared_voices","青年-女-Lily-Wolff.mp3")],
#     "青年-女-Alexandra":         [  "kdmDKE6EkgrWrrykO9Qt", os.path.join(resource_path, "prepared_voices","青年-女-Alexandra.mp3")],
#     "青年-女-Ivanan":            [  "4NejU5DwQjevnR6mh3mb", os.path.join(resource_path, "prepared_voices","青年-女-Ivanan.mp3")],
#     "青年-女-Hope":              [  "tnSpp4vdxKPjI9w0GnoV", os.path.join(resource_path, "prepared_voices","青年-女-Hope.mp3")],
#     "青年-女-Tanya":             [  "DusxpIechtn2D8hID1Jy", os.path.join(resource_path, "prepared_voices","青年-女-Tanya.mp3")],
#     "青年-男-Hey Its Brad":      [  "f5HLTX707KIM4SzJYzSz", os.path.join(resource_path, "prepared_voices","青年-男-HeyItsBrad.mp3")],
#     "青年-男-Mark":              [  "UgBBYS2sOqTuMpoF3BR0", os.path.join(resource_path, "prepared_voices","青年-男-Mark.mp3")],
#     "青年-男-Patrack":           [  "IoYPiP0wwoQzmraBbiju", os.path.join(resource_path, "prepared_voices","青年-男-Patrack.mp3")],
#     "青年-男-Viraj":             [  "bajNon13EdhNMndG3z05", os.path.join(resource_path, "prepared_voices","青年-男-Viraj.mp3")],
#     "青年-男-Asher":             [  "tCI2WpOKOENuucvQrEeR", os.path.join(resource_path, "prepared_voices","青年-男-Asher.mp3")],
#     "中年-女-Alexis Lancaster":  [  "O4fnkotIypvedJqBp4yb", os.path.join(resource_path, "prepared_voices","中年-女-AlexisLancaster.mp3")],
#     "中年-女-Kylee_M":           [  "pcKdPWtbF6bM9o7NHjCI", os.path.join(resource_path, "prepared_voices","中年-女-Kylee_M.mp3")],
#     "中年-女-Beatrice":          [  "kkPJzQOWz2Oz9cUaEaQd", os.path.join(resource_path, "prepared_voices","中年-女-Beatrice.mp3")],
#     "中年-男-Peter":             [  "ZthjuvLPty3kTMaNKVKb", os.path.join(resource_path, "prepared_voices","中年-男-Peter.mp3")],
#     "中年-男-Professor Bill":    [  "lnieQLGTodpbhjpZtg1k", os.path.join(resource_path, "prepared_voices","中年-男-ProfessorBill.mp3")],
#     "中年-男-Shrey":             [  "x3gYeuNB0kLLYxOZsaSh", os.path.join(resource_path, "prepared_voices","中年-男-Shrey.mp3")],
#     "老年-女-Leesie":             [   "FOBaORWwYmHBGhidTqtx", os.path.join(resource_path, "prepared_voices","老年-女-Leesie.mp3")],
#     "老年-女-Fantine Art":        [   "LBy8sNrEohVcRSkF8TAd", os.path.join(resource_path, "prepared_voices","老年-女-FantineArt.mp3")],
#     "老年-男-Oxley":              [   "NOpBlnGInO9m6vDvFkFC", os.path.join(resource_path, "prepared_voices","老年-男-Oxley.mp3")],
#     "老年-男-Ralf Eisend":        [   "A9evEp8yGjv4c3WsIKuY", os.path.join(resource_path, "prepared_voices","老年-男-RalfEisend.mp3")],
# }
#
#
# spare_voices = {
#     "自动克隆":  ["", ""],
#     "不配音": ["",""],
#     "默认声音":  ["uju3wxzG5OhpWcoi3SMy", os.path.join(resource_path, "prepared_voices", "default.mp3")],
# }

# from functools import lru_cache
# from importlib import import_module
#
# @lru_cache(maxsize=None)
# def _load_module(path: str):
#     return import_module(path)
#
#
# def _get_attr(module_path: str, attr_name: str):
#     return getattr(_load_module(module_path), attr_name)
#
#

class VoiceLoaderWorker(QThread):
    voice_dict_loaded = pyqtSignal(dict, list)  # 成功时发射

    # @pyqtSlot()
    def run(self):
        try:
            from Service.datasetUtils import datasetUtils
            # datasetUtils = _get_attr("Service.datasetUtils", "datasetUtils")
            voiceDict1 = datasetUtils.getInstance().query_voice_id(1)

            # voice_module = _load_module("Compoment.DubbingParamParams")
            # spare_voices = getattr(voice_module, "spare_voices")
            # prepared_voices = getattr(voice_module, "prepared_voices")

            voiceDict2 = {key: [value, ""] for key, value in voiceDict1.items()}
            voiceDict = spare_voices | voiceDict2 | prepared_voices
            voiceNameList = list(voiceDict.keys())

            self.voice_dict_loaded.emit(voiceDict, voiceNameList)
        except Exception as exc:
            logging.error(f"加载声音资源失败: {exc}")
            self.voice_dict_loaded.emit({}, [])


class VoiceSelectorWindow(QMainWindow):
    return_signal = pyqtSignal(str)
    return_signal2 = pyqtSignal(str, str)

    def __init__(self, voices: dict = prepared_voices):
        super().__init__()

        print("开始初始化")
        self.setWindowTitle("声音列表")
        self.setMinimumWidth(750)
        self.setMinimumHeight(600)
        self.voices_dict = voices
        self._voice_loader_worker = None
        self._pull_voice_worker = None
        self._is_refreshing = False
        self.initUI()

    def initUI(self):
        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # 创建主布局
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10,10,10,10)

        # 创建标题栏布局（包含刷新按钮）
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(5,5,5,5)
        # header_layout.addStretch()

        self._refresh_btn = ToolButton(FluentIcon.UPDATE)
        self._refresh_btn.setToolTip("拉取并刷新最新声音列表")
        # self._refresh_btn.setFixedSize(30, 30)
        self._refresh_btn.clicked.connect(self._on_refresh_clicked)
        header_layout.addWidget(self._refresh_btn, alignment=Qt.AlignLeft)

        main_layout.addLayout(header_layout)

        # 创建并配置QScrollArea，命名为VoiceScroll
        self.VoiceScroll = QScrollArea()
        self.VoiceScroll.setWidgetResizable(True)  # 允许内容自动调整大小
        self.VoiceScroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.VoiceScroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.HistoryCardContainer = QWidget()

        self.HistoryCardContainer.setObjectName("HistoryCardContainer")
        self.HistoryCardContainer.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Minimum)

        self.VoiceLayout = QGridLayout()
        self.VoiceLayout.setAlignment(Qt.AlignTop)  # 内容顶部对齐
        self.VoiceLayout.setSpacing(10)
        self.VoiceLayout.setContentsMargins(5,5,9,5)

        self.audio_bar = SimpleMediaPlayBar()
        self.HistoryCardContainer.setLayout(self.VoiceLayout)
        # 将容器添加到滚动区域
        self.VoiceScroll.setWidget(self.HistoryCardContainer)
        self.VoiceScroll.setStyleSheet(
            """ QScrollArea{ background: transparent;border: None; } #HistoryCardContainer{ background: transparent; } """)

        main_layout.addWidget(self.VoiceScroll)
        main_layout.addWidget(self.audio_bar)
        central_widget.setLayout(main_layout)

        # 创建加载遮罩层（参照 edit_panel.py）
        self._overlay = QWidget(self)
        self._overlay.setStyleSheet("QWidget { background: rgba(255,255,255,0.72); }")
        ov = QVBoxLayout(self._overlay)
        ov.addStretch(1)
        self._ring = IndeterminateProgressRing(self._overlay)
        self._ring.setFixedSize(64, 64)
        self._ring_label = BodyLabel("正在刷新声音列表…", self._overlay)
        hl = QHBoxLayout()
        hl.addStretch(1)
        hl.addWidget(self._ring)
        hl.addStretch(1)
        ov.addLayout(hl)
        hl2 = QHBoxLayout()
        hl2.addStretch(1)
        hl2.addWidget(self._ring_label)
        hl2.addStretch(1)
        ov.addLayout(hl2)
        ov.addStretch(1)
        self._overlay.hide()
        self._overlay.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self._render_voice_cards()
        self.adjust_width()

    def _render_voice_cards(self):
        """渲染声音卡片"""
        # 清除现有卡片
        while self.VoiceLayout.count():
            item = self.VoiceLayout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # 计算行和列的位置
        row = 0
        col = 0
        for key, value in self.voices_dict.items():
            print(key, value)
            card = VoiceCardItem(key, value[1], value[0])
            card.btn_signal.connect(self.return_voice)
            card.self_click.connect(self.set_voice_url)
            # 添加到网格布局中
            self.VoiceLayout.addWidget(card, row, col)

            # 更新列和行位置
            col += 1
            if col >= 2:  # 每行两个元素
                col = 0
                row += 1

    def _on_refresh_clicked(self):
        """刷新按钮点击处理"""
        if self._is_refreshing:
            return

        self._is_refreshing = True
        self._refresh_btn.setEnabled(False)
        self._show_loading_overlay("正在刷新声音列表…")

        # 使用 PullVoiceWorker 从云端拉取声音
        from ThreadWorker.SubtitleInterfaceWorker import PullVoiceWorker
        self._pull_voice_worker = PullVoiceWorker()
        self._pull_voice_worker.finished.connect(self._on_pull_voice_finished)
        self._pull_voice_worker.start()

    def _on_pull_voice_finished(self, message: str):
        """拉取声音完成后的处理"""
        print(message)

        # 断开并清理 PullVoiceWorker
        if self._pull_voice_worker:
            self._pull_voice_worker.finished.disconnect(self._on_pull_voice_finished)
            self._pull_voice_worker = None

        self._is_refreshing = True
        self._refresh_btn.setEnabled(False)
        self._show_loading_overlay("正在加载声音列表…")

        # 检查是否失败（失败消息通常包含"出错"关键字）
        if "出错" in message or "失败" in message:
            self._is_refreshing = False
            self._refresh_btn.setEnabled(True)
            self._hide_loading_overlay()
            InfoBar.error(
                title="刷新失败",
                content=message,
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP_RIGHT,
                duration=5000,
                parent=self,
            )
            return

        # 重新加载声音列表
        self._voice_loader_worker = VoiceLoaderWorker()
        self._voice_loader_worker.voice_dict_loaded.connect(self._on_voice_dict_loaded)
        self._voice_loader_worker.start()

    def _on_voice_dict_loaded(self, voice_dict: dict, voice_name_list: list):
        """声音字典加载完成"""
        # 断开并清理 VoiceLoaderWorker
        if self._voice_loader_worker:
            self._voice_loader_worker.voice_dict_loaded.disconnect(self._on_voice_dict_loaded)
            self._voice_loader_worker = None

        # 检查是否加载失败（返回空字典）
        if not voice_dict:
            self._is_refreshing = False
            self._refresh_btn.setEnabled(True)
            self._hide_loading_overlay()
            InfoBar.error(
                title="加载失败",
                content="加载声音列表失败，请重试",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP_RIGHT,
                duration=5000,
                parent=self,
            )
            return

        # 更新声音数据
        self.voices_dict = voice_dict
        self.voiceNameList = voice_name_list

        # 重新渲染卡片
        self._render_voice_cards()

        # 隐藏遮罩层
        self._is_refreshing = False
        self._refresh_btn.setEnabled(True)
        self._hide_loading_overlay()
        self.adjust_width()

    def _show_loading_overlay(self, msg: str=""):
        """显示加载遮罩层"""
        self._overlay.resize(self.size())
        self._overlay.move(0, 0)
        if msg:
            self._ring_label.setText(msg)
        self._overlay.show()
        self._overlay.raise_()

    def _hide_loading_overlay(self):
        """隐藏加载遮罩层"""
        self._overlay.hide()

    def return_voice(self, voice_name, voice_id):
        self.hide()
        self.return_signal.emit(voice_name)
        self.return_signal2.emit(voice_name, voice_id)

    def set_voice_url(self, file_path, voice_id):
        # from Service.dubbingMain.dubbingElevenlabs2 import dubbingElevenLabs2
        from Service.dubbingMain.dubbingElevenLabs import dubbingElevenLabs

        print(voice_id, file_path)
        if not file_path and voice_id:
            try:
                file_path = dubbingElevenLabs.getInstance().elevenlabs.voices.get(voice_id=voice_id).preview_url
            except Exception as e:
                print(f"获取声音失败: {e}")
                file_path = os.path.join(resource_path, "prepared_voices", "default.mp3")
        if not file_path:
            file_path = os.path.join(resource_path, "prepared_voices", "default.mp3")
        print(file_path)
        if file_path.startswith("http"):
            self.audio_bar.player.setSource(QUrl(file_path))
        else:
            self.audio_bar.player.setSource(QUrl.fromLocalFile(file_path))
        self.audio_bar.play()

    def adjust_width(self):
        """调整窗口宽度以适应内容（延迟执行，确保布局计算完成）"""
        QTimer.singleShot(0, self._do_adjust_width)

    def _do_adjust_width(self):
        """实际执行窗口宽度调整"""
        # 强制布局重新计算
        self.HistoryCardContainer.layout().update()
        self.HistoryCardContainer.layout().activate()
        self.VoiceScroll.updateGeometry()

        # 获取内容的理想尺寸
        content_size = self.HistoryCardContainer.sizeHint()

        # 计算所需宽度：内容宽度 + 滚动条宽度 + 边距
        scrollbar_width = 17  # 系统滚动条宽度
        margin = 40  # 窗口边距和额外空间
        required_width = content_size.width() + scrollbar_width + margin

        # 确保最小宽度
        min_width = max(750, required_width)

        # 设置窗口最小宽度
        self.setMinimumWidth(min_width)

        # 如果当前宽度小于最小宽度，调整窗口大小
        current_width = self.width()
        if current_width < min_width:
            self.resize(min_width, self.height())

if __name__ == '__main__':
    from Service.ccTest import read_config
    read_config()

    app = QApplication(sys.argv)
    window = VoiceSelectorWindow()
    window.show()
    window._on_pull_voice_finished("成功")
    sys.exit(app.exec_())