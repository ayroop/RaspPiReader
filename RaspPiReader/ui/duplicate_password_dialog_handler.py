from PyQt5 import QtWidgets
from RaspPiReader.ui.duplicate_password_dialog import Ui_DuplicatePasswordDialog

class DuplicatePasswordDialog(QtWidgets.QDialog):
    def __init__(self, duplicate_serials, parent=None):
        super(DuplicatePasswordDialog, self).__init__(parent)
        self.ui = Ui_DuplicatePasswordDialog()
        self.ui.setupUi(self)
        # Set the duplicate serial list in the QTextBrowser
        self.ui.duplicateList.setText("\n".join(duplicate_serials))
        self.ui.okButton.clicked.connect(self.accept)
        self.ui.cancelButton.clicked.connect(self.reject)

    def get_credentials(self):
        username = self.ui.supervisorUsernameLineEdit.text().strip()
        password = self.ui.supervisorPasswordLineEdit.text().strip()
        return username, password