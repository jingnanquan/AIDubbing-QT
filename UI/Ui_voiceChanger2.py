# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'Ui_voiceChanger2.ui'
#
# Created by: PyQt5 UI code generator 5.14.0
#
# WARNING! All changes made in this file will be lost!


from PyQt5 import QtCore, QtGui, QtWidgets


class Ui_VoiceChanger(object):
    def setupUi(self, VoiceChanger):
        VoiceChanger.setObjectName("VoiceChanger")
        VoiceChanger.resize(1300, 910)
        VoiceChanger.setStyleSheet("/*\n"
"Overall Style\n"
"*/\n"
"QWidget#centralwidget {\n"
"    background-color: #F8F9FA;\n"
"}\n"
"\n"
"/*\n"
"Labels\n"
"*/\n"
"\n"
"\n"
"QLabel#uploadTextLabel_1 {\n"
"    color: #495057;\n"
"    font-size: 17px;\n"
"    font-weight: 500;\n"
"\n"
"}\n"
"\n"
"\n"
"QLabel#uploadTextLabel_3 {\n"
"    color: #6C757D;\n"
"    font-size: 14px;\n"
"\n"
"}\n"
"QLabel#uploadTextLabel_2 {\n"
"    color: #6C757D;\n"
"    font-size: 14px;\n"
"\n"
"}\n"
"\n"
"\n"
"/*\n"
"Buttons\n"
"*/\n"
"QPushButton#generateButton {\n"
"    border-radius: 10px;\n"
"    border: 1px solid #E9ECEF;\n"
"    background-color: #666666;\n"
"    color: #eeeeee;\n"
"    text-align: center;\n"
"    font-weight: 600;\n"
"    font-size: 16px;\n"
"    padding: 16px;\n"
"}\n"
"\n"
"QPushButton#generateButton:hover {\n"
"    background-color: #999999;\n"
"}\n"
"\n"
"QPushButton#resetButton {\n"
"    background-color: transparent;\n"
"    border: none;\n"
"    color: #495057;\n"
"    font-size: 13px;\n"
"    text-align: right;\n"
"}\n"
"\n"
"QPushButton#resetButton:hover {\n"
"    text-decoration: underline;\n"
"}\n"
"\n"
"/*\n"
"Tab Widget\n"
"*/\n"
"QTabWidget::pane {\n"
"    border: none;\n"
"}\n"
"\n"
"QTabBar::tab {\n"
"    width: 90px;\n"
"    height: 35px;\n"
"    font-size: 16px;\n"
"    font-weight: 500;\n"
"    color: #6C757D;\n"
"    border-bottom: 2px solid transparent;\n"
"\n"
"    margin: 10px 10px 10px 10px;\n"
"}\n"
"\n"
"QTabBar::tab:selected {\n"
"    color: #212529;\n"
"    border-bottom: 2px solid #212529;\n"
"}\n"
"\n"
"QTabBar::tab:hover {\n"
"    color: #212529;\n"
"}\n"
"\n"
"/*\n"
"Sliders\n"
"*/\n"
"QSlider {\n"
"    padding: 5px 0;\n"
"}\n"
"\n"
"QSlider::groove:horizontal {\n"
"    border: 1px solid #DEE2E6;\n"
"    background: #e1e3e5;\n"
"    height: 6px;\n"
"    border-radius: 3px;\n"
"}\n"
"\n"
"QSlider::handle:horizontal {\n"
"    background: #F1F1F1;\n"
"    border: 1px solid #CED4DA;\n"
"    width: 20px;\n"
"    height: 20px;\n"
"    margin: -8px 0;\n"
"    border-radius: 10px;\n"
"}\n"
"\n"
"QSlider::handle:horizontal:hover {\n"
"    border-color: #ADB5BD;\n"
"}\n"
"\n"
"/*\n"
"Switches (Styled QCheckBox)\n"
"*/\n"
"\n"
"CheckBox {\n"
"    font-size: 14px;\n"
"    color: #343A40;\n"
"    font-weight: 500;\n"
"}\n"
"/*\n"
"Frames and Separators\n"
"*/\n"
"QFrame#uploadFrame {\n"
"    background-color: #FFFFFF;\n"
"    border: 2px dashed #CED4DA;\n"
"    border-radius: 12px;\n"
"}\n"
"\n"
"QFrame#uploadFrame:hover {\n"
"    background-color: #FFFFFF;\n"
"    border: 2px dashed #a1bbd7;\n"
"    border-radius: 12px;\n"
"}\n"
"\n"
"QFrame#rightPanelFrame {\n"
"    background-color: #FFFFFF;\n"
"    border: 1px solid #E9ECEF;\n"
"    border-radius: 12px;\n"
"    padding: 10px;\n"
"}\n"
"\n"
"QFrame#separatorLine {\n"
"    background-color: #E9ECEF;\n"
"}")
        self.verticalLayout = QtWidgets.QVBoxLayout(VoiceChanger)
        self.verticalLayout.setContentsMargins(12, 32, 16, 16)
        self.verticalLayout.setObjectName("verticalLayout")
        self.PackageTitile = QtWidgets.QLabel(VoiceChanger)
        self.PackageTitile.setMaximumSize(QtCore.QSize(16777215, 3000))
        font = QtGui.QFont()
        font.setFamily("微软雅黑")
        font.setPointSize(26)
        font.setBold(True)
        font.setWeight(75)
        font.setKerning(True)
        self.PackageTitile.setFont(font)
        self.PackageTitile.setObjectName("PackageTitile")
        self.verticalLayout.addWidget(self.PackageTitile)
        self.mainLayout = QtWidgets.QHBoxLayout()
        self.mainLayout.setSpacing(25)
        self.mainLayout.setObjectName("mainLayout")
        self.uploadFrame = QtWidgets.QFrame(VoiceChanger)
        self.uploadFrame.setFrameShape(QtWidgets.QFrame.StyledPanel)
        self.uploadFrame.setFrameShadow(QtWidgets.QFrame.Raised)
        self.uploadFrame.setObjectName("uploadFrame")
        self.verticalLayout_2 = QtWidgets.QVBoxLayout(self.uploadFrame)
        self.verticalLayout_2.setSpacing(15)
        self.verticalLayout_2.setObjectName("verticalLayout_2")
        self.horizontalLayout_7 = QtWidgets.QHBoxLayout()
        self.horizontalLayout_7.setContentsMargins(-1, -1, -1, 0)
        self.horizontalLayout_7.setObjectName("horizontalLayout_7")
        spacerItem = QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.horizontalLayout_7.addItem(spacerItem)
        self.clearButton = PushButton(self.uploadFrame)
        self.clearButton.setObjectName("clearButton")
        self.horizontalLayout_7.addWidget(self.clearButton)
        self.verticalLayout_2.addLayout(self.horizontalLayout_7)
        spacerItem1 = QtWidgets.QSpacerItem(20, 40, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding)
        self.verticalLayout_2.addItem(spacerItem1)
        self.uploadIconLabel = QtWidgets.QLabel(self.uploadFrame)
        font = QtGui.QFont()
        font.setFamily("Segoe UI")
        font.setPointSize(36)
        self.uploadIconLabel.setFont(font)
        self.uploadIconLabel.setAlignment(QtCore.Qt.AlignCenter)
        self.uploadIconLabel.setObjectName("uploadIconLabel")
        self.verticalLayout_2.addWidget(self.uploadIconLabel)
        self.uploadTextLabel_1 = QtWidgets.QLabel(self.uploadFrame)
        font = QtGui.QFont()
        font.setFamily("Microsoft JhengHei UI")
        font.setPointSize(-1)
        font.setBold(True)
        font.setWeight(62)
        self.uploadTextLabel_1.setFont(font)
        self.uploadTextLabel_1.setAlignment(QtCore.Qt.AlignCenter)
        self.uploadTextLabel_1.setObjectName("uploadTextLabel_1")
        self.verticalLayout_2.addWidget(self.uploadTextLabel_1)
        self.uploadTextLabel_3 = QtWidgets.QLabel(self.uploadFrame)
        font = QtGui.QFont()
        font.setFamily("Microsoft JhengHei UI")
        font.setPointSize(-1)
        font.setBold(False)
        font.setWeight(50)
        self.uploadTextLabel_3.setFont(font)
        self.uploadTextLabel_3.setAlignment(QtCore.Qt.AlignCenter)
        self.uploadTextLabel_3.setObjectName("uploadTextLabel_3")
        self.verticalLayout_2.addWidget(self.uploadTextLabel_3)
        self.uploadTextLabel_2 = QtWidgets.QLabel(self.uploadFrame)
        font = QtGui.QFont()
        font.setFamily("Microsoft JhengHei UI")
        font.setPointSize(-1)
        font.setBold(False)
        font.setWeight(50)
        self.uploadTextLabel_2.setFont(font)
        self.uploadTextLabel_2.setAlignment(QtCore.Qt.AlignCenter)
        self.uploadTextLabel_2.setObjectName("uploadTextLabel_2")
        self.verticalLayout_2.addWidget(self.uploadTextLabel_2)
        spacerItem2 = QtWidgets.QSpacerItem(20, 40, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding)
        self.verticalLayout_2.addItem(spacerItem2)
        self.mainLayout.addWidget(self.uploadFrame)
        self.rightPanelFrame = QtWidgets.QFrame(VoiceChanger)
        self.rightPanelFrame.setFrameShape(QtWidgets.QFrame.StyledPanel)
        self.rightPanelFrame.setFrameShadow(QtWidgets.QFrame.Raised)
        self.rightPanelFrame.setObjectName("rightPanelFrame")
        self.verticalLayout_3 = QtWidgets.QVBoxLayout(self.rightPanelFrame)
        self.verticalLayout_3.setContentsMargins(15, 5, 15, 15)
        self.verticalLayout_3.setSpacing(24)
        self.verticalLayout_3.setObjectName("verticalLayout_3")
        self.tabWidget = QtWidgets.QTabWidget(self.rightPanelFrame)
        font = QtGui.QFont()
        font.setFamily("Microsoft JhengHei UI")
        font.setPointSize(14)
        font.setBold(True)
        font.setWeight(75)
        self.tabWidget.setFont(font)
        self.tabWidget.setObjectName("tabWidget")
        self.settingsTab = QtWidgets.QWidget()
        self.settingsTab.setObjectName("settingsTab")
        self.verticalLayout_4 = QtWidgets.QVBoxLayout(self.settingsTab)
        self.verticalLayout_4.setContentsMargins(0, 20, 0, 10)
        self.verticalLayout_4.setSpacing(10)
        self.verticalLayout_4.setObjectName("verticalLayout_4")
        self.voiceLayout = QtWidgets.QVBoxLayout()
        self.voiceLayout.setSpacing(6)
        self.voiceLayout.setObjectName("voiceLayout")
        self.sectionTitleLabel = QtWidgets.QLabel(self.settingsTab)
        font = QtGui.QFont()
        font.setFamily("Microsoft JhengHei UI")
        font.setPointSize(12)
        font.setBold(True)
        font.setWeight(75)
        self.sectionTitleLabel.setFont(font)
        self.sectionTitleLabel.setObjectName("sectionTitleLabel")
        self.voiceLayout.addWidget(self.sectionTitleLabel)
        self.voiceSelector = ComboBox(self.settingsTab)
        self.voiceSelector.setObjectName("voiceSelector")
        self.voiceLayout.addWidget(self.voiceSelector)
        self.voiceLineEdit = LineEdit(self.settingsTab)
        self.voiceLineEdit.setObjectName("voiceLineEdit")
        self.voiceLayout.addWidget(self.voiceLineEdit)
        self.verticalLayout_4.addLayout(self.voiceLayout)
        self.modelLayout = QtWidgets.QVBoxLayout()
        self.modelLayout.setSpacing(6)
        self.modelLayout.setObjectName("modelLayout")
        self.sectionTitleLabel_2 = QtWidgets.QLabel(self.settingsTab)
        font = QtGui.QFont()
        font.setFamily("Microsoft JhengHei UI")
        font.setPointSize(12)
        font.setBold(True)
        font.setWeight(75)
        self.sectionTitleLabel_2.setFont(font)
        self.sectionTitleLabel_2.setObjectName("sectionTitleLabel_2")
        self.modelLayout.addWidget(self.sectionTitleLabel_2)
        self.modelSelector = ComboBox(self.settingsTab)
        self.modelSelector.setObjectName("modelSelector")
        self.modelLayout.addWidget(self.modelSelector)
        self.verticalLayout_4.addLayout(self.modelLayout)
        self.separatorLine = QtWidgets.QFrame(self.settingsTab)
        self.separatorLine.setMinimumSize(QtCore.QSize(0, 1))
        self.separatorLine.setMaximumSize(QtCore.QSize(16777215, 1))
        self.separatorLine.setFrameShape(QtWidgets.QFrame.StyledPanel)
        self.separatorLine.setFrameShadow(QtWidgets.QFrame.Raised)
        self.separatorLine.setObjectName("separatorLine")
        self.verticalLayout_4.addWidget(self.separatorLine)
        self.stabilityLayout = QtWidgets.QVBoxLayout()
        self.stabilityLayout.setObjectName("stabilityLayout")
        self.horizontalLayout_2 = QtWidgets.QHBoxLayout()
        self.horizontalLayout_2.setObjectName("horizontalLayout_2")
        self.label = QtWidgets.QLabel(self.settingsTab)
        font = QtGui.QFont()
        font.setFamily("Segoe UI")
        font.setPointSize(11)
        font.setBold(True)
        font.setWeight(75)
        self.label.setFont(font)
        self.label.setObjectName("label")
        self.horizontalLayout_2.addWidget(self.label)
        spacerItem3 = QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.horizontalLayout_2.addItem(spacerItem3)
        self.StabilityValue = QtWidgets.QLabel(self.settingsTab)
        font = QtGui.QFont()
        font.setFamily("Segoe UI")
        font.setPointSize(10)
        self.StabilityValue.setFont(font)
        self.StabilityValue.setObjectName("StabilityValue")
        self.horizontalLayout_2.addWidget(self.StabilityValue)
        self.stabilityLayout.addLayout(self.horizontalLayout_2)
        self.stabilitySlider = Slider(self.settingsTab)
        self.stabilitySlider.setProperty("value", 60)
        self.stabilitySlider.setOrientation(QtCore.Qt.Horizontal)
        self.stabilitySlider.setObjectName("stabilitySlider")
        self.stabilityLayout.addWidget(self.stabilitySlider)
        self.horizontalLayout_3 = QtWidgets.QHBoxLayout()
        self.horizontalLayout_3.setObjectName("horizontalLayout_3")
        self.label_3 = QtWidgets.QLabel(self.settingsTab)
        font = QtGui.QFont()
        font.setFamily("Segoe UI")
        font.setPointSize(10)
        font.setBold(False)
        font.setWeight(50)
        self.label_3.setFont(font)
        self.label_3.setStyleSheet("color: #6C757D;")
        self.label_3.setObjectName("label_3")
        self.horizontalLayout_3.addWidget(self.label_3)
        spacerItem4 = QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.horizontalLayout_3.addItem(spacerItem4)
        self.label_4 = QtWidgets.QLabel(self.settingsTab)
        font = QtGui.QFont()
        font.setFamily("Segoe UI")
        font.setPointSize(10)
        self.label_4.setFont(font)
        self.label_4.setStyleSheet("color: #6C757D;")
        self.label_4.setObjectName("label_4")
        self.horizontalLayout_3.addWidget(self.label_4)
        self.stabilityLayout.addLayout(self.horizontalLayout_3)
        self.verticalLayout_4.addLayout(self.stabilityLayout)
        self.similarityLayout = QtWidgets.QVBoxLayout()
        self.similarityLayout.setObjectName("similarityLayout")
        self.horizontalLayout_4 = QtWidgets.QHBoxLayout()
        self.horizontalLayout_4.setObjectName("horizontalLayout_4")
        self.label_5 = QtWidgets.QLabel(self.settingsTab)
        font = QtGui.QFont()
        font.setFamily("Segoe UI")
        font.setPointSize(11)
        font.setBold(True)
        font.setWeight(75)
        self.label_5.setFont(font)
        self.label_5.setObjectName("label_5")
        self.horizontalLayout_4.addWidget(self.label_5)
        spacerItem5 = QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.horizontalLayout_4.addItem(spacerItem5)
        self.SimilarityValue = QtWidgets.QLabel(self.settingsTab)
        font = QtGui.QFont()
        font.setFamily("Segoe UI")
        font.setPointSize(10)
        self.SimilarityValue.setFont(font)
        self.SimilarityValue.setObjectName("SimilarityValue")
        self.horizontalLayout_4.addWidget(self.SimilarityValue)
        self.similarityLayout.addLayout(self.horizontalLayout_4)
        self.similaritySlider = Slider(self.settingsTab)
        self.similaritySlider.setProperty("value", 80)
        self.similaritySlider.setOrientation(QtCore.Qt.Horizontal)
        self.similaritySlider.setObjectName("similaritySlider")
        self.similarityLayout.addWidget(self.similaritySlider)
        self.horizontalLayout_5 = QtWidgets.QHBoxLayout()
        self.horizontalLayout_5.setObjectName("horizontalLayout_5")
        self.label_6 = QtWidgets.QLabel(self.settingsTab)
        font = QtGui.QFont()
        font.setFamily("Segoe UI")
        font.setPointSize(10)
        self.label_6.setFont(font)
        self.label_6.setStyleSheet("color: #6C757D;")
        self.label_6.setObjectName("label_6")
        self.horizontalLayout_5.addWidget(self.label_6)
        spacerItem6 = QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.horizontalLayout_5.addItem(spacerItem6)
        self.label_7 = QtWidgets.QLabel(self.settingsTab)
        font = QtGui.QFont()
        font.setFamily("Segoe UI")
        font.setPointSize(10)
        self.label_7.setFont(font)
        self.label_7.setStyleSheet("color: #6C757D;")
        self.label_7.setObjectName("label_7")
        self.horizontalLayout_5.addWidget(self.label_7)
        self.similarityLayout.addLayout(self.horizontalLayout_5)
        self.verticalLayout_4.addLayout(self.similarityLayout)
        self.exaggerationLayout = QtWidgets.QVBoxLayout()
        self.exaggerationLayout.setObjectName("exaggerationLayout")
        self.horizontalLayout_8 = QtWidgets.QHBoxLayout()
        self.horizontalLayout_8.setObjectName("horizontalLayout_8")
        self.label_8 = QtWidgets.QLabel(self.settingsTab)
        font = QtGui.QFont()
        font.setFamily("Segoe UI")
        font.setPointSize(11)
        font.setBold(True)
        font.setWeight(75)
        self.label_8.setFont(font)
        self.label_8.setObjectName("label_8")
        self.horizontalLayout_8.addWidget(self.label_8)
        spacerItem7 = QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.horizontalLayout_8.addItem(spacerItem7)
        self.ExaggerationValue = QtWidgets.QLabel(self.settingsTab)
        font = QtGui.QFont()
        font.setFamily("Segoe UI")
        font.setPointSize(10)
        self.ExaggerationValue.setFont(font)
        self.ExaggerationValue.setObjectName("ExaggerationValue")
        self.horizontalLayout_8.addWidget(self.ExaggerationValue)
        self.exaggerationLayout.addLayout(self.horizontalLayout_8)
        self.exaggerationSlider = Slider(self.settingsTab)
        self.exaggerationSlider.setProperty("value", 80)
        self.exaggerationSlider.setOrientation(QtCore.Qt.Horizontal)
        self.exaggerationSlider.setObjectName("exaggerationSlider")
        self.exaggerationLayout.addWidget(self.exaggerationSlider)
        self.horizontalLayout_9 = QtWidgets.QHBoxLayout()
        self.horizontalLayout_9.setObjectName("horizontalLayout_9")
        self.label_9 = QtWidgets.QLabel(self.settingsTab)
        font = QtGui.QFont()
        font.setFamily("Segoe UI")
        font.setPointSize(10)
        self.label_9.setFont(font)
        self.label_9.setStyleSheet("color: #6C757D;")
        self.label_9.setObjectName("label_9")
        self.horizontalLayout_9.addWidget(self.label_9)
        spacerItem8 = QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.horizontalLayout_9.addItem(spacerItem8)
        self.label_10 = QtWidgets.QLabel(self.settingsTab)
        font = QtGui.QFont()
        font.setFamily("Segoe UI")
        font.setPointSize(10)
        self.label_10.setFont(font)
        self.label_10.setStyleSheet("color: #6C757D;")
        self.label_10.setObjectName("label_10")
        self.horizontalLayout_9.addWidget(self.label_10)
        self.exaggerationLayout.addLayout(self.horizontalLayout_9)
        self.verticalLayout_4.addLayout(self.exaggerationLayout)
        self.horizontalLayout = QtWidgets.QHBoxLayout()
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.removeBgNoiseCheck = CheckBox(self.settingsTab)
        font = QtGui.QFont()
        font.setFamily("Microsoft JhengHei UI")
        font.setPointSize(12)
        font.setBold(True)
        font.setWeight(75)
        self.removeBgNoiseCheck.setFont(font)
        self.removeBgNoiseCheck.setObjectName("removeBgNoiseCheck")
        self.horizontalLayout.addWidget(self.removeBgNoiseCheck)
        self.speakerBoostCheck = CheckBox(self.settingsTab)
        font = QtGui.QFont()
        font.setFamily("Microsoft JhengHei UI")
        font.setPointSize(12)
        font.setBold(True)
        font.setWeight(75)
        self.speakerBoostCheck.setFont(font)
        self.speakerBoostCheck.setChecked(True)
        self.speakerBoostCheck.setObjectName("speakerBoostCheck")
        self.horizontalLayout.addWidget(self.speakerBoostCheck)
        self.verticalLayout_4.addLayout(self.horizontalLayout)
        spacerItem9 = QtWidgets.QSpacerItem(20, 40, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Fixed)
        self.verticalLayout_4.addItem(spacerItem9)
        self.tabWidget.addTab(self.settingsTab, "")
        self.historyTab = QtWidgets.QWidget()
        self.historyTab.setObjectName("historyTab")
        self.verticalLayout_5 = QtWidgets.QVBoxLayout(self.historyTab)
        self.verticalLayout_5.setContentsMargins(0, 0, 0, 0)
        self.verticalLayout_5.setSpacing(0)
        self.verticalLayout_5.setObjectName("verticalLayout_5")
        self.HistoryScroll = QtWidgets.QScrollArea(self.historyTab)
        self.HistoryScroll.setWidgetResizable(True)
        self.HistoryScroll.setObjectName("HistoryScroll")
        self.scrollAreaWidgetContents = QtWidgets.QWidget()
        self.scrollAreaWidgetContents.setGeometry(QtCore.QRect(0, 0, 98, 28))
        self.scrollAreaWidgetContents.setObjectName("scrollAreaWidgetContents")
        self.HistoryScroll.setWidget(self.scrollAreaWidgetContents)
        self.verticalLayout_5.addWidget(self.HistoryScroll)
        self.tabWidget.addTab(self.historyTab, "")
        self.verticalLayout_3.addWidget(self.tabWidget)
        self.horizontalLayout_6 = QtWidgets.QHBoxLayout()
        self.horizontalLayout_6.setContentsMargins(-1, 16, -1, 10)
        self.horizontalLayout_6.setObjectName("horizontalLayout_6")
        self.generateButton = QtWidgets.QPushButton(self.rightPanelFrame)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.MinimumExpanding, QtWidgets.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.generateButton.sizePolicy().hasHeightForWidth())
        self.generateButton.setSizePolicy(sizePolicy)
        self.generateButton.setObjectName("generateButton")
        self.horizontalLayout_6.addWidget(self.generateButton)
        self.resetButton = QtWidgets.QPushButton(self.rightPanelFrame)
        self.resetButton.setObjectName("resetButton")
        self.horizontalLayout_6.addWidget(self.resetButton)
        self.verticalLayout_3.addLayout(self.horizontalLayout_6)
        self.verticalLayout_3.setStretch(0, 6)
        self.verticalLayout_3.setStretch(1, 1)
        self.mainLayout.addWidget(self.rightPanelFrame)
        self.mainLayout.setStretch(0, 5)
        self.mainLayout.setStretch(1, 4)
        self.verticalLayout.addLayout(self.mainLayout)

        self.retranslateUi(VoiceChanger)
        self.tabWidget.setCurrentIndex(0)
        QtCore.QMetaObject.connectSlotsByName(VoiceChanger)

    def retranslateUi(self, VoiceChanger):
        _translate = QtCore.QCoreApplication.translate
        VoiceChanger.setWindowTitle(_translate("VoiceChanger", "Form"))
        self.PackageTitile.setText(_translate("VoiceChanger", "声线转换"))
        self.clearButton.setText(_translate("VoiceChanger", "清空文件"))
        self.uploadIconLabel.setText(_translate("VoiceChanger", "🔃"))
        self.uploadTextLabel_1.setText(_translate("VoiceChanger", "点击或拖动上传音频文件"))
        self.uploadTextLabel_3.setText(_translate("VoiceChanger", "可上传多个音频文件"))
        self.uploadTextLabel_2.setText(_translate("VoiceChanger", "单个文件最大50MB"))
        self.sectionTitleLabel.setText(_translate("VoiceChanger", "声音列表"))
        self.sectionTitleLabel_2.setText(_translate("VoiceChanger", "模型列表"))
        self.label.setText(_translate("VoiceChanger", "Stability"))
        self.StabilityValue.setText(_translate("VoiceChanger", "1/100"))
        self.label_3.setText(_translate("VoiceChanger", "More variable"))
        self.label_4.setText(_translate("VoiceChanger", "More stable"))
        self.label_5.setText(_translate("VoiceChanger", "Similarity"))
        self.SimilarityValue.setText(_translate("VoiceChanger", "99/100"))
        self.label_6.setText(_translate("VoiceChanger", "Low"))
        self.label_7.setText(_translate("VoiceChanger", "High"))
        self.label_8.setText(_translate("VoiceChanger", "Style Exaggeration"))
        self.ExaggerationValue.setText(_translate("VoiceChanger", "99/100"))
        self.label_9.setText(_translate("VoiceChanger", "None"))
        self.label_10.setText(_translate("VoiceChanger", "Exaggerated"))
        self.removeBgNoiseCheck.setText(_translate("VoiceChanger", "去除背景噪声"))
        self.speakerBoostCheck.setText(_translate("VoiceChanger", "音效增强"))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.settingsTab), _translate("VoiceChanger", "设置"))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.historyTab), _translate("VoiceChanger", "历史记录"))
        self.generateButton.setText(_translate("VoiceChanger", "生成语音"))
        self.resetButton.setText(_translate("VoiceChanger", "重置设置值"))
from qfluentwidgets import CheckBox, ComboBox, LineEdit, PushButton, Slider
