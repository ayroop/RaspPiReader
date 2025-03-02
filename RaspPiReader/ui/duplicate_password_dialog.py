import logging
from PyQt5 import QtWidgets
from RaspPiReader.ui.duplicate_password_dialog_ui import Ui_DuplicatePasswordDialog
from RaspPiReader import pool
from RaspPiReader.libs.database import Database

logger = logging.getLogger(__name__)

class DuplicatePasswordDialog(QtWidgets.QDialog):
    def __init__(self, duplicate_list, parent=None):
        super(DuplicatePasswordDialog, self).__init__(parent)
        self.ui = Ui_DuplicatePasswordDialog()
        self.ui.setupUi(self)
        
        # Set window title and labels
        self.setWindowTitle("Duplicate Serial Authorization")
        if hasattr(self.ui, "instructionLabel"):
            self.ui.instructionLabel.setText("The following serial numbers already exist in the system:")
        
        # Set label text if not already set in the UI
        if hasattr(self.ui, "userLabel"):
            self.ui.userLabel.setText("User Password:")
        
        if hasattr(self.ui, "supervisorLabel"):
            self.ui.supervisorLabel.setText("Supervisor Password:")
        
        # Set button text if not in the UI
        if hasattr(self.ui, "okButton"):
            self.ui.okButton.setText("OK")
        
        if hasattr(self.ui, "cancelButton"):
            self.ui.cancelButton.setText("Cancel")
        
        # Set echo mode for password fields
        if hasattr(self.ui, "userPasswordLineEdit"):
            self.ui.userPasswordLineEdit.setEchoMode(QtWidgets.QLineEdit.Password)
        
        if hasattr(self.ui, "supervisorPasswordLineEdit"):
            self.ui.supervisorPasswordLineEdit.setEchoMode(QtWidgets.QLineEdit.Password)
        
        # Show the duplicate serials in a text browser
        self.ui.duplicateList.setPlainText("\n".join(duplicate_list))
        
        # Connect buttons
        self.ui.okButton.clicked.connect(self.check_passwords)
        self.ui.cancelButton.clicked.connect(self.reject)
        
        self.db = Database("sqlite:///local_database.db")
    
    def check_passwords(self):
        user_pass = self.ui.userPasswordLineEdit.text().strip()
        supervisor_pass = self.ui.supervisorPasswordLineEdit.text().strip()
        
        current_username = pool.get("current_user")
        if not current_username:
            QtWidgets.QMessageBox.critical(self, "Error", "No current user found.")
            return
        
        # Get current user from database
        current_user = self.db.get_user(current_username)
        if not current_user or current_user.password != user_pass:
            QtWidgets.QMessageBox.critical(self, "Error", "Invalid user password.")
            return
        
        # Get a supervisor user (any user with user_mgmt_page permission)
        supervisor_users = self.db.session.query(self.db.User).filter_by(user_mgmt_page=True).all()
        supervisor_authenticated = False
        
        for supervisor in supervisor_users:
            if supervisor.password == supervisor_pass:
                supervisor_authenticated = True
                break
        
        if not supervisor_authenticated:
            QtWidgets.QMessageBox.critical(self, "Error", "Invalid supervisor password.")
            return
        
        # Both user and supervisor authentication successful
        QtWidgets.QMessageBox.information(
            self, "Authorization Successful", 
            "You are authorized to use duplicate serial numbers."
        )
        self.accept()