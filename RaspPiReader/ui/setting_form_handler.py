import serial
from PyQt5.QtCore import QSettings, Qt
from PyQt5.QtWidgets import QMainWindow, QSpinBox, QDoubleSpinBox, QLineEdit, QComboBox, QLabel, QCheckBox, QMessageBox, QErrorMessage

from RaspPiReader import pool
from .color_label import ColorLabel
from .settingForm import Ui_SettingForm as SettingForm
from RaspPiReader.libs.database import Database
from RaspPiReader.libs.models import GeneralConfigSettings

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
        self.db = Database("sqlite:///local_database.db")
        self.settings = QSettings('RaspPiHandler', 'RaspPiModbusReader')
        self.set_connections()
        self.close_prompt = True
        self.setWindowModality(Qt.ApplicationModal)
        self.showMaximized()
        self.show()

    def set_connections(self):
        self.form_obj.buttonSave.clicked.connect(self.save_and_close)
        self.form_obj.buttonCancel.clicked.connect(self.close)

    def save_settings(self):
        settings = self.db.session.query(GeneralConfigSettings).first()
        if settings:
            settings.baudrate = int(self.get_val("baudrateComboBox"))
            settings.parity = self.get_val("parityComboBox")
            settings.databits = int(self.get_val("databitsComboBox"))
            settings.stopbits = float(self.get_val("stopbitsComboBox"))
            settings.reading_address = self.get_val("readingaddrLineEdit")
            settings.register_read_type = self.get_val("conTypeComboBox")
            settings.port = self.get_val("portLineEdit")
            settings.left_v_label = self.get_val("editLeftVLabel")
            settings.right_v_label = self.get_val("editRightVLabel")
            settings.h_label = self.get_val("editHLabel")
            settings.time_interval = self.get_val("timeIntervalDoubleSpinBox")
            settings.panel_time_interval = self.get_val("panelTimeIntervalDoubleSpinBox")
            settings.accuarate_data_time = self.get_val("accurateTimeDoubleSpinBox")
            settings.signin_status = self.get_val("signinStatus")
            settings.signin_email = self.get_val("signinEmail")
            settings.csv_file_path = self.get_val("filePathLineEdit")
            settings.csv_delimiter = self.get_val("delimiterLineEdit")
            settings.gdrive_update_interval = self.get_val("gdriveSpinBox")
            settings.core_temp_channel = self.get_val("CoreTempChannelSpinBox")
            settings.pressure_channel = self.get_val("pressureChannelSpinBox")
        else:
            settings = GeneralConfigSettings(
                baudrate=int(self.get_val("baudrateComboBox")),
                parity=self.get_val("parityComboBox"),
                databits=int(self.get_val("databitsComboBox")),
                stopbits=float(self.get_val("stopbitsComboBox")),
                reading_address=self.get_val("readingaddrLineEdit"),
                register_read_type=self.get_val("conTypeComboBox"),
                port=self.get_val("portLineEdit"),
                left_v_label=self.get_val("editLeftVLabel"),
                right_v_label=self.get_val("editRightVLabel"),
                h_label=self.get_val("editHLabel"),
                time_interval=self.get_val("timeIntervalDoubleSpinBox"),
                panel_time_interval=self.get_val("panelTimeIntervalDoubleSpinBox"),
                accuarate_data_time=self.get_val("accurateTimeDoubleSpinBox"),
                signin_status=self.get_val("signinStatus"),
                signin_email=self.get_val("signinEmail"),
                csv_file_path=self.get_val("filePathLineEdit"),
                csv_delimiter=self.get_val("delimiterLineEdit"),
                gdrive_update_interval=self.get_val("gdriveSpinBox"),
                core_temp_channel=self.get_val("CoreTempChannelSpinBox"),
                pressure_channel=self.get_val("pressureChannelSpinBox")
            )
            self.db.session.add(settings)
        self.db.session.commit()

        self.write_to_device()

    def load_settings(self):
        self.load_connection_combo_boxes()

        settings = self.db.session.query(GeneralConfigSettings).first()
        if settings:
            self.set_val("baudrateComboBox", settings.baudrate)
            self.set_val("parityComboBox", settings.parity)
            self.set_val("databitsComboBox", settings.databits)
            self.set_val("stopbitsComboBox", settings.stopbits)
            self.set_val("readingaddrLineEdit", settings.reading_address)
            self.set_val("conTypeComboBox", settings.register_read_type)
            self.set_val("portLineEdit", settings.port)
            self.set_val("editLeftVLabel", settings.left_v_label)
            self.set_val("editRightVLabel", settings.right_v_label)
            self.set_val("editHLabel", settings.h_label)
            self.set_val("timeIntervalDoubleSpinBox", settings.time_interval)
            self.set_val("panelTimeIntervalDoubleSpinBox", settings.panel_time_interval)
            self.set_val("accurateTimeDoubleSpinBox", settings.accuarate_data_time)
            self.set_val("signinStatus", settings.signin_status)
            self.set_val("signinEmail", settings.signin_email)
            self.set_val("filePathLineEdit", settings.csv_file_path)
            self.set_val("delimiterLineEdit", settings.csv_delimiter)
            self.set_val("gdriveSpinBox", settings.gdrive_update_interval)
            self.set_val("CoreTempChannelSpinBox", settings.core_temp_channel)
            self.set_val("pressureChannelSpinBox", settings.pressure_channel)
        else:
            self.set_val("baudrateComboBox", '9600')
            self.set_val("parityComboBox", 'N')
            self.set_val("databitsComboBox", '8')
            self.set_val("stopbitsComboBox", '1')
            self.set_val("readingaddrLineEdit", '0')
            self.set_val("conTypeComboBox", 'Read Holding Registers')
            self.set_val("portLineEdit", 'COM1')
            self.set_val("editLeftVLabel", 'Left V')
            self.set_val("editRightVLabel", 'Right V')
            self.set_val("editHLabel", 'H')
            self.set_val("timeIntervalDoubleSpinBox", 1.0)
            self.set_val("panelTimeIntervalDoubleSpinBox", 1.0)
            self.set_val("accurateTimeDoubleSpinBox", 1.0)
            self.set_val("signinStatus", False)
            self.set_val("signinEmail", '')
            self.set_val("filePathLineEdit", '')
            self.set_val("delimiterLineEdit", ',')
            self.set_val("gdriveSpinBox", 60)
            self.set_val("CoreTempChannelSpinBox", 1)
            self.set_val("pressureChannelSpinBox", 1)

    def load_connection_combo_boxes(self):
        self.form_obj.baudrateComboBox.addItems(['9600', '19200', '38400', '56800', '115200'])

        self.form_obj.parityComboBox.addItems([serial.PARITY_NAMES[serial.PARITY_NONE],
                                               serial.PARITY_NAMES[serial.PARITY_ODD],
                                               serial.PARITY_NAMES[serial.PARITY_EVEN]])

        self.form_obj.databitsComboBox.addItems([str(serial.SEVENBITS),
                                                 str(serial.EIGHTBITS)])

        self.form_obj.stopbitsComboBox.addItems([str(serial.STOPBITS_ONE),
                                                 str(serial.STOPBITS_ONE_POINT_FIVE),
                                                 str(serial.STOPBITS_TWO)])

        self.form_obj.conTypeComboBox.addItems([READ_HOLDING_REGISTERS,
                                                READ_INPUT_REGISTERS])

    def get_val(self, name):
        if hasattr(self.form_obj, name):
            obj = getattr(self.form_obj, name)
            return get_value_method_map[type(obj)]["get"](obj)

    def set_val(self, name, value):
        if hasattr(self.form_obj, name):
            obj = getattr(self.form_obj, name)
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