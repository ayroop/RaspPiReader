from PyQt5 import QtWidgets
from RaspPiReader.ui.duplicate_password_dialog import DuplicatePasswordDialog as UiDuplicatePasswordDialog

class DuplicatePasswordDialog(QtWidgets.QDialog):
    def __init__(self, duplicate_serials, parent=None):
        super(DuplicatePasswordDialog, self).__init__(parent)
        self.ui = UiDuplicatePasswordDialog()
        self.ui.setupUi(self)

        # Populate the duplicate list with the provided serial numbers
        self.ui.duplicateList.setText("\n".join(duplicate_serials))

        # Connect the OK and Cancel buttons to close the dialog appropriately
        self.ui.okButton.clicked.connect(self.accept)
        self.ui.cancelButton.clicked.connect(self.reject)

    def get_passwords(self):
        """
        Retrieve the entered user and supervisor passwords.
        Returns:
            tuple: (user_password, supervisor_password)
        """
        user_password = self.ui.userPasswordLineEdit.text()
        supervisor_password = self.ui.supervisorPasswordLineEdit.text()
        return user_password, supervisor_password
