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
        username = self.ui.usernameLineEdit.text().strip()
        password = self.ui.passwordLineEdit.text().strip()
        role = self.ui.roleLineEdit.text().strip()  # new field for the role
        settings = self.ui.settingsCheckBox.isChecked() if hasattr(self.ui, "settingsCheckBox") else False
        search = self.ui.searchCheckBox.isChecked() if hasattr(self.ui, "searchCheckBox") else False
        # Set user_mgmt_page True if role is "Supervisor" (case-insensitive), otherwise False
        user_mgmt_page = True if role.lower() == "supervisor" else False
        return {
            "username": username,
            "password": password,
            "role": role,
            "settings": settings,
            "search": search,
            "user_mgmt_page": user_mgmt_page
        }