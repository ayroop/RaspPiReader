import os
import csv
from PyQt5 import QtWidgets
from RaspPiReader import pool
from .login_form import Ui_LoginForm
from .main_form_handler import MainFormHandler

USER_DATA_FILE = os.path.join(os.path.dirname(__file__), '..', 'users.csv')

class LoginFormHandler(QtWidgets.QMainWindow):
    def __init__(self):
        super(LoginFormHandler, self).__init__()
        self.form = Ui_LoginForm()
        self.form.setupUi(self)
        self.form.loginPushButton.clicked.connect(self.handle_login)

    def handle_login(self):
        username = self.form.usernameLineEdit.text().strip()
        password = self.form.passwordLineEdit.text().strip()
        user_record = self.authenticate(username, password)
        if user_record:
            QtWidgets.QMessageBox.information(self, 'Success', 'Login successful')
            self.show_main_form(user_record)
            self.close()
        else:
            QtWidgets.QMessageBox.critical(self, "Error", "Invalid credentials!")

    def authenticate(self, username, password):
        if pool.config('demo', bool, False):
            # Authenticate demo users
            demo_users = [
                {"username": "admin", "password": "admin", "settings": True, "search": True, "user_mgmt_page": True},
                {"username": "demo_user1", "password": "password1", "settings": True, "search": True, "user_mgmt_page": True},
                {"username": "demo_user2", "password": "password2", "settings": False, "search": True, "user_mgmt_page": False}
            ]
            for user in demo_users:
                if user['username'] == username and user['password'] == password:
                    return user
            return None

        # Return default admin if admin credentials entered.
        if username.lower() == "admin" and password == "admin":
            return {"username": "admin", "password": "admin", "settings": True, "search": True, "user_mgmt_page": True}
        
        # Check the CSV user file.
        if os.path.exists(USER_DATA_FILE):
            with open(USER_DATA_FILE, mode='r', newline='', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    csv_username = (row.get('username') or '').strip()
                    csv_password = (row.get('password') or '').strip()
                    if username == csv_username and password == csv_password:
                        row['settings'] = str(row.get('settings', 'False')).strip().lower() == 'true'
                        row['search'] = str(row.get('search', 'False')).strip().lower() == 'true'
                        row['user_mgmt_page'] = str(row.get('user_mgmt_page', 'False')).strip().lower() == 'true'
                        return row
        return None

    def show_main_form(self, user_record):
        self.main_form = MainFormHandler(user_record)
        self.main_form.show()