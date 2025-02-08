from PyQt5 import QtWidgets
from .user_management_form import Ui_UserManagementDialog
from .user_edit_form_handler import UserEditFormHandler
import os
import csv

USER_DATA_FILE = os.path.join(os.path.dirname(__file__), '..', 'users.csv')
CSV_HEADER = [
    'username',
    'password',
    'settings',
    'search',
    'user_mgmt_page'
]

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
        users = []
        if os.path.exists(USER_DATA_FILE):
            with open(USER_DATA_FILE, newline='') as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    users.append(row)
        return users

    def refresh_table(self):
        table = self.ui.userTableWidget
        table.clearContents()
        table.setRowCount(len(self.users))
        table.setColumnCount(len(CSV_HEADER))
        table.setHorizontalHeaderLabels(CSV_HEADER)
        for row_index, user in enumerate(self.users):
            for col_index, key in enumerate(CSV_HEADER):
                table.setItem(row_index, col_index, QtWidgets.QTableWidgetItem(user[key]))
        table.resizeColumnsToContents()

    def save_users(self):
        with open(USER_DATA_FILE, 'w', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=CSV_HEADER)
            writer.writeheader()
            for user in self.users:
                writer.writerow(user)

    def add_user(self):
        dlg = UserEditFormHandler(parent=self)
        if dlg.exec_() == QtWidgets.QDialog.Accepted:
            new_user = dlg.get_data()
            if new_user['username']:
                self.users.append(new_user)
                self.refresh_table()
                self.save_users()

    def edit_user(self):
        table = self.ui.userTableWidget
        current_row = table.currentRow()
        if current_row < 0 or current_row >= len(self.users):
            return
        user_data = self.users[current_row]
        dlg = UserEditFormHandler(user_data, parent=self)
        if dlg.exec_() == QtWidgets.QDialog.Accepted:
            self.users[current_row] = dlg.get_data()
            self.refresh_table()
            self.save_users()

    def remove_user(self):
        table = self.ui.userTableWidget
        current_row = table.currentRow()
        if current_row < 0 or current_row >= len(self.users):
            return
        confirm = QtWidgets.QMessageBox.question(
            self, "Remove User", "Are you sure you want to remove the selected user?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        if confirm == QtWidgets.QMessageBox.Yes:
            del self.users[current_row]
            self.refresh_table()
            self.save_users()