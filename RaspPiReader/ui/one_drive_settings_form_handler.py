from PyQt5 import QtWidgets
from PyQt5.QtWidgets import QMessageBox
from .one_drive_settings import Ui_OneDriveSettingsDialog
from RaspPiReader.libs.database import Database
from RaspPiReader.libs.models import OneDriveSettings
from RaspPiReader.libs.onedrive_api import OneDriveAPI
from RaspPiReader import pool
import logging

class OneDriveSettingsFormHandler(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super(OneDriveSettingsFormHandler, self).__init__(parent)
        self.ui = Ui_OneDriveSettingsDialog()
        self.ui.setupUi(self)
        self.ui.testConnectionPushButton.clicked.connect(self.test_connection)
        self.ui.savePushButton.clicked.connect(self.save_settings)
        self.ui.cancelPushButton.clicked.connect(self.reject)
        self.db = Database("sqlite:///local_database.db")
        self.load_settings()

    def load_settings(self):
        settings = self.db.session.query(OneDriveSettings).first()
        if settings:
            self.ui.clientIdLineEdit.setText(settings.client_id)
            self.ui.clientSecretLineEdit.setText(settings.client_secret)
            self.ui.tenantIdLineEdit.setText(settings.tenant_id)
            self.ui.updateIntervalSpinBox.setValue(settings.update_interval)
        else:
            self.ui.clientIdLineEdit.setText("")
            self.ui.clientSecretLineEdit.setText("")
            self.ui.tenantIdLineEdit.setText("")
            self.ui.updateIntervalSpinBox.setValue(60)

    def save_settings(self):
        client_id = self.ui.clientIdLineEdit.text().strip()
        client_secret = self.ui.clientSecretLineEdit.text().strip()
        tenant_id = self.ui.tenantIdLineEdit.text().strip()
        update_interval = self.ui.updateIntervalSpinBox.value()

        settings = self.db.session.query(OneDriveSettings).first()
        if settings:
            settings.client_id = client_id
            settings.client_secret = client_secret
            settings.tenant_id = tenant_id
            settings.update_interval = update_interval
        else:
            settings = OneDriveSettings(
                client_id=client_id,
                client_secret=client_secret,
                tenant_id=tenant_id,
                update_interval=update_interval
            )
            self.db.session.add(settings)
        self.db.session.commit()

        # Update pool config for immediate use
        pool.set_config('onedrive_client_id', client_id)
        pool.set_config('onedrive_client_secret', client_secret)
        pool.set_config('onedrive_tenant_id', tenant_id)
        pool.set_config('onedrive_update_interval', update_interval)
        
        self.accept()

    def test_connection(self):
        client_id = self.ui.clientIdLineEdit.text().strip()
        client_secret = self.ui.clientSecretLineEdit.text().strip()
        tenant_id = self.ui.tenantIdLineEdit.text().strip()
        try:
            onedrive_api = OneDriveAPI()
            onedrive_api.authenticate(client_id, client_secret, tenant_id)
            if onedrive_api.check_connection():
                QMessageBox.information(self, "Success", "Connected to OneDrive successfully!")
            else:
                QMessageBox.warning(self, "Warning", "Authentication succeeded but connection test failed.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Connection test failed: {str(e)}")
            logging.error(f"OneDrive connection test failed: {str(e)}")