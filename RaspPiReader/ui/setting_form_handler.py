from PyQt5.QtCore import QSettings, Qt, QTimer, QThreadPool, QRunnable
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
from PyQt5 import QtWidgets
from PyQt5.QtGui import QFont
import logging
from RaspPiReader import pool
from .color_label import ColorLabel
from .settingForm import Ui_SettingForm as SettingForm
from RaspPiReader.libs.database import Database
from RaspPiReader.libs.models import GeneralConfigSettings, ChannelConfigSettings, BooleanAddress
from RaspPiReader.libs.configuration import config
from RaspPiReader.ui.serial_number_management_form_handler import SerialNumberManagementFormHandler

CHANNEL_COUNT = 14
READ_INPUT_REGISTERS = "Read Input Registers"
READ_HOLDING_REGISTERS = "Read Holding Registers"

logging.basicConfig(level=logging.DEBUG)

# ---- Removed Worker class in favor of timer-based approach ----

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
        
        # Add both tabs
        self.add_boolean_addresses_tab()
        self.add_serial_number_management_tab()
        
        self.show()

    def add_serial_number_management_tab(self):
        # Create an instance of our Serial Number Management widget
        self.serial_manager = SerialNumberManagementFormHandler(self)
        # Assuming the tabWidget exists and you want to add a widget:
        serial_tab = QtWidgets.QWidget()
        serial_tab.setObjectName("tabSerialNumbers")
        layout = QtWidgets.QVBoxLayout(serial_tab)
        layout.addWidget(self.serial_manager)
        self.form_obj.tabWidget.addTab(serial_tab, "Serial Numbers")
        
        # Connect tab change signal to ensure data loads when tab is selected
        self.form_obj.tabWidget.currentChanged.connect(self._handle_tab_changed)

    def _handle_tab_changed(self, index):
        current_tab = self.form_obj.tabWidget.widget(index)
        if current_tab and current_tab.objectName() == "tabSerialNumbers":
            if hasattr(self, 'serial_manager'):
                # Force reload of the serial numbers
                self.serial_manager.load_all_serials()

    def add_boolean_addresses_tab(self):
        boolean_tab = self.create_boolean_tab(config)
        self.form_obj.tabWidget.addTab(boolean_tab, "Boolean Addresses")

    def create_boolean_tab(self, config):
        # Create a new widget as tab for Boolean Address settings
        boolean_tab = QtWidgets.QWidget()
        boolean_tab.setObjectName("booleanTab")
        boolean_layout = QtWidgets.QVBoxLayout(boolean_tab)
        boolean_layout.setObjectName("booleanLayout")
        
        self.boolTable = QtWidgets.QTableWidget(boolean_tab)
        # Attempt to load existing BooleanAddress entries from the database; fall back on config defaults if none exist.
        boolean_entries = self.db.session.query(BooleanAddress).all()
        if boolean_entries:
            rowCount = len(boolean_entries)
        else:
            rowCount = len(config.bool_addresses)
        self.boolTable.setRowCount(rowCount)
        self.boolTable.setColumnCount(2)
        self.boolTable.setHorizontalHeaderLabels(["Address", "Label"])
        
        if boolean_entries:
            for i, entry in enumerate(boolean_entries):
                addr_item = QtWidgets.QTableWidgetItem(str(entry.address))
                label_item = QtWidgets.QTableWidgetItem(entry.label)
                self.boolTable.setItem(i, 0, addr_item)
                self.boolTable.setItem(i, 1, label_item)
        else:
            for i, addr in enumerate(config.bool_addresses):
                addr_item = QtWidgets.QTableWidgetItem(str(addr))
                label_item = QtWidgets.QTableWidgetItem(f"Bool Addr {addr}")
                self.boolTable.setItem(i, 0, addr_item)
                self.boolTable.setItem(i, 1, label_item)
        
        boolean_layout.addWidget(self.boolTable)
        return boolean_tab

    def set_connections(self):
        if hasattr(self.form_obj, "buttonSave"):
            self.form_obj.buttonSave.clicked.connect(self.save_and_close)
        if hasattr(self.form_obj, "buttonCancel"):
            self.form_obj.buttonCancel.clicked.connect(self.close)
        
        # Add connection for serial number management
        if hasattr(self.form_obj, "serialNumbersButton"):
            self.form_obj.serialNumbersButton.clicked.connect(self.open_serial_number_management)

    def save_settings(self):
        try:
            if hasattr(self.form_obj, "buttonSave"):
                self.form_obj.buttonSave.setEnabled(False)
                
            # Retrieve general settings from the UI
            baudrate_val = self.get_val("baudrateLineEdit") or "9600"
            parity_val = self.get_val("parityLineEdit") or "N"
            databits_val = self.get_val("databitsLineEdit") or "8"
            stopbits_val = self.get_val("stopbitsLineEdit") or "1"
            reading_addr_val = self.get_val("readingaddrLineEdit") or "0"
            register_read_type = self.get_val("conTypeComboBox") if hasattr(self.form_obj, "conTypeComboBox") else ""
            port_val = self.get_val("portLineEdit") if hasattr(self.form_obj, "portLineEdit") else ""
            left_v_label_val = self.get_val("editLeftVLabel") or "Left V"
            right_v_label_val = self.get_val("editRightVLabel") or "Right V"
            h_label_val = self.get_val("editHLabel") or "H"
            time_interval_val = self.get_val("timeIntervalDoubleSpinBox") or "1.0"
            scale_range_val = self.get_val("editScaleRange") or "1000"
            file_path_val = self.get_val("filePathLineEdit") or ""
            delimiter_val = self.get_val("delimiterLineEdit") or ","
            panel_time_interval_val = self.get_val("panelTimeIntervalLineEdit") or "1.0"
            accurate_data_time_val = self.get_val("accurateDataTimeLineEdit") or "1.0"
            core_temp_channel_val = self.get_val("CoreTempChannelSpinBox") or "1"
            pressure_channel_val = self.get_val("pressureChannelSpinBox") or "1"

            # Retrieve (or create) the general settings record.
            settings = self.db.session.query(GeneralConfigSettings).first()
            if settings:
                settings.baudrate = int(baudrate_val)
                settings.parity = parity_val
                settings.databits = int(databits_val)
                settings.stopbits = float(stopbits_val)
                settings.reading_address = reading_addr_val
                settings.register_read_type = register_read_type
                settings.port = port_val
                settings.left_v_label = left_v_label_val
                settings.right_v_label = right_v_label_val
                settings.h_label = h_label_val
                settings.time_interval = float(time_interval_val)
                settings.scale_range = int(scale_range_val)
                settings.csv_file_path = file_path_val
                settings.csv_delimiter = delimiter_val
                settings.core_temp_channel = int(core_temp_channel_val)
                settings.pressure_channel = int(pressure_channel_val)
                settings.panel_time_interval = float(panel_time_interval_val)
                settings.accuarate_data_time = float(accurate_data_time_val)
            else:
                settings = GeneralConfigSettings(
                    baudrate = int(baudrate_val),
                    parity = parity_val,
                    databits = int(databits_val),
                    stopbits = float(stopbits_val),
                    reading_address = reading_addr_val,
                    register_read_type = register_read_type,
                    port = port_val,
                    left_v_label = left_v_label_val,
                    right_v_label = right_v_label_val,
                    h_label = h_label_val,
                    time_interval = float(time_interval_val),
                    scale_range = int(scale_range_val),
                    csv_file_path = file_path_val,
                    csv_delimiter = delimiter_val,
                    core_temp_channel = int(core_temp_channel_val),
                    pressure_channel = int(pressure_channel_val),
                    panel_time_interval = float(panel_time_interval_val),
                    accuarate_data_time = float(accurate_data_time_val)
                )
                self.db.session.add(settings)
            self.db.session.commit()

            # Dynamic channel settings mapping (ensure load and save use consistent keys, especially "editSP")
            channel_fields = {
                "editAd": ("address", 0),
                "editLabel": ("label", ""),
                "editPV": ("pv", 0),
                "editSV": ("sv", 0),
                "editSP": ("set_point", 0),  # maps the editSP widget to the "set_point" field
                "editLimitLow": ("limit_low", 0),
                "editLimitHigh": ("limit_high", 0),
                # Updated mapping: use "decimal_point" to match the database schema and load_settings method.
                "editDecPoint": ("decimal_point", 0),
                "checkScale": ("scale", False),
                "comboAxis": ("axis_direction", "L"),
                "labelColor": ("color", "#FFFFFF"),
                "active": ("active", False),
                "min_scale_range": ("min_scale_range", 0),
                "max_scale_range": ("max_scale_range", 0)
            }
            for ch in range(1, CHANNEL_COUNT + 1):
                channel_settings = self.db.session.query(ChannelConfigSettings).filter_by(id=ch).first()
                if not channel_settings:
                    channel_settings = ChannelConfigSettings(id=ch)
                    self.db.session.add(channel_settings)
                for prefix, (attribute, default_val) in channel_fields.items():
                    widget_name = f"{prefix}{ch}"
                    if hasattr(self.form_obj, widget_name):
                        value = self.get_val(widget_name)
                        if value in [None, ""]:
                            value = default_val
                    else:
                        value = default_val
                    # Ensure decimal_point is not None
                    if attribute == "decimal_point" and value is None:
                        value = 0
                    setattr(channel_settings, attribute, value)
            self.db.session.commit()
                
            # Save Boolean Address settings to the database.
            numRows = self.boolTable.rowCount()
            self.db.session.query(BooleanAddress).delete()
            for row in range(numRows):
                addr_item = self.boolTable.item(row, 0)
                label_item = self.boolTable.item(row, 1)
                if addr_item and label_item:
                    try:
                        address = int(addr_item.text())
                    except ValueError:
                        address = 0
                    label = label_item.text().strip()
                    new_entry = BooleanAddress(address=address, label=label)
                    self.db.session.add(new_entry)
            self.db.session.commit()

            logging.info("Settings saved successfully.")
            QTimer.singleShot(100, self._delayed_write_to_device)
        except Exception as e:
            logging.error(f"Error saving settings: {e}")
            if hasattr(self.form_obj, "buttonSave"):
                self.form_obj.buttonSave.setEnabled(True)

    def load_settings(self):
        try:
            self.load_connection_combo_boxes()
            settings = self.db.session.query(GeneralConfigSettings).first()
            if settings:
                self.set_val("baudrateLineEdit", settings.baudrate)
                self.set_val("parityLineEdit", settings.parity)
                self.set_val("databitsLineEdit", settings.databits)
                self.set_val("stopbitsLineEdit", settings.stopbits)
                self.set_val("readingaddrLineEdit", settings.reading_address)
                if hasattr(self.form_obj, "conTypeComboBox"):
                    self.set_val("conTypeComboBox", settings.register_read_type)
                if hasattr(self.form_obj, "portLineEdit"):
                    self.set_val("portLineEdit", settings.port)
                self.set_val("editLeftVLabel", settings.left_v_label)
                self.set_val("editRightVLabel", settings.right_v_label)
                self.set_val("editHLabel", settings.h_label)
                self.set_val("timeIntervalDoubleSpinBox", settings.time_interval)
                self.set_val("editScaleRange", settings.scale_range)
                self.set_val("filePathLineEdit", settings.csv_file_path)
                self.set_val("delimiterLineEdit", settings.csv_delimiter)
                if hasattr(self.form_obj, "gdriveSpinBox"):
                    self.set_val("gdriveSpinBox", settings.gdrive_update_interval)
                if hasattr(self.form_obj, "CoreTempChannelSpinBox"):
                    self.set_val("CoreTempChannelSpinBox", settings.core_temp_channel)
                if hasattr(self.form_obj, "pressureChannelSpinBox"):
                    self.set_val("pressureChannelSpinBox", settings.pressure_channel)
                if hasattr(self.form_obj, "signinStatus"):
                    self.set_val("signinStatus", settings.signin_status)
                if hasattr(self.form_obj, "signinEmail"):
                    self.set_val("signinEmail", settings.signin_email)
                if hasattr(self.form_obj, "panelTimeIntervalLineEdit"):
                    self.set_val("panelTimeIntervalLineEdit", settings.panel_time_interval)
                if hasattr(self.form_obj, "accurateDataTimeLineEdit"):
                    self.set_val("accurateDataTimeLineEdit", settings.accuarate_data_time)
            else:
                # Set defaults if no general settings record exists.
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
                if hasattr(self.form_obj, "signinStatus"):
                    self.set_val("signinStatus", 0)
                if hasattr(self.form_obj, "signinEmail"):
                    self.set_val("signinEmail", "")
                if hasattr(self.form_obj, "panelTimeIntervalLineEdit"):
                    self.set_val("panelTimeIntervalLineEdit", 1.0)
                if hasattr(self.form_obj, "accurateDataTimeLineEdit"):
                    self.set_val("accurateDataTimeLineEdit", 1.0)

            # Load dynamic channel settings with consistent keys.
            for ch in range(1, CHANNEL_COUNT + 1):
                channel_settings = self.db.session.query(ChannelConfigSettings).filter_by(id=ch).first()
                if channel_settings:
                    for prefix, (attribute, default_val) in {
                        "editAd": ("address", 0),
                        "editLabel": ("label", ""),
                        "editPV": ("pv", 0),
                        "editSV": ("sv", 0),
                        "editSP": ("set_point", 0),
                        "editLimitLow": ("limit_low", 0),
                        "editLimitHigh": ("limit_high", 0),
                        "editDecPoint": ("decimal_point", 0),  # Ensure default value
                        "checkScale": ("scale", False),
                        "comboAxis": ("axis_direction", "L"),
                        "labelColor": ("color", "#FFFFFF"),
                        "active": ("active", False),
                        "min_scale_range": ("min_scale_range", 0),
                        "max_scale_range": ("max_scale_range", 0)
                    }.items():
                        widget_name = f"{prefix}{ch}"
                        if hasattr(self.form_obj, widget_name):
                            self.set_val(widget_name, getattr(channel_settings, attribute, default_val))
                        else:
                            logging.warning(f"Widget {widget_name} not found in form.")
            logging.info("Settings loaded successfully.")
        except Exception as e:
            logging.error(f"Error loading settings: {e}")

    def load_connection_combo_boxes(self):
        if hasattr(self.form_obj, "baudrateLineEdit"):
            self.form_obj.baudrateLineEdit.setText("9600")
        else:
            logging.warning("baudrateLineEdit not found in form.")
        if hasattr(self.form_obj, "parityLineEdit"):
            self.form_obj.parityLineEdit.setText("N")
        else:
            logging.warning("parityLineEdit not found in form.")
        if hasattr(self.form_obj, "databitsLineEdit"):
            self.form_obj.databitsLineEdit.setText("8")
        else:
            logging.warning("databitsLineEdit not found in form.")
        if hasattr(self.form_obj, "stopbitsLineEdit"):
            self.form_obj.stopbitsLineEdit.setText("1")
        else:
            logging.warning("stopbitsLineEdit not found in form.")
        if hasattr(self.form_obj, "conTypeComboBox"):
            self.form_obj.conTypeComboBox.addItems([READ_HOLDING_REGISTERS, READ_INPUT_REGISTERS])
        else:
            logging.warning("conTypeComboBox not found in form.")

    def get_val(self, name):
        if not hasattr(self.form_obj, name):
            logging.warning(f"{name} widget not found in form.")
            return ""
        widget = getattr(self.form_obj, name)
        try:
            if isinstance(widget, QSpinBox):
                return widget.value()
            elif isinstance(widget, QDoubleSpinBox):
                return widget.value()
            elif isinstance(widget, QLineEdit):
                return widget.text()
            elif isinstance(widget, QComboBox):
                return widget.currentText()
            elif isinstance(widget, QCheckBox):
                return 1 if widget.isChecked() else 0
            elif isinstance(widget, ColorLabel):
                # Return the selected color string.
                return widget.value()
            else:
                logging.warning(f"No getter defined for {name} of type {type(widget)}")
                return ""
        except Exception as e:
            logging.error(f"Error getting value for {name}: {e}")
            return ""
    def set_val(self, name, value):
        """Set a value in a UI widget with proper type conversion"""
        # Retrieve the widget from the form_obj rather than self.
        widget = getattr(self.form_obj, name, None)
        if widget:
            try:
                if isinstance(widget, QtWidgets.QSpinBox):
                    widget.setValue(int(float(value)))  # Convert to int for QSpinBox
                elif isinstance(widget, QtWidgets.QDoubleSpinBox):
                    widget.setValue(float(value))  # Convert to float for QDoubleSpinBox
                elif isinstance(widget, QtWidgets.QLineEdit):
                    widget.setText(str(value))
                elif isinstance(widget, QtWidgets.QComboBox):
                    index = widget.findText(str(value))
                    if index >= 0:
                        widget.setCurrentIndex(index)
                elif isinstance(widget, QtWidgets.QCheckBox):
                    widget.setChecked(bool(value))
                elif isinstance(widget, ColorLabel):
                    widget.setValue(str(value))
                else:
                    logging.warning(f"No set method defined for widget {name} of type {type(widget)}")
            except Exception as e:
                logging.error(f"Error setting {name}: {e}")
        else:
            logging.warning(f"Widget {name} not found in form_obj")
    def _delayed_write_to_device(self):
        """
        Perform device write operations after a short delay to prevent UI freezing.
        This method is called via QTimer instead of directly or via a worker thread.
        """
        from RaspPiReader.libs.communication import dataReader
        try:
            # Show a status message if possible
            if hasattr(self.form_obj, "statusBar"):
                self.form_obj.statusBar().showMessage("Writing settings to device...")
            
            # Start the data reader
            dataReader.start()
            
            # Process each channel
            for ch in range(CHANNEL_COUNT):
                # Skip inactive channels
                if not pool.config("active" + str(ch + 1), bool):
                    continue
                try:
                    address = pool.config("address" + str(ch + 1), int)
                    set_point = pool.config("set_point" + str(ch + 1), int)
                    sv_value = pool.config("sv" + str(ch + 1), str)
                    if sv_value is None or str(sv_value).strip().lower() == "none":
                        logging.warning(f"sv{ch+1} is missing, using default value 0")
                        sv_value = "0"
                    sv_int = int(sv_value, 14)


                    
                    # Write the settings data to the device
                    dataReader.writeData(address, sv_int, set_point)
                except Exception as e:
                    error_dialog = QErrorMessage(self)
                    error_dialog.showMessage(f"Failed to write settings to device: {e}")
                    break

            
            # Stop the data reader
            dataReader.stop()
            
            # Update status and re-enable save button
            if hasattr(self.form_obj, "statusBar"):
                self.form_obj.statusBar().showMessage("Settings applied successfully", 3000)
            if hasattr(self.form_obj, "buttonSave"):
                self.form_obj.buttonSave.setEnabled(True)
                
            # Close the form if this was triggered from save_and_close
            if not self.close_prompt:
                self.close()
                
        except Exception as e:
            logging.error(f"Error in delayed write to device: {e}")
            # Show error message
            error_dialog = QErrorMessage(self)
            error_dialog.showMessage(f"Error writing to device: {e}")
            # Re-enable save button
            if hasattr(self.form_obj, "buttonSave"):
                self.form_obj.buttonSave.setEnabled(True)
    
    def write_to_device(self):
        """
        Legacy method maintained for compatibility.
        Now uses the timer-based approach to prevent UI freezing.
        """
        QTimer.singleShot(100, self._delayed_write_to_device)

    def save_and_close(self):
        """
        Save settings and close the form.
        Uses the timer-based approach to prevent UI freezing.
        """
        self.close_prompt = False
        self.save_settings()
        # The form will be closed in _delayed_write_to_device after settings are saved

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
                "Message",
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
