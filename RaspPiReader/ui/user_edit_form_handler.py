from PyQt5 import QtWidgets
from .user_edit_form import Ui_UserEditDialog

class UserEditFormHandler(QtWidgets.QDialog):
    def __init__(self, user_data=None, parent=None):
        super(UserEditFormHandler, self).__init__(parent)
        self.ui = Ui_UserEditDialog()
        self.ui.setupUi(self)
        
        # Create missing UI elements if they don't exist
        if not hasattr(self.ui, "roleLineEdit"):
            self.ui.roleLineEdit = QtWidgets.QLineEdit(self)
            self.ui.roleLineEdit.setPlaceholderText("Enter user role (e.g. Operator, Supervisor, etc.)")
            self.ui.formLayout.addRow("Role:", self.ui.roleLineEdit)
            
        if not hasattr(self.ui, "settingsCheckBox"):
            self.ui.settingsCheckBox = QtWidgets.QCheckBox(self)
            self.ui.settingsCheckBox.setText("Settings Access")
            self.ui.formLayout.addRow("", self.ui.settingsCheckBox)
            
        if not hasattr(self.ui, "searchCheckBox"):
            self.ui.searchCheckBox = QtWidgets.QCheckBox(self)
            self.ui.searchCheckBox.setText("Search Access")
            self.ui.formLayout.addRow("", self.ui.searchCheckBox)

        self.ui.okPushButton.clicked.connect(self.accept)
        self.ui.cancelPushButton.clicked.connect(self.reject)
        
        if user_data:
            # Set username and password if those fields exist
            if hasattr(self.ui, "usernameLineEdit"):
                self.ui.usernameLineEdit.setText(user_data.username)
            if hasattr(self.ui, "passwordLineEdit"):
                self.ui.passwordLineEdit.setText(user_data.password)
            
            # Set checkboxes if they exist and user has the attributes
            if hasattr(self.ui, "settingsCheckBox") and hasattr(user_data, "settings"):
                self.ui.settingsCheckBox.setChecked(user_data.settings)
            if hasattr(self.ui, "searchCheckBox") and hasattr(user_data, "search"):
                self.ui.searchCheckBox.setChecked(user_data.search)
                
            # Set role if it exists
            if hasattr(self.ui, "roleLineEdit") and hasattr(user_data, 'role') and user_data.role:
                self.ui.roleLineEdit.setText(user_data.role)

    def get_data(self):
        data = {
            'username': self.ui.usernameLineEdit.text().strip() if hasattr(self.ui, "usernameLineEdit") else "",
            'password': self.ui.passwordLineEdit.text().strip() if hasattr(self.ui, "passwordLineEdit") else "",
            'settings': self.ui.settingsCheckBox.isChecked() if hasattr(self.ui, "settingsCheckBox") else False,
            'search': self.ui.searchCheckBox.isChecked() if hasattr(self.ui, "searchCheckBox") else False,
            'user_mgmt_page': False,  # Default value
            'role': self.ui.roleLineEdit.text().strip() or "Operator" if hasattr(self.ui, "roleLineEdit") else "Operator"
        }
        return data