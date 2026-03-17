import os

from PyQt5.QtCore import pyqtSignal, Qt, QUrl
from PyQt5.QtWidgets import QWidget, QMainWindow, QVBoxLayout, QScrollArea, QGridLayout
from qfluentwidgets.multimedia import SimpleMediaPlayBar

from Compoment.DubbingParamParams import prepared_voices
from Compoment.HistoryCard import VoiceCardItem
from Config import resource_path
#
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



class VoiceSelectorWindow(QMainWindow):
    return_signal = pyqtSignal(str)

    def __init__(self, voices: dict = prepared_voices):
        super().__init__()

        self.setWindowTitle("声音列表")
        self.setMinimumWidth(750)
        self.setMinimumHeight(600)
        self.voices_dict = voices
        self.initUI()

    def initUI(self):
        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # 创建主布局
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10,10,10,10)


        # 创建并配置QScrollArea，命名为VoiceScroll
        self.VoiceScroll = QScrollArea()
        self.VoiceScroll.setWidgetResizable(True)  # 允许内容自动调整大小
        self.VoiceScroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.VoiceScroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.HistoryCardContainer = QWidget()

        self.HistoryCardContainer.setObjectName("HistoryCardContainer")

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

        self.adjust_width()

    def return_voice(self, voice_name):
        self.hide()
        self.return_signal.emit(voice_name)

    def set_voice_url(self, file_path, voice_id):
        from Service.dubbingMain.dubbingElevenlabs2 import dubbingElevenLabs2

        print(voice_id, file_path)
        if not file_path and voice_id:
            try:
                file_path = dubbingElevenLabs2.getInstance().connect.elevenlabs.voices.get(voice_id=voice_id).preview_url
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
        self.setMinimumWidth(self.HistoryCardContainer.sizeHint().width()+80)