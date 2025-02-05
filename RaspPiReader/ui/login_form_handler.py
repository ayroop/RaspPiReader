from PyQt5 import QtWidgets
from .login_form import Ui_LoginForm
from .main_form_handler import MainFormHandler

class LoginFormHandler(QtWidgets.QMainWindow):
    def __init__(self):
        super(LoginFormHandler, self).__init__()
        self.form = Ui_LoginForm()
        self.form.setupUi(self)
        self.form.loginPushButton.clicked.connect(self.handle_login)

    def handle_login(self):
        username = self.form.usernameLineEdit.text()
        password = self.form.passwordLineEdit.text()
        if self.authenticate(username, password):
            QtWidgets.QMessageBox.information(self, 'Success', 'Login successful')
            self.close()
            self.show_main_form(username)
        else:
            QtWidgets.QMessageBox.warning(self, 'Error', 'Invalid credentials')

    def authenticate(self, username, password):
        # Replace with actual authentication logic
        return username == 'admin' and password == 'password'

    def show_main_form(self, username):
        self.main_form = MainFormHandler(username)
        self.main_form.show()