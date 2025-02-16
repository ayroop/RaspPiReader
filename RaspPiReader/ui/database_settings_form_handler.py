from PyQt5 import QtWidgets
from RaspPiReader.ui.database_settings import Ui_DatabaseSettingsDialog
from RaspPiReader.libs.database import Database
from RaspPiReader.libs.models import DatabaseSettings
from RaspPiReader import pool

class DatabaseSettingsFormHandler(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super(DatabaseSettingsFormHandler, self).__init__(parent)
        self.ui = Ui_DatabaseSettingsDialog()
        self.ui.setupUi(self)
        self.ui.testConnectionPushButton.clicked.connect(self.test_connection)
        self.ui.savePushButton.clicked.connect(self.save_settings)
        self.ui.cancelPushButton.clicked.connect(self.reject)
        self.db = Database("sqlite:///local_database.db")
        self.load_settings()

    def load_settings(self):
        settings = self.db.session.query(DatabaseSettings).first()
        if settings:
            self.ui.usernameLineEdit.setText(settings.db_username)
            self.ui.passwordLineEdit.setText(settings.db_password)
            self.ui.serverLineEdit.setText(settings.db_server)
            self.ui.databaseLineEdit.setText(settings.db_name)
        else:
            self.ui.usernameLineEdit.setText('')
            self.ui.passwordLineEdit.setText('')
            self.ui.serverLineEdit.setText('')
            self.ui.databaseLineEdit.setText('')

    def save_settings(self):
        db_username = self.ui.usernameLineEdit.text().strip()
        db_password = self.ui.passwordLineEdit.text().strip()
        db_server = self.ui.serverLineEdit.text().strip()
        db_name = self.ui.databaseLineEdit.text().strip()

        settings = self.db.session.query(DatabaseSettings).first()
        if settings:
            settings.db_username = db_username
            settings.db_password = db_password
            settings.db_server = db_server
            settings.db_name = db_name
        else:
            settings = DatabaseSettings(
                db_username=db_username,
                db_password=db_password,
                db_server=db_server,
                db_name=db_name
            )
            self.db.session.add(settings)
        self.db.session.commit()

        self.accept()

    def test_connection(self):
        db_username = self.ui.usernameLineEdit.text().strip()
        db_password = self.ui.passwordLineEdit.text().strip()
        db_server = self.ui.serverLineEdit.text().strip()
        db_name = self.ui.databaseLineEdit.text().strip()
        database_url = f"mssql+pyodbc://{db_username}:{db_password}@{db_server}/{db_name}?driver=ODBC+Driver+17+for+SQL+Server"
        try:
            db = Database(database_url)
            db.create_tables()
            QtWidgets.QMessageBox.information(self, "Success", "Connection successful")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", str(e))