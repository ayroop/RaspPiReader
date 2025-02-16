from PyQt5 import QtWidgets
from RaspPiReader import pool
from RaspPiReader.libs.models import User
from RaspPiReader.libs.database import Database
from .user_management_form import Ui_UserManagementDialog
from .user_edit_form_handler import UserEditFormHandler

class UserManagementFormHandler(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super(UserManagementFormHandler, self).__init__(parent)
        self.ui = Ui_UserManagementDialog()
        self.ui.setupUi(self)
        self.setWindowTitle("User Management")
        self.db = Database("sqlite:///local_database.db")
        self.users = self.load_users()
        self.refresh_table()
        self.ui.addUserPushButton.clicked.connect(self.add_user)
        self.ui.editUserPushButton.clicked.connect(self.edit_user)
        self.ui.removeUserPushButton.clicked.connect(self.remove_user)

    def load_users(self):
        return self.db.get_users()

    def refresh_table(self):
        table = self.ui.userTableWidget
        table.clearContents()
        table.setRowCount(len(self.users))
        table.setColumnCount(5)
        table.setHorizontalHeaderLabels(['Username', 'Password', 'Settings', 'Search', 'User Mgmt Page'])
        for row_index, user in enumerate(self.users):
            table.setItem(row_index, 0, QtWidgets.QTableWidgetItem(user.username))
            table.setItem(row_index, 1, QtWidgets.QTableWidgetItem(user.password))
            table.setItem(row_index, 2, QtWidgets.QTableWidgetItem(str(user.settings)))
            table.setItem(row_index, 3, QtWidgets.QTableWidgetItem(str(user.search)))
            table.setItem(row_index, 4, QtWidgets.QTableWidgetItem(str(user.user_mgmt_page)))
        table.resizeColumnsToContents()

    def add_user(self):
        dlg = UserEditFormHandler(parent=self)
        if dlg.exec_() == QtWidgets.QDialog.Accepted:
            user_data = dlg.get_data()
            new_user = User(
                username=user_data['username'],
                password=user_data['password'],
                settings=user_data['settings'],
                search=user_data['search'],
                user_mgmt_page=user_data['user_mgmt_page']
            )
            self.db.add_user(new_user)
            self.users.append(new_user)
            self.refresh_table()

    def edit_user(self):
        table = self.ui.userTableWidget
        current_row = table.currentRow()
        if current_row < 0 or current_row >= len(self.users):
            return
        user = self.users[current_row]
        dlg = UserEditFormHandler(user_data=user, parent=self)
        if dlg.exec_() == QtWidgets.QDialog.Accepted:
            updated_user = dlg.get_data()
            user.username = updated_user['username']
            user.password = updated_user['password']
            user.settings = updated_user['settings']
            user.search = updated_user['search']
            user.user_mgmt_page = updated_user['user_mgmt_page']
            self.db.add_user(user)  # Update user in the database
            self.refresh_table()

    def remove_user(self):
        table = self.ui.userTableWidget
        current_row = table.currentRow()
        if current_row < 0 or current_row >= len(self.users):
            return
        user = self.users.pop(current_row)
        self.db.session.delete(user)
        self.db.session.commit()
        self.refresh_table()