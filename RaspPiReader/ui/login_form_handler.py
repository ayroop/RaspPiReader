# filepath: /c:/DEV/Python/PLC Integration/src1-main/src1-main/RaspPiReader-master/RaspPiReader/ui/login_form_handler.py
from PyQt5 import QtWidgets
from .login_form import LoginForm

class LoginFormHandler(QtWidgets.QMainWindow):
    def __init__(self):
        super(LoginFormHandler, self).__init__()
        self.form = LoginForm()
        self.form.setupUi(self)
        self.form.loginPushButton.clicked.connect(self.handle_login)

    def handle_login(self):
        username = self.form.usernameLineEdit.text()
        password = self.form.passwordLineEdit.text()
        if self.authenticate(username, password):
            QtWidgets.QMessageBox.information(self, 'Success', 'Login successful')
            self.close()
            # Proceed to the main application
        else:
            QtWidgets.QMessageBox.warning(self, 'Error', 'Invalid credentials')

    def authenticate(self, username, password):
        # Replace with actual authentication logic
        return username == 'admin' and password == 'password'