import os
import csv
from datetime import datetime, timedelta
from threading import Thread, Lock
from time import sleep

from PyQt5.QtCore import pyqtSignal, Qt, QTimer
from PyQt5.QtWidgets import QMainWindow, QMessageBox

from RaspPiReader import pool
from RaspPiReader.libs.communication import dataReader
from RaspPiReader.libs.demo_data_reader import data as demo_data
from RaspPiReader.ui.setting_form_handler import CHANNEL_COUNT, SettingFormHandler
from RaspPiReader.ui.startCycleForm import StartCycleForm

from RaspPiReader.libs.database import Database
from RaspPiReader.libs.models import CycleData

cycle_settings = {
    "orderNumberLineEdit": "order_id",
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

    def __init__(self) -> object:
        super(StartCycleFormHandler, self).__init__()
        self.form_obj = StartCycleForm()
        self.form_obj.setupUi(self)
        self.set_connections()
        pool.set('start_cycle_form', self)
        self.last_update_time = datetime.now()
        self.setWindowModality(Qt.ApplicationModal)
        self.load_cycle_data()
        self.data_reader_lock = Lock()

    def set_connections(self):
        self.startPushButton.clicked.connect(self.start_cycle)
        self.startPushButton.clicked.connect(pool.get('main_form').update_cycle_info_pannel)
        self.cancelPushButton.clicked.connect(self.close)
        self.data_updated_signal.connect(pool.get('main_form').update_data)
        self.test_data_updated_signal.connect(pool.get('main_form').update_immediate_test_values_panel)
        self.exit_with_error_signal.connect(pool.get('main_form').show_error_and_stop)

    def initiate_onedrive_update_thread(self):
        self.onedrive_thread = Thread(target=self.onedrive_upload_loop)
        self.onedrive_thread.daemon = True
        self.onedrive_thread.start()

    def onedrive_upload_loop(self):
        while True:
            sleep(pool.config('onedrive_update_interval', int))
            pool.get('main_form')._sync_onedrive(upload_csv=True, upload_pdf=True, show_message=False)

    def upload_to_onedrive(self):
        main_form = pool.get('main_form')
        main_form._sync_onedrive(upload_csv=True, upload_pdf=True, show_message=False)

    def show(self):
        try:
            dataReader.stop()
        except Exception as e:
            pass
        try:
            dataReader.start()
        except:
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
        # Pre-populate UI values from config settings.
        for obj_name, key_name in cycle_settings.items():
            value = pool.config(key_name)
            if value is not None:
                SettingFormHandler.set_val(self, obj_name, value)

    def run_test_read_thread(self):
        self.cycle_start_time = datetime.now()
        dt = pool.config('panel_time_interval', float)
        self.running = True
        self.test_read_thread = Thread(
            target=StartCycleFormHandler.read_data,
            args=(self, pool.get('test_data_stack'), self.test_data_updated_signal, dt,),
            kwargs={'process_data': False}
        )
        self.test_read_thread.daemon = True
        self.test_read_thread.start()

    def initiate_gdrive_update_thread(self):
        self.gdrive_update_thread = Thread(target=self.gdrive_upload_loop)
        self.gdrive_update_thread.daemon = True

    def gdrive_upload_loop(self):
        last_time = datetime.now()
        while self.running:
            if (datetime.now() - last_time).total_seconds() >= pool.config('gdrive_update_interval', int):
                pool.get('main_form')._sync_gdrive(upload_pdf=False, show_message=False, delete_existing=False)
                last_time = datetime.now()
            sleep(3)

    def initiate_reader_thread(self):
        dt = pool.config('time_interval', float)
        self.read_thread = Thread(
            target=StartCycleFormHandler.read_data,
            args=(self, pool.get('data_stack'), self.data_updated_signal, dt)
        )
        self.read_thread.daemon = True

    def save_cycle_data(self):
        # Save the settings from the cycle form into the persistent config.
        for obj_name, key_name in cycle_settings.items():
            pool.set_config(key_name, SettingFormHandler.get_val(self, obj_name))

        # Compute file folder name based on order_id and cycle start time.
        order_id = pool.config("order_id", str, "DEFAULT_ORDER")
        self.file_name = order_id + self.cycle_start_time.strftime("  %Y.%m.%d  %H.%M.%S")
        pool.get('main_form').folder_name = self.file_name

        # Create output folder using the csv_file_path configuration; default to current working directory.
        csv_file_path = pool.config('csv_file_path', str, os.getcwd())
        self.folder_path = os.path.join(csv_file_path, self.file_name)
        os.makedirs(self.folder_path)

        # Create a CycleData instance using form data.
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
            # Save the cycle data to local SQLite DB.
            db = Database("sqlite:///local_database.db")
            db.add_cycle_data(cycle_data)
        except Exception as e:
            QMessageBox.critical(self, "Database Error", f"Could not save cycle data: {e}")
            return

    def start_cycle(self):
        self.cycle_start_time = datetime.now()
        self.save_cycle_data()
        main_form = pool.get('main_form')
        main_form.actionStart.setEnabled(False)
        main_form.actionStop.setEnabled(True)
        main_form.actionPlot_preview.setEnabled(True)
        main_form.create_csv_file()
        self.running = True
        self.hide()
        self.initiate_reader_thread()
        self.initiate_gdrive_update_thread()
        main_form.cycle_timer.start(500)
        self.read_thread.start()
        self.gdrive_update_thread.start()
        self.initiate_onedrive_update_thread()

    def stop_cycle(self):
        self.cycle_end_time = datetime.now()
        pool.get('main_form').cycle_timer.stop()
        self.running = False

    def read_data(self, data_stack, updated_signal, dt, process_data=True):
        active_channels = pool.get('active_channels')
        core_temp_channel = pool.config('core_temp_channel', int)
        pressure_channel = pool.config('pressure_channel', int)
        core_temp_setpoint = pool.config('core_temp_setpoint', int)
        self.pressure_drop_core_temp = None
        core_temp_above_setpoint_start_time = None
        self.core_temp_above_setpoint_time = 0
        pressure_drop_flag = False

        if pool.get('demo'):
            read_index = 0
            n_data = len(demo_data)
            while self.running and read_index < n_data:
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
                    data_stack[0].append(round((datetime.now() - self.cycle_start_time).total_seconds() / 60, 2))
                    data_stack[15].append(datetime.now())
                    if not core_temp_above_setpoint_start_time and data_stack[core_temp_channel][-1] >= core_temp_setpoint:
                        core_temp_above_setpoint_start_time = datetime.now()
                    elif core_temp_above_setpoint_start_time and data_stack[core_temp_channel][-1] < core_temp_setpoint:
                        self.core_temp_above_setpoint_time += round(
                            (datetime.now() - core_temp_above_setpoint_start_time).total_seconds() / 60, 2)
                        core_temp_above_setpoint_start_time = None

                    if len(data_stack[0]) > 1 and (data_stack[pressure_channel][-2] > data_stack[pressure_channel][-1]):
                        if not pressure_drop_flag:
                            self.pressure_drop_core_temp = data_stack[core_temp_channel][-2]
                            pressure_drop_flag = True
                    else:
                        pressure_drop_flag = False

                updated_signal.emit()
                while (datetime.now() - iteration_start_time) < timedelta(seconds=0.001):
                    sleep(0.0001)

        else:
            while self.running:
                iteration_start_time = datetime.now()
                temp_arr = []
                self.data_reader_lock.acquire()
                for i in range(CHANNEL_COUNT):
                    if (i + 1) in active_channels:
                        try:
                            temp = dataReader.readData(
                                int(pool.config('address' + str(i + 1)), 16),
                                int(pool.config('pv' + str(i + 1)), 16)
                            )
                            if temp & 0x8000 > 0:
                                temp = -((0xFFFF - temp) + 1)
                            dec_point = pool.config('decimal_point' + str(i + 1), int)
                            if dec_point > 0:
                                temp = temp / pow(10, dec_point)
                            if pool.config('scale' + str(i + 1), bool):
                                input_low = pool.config('limit_low' + str(i + 1), float)
                                input_high = pool.config('limit_high' + str(i + 1), float)
                                if input_high >= input_low + 10 and temp >= input_low:
                                    output_high = pool.config('max_scale_range' + str(i + 1), float)
                                    output_low = pool.config('min_scale_range' + str(i + 1), float)
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
                                print(f"Restart failed {i + 1}.\n" + str(e))
                            temp = -1000.00
                    else:
                        temp = 0.00
                    temp_arr.append(temp)
                self.data_reader_lock.release()

                for i in range(CHANNEL_COUNT):
                    data_stack[i + 1].append(temp_arr[i])
                if process_data:
                    data_stack[0].append(round((datetime.now() - self.cycle_start_time).total_seconds() / 60, 2))
                    data_stack[15].append(datetime.now())
                    if not core_temp_above_setpoint_start_time and data_stack[core_temp_channel][-1] >= core_temp_setpoint:
                        core_temp_above_setpoint_start_time = datetime.now()
                    elif core_temp_above_setpoint_start_time and data_stack[core_temp_channel][-1] < core_temp_setpoint:
                        self.core_temp_above_setpoint_time += round((datetime.now() - core_temp_above_setpoint_start_time).total_seconds() / 60, 2)
                        core_temp_above_setpoint_start_time = None
                    if len(data_stack[0]) > 1 and (data_stack[pressure_channel][-2] > data_stack[pressure_channel][-1]):
                        if not pressure_drop_flag:
                            self.pressure_drop_core_temp = data_stack[core_temp_channel][-2]
                            pressure_drop_flag = True
                    else:
                        pressure_drop_flag = False
                updated_signal.emit()
                while (datetime.now() - iteration_start_time) < timedelta(seconds=dt):
                    sleep(0.001)

        try:
            dataReader.stop()
        except:
            print('unable to stop data reader')