from PyQt5 import QtWidgets
from RaspPiReader import pool
from RaspPiReader.ui import plc_comm_settings_form

class PLCCommSettingsFormHandler(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super(PLCCommSettingsFormHandler, self).__init__(parent)
        self.ui = plc_comm_settings_form.Ui_PLCCommSettingsDialog()
        self.ui.setupUi(self)
        # Ensure a combobox exists for communication mode selection.
        if not hasattr(self.ui, 'commModeComboBox'):
            self.ui.commModeComboBox = QtWidgets.QComboBox(self)
            # Add available options.
            self.ui.commModeComboBox.addItems(["RS485", "TCP"])
            # Insert at the top of the vertical layout.
            self.ui.verticalLayout.insertWidget(0, self.ui.commModeComboBox)
        # Connect UI buttons.
        self.ui.savePushButton.clicked.connect(self.save_settings)
        self.ui.cancelPushButton.clicked.connect(self.reject)
        self.load_settings()

    def load_settings(self):
        comm_mode = pool.config("comm_mode", default_val="rs485").lower()
        index = self.ui.commModeComboBox.findText(comm_mode.upper())
        if index >= 0:
            self.ui.commModeComboBox.setCurrentIndex(index)

    def save_settings(self):
        selected_mode = self.ui.commModeComboBox.currentText().lower()
        pool.set_config("comm_mode", selected_mode)
        self.accept()