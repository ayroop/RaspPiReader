from PyQt5 import QtWidgets
from RaspPiReader import pool
from RaspPiReader.ui import plc_comm_settings_form
from RaspPiReader.libs.database import Database
from RaspPiReader.libs.models import PLCCommSettings

class PLCCommSettingsFormHandler(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super(PLCCommSettingsFormHandler, self).__init__(parent)
        self.ui = plc_comm_settings_form.Ui_PLCCommSettingsDialog()
        self.ui.setupUi(self)
        self.db = Database("sqlite:///local_database.db")

        # Connect UI buttons.
        self.ui.savePushButton.clicked.connect(self.save_settings)
        self.ui.cancelPushButton.clicked.connect(self.reject)

        self.load_settings()

    def load_settings(self):
        # Load the saved setting if any.
        settings = self.db.session.query(PLCCommSettings).first()
        if settings:
            self.ui.commModeComboBox.setCurrentText(settings.comm_mode)
            self.ui.ipLineEdit.setText(settings.tcp_host)
            self.ui.portLineEdit.setText(str(settings.tcp_port))
            self.ui.comPortLineEdit.setText(settings.com_port)
        else:
            self.ui.commModeComboBox.setCurrentText('RS485')
            self.ui.ipLineEdit.setText('127.0.0.1')
            self.ui.portLineEdit.setText('502')
            self.ui.comPortLineEdit.setText('COM3')

    def save_settings(self):
        selected_mode = self.ui.commModeComboBox.currentText()
        tcp_host = self.ui.ipLineEdit.text().strip()
        tcp_port = int(self.ui.portLineEdit.text().strip())
        com_port = self.ui.comPortLineEdit.text().strip()

        settings = self.db.session.query(PLCCommSettings).first()
        if settings:
            settings.comm_mode = selected_mode
            settings.tcp_host = tcp_host
            settings.tcp_port = tcp_port
            settings.com_port = com_port
        else:
            settings = PLCCommSettings(
                comm_mode=selected_mode,
                tcp_host=tcp_host,
                tcp_port=tcp_port,
                com_port=com_port
            )
            self.db.session.add(settings)
        self.db.session.commit()

        self.accept()