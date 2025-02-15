from PyQt5 import QtWidgets
from RaspPiReader import pool
from RaspPiReader.ui import plc_comm_settings_form

class PLCCommSettingsFormHandler(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super(PLCCommSettingsFormHandler, self).__init__(parent)
        self.ui = plc_comm_settings_form.Ui_PLCCommSettingsDialog()
        self.ui.setupUi(self)

        # Ensure the combobox for communication mode exists and is populated.
        if not hasattr(self.ui, 'commModeComboBox'):
            # Create and add the combo box if not already created.
            self.ui.commModeComboBox = QtWidgets.QComboBox(self)
            self.ui.commModeComboBox.addItems(['RS485', 'TCP'])
            # You may need to insert it into your layout if it wasn't added by the designer.
            self.ui.verticalLayout.insertWidget(0, self.ui.commModeComboBox)

        # Add IP and port fields for TCP communication
        self.ui.ipLineEdit = QtWidgets.QLineEdit(self)
        self.ui.portLineEdit = QtWidgets.QLineEdit(self)
        self.ui.formLayout.addRow("IP Address:", self.ui.ipLineEdit)
        self.ui.formLayout.addRow("Port:", self.ui.portLineEdit)

        # Connect UI buttons.
        self.ui.savePushButton.clicked.connect(self.save_settings)
        self.ui.cancelPushButton.clicked.connect(self.reject)

        self.load_settings()

    def load_settings(self):
        # Load the saved setting if any.
        current_mode = pool.config('commMode', str, 'RS485')
        index = self.ui.commModeComboBox.findText(current_mode)
        if index >= 0:
            self.ui.commModeComboBox.setCurrentIndex(index)

        # Load IP and port settings
        self.ui.ipLineEdit.setText(pool.config('tcp_host', str, '127.0.0.1'))
        self.ui.portLineEdit.setText(str(pool.config('tcp_port', int, 502)))

    def save_settings(self):
        selected_mode = self.ui.commModeComboBox.currentText()
        pool.set_config('commMode', selected_mode)

        # Save IP and port settings
        pool.set_config('tcp_host', self.ui.ipLineEdit.text().strip())
        pool.set_config('tcp_port', int(self.ui.portLineEdit.text().strip()))

        self.accept()