from PyQt5 import QtWidgets
from RaspPiReader.ui.database_settings import Ui_DatabaseSettingsDialog
from RaspPiReader.libs.database import Database
from RaspPiReader import pool

class DatabaseSettingsFormHandler(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super(DatabaseSettingsFormHandler, self).__init__(parent)
        self.ui = Ui_DatabaseSettingsDialog()
        self.ui.setupUi(self)
        self.ui.testConnectionPushButton.clicked.connect(self.test_connection)
        self.ui.savePushButton.clicked.connect(self.save_settings)
        self.ui.cancelPushButton.clicked.connect(self.reject)
        self.load_settings()

    def load_settings(self):
        self.ui.usernameLineEdit.setText(pool.config('db_username', str, ''))
        self.ui.passwordLineEdit.setText(pool.config('db_password', str, ''))
        self.ui.serverLineEdit.setText(pool.config('db_server', str, ''))
        self.ui.databaseLineEdit.setText(pool.config('db_name', str, ''))

    def save_settings(self):
        pool.set_config('db_username', self.ui.usernameLineEdit.text().strip())
        pool.set_config('db_password', self.ui.passwordLineEdit.text().strip())
        pool.set_config('db_server', self.ui.serverLineEdit.text().strip())
        pool.set_config('db_name', self.ui.databaseLineEdit.text().strip())
        self.accept()

    def test_connection(self):
        username = self.ui.usernameLineEdit.text().strip()
        password = self.ui.passwordLineEdit.text().strip()
        server = self.ui.serverLineEdit.text().strip()
        database = self.ui.databaseLineEdit.text().strip()
        database_url = f"mssql+pyodbc://{username}:{password}@{server}/{database}?driver=ODBC+Driver+17+for+SQL+Server"
        try:
            db = Database(database_url)
            db.create_tables()
            QtWidgets.QMessageBox.information(self, "Success", "Connection successful")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", str(e))