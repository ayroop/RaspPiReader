import os
import csv
from datetime import datetime, timedelta
from threading import Thread, Lock
from time import sleep

from PyQt5.QtCore import pyqtSignal, Qt, QTimer
from PyQt5.QtWidgets import QMainWindow, QMessageBox, QLineEdit, QSpinBox, QDoubleSpinBox

from RaspPiReader import pool
from RaspPiReader.libs.communication import dataReader
from RaspPiReader.libs.demo_data_reader import data as demo_data
# CHANNEL_COUNT and SettingFormHandler are imported for legacy support;
# however, we now access our own UI directly.
from RaspPiReader.ui.setting_form_handler import CHANNEL_COUNT, SettingFormHandler
from RaspPiReader.ui.startCycleForm import Ui_CycleStart  

from RaspPiReader.libs.database import Database
from RaspPiReader.libs.models import CycleData, DefaultProgram
from RaspPiReader.libs.cycle_finalization import finalize_cycle

# Mapping from widget object names in the UI to model field names.
cycle_settings = {
    "orderNumberLineEdit": "order_number",  # Updated name
    "cycleIDLineEdit": "cycle_id",
    "quantityLineEdit": "quantity",
    "sizeLineEdit": "size",
    "cycleLocationLineEdit": "cycle_location",
    "dwellTimeLineEdit": "dwell_time",
    "cooldownTempSpinBox": "cool_down_temp",
    "tempSetpointSpinBox": "core_temp_setpoint",
    "setTempRampLineDoubleSpinBox": "temp_ramp",
    "setPressureKPaDoubleSpinBox": "set_pressure",
    "maintainVacuumSpinBox": "maintain_vacuum",
    "initialSetCureTempSpinBox": "initial_set_cure_temp",
    "finalSetCureTempSpinBox": "final_set_cure_temp",
}

class StartCycleFormHandler(QMainWindow):
    data_updated_signal = pyqtSignal()
    test_data_updated_signal = pyqtSignal()
    exit_with_error_signal = pyqtSignal(str)

    def __init__(self, parent=None):
        super(StartCycleFormHandler, self).__init__(parent)
        self.ui = Ui_CycleStart()
        self.ui.setupUi(self)
        # Initialize cycle_data as an empty dictionary for later use
        self.cycle_data = {}
        self.db = Database("sqlite:///local_database.db")
        self.set_connections()
        pool.set('start_cycle_form', self)
        self.last_update_time = datetime.now()
        self.setWindowModality(Qt.ApplicationModal)
        self.load_cycle_data()
        self.data_reader_lock = Lock()
        self.running = False
        self.cycle_start_time = None
        self.read_thread = None

    def set_connections(self):
        self.ui.startPushButton.clicked.connect(self.start_cycle)
        if pool.get('main_form'):
            self.ui.startPushButton.clicked.connect(pool.get('main_form').update_cycle_info_pannel)
        self.ui.cancelPushButton.clicked.connect(self.close)
        self.data_updated_signal.connect(pool.get('main_form').update_data)
        self.test_data_updated_signal.connect(pool.get('main_form').update_immediate_test_values_panel)
        self.exit_with_error_signal.connect(pool.get('main_form').show_error_and_stop)
        self.ui.programComboBox.currentIndexChanged.connect(self.apply_default_values)

    def apply_default_values(self):
        # When the programComboBox changes, update UI values from the default program.
        program_index = self.ui.programComboBox.currentIndex() + 1
        default_program = self.db.session.query(DefaultProgram).filter_by(
            username=pool.get("current_user"), program_number=program_index
        ).first()
        if default_program:
            for widget_name, field_name in cycle_settings.items():
                if hasattr(self.ui, widget_name):
                    widget = getattr(self.ui, widget_name)
                    value = getattr(default_program, field_name, None)
                    if value is not None:
                        if isinstance(widget, QLineEdit):
                            widget.setText(str(value))
                        elif isinstance(widget, QSpinBox) or isinstance(widget, QDoubleSpinBox):
                            try:
                                widget.setValue(float(value))
                            except Exception as e:
                                print(f"Error setting value for {widget_name}: {e}")
                else:
                    print(f"Warning: ui has no attribute '{widget_name}'")
        else:
            QMessageBox.warning(self, "Warning", f"No default values found for Program {program_index}")

    def initiate_onedrive_update_thread(self):
        self.onedrive_thread = Thread(target=self.onedrive_upload_loop)
        self.onedrive_thread.daemon = True
        self.onedrive_thread.start()

    def onedrive_upload_loop(self):
        while True:
            sleep(pool.config('onedrive_update_interval', int, 60))
            main_form = pool.get('main_form')
            if main_form:
                main_form._sync_onedrive(upload_csv=True, upload_pdf=True, show_message=False)

    def upload_to_onedrive(self):
        main_form = pool.get('main_form')
        if main_form:
            main_form._sync_onedrive(upload_csv=True, upload_pdf=True, show_message=False)

    def show(self):
        try:
            dataReader.stop()
        except Exception:
            pass
        try:
            dataReader.start()
        except Exception:
            self.exit_with_error_signal.emit('Failed to connect to device.')
            print('Failed to connect to device.')
            return
        self.run_test_read_thread()
        self.initiate_gdrive_update_thread()
        super().show()

    def close(self):
        self.running = False
        super().close()

    def load_cycle_data(self):
        # Pre-populate UI values from persistent config (using pool config)
        for widget_name, key_name in cycle_settings.items():
            value = pool.config(key_name)
            if value is not None and hasattr(self.ui, widget_name):
                widget = getattr(self.ui, widget_name)
                if isinstance(widget, QLineEdit):
                    widget.setText(str(value))
                elif isinstance(widget, QSpinBox) or isinstance(widget, QDoubleSpinBox):
                    try:
                        widget.setValue(float(value))
                    except Exception as e:
                        print(f"Error setting {widget_name}: {e}")
            else:
                print(f"Warning: config for {key_name} not found or ui missing {widget_name}")

    def run_test_read_thread(self):
        self.cycle_start_time = datetime.now()
        dt = pool.config('panel_time_interval', float, 1.0)
        self.running = True
        self.test_read_thread = Thread(
            target=StartCycleFormHandler.read_data,
            args=(self, pool.get('test_data_stack'), self.test_data_updated_signal, dt),
            kwargs={'process_data': False}
        )
        self.test_read_thread.daemon = True
        self.test_read_thread.start()

    def initiate_gdrive_update_thread(self):
        self.gdrive_update_thread = Thread(target=self.gdrive_upload_loop)
        self.gdrive_update_thread.daemon = True
        self.gdrive_update_thread.start()

    def initiate_reader_thread(self):
        dt = pool.config('time_interval', float, 1.0)
        self.read_thread = Thread(
            target=StartCycleFormHandler.read_data,
            args=(self, pool.get('data_stack'), self.data_updated_signal, dt)
        )
        self.read_thread.daemon = True

    def save_cycle_data(self):
        # Save the cycle form settings into persistent configuration.
        for widget_name, key_name in cycle_settings.items():
            if hasattr(self.ui, widget_name):
                widget = getattr(self.ui, widget_name)
                value = None
                if isinstance(widget, QLineEdit):
                    value = widget.text()
                elif isinstance(widget, QSpinBox) or isinstance(widget, QDoubleSpinBox):
                    value = widget.value()
                pool.set_config(key_name, value)
        order_id = pool.config("order_id", str, "DEFAULT_ORDER")
        self.file_name = order_id + self.cycle_start_time.strftime(" %Y.%m.%d %H.%M.%S")
        main_form = pool.get('main_form')
        if main_form:
            main_form.folder_name = self.file_name
        csv_file_path = pool.config('csv_file_path', str, os.getcwd())
        self.folder_path = os.path.join(csv_file_path, self.file_name)
        os.makedirs(self.folder_path, exist_ok=True)
        cycle_data = CycleData(
            order_id = pool.config("order_id", str, "DEFAULT_ORDER"),
            cycle_id = pool.config("cycle_id", str, ""),
            quantity = pool.config("quantity", str, ""),
            size = pool.config("size", str, ""),
            cycle_location = pool.config("cycle_location", str, ""),
            dwell_time = pool.config("dwell_time", str, ""),
            cool_down_temp = pool.config("cool_down_temp", float, 0.0),
            core_temp_setpoint = pool.config("core_temp_setpoint", float, 0.0),
            temp_ramp = pool.config("temp_ramp", float, 0.0),
            set_pressure = pool.config("set_pressure", float, 0.0),
            maintain_vacuum = pool.config("maintain_vacuum", float, 0.0),
            initial_set_cure_temp = pool.config("initial_set_cure_temp", float, None),
            final_set_cure_temp = pool.config("final_set_cure_temp", float, None)
        )
        try:
            db = Database("sqlite:///local_database.db")
            db.add_cycle_data(cycle_data)
        except Exception as e:
            QMessageBox.critical(self, "Database Error", f"Could not save cycle data: {e}")
            return

    def start_cycle(self):
        self.cycle_start_time = datetime.now()
        self.save_cycle_data()
        main_form = pool.get('main_form')
        if main_form:
            main_form.actionStart.setEnabled(False)
            main_form.actionStop.setEnabled(True)
            main_form.actionPlot_preview.setEnabled(True)
            main_form.create_csv_file()
            main_form.cycle_timer.start(500)
        self.running = True
        self.hide()
        self.initiate_reader_thread()
        self.initiate_gdrive_update_thread()
        if self.read_thread:
            self.read_thread.start()
        self.initiate_onedrive_update_thread()

    def stop_cycle(self):
        stop_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.cycle_data["stop_time"] = stop_time
        serial_numbers = self.get_serial_numbers()  # Dummy implementation below
        supervisor_username = self.get_supervisor_override()  # Dummy implementation
        alarm_values = self.read_alarms()  # Dummy implementation
        try:
            pdf_file, csv_file = finalize_cycle(
                cycle_data=self.cycle_data,
                serial_numbers=serial_numbers,
                supervisor_username=supervisor_username,
                alarm_values=alarm_values,
                reports_folder="reports",
                template_file="RaspPiReader/ui/result_template.html"
            )
        except Exception as e:
            QMessageBox.critical(self, "Report Generation Error", f"Error finalizing cycle: {e}")
            return
        db = Database("sqlite:///local_database.db")
        new_cycle = CycleData(
            order_id=self.cycle_data.get("order_id"),
            cycle_id=self.cycle_data.get("program"),
            quantity=str(len(serial_numbers)),
            serial_numbers=",".join(serial_numbers),
            created_at=datetime.now()
        )
        try:
            db.session.add(new_cycle)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            QMessageBox.critical(self, "Database Error", f"Could not save cycle data: {e}")
            return
        QMessageBox.information(self, "Cycle Stopped",
            f"Cycle stopped successfully!\nPDF Report: {pdf_file}\nCSV Report: {csv_file}")
        self.close()

    # Dummy implementations – replace with your real methods:
    def get_serial_numbers(self):
        return ["SN001", "SN002", "SN003"]

    def get_supervisor_override(self):
        return "supervisor_user"

    def read_alarms(self):
        return {100: 0, 101: 1, 102: 0, 103: 0, 104: 0, 105: 0, 106: 1, 107: 0}

    @staticmethod
    def read_data(handler, data_stack, updated_signal, dt, process_data=True):
        core_temp_channel = pool.config('core_temp_channel', int, 1)
        pressure_channel = pool.config('pressure_channel', int, 1)
        core_temp_setpoint = pool.config('core_temp_setpoint', int, 0)
        active_channels = pool.get('active_channels')
        handler.pressure_drop_core_temp = None
        core_temp_above_setpoint_start_time = None
        handler.core_temp_above_setpoint_time = 0
        pressure_drop_flag = False

        if pool.get('demo'):
            read_index = 0
            n_data = len(demo_data)
            while handler.running and read_index < n_data:
                iteration_start_time = datetime.now()
                temp_arr = []
                for i in range(CHANNEL_COUNT):
                    if (i + 1) in active_channels:
                        temp = float(demo_data[read_index][i])
                    else:
                        temp = 0.00
                    temp_arr.append(temp)
                read_index += 1
                for i in range(CHANNEL_COUNT):
                    data_stack[i + 1].append(temp_arr[i])
                if process_data:
                    data_stack[0].append(
                        round((datetime.now() - handler.cycle_start_time).total_seconds() / 60, 2)
                    )
                    data_stack[15].append(datetime.now())
                    if (not core_temp_above_setpoint_start_time and 
                        data_stack[core_temp_channel][-1] >= core_temp_setpoint):
                        core_temp_above_setpoint_start_time = datetime.now()
                    elif core_temp_above_setpoint_start_time and data_stack[core_temp_channel][-1] < core_temp_setpoint:
                        handler.core_temp_above_setpoint_time += round(
                            (datetime.now() - core_temp_above_setpoint_start_time).total_seconds() / 60, 2
                        )
                        core_temp_above_setpoint_start_time = None
                    if len(data_stack[0]) > 1 and (data_stack[pressure_channel][-2] > data_stack[pressure_channel][-1]):
                        if not pressure_drop_flag:
                            handler.pressure_drop_core_temp = data_stack[core_temp_channel][-2]
                            pressure_drop_flag = True
                    else:
                        pressure_drop_flag = False
                updated_signal.emit()
                while (datetime.now() - iteration_start_time) < timedelta(seconds=dt):
                    sleep(0.001)
        else:
            while handler.running:
                iteration_start_time = datetime.now()
                temp_arr = []
                handler.data_reader_lock.acquire()
                for i in range(CHANNEL_COUNT):
                    if (i + 1) in active_channels:
                        try:
                            temp = dataReader.readData(
                                int(pool.config('address' + str(i + 1), int, 0)),
                                int(pool.config('pv' + str(i + 1), int, 0), 16)
                            )
                            if temp & 0x8000 > 0:
                                temp = -((0xFFFF - temp) + 1)
                            dec_point = pool.config('decimal_point' + str(i + 1), int, 0)
                            if dec_point > 0:
                                temp = temp / pow(10, dec_point)
                            if pool.config('scale' + str(i + 1), bool, False):
                                input_low = pool.config('limit_low' + str(i + 1), float, 0.0)
                                input_high = pool.config('limit_high' + str(i + 1), float, 0.0)
                                if input_high >= input_low + 10 and temp >= input_low:
                                    output_high = pool.config('max_scale_range' + str(i + 1), float, 1000.0)
                                    output_low = pool.config('min_scale_range' + str(i + 1), float, 0.0)
                                    temp = (output_high - output_low) / (input_high - input_low) * (temp - input_low) + output_low
                                    temp = round(temp, dec_point)
                        except Exception as e:
                            print(f"Failed to read or process data from channel {i + 1}.\n" + str(e))
                            try:
                                print("Restarting data reader")
                                dataReader.stop()
                                dataReader.start()
                                print('Restart successful')
                            except Exception as e:
                                print(f"Restart failed channel {i + 1}.\n" + str(e))
                            temp = -1000.00
                    else:
                        temp = 0.00
                    temp_arr.append(temp)
                handler.data_reader_lock.release()
                for i in range(CHANNEL_COUNT):
                    data_stack[i + 1].append(temp_arr[i])
                if process_data:
                    data_stack[0].append(
                        round((datetime.now() - handler.cycle_start_time).total_seconds() / 60, 2)
                    )
                    data_stack[15].append(datetime.now())
                    if (not core_temp_above_setpoint_start_time and
                        data_stack[core_temp_channel][-1] >= core_temp_setpoint):
                        core_temp_above_setpoint_start_time = datetime.now()
                    elif core_temp_above_setpoint_start_time and data_stack[core_temp_channel][-1] < core_temp_setpoint:
                        handler.core_temp_above_setpoint_time += round(
                            (datetime.now() - core_temp_above_setpoint_start_time).total_seconds() / 60, 2
                        )
                        core_temp_above_setpoint_start_time = None
                    if len(data_stack[0]) > 1 and (data_stack[pressure_channel][-2] > data_stack[pressure_channel][-1]):
                        if not pressure_drop_flag:
                            handler.pressure_drop_core_temp = data_stack[core_temp_channel][-2]
                            pressure_drop_flag = True
                    else:
                        pressure_drop_flag = False
                updated_signal.emit()
                while (datetime.now() - iteration_start_time) < timedelta(seconds=dt):
                    sleep(0.001)
        try:
            dataReader.stop()
        except Exception:
            print('unable to stop data reader')

    def _start(self):
        """Start reading data"""
        # First make sure communication is properly set up
        if not plc_communication.is_connected():
            # Try to initialize PLC communication
            success = plc_communication.initialize_plc_communication()
            if not success:
                QMessageBox.critical(self, "Connection Error",
                                    "Failed to connect to PLC. Please check your connection settings.")
                return

        # Start the data reader
        dataReader.start()
        
        # Update the UI to reflect the current connection type
        self.update_connection_status_display()
        
        # Start the data reading timer
        self.timer.start(1000)
        self.running = True