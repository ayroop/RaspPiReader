import enum

import serial
from PyQt5.QtCore import QSettings, Qt
from PyQt5.QtWidgets import QMainWindow, QSpinBox, QDoubleSpinBox, QLineEdit, QComboBox, QLabel, QCheckBox, QMessageBox, \
    QErrorMessage

from RaspPiReader import pool
from .color_label import ColorLabel
from .settingForm import SettingForm

CHANNEL_COUNT = 14
general_settings = {
    "baudrateComboBox": "baudrate",
    "parityComboBox": "parity",
    "databitsComboBox": "databits",
    "stopbitsComboBox": "stopbits",
    "readingaddrLineEdit": "reading_address",
    "conTypeComboBox": "register_read_type",
    "portLineEdit": "port",
    "editLeftVLabel": "left_v_label",
    "editRightVLabel": "right_v_label",
    "editHLabel": "h_label",
    "timeIntervalDoubleSpinBox": "time_interval",
    "panelTimeIntervalDoubleSpinBox": "panel_time_interval",
    "accurateTimeDoubleSpinBox": "accuarate_data_time",
    "signinStatus": "signin_status",
    "signinEmail": "signin_email",
    "filePathLineEdit": "csv_file_path",
    "delimiterLineEdit": "csv_delimiter",
    "gdriveSpinBox": "gdrive_update_interval",
    "CoreTempChannelSpinBox": "core_temp_channel",
    "pressureChannelSpinBox": "pressure_channel",
}

channel_settings = {
    "editAd": "address",
    "editLabel": "label",
    "editPV": "pv",
    "editSV": "sv",
    "editSP": "sp",
    "editLimitLow": "limit_low",
    "editLimitHigh": "limit_high",
    "editDecPoint": "decimal_point",
    "checkScale": "scale",
    "comboAxis": "axis_direction",
    "labelColor": "color",
    'checkActive': "active",
    'editOutLimitLow': "min_scale_range",
    'editOutLimitHigh': "max_scale_range",
}

READ_INPUT_REGISTERS = "Read Input Registers"
READ_HOLDING_REGISTERS = "Read Holding Registers"

get_value_method_map = {
    QSpinBox: {
        "get": QSpinBox.value,
        "set": lambda self, val: QSpinBox.setValue(self, int(val)),
    },
    QDoubleSpinBox: {
        "get": QDoubleSpinBox.value,
        "set": lambda self, val: QDoubleSpinBox.setValue(self, float(val)),
    },
    QLineEdit: {
        "get": QLineEdit.text,
        "set": lambda self, val: QLineEdit.setText(self, str(val)),
    },
    QComboBox: {
        "get": QComboBox.currentText,
        "set": lambda self, val: QComboBox.setCurrentText(self, str(val)),
    },
    QLabel: {
        "get": QLabel.text,
        "set": lambda self, val: QLabel.setText(self, str(val)),
    },
    QCheckBox: {
        "get": lambda self: int(QCheckBox.isChecked(self)),
        "set": lambda self, val: QCheckBox.setChecked(self, bool(int(val))),
    },
    ColorLabel: {
        "get": ColorLabel.value,
        "set": lambda self, val: ColorLabel.setValue(self, str(val)),
    },
}


class SettingFormHandler(QMainWindow):
    def __init__(self) -> object:
        super(SettingFormHandler, self).__init__()
        self.form_obj = SettingForm()
        self.form_obj.setupUi(self)
        self.settings = QSettings('RaspPiHandler', 'RaspPiModbusReader')
        self.set_connections()
        self.close_prompt = True
        self.setWindowModality(Qt.ApplicationModal)
        self.showMaximized()
        self.show()

    def set_connections(self):
        self.buttonSave.clicked.connect(self.save_and_close)
        self.buttonCancel.clicked.connect(self.close)

    def save_settings(self):
        for obj_name, key_name in general_settings.items():
            self.settings.setValue(key_name, self.get_val(obj_name))

        for obj_name, key_name in channel_settings.items():
            for i in range(1, CHANNEL_COUNT + 1):
                self.settings.setValue(key_name + str(i), self.get_val(obj_name + str(i)))

        self.write_to_device()

    def load_settings(self):
        self.load_connection_combo_boxes()

        for obj_name, key_name in general_settings.items():
            value = self.settings.value(key_name)
            if value != None:
                self.set_val(obj_name, value)

        for obj_name, key_name in channel_settings.items():
            for i in range(1, CHANNEL_COUNT + 1):
                value = self.settings.value(key_name + str(i))
                if value != None:
                    self.set_val(obj_name + str(i), value)

    def load_connection_combo_boxes(self):
        self.baudrateComboBox.addItems(['9600', '19200', '38400', '56800', '115200'])

        self.parityComboBox.addItems([serial.PARITY_NAMES[serial.PARITY_NONE],
                                      serial.PARITY_NAMES[serial.PARITY_ODD],
                                      serial.PARITY_NAMES[serial.PARITY_EVEN]])

        self.databitsComboBox.addItems([str(serial.SEVENBITS),
                                        str(serial.EIGHTBITS)])

        self.stopbitsComboBox.addItems([str(serial.STOPBITS_ONE),
                                        str(serial.STOPBITS_ONE_POINT_FIVE),
                                        str(serial.STOPBITS_TWO)])

        self.conTypeComboBox.addItems([READ_HOLDING_REGISTERS,
                                       READ_INPUT_REGISTERS]),


    def get_val(self, name):
        if hasattr(self, name):
            obj = getattr(self, name)
            return get_value_method_map[type(obj)]["get"](obj)

    def set_val(self, name, value):
        if hasattr(self, name):
            obj = getattr(self, name)
            try:
                get_value_method_map[type(obj)]["set"](obj, value)
            except Exception as e:
                print(e)
        return

    def write_to_device(self):
        from RaspPiReader.libs.communication import dataReader
        try:
            dataReader.start()
        except Exception as e:
            print("Failed to start data reader or it is already started.\n" + str(e))

        for ch in range(CHANNEL_COUNT):
            if not pool.config('active' + str(ch + 1), bool):
                continue

            try:
                dataReader.writeData(pool.config('address' + str(ch + 1), int), int(pool.config('sv' + str(ch + 1)), 16),
                                     pool.config('sp' + str(ch + 1), int))
            except Exception as e:
                error_dialog = QErrorMessage(self)
                error_dialog.showMessage('Failed to write settings to device.\n' + str(e))
                break

        dataReader.stop()

    def save_and_close(self):
        self.save_settings()
        self.close_prompt = False
        self.close()

    def close(self):
        self.close_prompt = False
        super().close()

    def show(self):
        self.load_settings()
        super().show()

    def closeEvent(self, event):
        if not self.close_prompt:
            event.accept()
        else:
            quit_msg = "Save changes before exit?"
            reply = QMessageBox.question(self, 'Message',
                                         quit_msg, (QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel))
            if reply == QMessageBox.Yes:
                self.save_settings()
                event.accept()
            elif reply == QMessageBox.No:
                event.accept()
            elif reply == QMessageBox.Cancel:
                event.ignore()
        # super().closeEvent(event)
