from PyQt5 import QtWidgets
from .user_edit_form import Ui_UserEditDialog

class UserEditFormHandler(QtWidgets.QDialog):
    def __init__(self, user_data=None, parent=None):
        super(UserEditFormHandler, self).__init__(parent)
        self.ui = Ui_UserEditDialog()
        self.ui.setupUi(self)
        
        # If the UI does not contain a roleComboBox, create one manually.
        if not hasattr(self.ui, "roleComboBox"):
            self.ui.roleComboBox = QtWidgets.QComboBox(self)
            self.ui.roleComboBox.addItems(["Operator", "Supervisor"])
            self.ui.formLayout.addRow("Role:", self.ui.roleComboBox)

        self.ui.okPushButton.clicked.connect(self.accept)
        self.ui.cancelPushButton.clicked.connect(self.reject)
        
        if user_data:
            self.ui.usernameLineEdit.setText(user_data.username)
            self.ui.passwordLineEdit.setText(user_data.password)
            self.ui.settingsCheckBox.setChecked(user_data.settings)
            self.ui.searchCheckBox.setChecked(user_data.search)
            # Set the role based on the provided data
            index = self.ui.roleComboBox.findText(user_data.role)
            if index >= 0:
                self.ui.roleComboBox.setCurrentIndex(index)

    def get_data(self):
        data = {
            'username': self.ui.usernameLineEdit.text().strip(),
            'password': self.ui.passwordLineEdit.text().strip(),
            'settings': self.ui.settingsCheckBox.isChecked(),
            'search': self.ui.searchCheckBox.isChecked(),
            'user_mgmt_page': False,  # Default value
            'role': self.ui.roleComboBox.currentText()
        }
        return data