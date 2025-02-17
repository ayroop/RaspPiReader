import serial
from PyQt5.QtCore import QSettings, Qt
from PyQt5.QtWidgets import (
    QMainWindow,
    QSpinBox,
    QDoubleSpinBox,
    QLineEdit,
    QComboBox,
    QLabel,
    QCheckBox,
    QMessageBox,
    QErrorMessage,
)
from RaspPiReader import pool
from .color_label import ColorLabel
from .settingForm import Ui_SettingForm as SettingForm
from RaspPiReader.libs.database import Database
from RaspPiReader.libs.models import GeneralConfigSettings
import logging

CHANNEL_COUNT = 14
READ_INPUT_REGISTERS = "Read Input Registers"
READ_HOLDING_REGISTERS = "Read Holding Registers"

logging.basicConfig(level=logging.DEBUG)


class SettingFormHandler(QMainWindow):
    def __init__(self) -> object:
        super(SettingFormHandler, self).__init__()
        self.form_obj = SettingForm()
        self.form_obj.setupUi(self)
        self.db = Database("sqlite:///local_database.db")
        # Ensure that database tables are created before any operation.
        self.db.create_tables()
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
        try:
            settings = self.db.session.query(GeneralConfigSettings).first()
            # Retrieve values from UI (using defaults if necessary)
            baudrate_val = self.get_val("baudrateLineEdit") or "9600"
            parity_val = self.get_val("parityLineEdit") or "N"
            databits_val = self.get_val("databitsLineEdit") or "8"
            stopbits_val = self.get_val("stopbitsLineEdit") or "1"
            reading_addr = self.get_val("readingaddrLineEdit") or "0"
            left_v_label = self.get_val("editLeftVLabel") or "Left V"
            right_v_label = self.get_val("editRightVLabel") or "Right V"
            h_label = self.get_val("editHLabel") or "H"
            time_interval_val = self.get_val("timeIntervalDoubleSpinBox") or "1.0"
            scale_range_val = self.get_val("editScaleRange") or "1000"
            file_path = self.get_val("filePathLineEdit") or ""
            delimiter = self.get_val("delimiterLineEdit") or ","
            gdrive_update_interval_val = self.get_val("gdriveSpinBox") or "60"
            core_temp_channel_val = self.get_val("CoreTempChannelSpinBox") or "1"
            pressure_channel_val = self.get_val("pressureChannelSpinBox") or "1"
            # Convert signin_status to boolean (default False if empty)
            signin_status_val = bool(int(self.get_val("signinStatus") or "0"))

            # For widgets not present in the UI (and model) such as conTypeComboBox and portLineEdit, use empty strings.
            register_read_type = self.get_val("conTypeComboBox") if hasattr(self.form_obj, "conTypeComboBox") else ""
            port_val = self.get_val("portLineEdit") if hasattr(self.form_obj, "portLineEdit") else ""

            if settings:
                settings.baudrate = int(baudrate_val)
                settings.parity = parity_val
                settings.databits = int(databits_val)
                settings.stopbits = float(stopbits_val)
                settings.reading_address = reading_addr
                settings.register_read_type = register_read_type
                settings.port = port_val
                settings.left_v_label = left_v_label
                settings.right_v_label = right_v_label
                settings.h_label = h_label
                settings.time_interval = float(time_interval_val)
                settings.scale_range = int(scale_range_val)
                settings.signin_status = signin_status_val
                settings.signin_email = self.get_val("signinEmail") if hasattr(self.form_obj, "signinEmail") else ""
                settings.csv_file_path = file_path
                settings.csv_delimiter = delimiter
                settings.gdrive_update_interval = int(gdrive_update_interval_val)
                settings.core_temp_channel = int(core_temp_channel_val)
                settings.pressure_channel = int(pressure_channel_val)
            else:
                settings = GeneralConfigSettings(
                    baudrate=int(baudrate_val),
                    parity=parity_val,
                    databits=int(databits_val),
                    stopbits=float(stopbits_val),
                    reading_address=reading_addr,
                    register_read_type=register_read_type,
                    port=port_val,
                    left_v_label=left_v_label,
                    right_v_label=right_v_label,
                    h_label=h_label,
                    time_interval=float(time_interval_val),
                    scale_range=int(scale_range_val),
                    signin_status=signin_status_val,
                    signin_email=self.get_val("signinEmail") if hasattr(self.form_obj, "signinEmail") else "",
                    csv_file_path=file_path,
                    csv_delimiter=delimiter,
                    gdrive_update_interval=int(gdrive_update_interval_val),
                    core_temp_channel=int(core_temp_channel_val),
                    pressure_channel=int(pressure_channel_val)
                )
                self.db.session.add(settings)
            self.db.session.commit()
            logging.info("Settings saved successfully.")
            self.write_to_device()
        except Exception as e:
            logging.error(f"Error saving settings: {e}")

    def load_settings(self):
        try:
            self.load_connection_combo_boxes()  # Populate connection combo boxes first.
            settings = self.db.session.query(GeneralConfigSettings).first()
            if settings:
                self.set_val("baudrateLineEdit", settings.baudrate if settings.baudrate else "9600")
                self.set_val("parityLineEdit", settings.parity if settings.parity else "N")
                self.set_val("databitsLineEdit", settings.databits if settings.databits else "8")
                self.set_val("stopbitsLineEdit", settings.stopbits if settings.stopbits else "1")
                self.set_val("readingaddrLineEdit", settings.reading_address if settings.reading_address else "0")
                if hasattr(self.form_obj, "editLeftVLabel"):
                    self.set_val("editLeftVLabel", settings.left_v_label if settings.left_v_label else "Left V")
                if hasattr(self.form_obj, "editRightVLabel"):
                    self.set_val("editRightVLabel", settings.right_v_label if settings.right_v_label else "Right V")
                if hasattr(self.form_obj, "editHLabel"):
                    self.set_val("editHLabel", settings.h_label if settings.h_label else "H")
                if hasattr(self.form_obj, "timeIntervalDoubleSpinBox"):
                    self.set_val("timeIntervalDoubleSpinBox", settings.time_interval if settings.time_interval else 1.0)
                if hasattr(self.form_obj, "editScaleRange"):
                    self.set_val("editScaleRange", settings.scale_range if settings.scale_range else 1000)
                if hasattr(self.form_obj, "filePathLineEdit"):
                    self.set_val("filePathLineEdit", settings.csv_file_path if settings.csv_file_path else "")
                if hasattr(self.form_obj, "delimiterLineEdit"):
                    self.set_val("delimiterLineEdit", settings.csv_delimiter if settings.csv_delimiter else ",")
                if hasattr(self.form_obj, "gdriveSpinBox"):
                    self.set_val("gdriveSpinBox", settings.gdrive_update_interval if settings.gdrive_update_interval else 60)
                if hasattr(self.form_obj, "CoreTempChannelSpinBox"):
                    self.set_val("CoreTempChannelSpinBox", settings.core_temp_channel if settings.core_temp_channel else 1)
                if hasattr(self.form_obj, "pressureChannelSpinBox"):
                    self.set_val("pressureChannelSpinBox", settings.pressure_channel if settings.pressure_channel else 1)
            else:
                # Apply defaults if no settings exist.
                self.set_val("baudrateLineEdit", "9600")
                self.set_val("parityLineEdit", "N")
                self.set_val("databitsLineEdit", "8")
                self.set_val("stopbitsLineEdit", "1")
                self.set_val("readingaddrLineEdit", "0")
                if hasattr(self.form_obj, "editLeftVLabel"):
                    self.set_val("editLeftVLabel", "Left V")
                if hasattr(self.form_obj, "editRightVLabel"):
                    self.set_val("editRightVLabel", "Right V")
                if hasattr(self.form_obj, "editHLabel"):
                    self.set_val("editHLabel", "H")
                if hasattr(self.form_obj, "timeIntervalDoubleSpinBox"):
                    self.set_val("timeIntervalDoubleSpinBox", 1.0)
                if hasattr(self.form_obj, "editScaleRange"):
                    self.set_val("editScaleRange", 1000)
                if hasattr(self.form_obj, "filePathLineEdit"):
                    self.set_val("filePathLineEdit", "")
                if hasattr(self.form_obj, "delimiterLineEdit"):
                    self.set_val("delimiterLineEdit", ",")
                if hasattr(self.form_obj, "gdriveSpinBox"):
                    self.set_val("gdriveSpinBox", 60)
                if hasattr(self.form_obj, "CoreTempChannelSpinBox"):
                    self.set_val("CoreTempChannelSpinBox", 1)
                if hasattr(self.form_obj, "pressureChannelSpinBox"):
                    self.set_val("pressureChannelSpinBox", 1)
        except Exception as e:
            logging.error(f"Error loading settings: {e}")

    def load_connection_combo_boxes(self):
        if hasattr(self.form_obj, "baudrateLineEdit"):
            self.form_obj.baudrateLineEdit.setText('9600')
        else:
            logging.warning("baudrateLineEdit not found in form.")

        if hasattr(self.form_obj, "parityLineEdit"):
            self.form_obj.parityLineEdit.setText('N')
        else:
            logging.warning("parityLineEdit not found in form.")

        if hasattr(self.form_obj, "databitsLineEdit"):
            self.form_obj.databitsLineEdit.setText('8')
        else:
            logging.warning("databitsLineEdit not found in form.")

        if hasattr(self.form_obj, "stopbitsLineEdit"):
            self.form_obj.stopbitsLineEdit.setText('1')
        else:
            logging.warning("stopbitsLineEdit not found in form.")

        if hasattr(self.form_obj, "conTypeComboBox"):
            self.form_obj.conTypeComboBox.addItems([READ_HOLDING_REGISTERS, READ_INPUT_REGISTERS])
        else:
            logging.warning("conTypeComboBox not found in form.")

    def get_val(self, name):
        """
        Retrieves the value from a widget by checking its type explicitly.
        """
        if not hasattr(self.form_obj, name):
            logging.warning(f"{name} widget not found in form.")
            return ""
        obj = getattr(self.form_obj, name)
        if isinstance(obj, QSpinBox):
            return obj.value()
        elif isinstance(obj, QDoubleSpinBox):
            return obj.value()
        elif isinstance(obj, QLineEdit):
            return obj.text()
        elif isinstance(obj, QComboBox):
            return obj.currentText()
        elif isinstance(obj, QLabel):
            return obj.text()
        elif isinstance(obj, QCheckBox):
            return int(obj.isChecked())
        elif isinstance(obj, ColorLabel):
            return obj.value()
        else:
            logging.warning(f"No get method defined for widget {name} of type {type(obj)}")
            return ""

    def set_val(self, name, value):
        """
        Sets the value for a widget by checking its type explicitly.
        """
        if not hasattr(self.form_obj, name):
            logging.warning(f"{name} widget not found in form.")
            return
        obj = getattr(self.form_obj, name)
        try:
            if isinstance(obj, QSpinBox):
                obj.setValue(int(value))
            elif isinstance(obj, QDoubleSpinBox):
                obj.setValue(float(value))
            elif isinstance(obj, QLineEdit):
                obj.setText(str(value))
            elif isinstance(obj, QComboBox):
                obj.setCurrentText(str(value))
            elif isinstance(obj, QLabel):
                obj.setText(str(value))
            elif isinstance(obj, QCheckBox):
                obj.setChecked(bool(int(value)))
            elif isinstance(obj, ColorLabel):
                obj.setValue(str(value))
            else:
                logging.warning(f"No set method defined for widget {name} of type {type(obj)}")
        except Exception as e:
            logging.error(f"Error setting value for {name}: {e}")

    def write_to_device(self):
        from RaspPiReader.libs.communication import dataReader
        try:
            dataReader.start()
        except Exception as e:
            logging.error(f"Failed to start data reader or it is already started: {e}")

        for ch in range(CHANNEL_COUNT):
            if not pool.config('active' + str(ch + 1), bool):
                continue
            try:
                dataReader.writeData(
                    pool.config('address' + str(ch + 1), int),
                    int(pool.config('sv' + str(ch + 1), str), 16),
                    pool.config('sp' + str(ch + 1), int)
                )
            except Exception as e:
                error_dialog = QErrorMessage(self)
                error_dialog.showMessage(f'Failed to write settings to device: {e}')
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
            reply = QMessageBox.question(
                self,
                'Message',
                quit_msg,
                (QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel)
            )
            if reply == QMessageBox.Yes:
                self.save_settings()
                event.accept()
            elif reply == QMessageBox.No:
                event.accept()
            elif reply == QMessageBox.Cancel:
                event.ignore()
