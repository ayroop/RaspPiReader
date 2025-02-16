from PyQt5 import QtWidgets
from .user_edit_form import Ui_UserEditDialog

class UserEditFormHandler(QtWidgets.QDialog):
    def __init__(self, user_data=None, parent=None):
        super(UserEditFormHandler, self).__init__(parent)
        self.ui = Ui_UserEditDialog()
        self.ui.setupUi(self)
        self.ui.okPushButton.clicked.connect(self.accept)
        self.ui.cancelPushButton.clicked.connect(self.reject)
        if user_data:
            self.ui.usernameLineEdit.setText(user_data.username)
            self.ui.passwordLineEdit.setText(user_data.password)
            self.ui.settingsCheckBox.setChecked(user_data.settings)
            self.ui.searchCheckBox.setChecked(user_data.search)

    def get_data(self):
        data = {
            'username': self.ui.usernameLineEdit.text().strip(),
            'password': self.ui.passwordLineEdit.text().strip(),
            'settings': self.ui.settingsCheckBox.isChecked(),
            'search': self.ui.searchCheckBox.isChecked(),
            'user_mgmt_page': False  # Default value, can be updated as needed
        }
        return data