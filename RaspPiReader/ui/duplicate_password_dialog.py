from PyQt5 import QtWidgets
from RaspPiReader.ui.duplicate_password_dialog_ui import Ui_DuplicatePasswordDialog
from RaspPiReader import pool
from RaspPiReader.libs.database import Database

class DuplicatePasswordDialog(QtWidgets.QDialog):
    def __init__(self, duplicate_list, parent=None):
        super(DuplicatePasswordDialog, self).__init__(parent)
        self.ui = Ui_DuplicatePasswordDialog()
        self.ui.setupUi(self)
        # Populate the list of duplicate serial numbers.
        self.ui.duplicateList.setPlainText("\n".join(duplicate_list))
        self.ui.okButton.clicked.connect(self.check_passwords)
        self.ui.cancelButton.clicked.connect(self.reject)
        self.db = Database("sqlite:///local_database.db")
    
    def check_passwords(self):
        user_pass = self.ui.userPasswordLineEdit.text().strip()
        supervisor_pass = self.ui.supervisorPasswordLineEdit.text().strip()
        
        # Retrieve the current user's username from the pool.
        current_username = pool.get("current_user")
        if not current_username:
            QtWidgets.QMessageBox.critical(self, "Error", "Current user not found.")
            self.reject()
            return
        
        # Use the database to look up user records.
        current_user = self.db.get_user(current_username)
        if not current_user:
            QtWidgets.QMessageBox.critical(self, "Error", "Current user record not found in database.")
            self.reject()
            return
        
        # Assume the supervisor account is stored with username 'supervisor'
        supervisor_user = self.db.get_user("supervisor")
        if not supervisor_user:
            QtWidgets.QMessageBox.critical(self, "Error", "Supervisor record not found in database.")
            self.reject()
            return

        # Validate entered passwords against those stored in the database.
        if user_pass == current_user.password and supervisor_pass == supervisor_user.password:
            self.accept()  # Authorized
        else:
            QtWidgets.QMessageBox.critical(self, "Authorization Failed", "Invalid credentials.")