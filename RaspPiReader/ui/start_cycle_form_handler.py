import os
from datetime import datetime, timedelta
import threading
from threading import Thread, Lock
from time import sleep
import logging
from PyQt5 import QtWidgets, QtCore
from PyQt5.QtCore import pyqtSignal, Qt, QTimer
from PyQt5.QtWidgets import QMainWindow, QMessageBox, QLineEdit, QSpinBox, QDoubleSpinBox, QDockWidget

from RaspPiReader import pool
from RaspPiReader.libs.communication import dataReader
from RaspPiReader.libs.demo_data_reader import data as demo_data
from RaspPiReader.ui.setting_form_handler import CHANNEL_COUNT, SettingFormHandler
from RaspPiReader.ui.startCycleForm import Ui_CycleStart  

from RaspPiReader.libs.database import Database
from RaspPiReader.libs.cycle_finalization import finalize_cycle
from RaspPiReader.ui.serial_number_management_form_handler import SerialNumberManagementFormHandler
from RaspPiReader.libs.models import CycleData, User, Alarm, DefaultProgram, CycleSerialNumber
from RaspPiReader.libs import plc_communication
from RaspPiReader.libs.plc_communication import write_coil

# Import here to avoid circular imports
from RaspPiReader.ui.visualization_dashboard import VisualizationDashboard       
from ..ui.visualization_dashboard import VisualizationDashboard


logger = logging.getLogger(__name__)

class VisualizationIntegrator:
    """
    Integrates the visualization dashboard with PLC communication
    and cycle start/stop events.
    """
    
    def __init__(self, main_window, plc_comm):
        """
        Initialize the visualization integrator.
        
        Args:
            main_window: The main application window
            plc_comm: The PLC communication instance
        """
        self.main_window = main_window
        self.plc_comm = plc_comm
        self.dashboard = None
        self.dock_widget = None
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update_visualization)
        logger.info("VisualizationIntegrator initialized")
        
    def setup_visualization(self):
        """Set up the visualization dashboard as a dock widget"""
        logger.info("Setting up visualization dashboard")
        
        # Create the dashboard
        self.dashboard = VisualizationDashboard()
        
        # Create a dock widget to host the dashboard
        self.dock_widget = QtWidgets.QDockWidget("Live Data Visualization", self.main_window)
        self.dock_widget.setWidget(self.dashboard)
        self.dock_widget.setFeatures(
            QtWidgets.QDockWidget.DockWidgetMovable | 
            QtWidgets.QDockWidget.DockWidgetFloatable
        )
        
        # Add the dock widget to the main window
        self.main_window.addDockWidget(QtCore.Qt.RightDockWidgetArea, self.dock_widget)
        
        # Hide dock widget initially (will show when cycle starts)
        self.dock_widget.hide()
        
        logger.info("Visualization dashboard setup complete")
        
    def on_cycle_start(self):
        """Handle cycle start event"""
        logger.info("Cycle start detected - initializing visualization")
        
        if not self.dashboard:
            self.setup_visualization()
            
        # Show the visualization dashboard
        self.dock_widget.show()
        
        # Start the visualization
        self.dashboard.start_visualization()
        
        # Start the update timer
        self.timer.start(100)  # Update every 100ms
        
        logger.info("Visualization started")
        
    def on_cycle_stop(self):
        """Handle cycle stop event"""
        logger.info("Cycle stop detected - stopping visualization")
        
        if self.dashboard:
            # Stop the visualization
            self.dashboard.stop_visualization()
            
            # Stop the update timer
            self.timer.stop()
            
            logger.info("Visualization stopped")
            
    def update_visualization(self):
        """Update the visualization with the latest PLC data"""
        if not self.dashboard or not self.plc_comm:
            return
            
        # Get the latest data from PLC
        try:
            plc_data = self.plc_comm.get_latest_data()
            
            # Update the visualization dashboard with each parameter
            for param_name, value in plc_data.items():
                self.dashboard.update_data(param_name, value)
        except AttributeError:
            # If get_latest_data method doesn't exist, use alternative approach
            try:
                # Try to get data from individual registers based on your system
                from RaspPiReader.libs.plc_communication import read_holding_register
                
                # Read example registers that might be relevant
                temperature = read_holding_register(100, 1)  # Adjust address as needed
                pressure = read_holding_register(102, 1)     # Adjust address as needed
                flow = read_holding_register(104, 1)         # Adjust address as needed
                
                # Update visualization with the data if available
                if temperature is not None:
                    self.dashboard.update_data("temperature", temperature)
                if pressure is not None:
                    self.dashboard.update_data("pressure", pressure)
                if flow is not None:
                    self.dashboard.update_data("flow_rate", flow)
            except Exception as e:
                logger.error(f"Error updating visualization data: {e}")
            
    def reset_visualization(self):
        """Reset the visualization"""
        if self.dashboard:
            self.dashboard.reset()
            logger.info("Visualization reset")

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
    data_updated_signal = pyqtSignal(object)
    test_data_updated_signal = pyqtSignal(object)
    exit_with_error_signal = pyqtSignal(str)

    def __init__(self, parent=None):
        super(StartCycleFormHandler, self).__init__(parent)
        self.ui = Ui_CycleStart()
        self.ui.setupUi(self)
        # Use the correct widget name: startPushButton, not startCycleButton
        self.ui.startPushButton.clicked.connect(self.on_start_cycle)
        # self.ui.stopCycleButton.clicked.connect(self.on_stop_cycle)
        # Store self only once in the pool; do not recreate later
        pool.set('start_cycle_form', self)
        self.db = Database("sqlite:///local_database.db")
        self.cycle_data = None  # will be built when starting the cycle
        self.default_program_applied = False
        self.reading_thread_running = False
        self.reading_thread = None
        self.running = False
        self.data_reader_lock = Lock()
        
        # Initialize visualization integrator
        main_form = pool.get('main_form')
        self.visualization = VisualizationIntegrator(main_form if main_form else self)

    def on_start_cycle(self):
        self.start_cycle()

    def on_stop_cycle(self):
        logger.info("Stop Cycle button clicked")
        self.stop_data_reading()
        # At this point you might call finalize_cycle() to generate reports
        QMessageBox.information(self, "Cycle Finished", "Cycle has been stopped and finalized.")

    def start_data_reading(self):
        self.reading_thread_running = True
        self.reading_thread = threading.Thread(target=self.data_reading_loop, daemon=True)
        self.reading_thread.start()
        logger.info("Data reading thread started")

    def stop_data_reading(self):
        self.reading_thread_running = False
        logger.info("Data reading thread stopping...")

    def data_reading_loop(self):
    # Simulate reading data from the PLC; include vacuum gauge and cycle info data.
        while self.reading_thread_running:
            new_data = {
                'temperature': 25,          # Example temperature
                'pressure': 101.3,          # Example pressure
                'timestamp': datetime.now().strftime("%H:%M:%S"),
                'vacuum': {
                    'CH1': 12.3,
                    'CH2': 12.5,
                    'CH3': 12.1,
                    'CH4': 12.4,
                    'CH5': 11.9,
                    'CH6': 12.0,
                    'CH7': 12.2,
                    'CH8': 12.6,
                },
                'cycle_info': {
                    'maintain_vacuum': 5.0,
                    'set_cure_temp': 180,
                    'temp_ramp': 2.5,
                    'set_pressure': 101.3,
                    'dwell_time': "N/A",
                    'cool_down_temp': 50,
                    'cycle_start_time': datetime.now().strftime("%H:%M:%S"),
                    'cycle_end_time': "N/A",
                }
            }
            self.data_updated_signal.emit(new_data)
            sleep(1)

    def apply_default_program_values(self):
        default_prog = self.db.session.query(DefaultProgram).first()
        if default_prog and self.cycle_data:
            self.cycle_data.temp_ramp = default_prog.temp_ramp
            self.cycle_data.cool_down_temp = default_prog.cool_down_temp
            self.cycle_data.initial_set_cure_temp = default_prog.core_temp_setpoint
            self.cycle_data.final_set_cure_temp = default_prog.final_set_cure_temp
            self.cycle_data.set_pressure = default_prog.set_pressure
            logger.info("Default program values applied to cycle data")
        else:
            logger.info("No default program found or cycle data not initialized")
              
    def set_connections(self):
        main_form = pool.get('main_form')
        self.ui.startPushButton.clicked.connect(self.start_cycle)
        if main_form:
            self.ui.startPushButton.clicked.connect(main_form.update_cycle_info_pannel)
            self.data_updated_signal.connect(main_form.update_data)
            self.test_data_updated_signal.connect(main_form.update_immediate_test_values_panel)
            self.exit_with_error_signal.connect(main_form.show_error_and_stop)
     
        self.ui.cancelPushButton.clicked.connect(self.close)
        self.ui.programComboBox.currentIndexChanged.connect(self.apply_default_values)
    def apply_default_values(self):
        program_index = self.ui.programComboBox.currentIndex() + 1
        default_program = self.db.session.query(DefaultProgram).filter_by(
            username=pool.get("current_user"),
            program_number=program_index
        ).first()
        if default_program:
            # cycle_settings maps widget names to field names stored in DefaultProgram
            for widget_name, field_name in cycle_settings.items():
                if hasattr(self.ui, widget_name):
                    widget = getattr(self.ui, widget_name)
                    value = getattr(default_program, field_name, None)
                    if value is not None:
                        if isinstance(widget, QLineEdit):
                            widget.setText(str(value))
                        elif isinstance(widget, (QSpinBox, QDoubleSpinBox)):
                            try:
                                widget.setValue(float(value))
                            except Exception as e:
                                print(f"Error setting value for {widget_name}: {e}")
                else:
                    print(f"Warning: UI does not have attribute '{widget_name}'")
        else:
            QMessageBox.warning(self, "Warning", f"No default values found for Program {program_index}")
            
    def initiate_onedrive_update_thread(self):
        try:
            from RaspPiReader.libs.onedrive_api import OneDriveAPI
            client_id = pool.config('onedrive_client_id', str, '')
            client_secret = pool.config('onedrive_client_secret', str, '')
            tenant_id = pool.config('onedrive_tenant_id', str, '')
            if not all([client_id, client_secret, tenant_id]):
                logger.warning("OneDrive settings incomplete - skipping OneDrive thread initialization")
                return
            logger.info("Initializing OneDrive update thread")
            def update_onedrive():
                try:
                    one_drive = OneDriveAPI()
                    one_drive.authenticate(client_id, client_secret, tenant_id)
                    today = datetime.now().strftime("%Y%m%d")
                    reports_folder = "reports"
                    if not os.path.exists(reports_folder):
                        os.makedirs(reports_folder)
                    logger.info("OneDrive update thread started")
                except Exception as e:
                    logger.error(f"OneDrive update thread error: {e}")
            from threading import Thread
            self.onedrive_thread = Thread(target=update_onedrive, daemon=True)
            self.onedrive_thread.start()
            logger.info("OneDrive update thread initialized")
        except Exception as e:
            logger.error(f"Failed to initialize OneDrive update thread: {e}")

    def open_serial_management(self):
        dialog = SerialNumberManagementFormHandler(self)
        dialog.exec_()

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
        self.initiate_onedrive_update_thread()
        super().show()

    def close(self):
        self.running = False
        super().close()

    def load_cycle_data(self):
        for widget_name, key_name in cycle_settings.items():
            value = pool.config(key_name)
            if value is not None and hasattr(self.ui, widget_name):
                widget = getattr(self.ui, widget_name)
                if isinstance(widget, QLineEdit):
                    widget.setText(str(value))
                elif isinstance(widget, (QSpinBox, QDoubleSpinBox)):
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

    def initiate_reader_thread(self):
        dt = pool.config('time_interval', float, 1.0)
        self.read_thread = Thread(
            target=StartCycleFormHandler.read_data,
            args=(self, pool.get('data_stack'), self.data_updated_signal, dt)
        )
        self.read_thread.daemon = True

    def save_cycle_data(self):
    # Save widget values into pool configuration.
        for widget_name, key_name in cycle_settings.items():
            if hasattr(self.ui, widget_name):
                widget = getattr(self.ui, widget_name)
                value = widget.text() if isinstance(widget, QLineEdit) else widget.value()
                pool.set_config(key_name, value)
        order_id = pool.config("order_id", str, "DEFAULT_ORDER")
        self.file_name = order_id + self.cycle_start_time.strftime(" %Y.%m.%d %H.%M.%S")
        main_form = pool.get('main_form')
        if main_form:
            main_form.folder_name = self.file_name
        csv_file_path = pool.config('csv_file_path', str, os.path.join(os.getcwd(), "reports"))
        self.folder_path = os.path.join(csv_file_path, self.file_name)
        os.makedirs(self.folder_path, exist_ok=True)
        
        # Retrieve the current user.
        current_username = pool.get("current_user")
        if current_username:
            user = self.db.get_user(current_username)
            if not user:
                QMessageBox.critical(self, "Database Error", "Logged-in user not found.")
                return
        else:
            main_form = pool.get('main_form')
            if main_form and hasattr(main_form, 'user'):
                current_username = main_form.user.username
                user = self.db.get_user(current_username)
                if not user:
                    QMessageBox.critical(self, "Database Error", "Logged-in user not found.")
                    return
            else:
                QMessageBox.critical(self, "Error", "No current user set in session.")
                return

        logger.info(f"Current username determined: {current_username}")

        # Create cycle_data now including size and cycle_location from default programs.
        cycle_data = CycleData(
            order_id = pool.config("order_id", str, "DEFAULT_ORDER"),
            quantity = pool.config("quantity", int, 0),
            size = pool.config("size", str, ""),
            cycle_location = pool.config("cycle_location", str, ""),
            dwell_time = pool.config("dwell_time", str, ""),
            cool_down_temp = pool.config("cool_down_temp", float, 0.0),
            core_temp_setpoint = pool.config("core_temp_setpoint", float, 0.0),
            temp_ramp = pool.config("temp_ramp", float, 0.0),
            set_pressure = pool.config("set_pressure", float, 0.0),
            maintain_vacuum = pool.config("maintain_vacuum", bool, False),
            initial_set_cure_temp = pool.config("initial_set_cure_temp", float, None),
            final_set_cure_temp = pool.config("final_set_cure_temp", float, None)
        )
        
        # Assign the retrieved user.
        cycle_data.user = user
        logger.info(f"CycleData before insert: order_id={cycle_data.order_id}, user_id={cycle_data.user_id}")
        try:
            if not self.db.add_cycle_data(cycle_data):
                QMessageBox.critical(self, "Database Error", "Could not save cycle data.")
                return
        except Exception as e:
            QMessageBox.critical(self, "Database Error", f"Could not save cycle data: {e}")
            return

        logger.info(f"Cycle data saved for order {cycle_data.order_id}")
        pool.set("current_cycle", cycle_data)  # Store the cycle data

    def start_cycle_signal(self):
        """
        Send a signal to the PLC that the cycle is starting. 
        Writes True (coil=1) to the dedicated coil address.
        """
        coil_addr = pool.config("cycle_start_coil_address", int, 100)
        success = plc_communication.write_coil(coil_addr, True)
        if success:
            self.cycle_start_time = datetime.now()
            logger.info(f"Cycle start signal sent (coil {coil_addr} set to True).")
        else:
            logger.error("Failed to send cycle start signal to PLC.")

    def stop_cycle_signal(self):
        """
        Send a signal to the PLC that the cycle is stopping.
        Writes False (coil=0) to the dedicated coil address.
        """
        coil_addr = pool.config("cycle_start_coil_address", int, 100)
        success = plc_communication.write_coil(coil_addr, False)
        if success:
            self.cycle_end_time = datetime.now()
            logger.info(f"Cycle stop signal sent (coil {coil_addr} set to False).")
        else:
            logger.error("Failed to send cycle stop signal to PLC.")

    def start_cycle(self):
        self.cycle_start_time = datetime.now()
        self.save_cycle_data()  # Stores the cycle data in pool as "current_cycle"
        self.cycle_record = pool.get("current_cycle")
        pool.set("start_cycle_form", self)
        self.start_cycle_signal()
        # Write to the start cycle coil so the PLC knows the cycle has started.
        start_coil_addr = pool.config('cycle_start_coil_address', int, 100)
        from RaspPiReader.libs.plc_communication import write_coil
        write_coil(start_coil_addr, True)
        
        main_form = pool.get('main_form')
        if main_form:
            main_form.actionStart.setEnabled(False)
            main_form.actionStop.setEnabled(True)
            main_form.create_csv_file()
            main_form.cycle_timer.start(500)
            main_form.update_cycle_info_pannel()
        self.running = True
        self.hide()
        self.initiate_reader_thread()
        if self.read_thread:
            self.read_thread.start()
        self.initiate_onedrive_update_thread()
        
        # Start visualization dashboard
        self.visualization.on_cycle_start()
        
        self.show()

    def stop_cycle(self):
        if not hasattr(self, "cycle_record") or self.cycle_record is None:
            QMessageBox.critical(self, "Error", "No active cycle record found.")
            return
        start_coil_addr = pool.config('cycle_start_coil_address', int, 100)
        from RaspPiReader.libs.plc_communication import write_coil
        write_coil(start_coil_addr, False)
        self.cycle_record.stop_time = datetime.now()
        try:
            serial_numbers = self.get_serial_numbers() or []
        except Exception as e:
            logger.error(f"Error retrieving serial numbers: {e}")
            QMessageBox.critical(self, "Error", f"Error retrieving serial numbers: {e}")
            return
        supervisor_username = self.get_supervisor_override() or ""
        alarm_values = self.read_alarms() or {}
        try:
            pdf_file, csv_file = finalize_cycle(
                cycle_data=self.cycle_record,
                serial_numbers=serial_numbers,
                supervisor_username=supervisor_username,
                alarm_values=alarm_values,
                reports_folder="reports",
                template_file="RaspPiReader/ui/result_template.html"
            )
        except Exception as e:
            logger.error(f"Error finalizing cycle: {e}")
            QMessageBox.critical(self, "Report Generation Error", f"Error finalizing cycle: {e}")
            return
        db = Database("sqlite:///local_database.db")
        order_id = getattr(self.cycle_record, "order_id", "unknown")
        if order_id == "unknown":
            logger.warning("No order_id found in cycle record; using default 'unknown'.")
        try:
            current_username = pool.get("current_user")
            user = db.session.query(User).filter_by(username=current_username).first()
            if not user:
                QMessageBox.critical(self, "Database Error", "Logged-in user not found for finalizing cycle.")
                return
            self.cycle_record.pdf_report_path = pdf_file
            self.cycle_record.html_report_path = csv_file
            db.session.commit()
            logger.info(f"Cycle record updated for order_id: {order_id}")
        except Exception as e:
            db.session.rollback()
            logger.error(f"Database error updating cycle record: {e}")
            QMessageBox.critical(self, "Database Error", f"Could not update cycle record: {e}")
            return
        QMessageBox.information(
            self,
            "Cycle Stopped",
            f"Cycle stopped successfully!\nPDF Report: {pdf_file}\nCSV Report: {csv_file}"
        )
        if hasattr(self, "csv_file"):
            try:
                self.csv_file.close()
            except Exception:
                pass
        self.running = False
        
        # Stop visualization dashboard
        self.visualization.on_cycle_stop()
        
        self.close()
        main_form = pool.get('main_form')
        if main_form:
            main_form.cycle_timer.stop()
            main_form.actionStart.setEnabled(True)
            main_form.actionStop.setEnabled(False)
        pool.set("start_cycle_form", None)
        pool.set("current_cycle", None)

    def get_serial_numbers(self):
        try:
            db = Database("sqlite:///local_database.db")
            latest_cycle = db.session.query(CycleData)\
                                .order_by(CycleData.id.desc())\
                                .first()
            if latest_cycle and latest_cycle.serial_numbers:
                return latest_cycle.serial_numbers.split(',')
            else:
                return []
        except Exception as e:
            logger.error(f"Error retrieving serial numbers: {e}")
            return []

    def get_supervisor_override(self):
        db = Database("sqlite:///local_database.db")
        supervisor_user = db.get_user("supervisor")
        if supervisor_user:
            return supervisor_user.username
        else:
            return "supervisor"

    def read_alarms(self):
        db = Database("sqlite:///local_database.db")
        alarms = db.session.query(Alarm).all()
        alarm_dict = {}
        for alarm in alarms:
            alarm_dict[alarm.channel] = alarm.alarm_text
        return alarm_dict

    @staticmethod
    def read_data(handler, data_stack, updated_signal, dt, process_data=True):
        # Retrieve configuration values:
        #   - core_temp_channel: channel 12 (default)
        #   - pressure_channel: channel 13 (default pressure measurement)
        #   - core_temp_setpoint: default 100 °C
        core_temp_channel = pool.config('core_temp_channel', int, 12)
        pressure_channel = pool.config('pressure_channel', int, 13)
        core_temp_setpoint = pool.config('core_temp_setpoint', int, 100)
        active_channels = pool.get('active_channels')
        if active_channels is None:
            active_channels = list(range(1, CHANNEL_COUNT + 1))
        # Ensure data_stack has CHANNEL_COUNT+2 slots
        if data_stack is None or not isinstance(data_stack, list) or len(data_stack) < (CHANNEL_COUNT + 2):
            data_stack = [[] for _ in range(CHANNEL_COUNT + 2)]
        
        handler.pressure_drop_core_temp = None
        core_temp_above_setpoint_start_time = None
        handler.core_temp_above_setpoint_time = 0
        pressure_drop_recorded = False  # To avoid multiple recordings for same drop event

        # Helper function: perform pressure drop check.
        # It looks back over the timestamp stack (index CHANNEL_COUNT+1) for a reading at least 5 seconds older.
        # If the pressure drop from that reading to the current one is >=10 units, record the current core temp.
        def check_pressure_drop():
            nonlocal pressure_drop_recorded
            current_time = datetime.now()
            current_pressure = data_stack[pressure_channel][-1]
            index_to_compare = None
            timestamps = data_stack[CHANNEL_COUNT + 1]
            # Look backward for the first timestamp at least 5 seconds old
            for idx in range(len(timestamps) - 2, -1, -1):
                if (current_time - timestamps[idx]).total_seconds() >= 5:
                    index_to_compare = idx
                    break
            if index_to_compare is not None:
                old_pressure = data_stack[pressure_channel][index_to_compare]
                if (old_pressure - current_pressure) >= 10 and not pressure_drop_recorded:
                    handler.pressure_drop_core_temp = data_stack[core_temp_channel][-1]
                    pressure_drop_recorded = True
                else:
                    pressure_drop_recorded = False

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
                    # Append elapsed time (in minutes) and current timestamp (to slot CHANNEL_COUNT+1)
                    elapsed_minutes = round((datetime.now() - handler.cycle_start_time).total_seconds() / 60, 2)
                    data_stack[0].append(elapsed_minutes)
                    data_stack[CHANNEL_COUNT + 1].append(datetime.now())
                    # Core temp setpoint logic
                    if (not core_temp_above_setpoint_start_time and 
                        data_stack[core_temp_channel][-1] >= core_temp_setpoint):
                        core_temp_above_setpoint_start_time = datetime.now()
                    elif core_temp_above_setpoint_start_time and data_stack[core_temp_channel][-1] < core_temp_setpoint:
                        handler.core_temp_above_setpoint_time += round(
                            (datetime.now() - core_temp_above_setpoint_start_time).total_seconds() / 60, 2)
                        core_temp_above_setpoint_start_time = None
                    # Pressure drop check based on channel 13
                    if len(data_stack[CHANNEL_COUNT + 1]) >= 2:
                        check_pressure_drop()
                new_data = {"data_stack": data_stack, "timestamp": datetime.now()}
                logger.info(f"Emitting new_data: {new_data}")
                updated_signal.emit(new_data)
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
                            addr_str = pool.config('address' + str(i + 1), str, "0")
                            pv_str = pool.config('pv' + str(i + 1), str, "0")
                            address = int(addr_str, 10)
                            pv = int(pv_str, 16)
                            temp = dataReader.readData(address, pv)
                            if temp is None:
                                raise ValueError("DataReader.readData returned None")
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
                            print(f"Failed to read or process data from channel {i + 1}.\n{e}")
                            try:
                                print("Restarting data reader")
                                dataReader.stop()
                                dataReader.reload()
                                print("Restart successful")
                            except Exception as e:
                                print(f"Restart failed channel {i + 1}.\n{e}")
                            temp = -1000.00
                    else:
                        temp = 0.00
                    temp_arr.append(temp)
                handler.data_reader_lock.release()
                for i in range(CHANNEL_COUNT):
                    try:
                        data_stack[i + 1].append(temp_arr[i])
                    except Exception as ex:
                        print(f"Error appending to data_stack at index {i + 1}: {ex}")
                if process_data:
                    elapsed_minutes = round((datetime.now() - handler.cycle_start_time).total_seconds() / 60, 2)
                    data_stack[0].append(elapsed_minutes)
                    data_stack[CHANNEL_COUNT + 1].append(datetime.now())
                    if (not core_temp_above_setpoint_start_time and
                        data_stack[core_temp_channel][-1] >= core_temp_setpoint):
                        core_temp_above_setpoint_start_time = datetime.now()
                    elif core_temp_above_setpoint_start_time and data_stack[core_temp_channel][-1] < core_temp_setpoint:
                        handler.core_temp_above_setpoint_time += round(
                            (datetime.now() - core_temp_above_setpoint_start_time).total_seconds() / 60, 2)
                        core_temp_above_setpoint_start_time = None
                    if len(data_stack[CHANNEL_COUNT + 1]) >= 2:
                        check_pressure_drop()
                new_data = {"data_stack": data_stack, "timestamp": datetime.now()}
                logger.info(f"Emitting new_data: {new_data}")
                updated_signal.emit(new_data)
                while (datetime.now() - iteration_start_time) < timedelta(seconds=dt):
                    sleep(0.001)
            try:
                dataReader.stop()
            except Exception:
                print('Unable to stop data reader')

        def _start(self):
            if not plc_communication.is_connected():
                success = plc_communication.initialize_plc_communication()
                if not success:
                    QMessageBox.critical(self, "Connection Error",
                                        "Failed to connect to PLC. Please check your connection settings.")
                    return
            dataReader.start()
            main_form = pool.get('main_form')
            if main_form is not None:
                main_form.update_connection_status_display()
            else:
                import logging
                logging.getLogger(__name__).error("Main form is not available; cannot update connection status.")
            if not hasattr(self, "timer"):
                from PyQt5.QtCore import QTimer
                self.timer = QTimer(self)
            self.timer.start(1000)
            self.running = True
