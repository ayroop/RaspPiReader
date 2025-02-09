from PyQt5 import QtWidgets
from RaspPiReader import pool
from RaspPiReader.libs.models import User
from .user_management_form import Ui_UserManagementDialog
from .user_edit_form_handler import UserEditFormHandler

class UserManagementFormHandler(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super(UserManagementFormHandler, self).__init__(parent)
        self.ui = Ui_UserManagementDialog()
        self.ui.setupUi(self)
        self.setWindowTitle("User Management")
        self.users = self.load_users()
        self.refresh_table()
        self.ui.addUserPushButton.clicked.connect(self.add_user)
        self.ui.editUserPushButton.clicked.connect(self.edit_user)
        self.ui.removeUserPushButton.clicked.connect(self.remove_user)

    def load_users(self):
        if pool.config('demo', bool, False):
            # Load demo users
            return [
                User(username='admin', password='admin', settings=True, search=True, user_mgmt_page=True),
                User(username='demo_user1', password='password1', settings=True, search=True, user_mgmt_page=True),
                User(username='demo_user2', password='password2', settings=False, search=True, user_mgmt_page=False)
            ]
        else:
            return session.query(User).all()

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

    def save_users(self):
        if not pool.config('demo', bool, False):
            session.commit()

    def add_user(self):
        dlg = UserEditFormHandler(parent=self)
        if dlg.exec_() == QtWidgets.QDialog.Accepted:
            user_data = dlg.get_data()
            new_user = User(**user_data)
            self.users.append(new_user)
            if not pool.config('demo', bool, False):
                session.add(new_user)
                self.save_users()
            self.refresh_table()

    def edit_user(self):
        table = self.ui.userTableWidget
        current_row = table.currentRow()
        if current_row < 0 or current_row >= len(self.users):
            return
        user = self.users[current_row]
        dlg = UserEditFormHandler(user_data=user, parent=self)
        if dlg.exec_() == QtWidgets.QDialog.Accepted:
            user_data = dlg.get_data()
            user.username = user_data['username']
            user.password = user_data['password']
            user.settings = user_data['settings']
            user.search = user_data['search']
            user.user_mgmt_page = user_data['user_mgmt_page']
            if not pool.config('demo', bool, False):
                self.save_users()
            self.refresh_table()

    def remove_user(self):
        table = self.ui.userTableWidget
        current_row = table.currentRow()
        if current_row < 0 or current_row >= len(self.users):
            return
        user = self.users[current_row]
        confirm = QtWidgets.QMessageBox.question(
            self, "Remove User", "Are you sure you want to remove the selected user?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        if confirm == QtWidgets.QMessageBox.Yes:
            self.users.remove(user)
            if not pool.config('demo', bool, False):
                session.delete(user)
                self.save_users()
            self.refresh_table()