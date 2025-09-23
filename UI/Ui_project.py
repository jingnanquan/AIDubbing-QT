# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'Ui_project.ui'
#
# Created by: PyQt5 UI code generator 5.14.0
#
# WARNING! All changes made in this file will be lost!


from PyQt5 import QtCore, QtGui, QtWidgets


class Ui_Project(object):
    def setupUi(self, Project):
        Project.setObjectName("Project")
        Project.resize(1300, 817)
        self.verticalLayout = QtWidgets.QVBoxLayout(Project)
        self.verticalLayout.setContentsMargins(12, 32, 16, 16)
        self.verticalLayout.setObjectName("verticalLayout")
        self.PackageTitile = QtWidgets.QLabel(Project)
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
        self.line = QtWidgets.QFrame(Project)
        self.line.setFrameShape(QtWidgets.QFrame.HLine)
        self.line.setFrameShadow(QtWidgets.QFrame.Sunken)
        self.line.setObjectName("line")
        self.verticalLayout.addWidget(self.line)
        self.container = QtWidgets.QWidget(Project)
        self.container.setObjectName("container")
        self.gridLayout = QtWidgets.QGridLayout(self.container)
        self.gridLayout.setContentsMargins(0, 0, 0, 0)
        self.gridLayout.setObjectName("gridLayout")
        self.containerLayout = QtWidgets.QGridLayout()
        self.containerLayout.setObjectName("containerLayout")
        self.gridLayout.addLayout(self.containerLayout, 0, 0, 1, 1)
        self.verticalLayout.addWidget(self.container)
        self.verticalLayout.setStretch(2, 10)

        self.retranslateUi(Project)
        QtCore.QMetaObject.connectSlotsByName(Project)

    def retranslateUi(self, Project):
        _translate = QtCore.QCoreApplication.translate
        Project.setWindowTitle(_translate("Project", "Form"))
        self.PackageTitile.setText(_translate("Project", "我的项目"))
