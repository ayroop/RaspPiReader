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

    def save_settings(self):
        selected_mode = self.ui.commModeComboBox.currentText()
        pool.set_config('commMode', selected_mode)
        self.accept()