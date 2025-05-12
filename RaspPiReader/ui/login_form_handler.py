from PyQt5 import QtWidgets
from RaspPiReader import pool
from .login_form import Ui_LoginForm
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .main_form_handler import MainFormHandler
from RaspPiReader.libs.database import Database
from RaspPiReader.libs.resource_path import resource_path

class LoginFormHandler(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super(LoginFormHandler, self).__init__(parent)
        self.ui = Ui_LoginForm()
        self.ui.setupUi(self)
        self.ui.loginPushButton.clicked.connect(self.login)
        # Use resource_path to resolve the database location.
        db_path = resource_path("local_database.db")
        self.db = Database(f"sqlite:///{db_path}")

    def login(self):
        username = self.ui.usernameLineEdit.text().strip()
        password = self.ui.passwordLineEdit.text().strip()
        user = self.authenticate(username, password)
        if user:
            # Store logged in username in the pool
            pool.set('current_user', user.username)
            self.accept()
            from .main_form_handler import MainFormHandler
            main_form = MainFormHandler(user=user)
            main_form.show()  # Use show() instead of showMaximized()
        else:
            QtWidgets.QMessageBox.critical(self, "Login Failed", "Invalid username or password")
            
    def authenticate(self, username, password):
        user = self.db.get_user(username)
        if user and user.password == password:
            return user
        return None
