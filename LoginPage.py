from Config import http_url
import sys
import os
import traceback

import requests
from UI.Ui_login import Ui_Login
from PyQt5.QtWidgets import QApplication, QWidget, QMessageBox
from PyQt5.QtGui import QPixmap, QPalette, QBrush, QIcon
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QObject



class LoginPage(QWidget, Ui_Login):

    def __init__(self, parent=None):
        super().__init__(parent)
        print("登录页加载")
        self.setupUi(self)
        self.get_saved_info()
        self.setFixedSize(self.size())
        self.label_2.setPixmap(QPixmap(':/qfluentwidgets/images/logo.png'))
        self.setWindowIcon(QIcon(':/qfluentwidgets/images/logo.png'))
        self.w = None
        
        pixmap = QPixmap(os.path.join(os.path.dirname(os.path.abspath(__file__)), "Service", "login", "login2.jpg"))
        palette = self.frame.palette()
        print(self.size())
        palette.setBrush(QPalette.Background, QBrush(pixmap.scaled(self.size(), Qt.IgnoreAspectRatio, Qt.SmoothTransformation)))
        self.frame.setPalette(palette)
        self.frame.setAutoFillBackground(True) 
        self.pushButton.clicked.connect(self.login)
        self.checkBox.setChecked(False)

    def login(self):
        # 登录
        print("登录")
        username = self.lineEdit_3.text().strip()
        password = self.lineEdit_4.text().strip()
        if not username or not password:
            QMessageBox.warning(self, "提示", "请输入用户名和密码")
            return

        self.pushButton.setDisabled(True)


        class LoginWorker(QObject):
            finished = pyqtSignal(dict, bool, str)
            def __init__(self, username, password):
                super().__init__()
                self.username = username
                self.password = password

            def run(self):
                try:
                    headers = {
                        "x-token": "YWlkdWJiaW5n"
                    }
                    response = requests.post(
                        http_url + "login/verify",
                        json={
                            "username": self.username,
                            "password": self.password
                        },
                        headers=headers
                    )
                    data = response.json()
                    detail = data.get('detail')
                    self.finished.emit(data, response.ok, str(detail))
                except requests.RequestException as e:
                    self.finished.emit({}, False, f"无法连接服务器: {e}")

        def on_finished(data, ok, detail):
            self.pushButton.setDisabled(False)
            if ok:
                self.sava_info(username, password)
                self.open_main_window()
            else:
                if detail:
                    QMessageBox.warning(self, "提示", detail)
                else:
                    QMessageBox.warning(self, "提示", "登录失败")

            # 清理线程
            worker.deleteLater()
            thread.quit()
            thread.wait()
            thread.deleteLater()

        thread = QThread()
        worker = LoginWorker(username, password)
        worker.moveToThread(thread)
        worker.finished.connect(on_finished)
        thread.started.connect(worker.run)
        thread.start()

    def sava_info(self, username, password):
        if self.checkBox.isChecked():
            with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "Service", "login", "login_info.txt"), "w") as f:
                f.write(f"{username}\n{password}")

    def get_saved_info(self):
        self.lineEdit_3.setFocus()
        filename = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Service", "login", "login_info.txt")
        if not filename:
            return
        try:
            with open(filename, "r") as f:
                username, password = f.read().splitlines()
                self.lineEdit_3.setText(username)
                self.lineEdit_4.setText(password)
        except Exception as e:
            pass



    def open_main_window(self):
        self.hide()
        self.loading_msg = QMessageBox(self)
        self.loading_msg.setWindowTitle("请稍候")
        self.loading_msg.setText("正在加载主界面，请稍候...")
        self.loading_msg.setStandardButtons(QMessageBox.NoButton)
        self.loading_msg.setModal(False)
        self.loading_msg.show()
        QApplication.processEvents()

        from AIMainPage import Window, StreamCapturer
        myCapturer = StreamCapturer()
        sys.stdout = myCapturer
        sys.stderr = myCapturer
        self.w = Window(capturer=myCapturer)
        self.loading_msg.hide()
        self.loading_msg.deleteLater()
        QApplication.processEvents()
        self.w.show()



    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Up:
            if self.lineEdit_4.hasFocus():
                self.lineEdit_3.setFocus()
        elif event.key() == Qt.Key_Down:
            if self.lineEdit_3.hasFocus():
                self.lineEdit_4.setFocus()
        else:
            super().keyPressEvent(event)

    def eventFilter(self, obj, event):
        if event.type() == event.KeyPress and event.key() == Qt.Key_Return:
            self.login()
            return True
        return super().eventFilter(obj, event)

    def showEvent(self, event):
        super().showEvent(event)
        self.lineEdit_3.installEventFilter(self)
        self.lineEdit_4.installEventFilter(self)
    

def run2():
    login = None
    try:
        app = QApplication(sys.argv)
        login = LoginPage()
        login.show()
        sys.exit(app.exec_())
    except Exception as e:
        print(f"发生错误: {str(e)}")
        traceback.print_exc()  # 打印完整的错误堆栈
        if login is not None:
            if login.w is not None:
                login.w.close()
        input("按 Enter 键退出...")  # 暂停等待用户输入
        sys.exit(1)

if __name__ == '__main__':
    login = None
    try:
        app = QApplication(sys.argv)
        login = LoginPage()
        login.show()
        sys.exit(app.exec_())
    except Exception as e:
        print(f"发生错误: {str(e)}")
        traceback.print_exc()  # 打印完整的错误堆栈
        if login is not None:
            if login.w is not None:
                login.w.close()
        input("按 Enter 键退出...")  # 暂停等待用户输入
        sys.exit(1)