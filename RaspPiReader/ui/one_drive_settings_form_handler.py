from PyQt5 import QtWidgets
from .one_drive_settings import Ui_OneDriveSettingsDialog
from RaspPiReader.libs.onedrive_api import OneDriveAPI
from RaspPiReader import pool

class OneDriveSettingsFormHandler(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super(OneDriveSettingsFormHandler, self).__init__(parent)
        self.ui = Ui_OneDriveSettingsDialog()
        self.ui.setupUi(self)
        self.ui.testConnectionPushButton.clicked.connect(self.test_connection)
        self.ui.savePushButton.clicked.connect(self.save_settings)
        self.ui.cancelPushButton.clicked.connect(self.reject)
        self.load_settings()

    def load_settings(self):
        self.ui.clientIdLineEdit.setText(pool.config('onedrive_client_id', str, ''))
        self.ui.clientSecretLineEdit.setText(pool.config('onedrive_client_secret', str, ''))
        self.ui.tenantIdLineEdit.setText(pool.config('onedrive_tenant_id', str, ''))
        self.ui.updateIntervalSpinBox.setValue(pool.config('onedrive_update_interval', int, 60))  # Default to 60 seconds

    def save_settings(self):
        pool.set_config('onedrive_client_id', self.ui.clientIdLineEdit.text().strip())
        pool.set_config('onedrive_client_secret', self.ui.clientSecretLineEdit.text().strip())
        pool.set_config('onedrive_tenant_id', self.ui.tenantIdLineEdit.text().strip())
        pool.set_config('onedrive_update_interval', self.ui.updateIntervalSpinBox.value())
        self.accept()

    def test_connection(self):
        client_id = self.ui.clientIdLineEdit.text().strip()
        client_secret = self.ui.clientSecretLineEdit.text().strip()
        tenant_id = self.ui.tenantIdLineEdit.text().strip()
        try:
            onedrive_api = OneDriveAPI()
            onedrive_api.authenticate(client_id, client_secret, tenant_id)
            if onedrive_api.check_connection():
                QtWidgets.QMessageBox.information(self, "Success", "Connection successful")
            else:
                QtWidgets.QMessageBox.critical(self, "Error", "Connection failed")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", str(e))