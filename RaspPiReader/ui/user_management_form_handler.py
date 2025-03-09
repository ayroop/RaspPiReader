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
        table.setColumnCount(5)  # Added one more column for Role
        table.setHorizontalHeaderLabels(['Username', 'Password', 'Settings', 'Search', 'Role'])
        for row, user in enumerate(self.users):
            table.setItem(row, 0, QtWidgets.QTableWidgetItem(user.username))
            table.setItem(row, 1, QtWidgets.QTableWidgetItem(user.password))
            table.setItem(row, 2, QtWidgets.QTableWidgetItem(str(user.settings)))
            table.setItem(row, 3, QtWidgets.QTableWidgetItem(str(user.search)))
            table.setItem(row, 4, QtWidgets.QTableWidgetItem(user.role))
        table.resizeColumnsToContents()

    def add_user(self):
    # Open the user edit dialog. (using for UserEditFormHandler.)
        dialog = UserEditFormHandler(parent=self)
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            data = dialog.get_data()
            new_user = User(
                username=data["username"],
                password=data["password"],
                role=data["role"],       # assign the role as entered
                settings=data["settings"],
                search=data["search"]
            )
            self.db.add_user(new_user)
            self.users = self.load_users()  # Reload the users from the database
            self.refresh_table()

    def edit_user(self):
        table = self.ui.userTableWidget
        current_row = table.currentRow()
        if current_row < 0:
            QtWidgets.QMessageBox.warning(self, "Edit User", "Please select a user to edit.")
            return
        user = self.users[current_row]
        dialog = UserEditFormHandler(user_data=user, parent=self)
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            updated_data = dialog.get_data()
            user.username = updated_data["username"]
            user.password = updated_data["password"]
            user.role = updated_data["role"]         # update the role from the dialog
            user.settings = updated_data["settings"]
            user.search = updated_data["search"]
            user.user_mgmt_page = updated_data["user_mgmt_page"]
            self.db.session.commit()  # commit to save changes
            self.users = self.load_users()  # reload the users
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