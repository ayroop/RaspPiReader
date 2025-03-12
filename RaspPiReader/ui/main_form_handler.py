import os
import csv
import pdfkit
from datetime import datetime
import logging
from colorama import Fore
import webbrowser
import tempfile 
import jinja2 
from PyQt5 import QtWidgets, uic
from PyQt5.QtCore import QTimer, pyqtSignal, QSettings
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QMainWindow, QErrorMessage, QMessageBox, QApplication, QLabel, QAction, QSizePolicy
from RaspPiReader.ui.start_cycle_form_handler import StartCycleFormHandler
from RaspPiReader import pool
from .mainForm import MainForm
from .plot_handler import InitiatePlotWidget
from .plot_preview_form_handler import PlotPreviewFormHandler
from .setting_form_handler import SettingFormHandler, CHANNEL_COUNT
from .start_cycle_form_handler import StartCycleFormHandler
from .user_management_form_handler import UserManagementFormHandler
from RaspPiReader.ui.one_drive_settings_form_handler import OneDriveSettingsFormHandler
from RaspPiReader.libs.onedrive_api import OneDriveAPI
from .plc_comm_settings_form_handler import PLCCommSettingsFormHandler
from RaspPiReader.ui.database_settings_form_handler import DatabaseSettingsFormHandler

import pyqtgraph as pg

# New import related with 6 bool addresses and new cycle widget
from RaspPiReader.libs.communication import dataReader
from RaspPiReader.libs.configuration import config
from .boolean_status import Ui_BooleanStatusWidget
from RaspPiReader.libs.models import BooleanStatus, PlotData, BooleanAddress
from RaspPiReader.libs.database import Database
from RaspPiReader.ui.new_cycle_handler import NewCycleHandler

# Add default program settings
from RaspPiReader.ui.default_program_form import DefaultProgramForm
# New Cycle logic
from RaspPiReader.ui.work_order_form_handler import WorkOrderFormHandler
# Add Alarm settings
from RaspPiReader.ui.alarm_settings_form_handler import AlarmSettingsFormHandler

# Add PLC connection status
from RaspPiReader.libs import plc_communication
from RaspPiReader.libs.cycle_finalization import finalize_cycle

logger = logging.getLogger(__name__)
def timedelta2str(td):
    # Use total_seconds to account for days as well
    total_seconds = int(td.total_seconds())
    h, rem = divmod(total_seconds, 3600)
    m, s = divmod(rem, 60)
    # Zero-pad each component to always have two digits
    def zp(val):
        return str(val).zfill(2)
    return f"{zp(h)}:{zp(m)}:{zp(s)}"

class MainFormHandler(QMainWindow):
    update_status_bar_signal = pyqtSignal(str, int, str)

    def __init__(self, user_record=None):
        super(MainFormHandler, self).__init__()
        self.user_record = user_record
        self.form_obj = MainForm()
        self.form_obj.setupUi(self)
        self.immediate_panel_update_locked = False

        # Retrieve or create StartCycleFormHandler
        self.start_cycle_form = pool.get("start_cycle_form")
        if not self.start_cycle_form:
            
            self.start_cycle_form = StartCycleFormHandler()
            pool.set("start_cycle_form", self.start_cycle_form)
            logger.info("Created new StartCycleFormHandler and set in pool inside MainFormHandler.")
        self.start_cycle_form.data_updated_signal.connect(self.update_data)
        logger.info("Connected data_updated_signal from StartCycleFormHandler")
        
        # Set main_form in the pool
        pool.set('main_form', self)
        
        # Define the headers used for CSV file creation.
        self.headers = ['Date', 'Time', 'Timer(min)', 'CycleID', 'OrderID', 'Quantity', 'CycleLocation']
        self.file_name = None
        self.folder_name = None
        self.csv_path = None
        self.pdf_path = None
        self.plot = None   # Will be set by setup_plot_data_display
        
        self.username = self.user_record.username if self.user_record else ''

        self.cycle_timer = QTimer()

        # Initialize the data stacks (data_stack and test_data_stack)
        self.create_stack()

        # Initialize connections, user display, and (optional) stacks
        self.set_connections()
        self.display_username()
        
        # Setup additional menus
        self.setup_access_controls()
        self.connect_menu_actions()
        self.add_one_drive_menu()
        self.add_plc_comm_menu()
        self.add_database_menu()
        
        # Initialize Boolean status area and plot area
        self.db = Database("sqlite:///local_database.db")
        self.setup_bool_status_display()
        self.setup_plot_data_display()  # creates plot widget and calls initialize_plot_widget
        self.integrate_new_cycle_widget()
        
        # Start timers
        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self.update_bool_status)
        self.status_timer.start(5000)
        self.add_default_program_menu()
        self.add_alarm_settings_menu()
        self.connectionTimer = QTimer(self)
        self.connectionTimer.timeout.connect(self.update_connection_status_display)
        self.connectionTimer.start(5000)
        self.live_update_timer = QTimer(self)
        self.live_update_timer.timeout.connect(self.update_live_data)
        self.live_update_timer.start(500)  # Update live data every 500ms (adjust as needed)
        logger.info("Live update timer started.")
        self.showMaximized()
        logger.info("MainFormHandler initialized.")

    def update_data(self, new_data):
        """
        Update UI elements based on the new_data dictionary.
        Keys expected:
         - temperature: float/int for temperature in °C
         - pressure: float/int for cylinder pressure in KPa
         - vacuum: dict with keys 'CH1'..'CH8' for vacuum gauge values (KPa)
         - cycle_info: dict with keys 'maintain_vacuum','set_cure_temp','temp_ramp',
                         'set_pressure','dwell_time','cool_down_temp','cycle_start_time','cycle_end_time'
         - plot: list of (time, value) pairs for plotting
        """
        logger.info(f"MainForm received update: {new_data}")
        try:
            # Temperature and Pressure
            temperature = new_data.get('temperature', 'N/A')
            pressure = new_data.get('pressure', 'N/A')
            self.form_obj.temperatureLabel.setText(f"Temperature: {temperature} °C")
            self.form_obj.pressureLabel.setText(f"Pressure: {pressure} KPa")
            
            # Vacuum Gauge channels CH1 to CH8
            vacuum_data = new_data.get('vacuum', {})
            if vacuum_data:
                self.form_obj.vacuumLabelCH1.setText(f"CH1: {vacuum_data.get('CH1', 0)} KPa")
                self.form_obj.vacuumLabelCH2.setText(f"CH2: {vacuum_data.get('CH2', 0)} KPa")
                self.form_obj.vacuumLabelCH3.setText(f"CH3: {vacuum_data.get('CH3', 0)} KPa")
                self.form_obj.vacuumLabelCH4.setText(f"CH4: {vacuum_data.get('CH4', 0)} KPa")
                self.form_obj.vacuumLabelCH5.setText(f"CH5: {vacuum_data.get('CH5', 0)} KPa")
                self.form_obj.vacuumLabelCH6.setText(f"CH6: {vacuum_data.get('CH6', 0)} KPa")
                self.form_obj.vacuumLabelCH7.setText(f"CH7: {vacuum_data.get('CH7', 0)} KPa")
                self.form_obj.vacuumLabelCH8.setText(f"CH8: {vacuum_data.get('CH8', 0)} KPa")
            
            # Cycle Info fields
            cycle_info = new_data.get('cycle_info', {})
            if cycle_info:
                self.form_obj.maintainVacuumLineEdit.setText(str(cycle_info.get('maintain_vacuum', '')))
                self.form_obj.setCureTempLineEdit.setText(str(cycle_info.get('set_cure_temp', '')))
                self.form_obj.tempRampLineEdit.setText(str(cycle_info.get('temp_ramp', '')))
                self.form_obj.setPressureLineEdit.setText(str(cycle_info.get('set_pressure', '')))
                self.form_obj.dwellTimeLineEdit.setText(str(cycle_info.get('dwell_time', 'N/A')))
                self.form_obj.coolDownTempLineEdit.setText(str(cycle_info.get('cool_down_temp', '')))
                self.form_obj.cycleStartTimeLabel.setText(cycle_info.get('cycle_start_time', 'N/A'))
                self.form_obj.cycleEndTimeLabel.setText(cycle_info.get('cycle_end_time', 'N/A'))
            
            # Plot update (expects plot data as a list of tuples, where each tuple has format: (time, val1, val2, ...))
            plot_data = new_data.get('plot', [])
            if plot_data and self.plot:
                self.plot.update_plot_data(plot_data)
        except Exception as e:
            logger.error(f"Error updating main form data: {e}")

    def update_cycle_info_pannel(self):
        self.d1.setText(pool.config("cycle_id"))
        self.d2.setText(pool.config("order_id"))
        self.d3.setText(pool.config("quantity"))
        self.d4.setText(self.start_cycle_form.cycle_start_time.strftime("%Y/%m/%d"))
        self.d5.setText(self.start_cycle_form.cycle_start_time.strftime("%H:%M:%S"))
        self.d7.setText(pool.config("cycle_location"))
        self.p1.setText(pool.config("maintain_vacuum"))
        self.p2.setText(pool.config("initial_set_cure_temp"))
        self.p3.setText(pool.config("temp_ramp"))
        self.p4.setText(pool.config("set_pressure"))
        self.p5.setText(pool.config("dwell_time"))
        self.p6.setText(pool.config("cool_down_temp"))
        self.cH1Label_36.setText(f"TIME (min) CORE TEMP ≥ {pool.config('core_temp_setpoint')} °C:")
    def _calculate_cycle_duration(self):
        if hasattr(self.start_cycle_form, "cycle_start_time"):
            duration = datetime.now() - self.start_cycle_form.cycle_start_time
            return str(duration).split('.')[0]
        return "N/A"

    def start_cycle_timer(self, cycle_start):
        self.cycle_start = cycle_start
        self.cycle_timer = QTimer(self)
        self.cycle_timer.timeout.connect(self.update_cycle_timer)
        self.cycle_timer.start(1000)

    def update_cycle_timer(self):
        elapsed = datetime.now() - self.cycle_start
        self.form_obj.cycleDurationLabel.setText(str(elapsed).split('.')[0])  
        
    def add_alarm_settings_menu(self):
        # Create a new menu called "Alarms" and add the alarm settings action.
        menubar = self.menuBar()
        alarms_menu = menubar.addMenu("Alarms")
        alarm_settings_action = QAction("Manage Alarms", self)
        alarm_settings_action.triggered.connect(self.open_alarm_settings)
        alarms_menu.addAction(alarm_settings_action)
    
    def open_alarm_settings(self):
        # Instantiate and show the Alarm Settings dialog.
        dialog = AlarmSettingsFormHandler(self)
        dialog.exec_()

    def new_cycle_start(self):
        self.workOrderForm = WorkOrderFormHandler()
        self.workOrderForm.show()

    def add_default_program_menu(self):
        menubar = self.menuBar()
        defaultProgMenu = menubar.addMenu("Default Programs")
        manageAction = QtWidgets.QAction("Manage Default Programs", self)
        manageAction.triggered.connect(self.open_default_program_management)
        defaultProgMenu.addAction(manageAction)

    def open_default_program_management(self):
        dlg = DefaultProgramForm(self)
        dlg.exec_()
    
    def setup_bool_status_display(self):
        # Create the container widget for Boolean status display
        self.boolStatusWidgetContainer = QtWidgets.QWidget(self)
        self.boolStatusWidget = Ui_BooleanStatusWidget()
        self.boolStatusWidget.setupUi(self.boolStatusWidgetContainer)
        self.boolStatusLabels = [
            self.boolStatusWidget.boolStatusLabel1,
            self.boolStatusWidget.boolStatusLabel2,
            self.boolStatusWidget.boolStatusLabel3,
            self.boolStatusWidget.boolStatusLabel4,
            self.boolStatusWidget.boolStatusLabel5,
            self.boolStatusWidget.boolStatusLabel6,
        ]
        # Insert the Boolean status widget into the central widget's layout
        central_layout = self.centralWidget().layout()
        if central_layout is None:
            central_layout = QtWidgets.QVBoxLayout(self.centralWidget())
            self.centralWidget().setLayout(central_layout)
        central_layout.addWidget(self.boolStatusWidgetContainer)
        
    def integrate_new_cycle_widget(self):
        # Create an instance of the new cycle widget
        self.new_cycle_handler = NewCycleHandler(self)
        
        # Get the central layout of the QMainWindow (set up by MainForm.setupUi)
        central_layout = self.centralWidget().layout()
        if central_layout is None:
            central_layout = QtWidgets.QVBoxLayout(self.centralWidget())
        
        # Remove the already added bool status widget container from the central layout
        central_layout.removeWidget(self.boolStatusWidgetContainer)
        
        # Create a new container with a horizontal layout
        container = QtWidgets.QWidget(self.centralWidget())
        h_layout = QtWidgets.QHBoxLayout(container)
        h_layout.setContentsMargins(0, 0, 0, 0)
        # Add the Boolean status container on the left
        h_layout.addWidget(self.boolStatusWidgetContainer)
        # Add the new cycle widget on the right
        h_layout.addWidget(self.new_cycle_handler)
        
        # Add the container to the central layout
        central_layout.addWidget(container)
        container.show()

    def update_bool_status(self):
        """
        Update the Boolean status labels with data from the database and real-time PLC status.
        Each label will show text like:
        "Bool Address 1: <Address> - <Label> - <Status>"
        where the <Address> and <Label> are formatted with the fixed color code #832116,
        and <Status> is the dynamic PLC value in green if True or red if False.
        """
        from RaspPiReader.libs.database import Database
        from RaspPiReader.libs.communication import dataReader

        db = Database("sqlite:///local_database.db")
        boolean_entries = db.session.query(BooleanAddress).all()
        fixed_color = "#832116"

        # Loop through each status widget (assumed to be stored in self.boolStatusLabels)
        for i, label in enumerate(self.boolStatusLabels):
            if i < len(boolean_entries):
                entry = boolean_entries[i]
                # Attempt to read dynamic bool status from the PLC for this address.
                try:
                    plc_status = dataReader.read_bool_address(entry.address, dev=1)  # Expected to return True or False
                except Exception as ex:
                    plc_status = None

                if plc_status is None:
                    status_text = "N/A"
                    status_color = "black"
                elif plc_status:
                    status_text = "True"
                    status_color = "green"
                else:
                    status_text = "False"
                    status_color = "red"

                display_text = (
                    f"Bool Address {i+1}: "
                    f"<span style='color:{fixed_color};'>{entry.address} - {entry.label}</span> - "
                    f"<span style='color:{status_color};'>{status_text}</span>"
                )
                label.setText(display_text)
            else:
                label.setText("N/A")
    def setup_plot_data_display(self):
        """
        Create a container for the plot widget, add it to the central widget layout,
        and delay initialization by 100ms.
        """
        self.plotWidgetContainer = QtWidgets.QWidget(self)
        container_layout = QtWidgets.QVBoxLayout()
        self.plotWidgetContainer.setLayout(container_layout)
        # Get (or create) the central widget's layout.
        central_widget = self.centralWidget()
        central_layout = central_widget.layout()
        if central_layout is None:
            central_layout = QtWidgets.QVBoxLayout(central_widget)
            central_widget.setLayout(central_layout)
        central_layout.addWidget(self.plotWidgetContainer)
        QTimer.singleShot(100, self.initialize_plot_widget)

    def initialize_plot_widget(self):
        """
        Create the plot widget using the InitiatePlotWidget class.
        """
        parent_layout = self.plotWidgetContainer.layout()
        self.plot = InitiatePlotWidget(
            active_channels=["CH1", "CH2", "CH3", "CH4", "CH5", "CH6", "CH7", "CH8"],
            parent_layout=parent_layout,
            headers=["Time", "Value"]
        )
        self.plot.update_plot()

    def init_custom_status_bar(self):
        """
        Create a custom composite widget in the status bar that consists of
        a fixed-size label (for connection info) and an expanding label for dynamic messages.
        """
        from PyQt5.QtWidgets import QWidget, QHBoxLayout, QLabel, QSizePolicy
        if not hasattr(self, 'customStatusWidget'):
            self.customStatusWidget = QWidget()
            layout = QHBoxLayout(self.customStatusWidget)
            layout.setContentsMargins(0, 0, 0, 0)
            # Fixed-size label for connection info (and optionally, username/admin info)
            self.connectionInfoLabel = QLabel()
            self.connectionInfoLabel.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
            self.connectionInfoLabel.setMinimumWidth(150)
            layout.addWidget(self.connectionInfoLabel)
            # Expanding label for dynamic status messages
            self.dynamicStatusLabel = QLabel()
            self.dynamicStatusLabel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            layout.addWidget(self.dynamicStatusLabel)
            # Remove any previous permanent widgets if needed
            self.statusbar.clearMessage()
            self.statusbar.addPermanentWidget(self.customStatusWidget, stretch=1)
    
    def update_connection_status_display(self):
        """
        Update the custom status bar widget:
          - The connectionInfoLabel shows connection type information.
          - The dynamicStatusLabel displays a temporary status message with color coding.
        
        It checks for PLC connection as well as active alarms.
        """
        # Make sure the custom status bar is initialized
        if not hasattr(self, 'customStatusWidget'):
            self.init_custom_status_bar()
        
        # Update the connection info (permanent) part.
        connection_type = pool.config('plc/connection_type', str, 'rtu')
        if connection_type == 'tcp':
            host = pool.config('plc/host', str, 'Not Set')
            port = pool.config('plc/tcp_port', int, 502)
            self.connectionInfoLabel.setText(f"TCP: {host}:{port}")
            self.connectionInfoLabel.setStyleSheet("color: blue;")
        else:
            port = pool.config('plc/port', str, 'Not Set')
            self.connectionInfoLabel.setText(f"RTU: {port}")
            self.connectionInfoLabel.setStyleSheet("color: green;")
        
        # Now update dynamic status (temporary message) area.
        try:
            # Check connection status via PLC communication module.
            is_connected = plc_communication.is_connected()
            # Optional: Check alarms (if check_alarms method exists).
            if hasattr(self, 'check_alarms'):
                alarm_active, alarm_msg = self.check_alarms()
            else:
                alarm_active, alarm_msg = False, ""
            
            if alarm_active:
                msg = alarm_msg
                bgcolor = "#FADBD8"
                fgcolor = "red"
            elif is_connected:
                msg = "Connected to PLC"
                bgcolor = "#D5F5E3"
                fgcolor = "#196F3D"
            else:
                msg = "Not connected to PLC - Check settings"
                bgcolor = "#FADBD8"
                fgcolor = "#943126"
            
            self.dynamicStatusLabel.setText(msg)
            self.dynamicStatusLabel.setStyleSheet(f"background-color: {bgcolor}; color: {fgcolor};")
        except Exception as e:
            self.dynamicStatusLabel.setText(f"Error: {str(e)}")
            self.dynamicStatusLabel.setStyleSheet("background-color: #FADBD8; color: #943126;")
    
    def update_status_bar(self, msg, ms_timeout, color):
        """
        Update the dynamic portion of the custom status bar.
        This method may be used by other parts of the code to temporarily override
        the status message.
        """
        # Update dynamicStatusLabel; since this is our expanding label it will display
        # the full message.
        if not hasattr(self, 'dynamicStatusLabel'):
            self.init_custom_status_bar()
        self.dynamicStatusLabel.setText(msg)
        self.dynamicStatusLabel.setStyleSheet(f"color: {color.lower()};")
        # The ms_timeout parameter can be used if you later decide to clear the message after some time.
        

    def check_alarms(self):
        """
        Check if there are any active alarms.
        Returns a tuple: (alarm_active: bool, alarm_message: str)
        """
        try:
            from RaspPiReader.libs.database import Database
            from RaspPiReader.libs.models import Alarm
            db = Database("sqlite:///local_database.db")
            # Example query: get alarms that are active (adjust field names as needed)
            alarms = db.session.query(Alarm).filter_by(active=True).all()
            if alarms:
                alarm_msgs = ", ".join([alarm.text for alarm in alarms])
                return True, f"ALARM: {alarm_msgs}"
        except Exception as e:
            # In case of query error, log but do not break
            pass
        return False, ""
    def add_one_drive_menu(self):
        one_drive_action = QAction("OneDrive Settings", self)
        one_drive_action.triggered.connect(self.show_onedrive_settings)
        self.menuBar().addAction(one_drive_action)

    def show_onedrive_settings(self):
        dialog = OneDriveSettingsFormHandler(self)
        dialog.exec_()

    def add_plc_comm_menu(self):
        menubar = self.menuBar()
        plc_menu = menubar.addMenu("PLC")
        plc_settings_action = QtWidgets.QAction("PLC Communication Settings", self)
        plc_menu.addAction(plc_settings_action)
        plc_settings_action.triggered.connect(self.show_plc_comm_settings)

    def show_plc_comm_settings(self):
        dialog = PLCCommSettingsFormHandler(self)
        dialog.exec_()

    def add_database_menu(self):
        database_menu = self.menuBar().addMenu("Database")
        database_settings_action = QtWidgets.QAction("Database Settings", self)
        database_settings_action.triggered.connect(self.show_database_settings)
        database_menu.addAction(database_settings_action)

    def show_database_settings(self):
        dlg = DatabaseSettingsFormHandler(parent=self)
        dlg.exec_()

    def setup_access_controls(self):
        """
        Disable or hide menu actions/pages based on user_record flags.
        The keys in 'permissions' must match those in user_record.
        """
        permissions = {
            "settings": "actionSetting",
            "search": "actionSearch",
            "user_mgmt_page": "actionUserManagement",
        }
        for perm_key, action_name in permissions.items():
            if not getattr(self.user_record, perm_key, False):
                if hasattr(self.form_obj, action_name):
                    getattr(self.form_obj, action_name).setEnabled(False)
                else:
                    print(f"Warning: '{action_name}' not found in MainForm UI.")

    def connect_menu_actions(self):
        """
        Connect menu actions and check permissions if necessary.
        """
        if hasattr(self.form_obj, "actionSetting"):
            self.form_obj.actionSetting.triggered.connect(self.handle_settings)
        else:
            print("Warning: 'actionSetting' not found in the MainForm UI.")
            
    def handle_settings(self):
        print(f"Handling settings with user_record: {self.user_record}")
        if getattr(self.user_record, 'settings', False):
            self.settings_handler = SettingFormHandler()
            self.settings_handler.show()
        else:
            QMessageBox.critical(self, "Access Denied", "You don't have permission to access Settings.")
            
    def set_connections(self):
        self.actionExit.triggered.connect(self.close)
        self.actionCycle_Info.triggered.connect(self._show_cycle_info)
        self.actionPlot.triggered.connect(self._show_plot)
        self.actionSetting.triggered.connect(self.handle_settings)
        self.actionStart.triggered.connect(self._start)
        self.actionStart.triggered.connect(lambda: self.actionPlot_preview.setEnabled(False))
        self.actionStop.triggered.connect(self._stop)
        self.actionPlot_preview.triggered.connect(self.show_plot_preview)
        self.actionPrint_results.triggered.connect(self.open_pdf)
        self.cycle_timer.timeout.connect(self.cycle_timer_update)
        self.update_status_bar_signal.connect(self.update_status_bar)
        if not hasattr(self, 'userMgmtAction'):
            self.userMgmtAction = QAction("User Management", self)
            self.userMgmtAction.triggered.connect(self.open_user_management)
            self.menuBar().addAction(self.userMgmtAction)

    def open_user_management(self):
        if getattr(self.user_record, 'user_mgmt_page', False):
            dlg = UserManagementFormHandler(self)
            dlg.exec_()
        else:
            QtWidgets.QMessageBox.warning(self, "Error", "Access denied. Only admin can manage users.")

    def display_username(self):
        """
        Instead of adding the username as a permanent widget in the status bar (which might
        reduce space for the dynamic message), consider placing it elsewhere in your UI
        (e.g. in a dedicated toolbar or a corner label). For this example, we include it
        at the right edge of the main window title.
        """
        self.setWindowTitle(f"Main Form - Logged in as: {self.user_record.username if self.user_record else 'N/A'}")

    def create_stack(self):
    # Initialize data_stack: one list for process_time and one for each channel plus one for sampling time.
        data_stack = [[] for _ in range(CHANNEL_COUNT + 2)]
        test_data_stack = [[] for _ in range(CHANNEL_COUNT + 2)]
        pool.set("data_stack", data_stack)
        pool.set("test_data_stack", test_data_stack)
        self.data_stack = data_stack
        self.test_data_stack = test_data_stack
    def load_active_channels(self):
        self.active_channels = []
        for i in range(CHANNEL_COUNT):
            if pool.config('active' + str(i + 1), bool):
                self.active_channels.append(i + 1)
        return pool.set('active_channels', self.active_channels)
        pass
    def _start(self):
        # Reset data stack
        self.create_stack()
        self.active_channels = self.load_active_channels()
        self.initialize_ui_panels()
        
        # Use a timer to ensure UI responsiveness for plot creation
        QTimer.singleShot(50, self.setup_plot)
        
        # Continue with other operations
        self.start_cycle_form.show()
        
    def setup_plot(self):
        # Clean up old plot if it exists
        if hasattr(self, 'plot') and self.plot:
            self.plot.cleanup()  # Add a cleanup method to your plot class
        
        self.plot = self.create_plot(
            plot_layout=self.plotAreaLayout, 
            legend_layout=self.formLayoutLegend
        )

    def _stop(self):
        """
        Stop the current cycle by delegating to the start cycle form,
        safely stopping timers and cleaning up the plot, update UI actions,
        and preview the plot.
        """
        try:
            # Stop any live update timers to prevent updates during cleanup.
            if hasattr(self, 'live_update_timer') and self.live_update_timer.isActive():
                self.live_update_timer.stop()
            if hasattr(self, 'connectionTimer') and self.connectionTimer.isActive():
                self.connectionTimer.stop()
            if hasattr(self, 'status_timer') and self.status_timer.isActive():
                self.status_timer.stop()
            
            # Attempt to stop cycle via start_cycle_form.
            if hasattr(self, 'start_cycle_form') and self.start_cycle_form is not None:
                logger.info("Using existing start_cycle_form to stop cycle")
                self.start_cycle_form.stop_cycle()
            else:
                logger.warning("No active start_cycle_form found; creating temporary form")
                from RaspPiReader.ui.start_cycle_form_handler import StartCycleFormHandler
                self.start_cycle_form = StartCycleFormHandler()
                self.start_cycle_form.cycle_data = {
                    "order_id": "unknown",
                    "start_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "stop_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                self.start_cycle_form.stop_cycle()

            # Clean up the plot widget if it exists to avoid later updates on deleted objects.
            if hasattr(self, 'plot') and self.plot:
                try:
                    self.plot.cleanup()
                except Exception as cleanup_error:
                    logger.error(f"Error during plot cleanup: {cleanup_error}")
                self.plot = None

            # Update UI actions (assume these actions exist in your MainFormHandler)
            if hasattr(self, 'actionStart'):
                self.actionStart.setEnabled(True)
            if hasattr(self, 'actionStop'):
                self.actionStop.setEnabled(False)
            if hasattr(self, 'actionPrint_results'):
                self.actionPrint_results.setEnabled(True)

            # Show plot preview if applicable.
            if hasattr(self, 'show_plot_preview'):
                self.show_plot_preview()

            # Close the CSV file after a short delay (if the method is defined)
            if hasattr(self, 'close_csv_file'):
                QTimer.singleShot(1000, self.close_csv_file)

            logger.info("Cycle stopping completed successfully")
        except Exception as e:
            logger.error(f"Error stopping cycle: {str(e)}")
            QtWidgets.QMessageBox.critical(
                self,
                "Error",
                f"Failed to stop cycle: {str(e)}"
            )

    def show_plot_preview(self):
        # Ensure headers is initialized
        if not hasattr(self, 'headers') or not self.headers:
            self.headers = ["Default Header 1", "Default Header 2"]
            # Initialize headers with defaults if not already set.
            self.headers = []
            self.headers.append(pool.config('h_label'))
            self.headers.append(pool.config('left_v_label'))
            self.headers.append(pool.config('right_v_label'))
            for i in range(1, CHANNEL_COUNT + 1):
                self.headers.append(pool.config('label' + str(i)))
        self.plot_preview_form = pool.set('plot_preview_form', PlotPreviewFormHandler())
        self.plot_preview_form.initiate_plot(self.headers)

    def _print_result(self):
        pass

    def _show_cycle_info(self, checked):
        self.cycle_infoGroupBox.setVisible(checked)

    def _show_plot(self, checked):
        self.mainPlotGroupBox.setVisible(checked)

    def _save(self):
        pass

    def _save_as(self):
        pass

    def _show_setting_form(self):
        self.setting_form = SettingFormHandler()

    def _exit(self):
        pass

    def create_plot(self, plot_layout=None, legend_layout=None):
        # Read header labels from the pool configuration.
        headers = []
        for i in range(1, CHANNEL_COUNT + 1):
            # Use pool.config with default value "CH{i}" if not set
            label = pool.config('label' + str(i), str, f'CH{i}')
            headers.append(label)
        
        # Clean out any old plot widget.
        if hasattr(self, 'plot') and self.plot:
            self.plot.cleanup()  # Let the plot widget free its resources
            # Remove the widget from its parent layout if needed.
            if plot_layout is None and hasattr(self, 'plot_layout'):
                plot_layout = self.plot_layout
            if plot_layout:
                # Remove all widgets from this layout.
                for index in reversed(range(plot_layout.count())):
                    widget = plot_layout.itemAt(index).widget()
                    if widget is not None:
                        widget.setParent(None)
            self.plot = None

        # Use the instance layout if none supplied.
        if plot_layout is None and hasattr(self, 'plot_layout'):
            plot_layout = self.plot_layout

        # Retrieve the active channels from the pool.
        active_channels = pool.get('active_channels')
        if active_channels is None:
            # If not set, fall back to all channels (1 to CHANNEL_COUNT).
            active_channels = list(range(1, CHANNEL_COUNT + 1))
        
        # Instantiate a new plot widget using the InitiatePlotWidget.
        self.plot = InitiatePlotWidget(
            active_channels=active_channels,
            parent_layout=plot_layout,
            legend_layout=legend_layout,
            headers=headers
        )
        return self.plot

    def update_plot(self):
        # Don't use instance variables for locking state, use a proper lock
        if not hasattr(self, '_plot_lock'):
            from threading import Lock
            self._plot_lock = Lock()
        
        # Use with statement for proper lock management
        if self._plot_lock.acquire(False):  # Non-blocking
            try:
                if hasattr(self, 'plot') and self.plot:
                    self.plot.update_plot()
            finally:
                self._plot_lock.release()
    def cleanup(self):
        """Clean up all resources used by the plot"""
        # Remove any timers
        if hasattr(self, 'update_timer') and self.update_timer:
            self.update_timer.stop()
            
        # Clear all plot items
        if hasattr(self, 'plot') and self.plot:
            self.plot.clear()
            
        # Any other cleanup needed
    def initialize_ui_panels(self):
        self.immediate_panel_update_locked = False
        active_channels = pool.get('active_channels')
        for i in range(CHANNEL_COUNT):

            getattr(self, 'chLabel' + str(i + 1)).setText(pool.config('label' + str(i + 1)))
            spin_widget = getattr(self, 'ch' + str(i + 1) + 'Value')
            if (i + 1) not in self.active_channels:
                spin_widget.setEnabled(False)
            else:
                spin_widget.setEnabled(True)
                decimal_value = pool.config('decimal_point' + str(i + 1), int, 2)
                spin_widget.setDecimals(decimal_value)
                spin_widget.setMinimum(-999999)
                spin_widget.setMaximum(+999999)

    def update_data(self):
        # Update CSV file
        self.update_csv_file()
        
        # Update UI elements in a way that maintains responsiveness
        def update_ui():
            self.update_immediate_values_panel()
            self.update_plot()
        
        # Use a short timer instead of processEvents()
        QTimer.singleShot(10, update_ui)

    def update_immediate_test_values_panel(self):
        for i in self.active_channels:
            spin_widget = getattr(self, 'ch' + str(i) + 'Value')
            if self.test_data_stack[i]:
                spin_widget.setValue(self.test_data_stack[i][-1])
            self.test_data_stack[i] = []

    def update_immediate_values_panel(self):
        if self.immediate_panel_update_locked:
            return
        self.immediate_panel_update_locked = True
        for i in range(CHANNEL_COUNT):
            spin_widget = getattr(self, 'ch' + str(i + 1) + 'Value')
            spin_widget.setValue(self.data_stack[i + 1][-1])
            self.o1.setText(str(self.start_cycle_form.core_temp_above_setpoint_time or 'N/A'))
            self.o2.setText(str(self.start_cycle_form.pressure_drop_core_temp or 'N/A'))
        self.immediate_panel_update_locked = False

    def cycle_timer_update(self):
        self.run_duration.setText(timedelta2str(datetime.now() - self.start_cycle_form.cycle_start_time))
        self.d6.setText(datetime.now().strftime("%H:%M:%S"))  # Cycle end time

    def update_cycle_info_pannel(self):
        self.d1.setText(pool.config("cycle_id"))
        self.d2.setText(pool.config("order_id"))
        self.d3.setText(str(pool.config("quantity")))
        # Use start_cycle_form’s cycle_start_time once it is set
        if self.start_cycle_form and hasattr(self.start_cycle_form, 'cycle_start_time'):
            self.d4.setText(self.start_cycle_form.cycle_start_time.strftime("%Y/%m/%d"))
            self.d5.setText(self.start_cycle_form.cycle_start_time.strftime("%H:%M:%S"))
        self.d7.setText(pool.config("cycle_location"))
        self.p1.setText(str(pool.config("maintain_vacuum")))
        self.p2.setText(str(pool.config("initial_set_cure_temp")))
        self.p3.setText(str(pool.config("temp_ramp")))
        self.p4.setText(str(pool.config("set_pressure")))
        self.p5.setText(pool.config("dwell_time"))
        self.p6.setText(str(pool.config("cool_down_temp")))
        self.cH1Label_36.setText(f"TIME (min) CORE TEMP ≥ {pool.config('core_temp_setpoint')} °C:")

    def update_live_data(self):
        try:
            # Update Vacuum Gauges (CH1 - CH8)
            gauge = getattr(self.form_obj, "vacuumGauge_CH1", None)
            if gauge is not None:
                gauge.setText(f"{pool.config('vacuum_CH1', float, 0.0):.1f} KPa")
            for chan in range(2, 9):
                widget = getattr(self.form_obj, f"vacuumGauge_CH{chan}", None)
                if widget is not None:
                    widget.setText(f"{pool.config(f'vacuum_CH{chan}', float, 0.0):.1f} KPa")
            
            # Update Temperature Channels (CH9 - CH12)
            for ch in range(9, 13):
                widget = getattr(self.form_obj, f"temp_CH{ch}", None)
                if widget is not None:
                    widget.setText(f"{pool.config(f'temp_CH{ch}', float, 0.0):.1f} °C")
            
            # Update Cylinder Pressure and System Vacuum
            if hasattr(self.form_obj, "pressure_CH13"):
                self.form_obj.pressure_CH13.setText(f"{pool.config('pressure_CH13', float, 0.0):.1f} KPa")
            if hasattr(self.form_obj, "vacuum_CH14"):
                self.form_obj.vacuum_CH14.setText(f"{pool.config('vacuum_CH14', float, 0.0):.1f} KPa")
            
            # Update Cycle Set Parameters (from default program)
            if hasattr(self.form_obj, "maintainVacuumLabel"):
                self.form_obj.maintainVacuumLabel.setText(str(pool.config("maintain_vacuum", bool, False)))
            if hasattr(self.form_obj, "setCureTempLabel"):
                self.form_obj.setCureTempLabel.setText(str(pool.config("initial_set_cure_temp", float, 0.0)))
            if hasattr(self.form_obj, "tempRampLabel"):
                self.form_obj.tempRampLabel.setText(str(pool.config("temp_ramp", float, 0.0)))
            if hasattr(self.form_obj, "setPressureLabel"):
                self.form_obj.setPressureLabel.setText(str(pool.config("set_pressure", float, 0.0)))
            if hasattr(self.form_obj, "dwellTimeLabel"):
                self.form_obj.dwellTimeLabel.setText(pool.config("dwell_time", str, "N/A"))
            if hasattr(self.form_obj, "coolDownTempLabel"):
                self.form_obj.coolDownTempLabel.setText(str(pool.config("cool_down_temp", float, 0.0)))
            
            # Update Cycle Details (from ongoing cycle and work order form):
            if self.start_cycle_form and hasattr(self.start_cycle_form, "cycle_start_time"):
                if hasattr(self.form_obj, "cycleDateLabel"):
                    self.form_obj.cycleDateLabel.setText(self.start_cycle_form.cycle_start_time.strftime("%Y-%m-%d"))
                if hasattr(self.form_obj, "cycleStartTimeLabel"):
                    self.form_obj.cycleStartTimeLabel.setText(self.start_cycle_form.cycle_start_time.strftime("%H:%M:%S"))
            if hasattr(self.form_obj, "cycleEndTimeLabel"):
                self.form_obj.cycleEndTimeLabel.setText(datetime.now().strftime("%H:%M:%S"))
            if hasattr(self.form_obj, "cycleNumberLabel"):
                self.form_obj.cycleNumberLabel.setText(str(pool.config("cycle_id", int, 0)))
            # Update work order and quantity values from the work order form
            if hasattr(self.form_obj, "workOrderLabel"):
                self.form_obj.workOrderLabel.setText(str(pool.config("order_id", str, "")))
            if hasattr(self.form_obj, "quantityLabel"):
                self.form_obj.quantityLabel.setText(str(pool.config("quantity", int, 0)))
        except Exception as e:
            logger.error("Error in update_live_data: " + str(e))
    def create_csv_file(self):
        self.csv_update_locked = False
        self.last_written_index = 0
        file_extension = '.csv'
        csv_full_path = os.path.join(self.start_cycle_form.folder_path,
                                    self.start_cycle_form.file_name + file_extension)
        self.csv_path = csv_full_path
        delimiter = pool.config('csv_delimiter') or ' '
        csv.register_dialect('unixpwd', delimiter=delimiter)
        self.open_csv_file(mode='w')
        self.write_cycle_info_to_csv()

    def open_csv_file(self, mode='a'):
        self.csv_file = open(self.csv_path, mode, newline='')
        self.csv_writer = csv.writer(self.csv_file)

    def close_csv_file(self):
        self.csv_file.close()

    def write_cycle_info_to_csv(self):
    # Write the first block of cycle information.
        data = [
            ["Work Order", pool.config("order_id")],
            ["Cycle Number", pool.config("cycle_id")],
            ["Quantity", pool.config("quantity")],
            ["Process Start Time", self.start_cycle_form.cycle_start_time.strftime("%Y-%m-%d %H:%M:%S")]
        ]
        self.csv_writer.writerows(data)
        
        # Ensure self.headers is defined. If not, define a default header list.
        if not hasattr(self, 'headers') or not self.headers:
            self.headers = ['Date', 'Time', 'Timer(min)', 'CycleID', 'OrderID', 'Quantity', 'CycleLocation']
        
        # Write the header row for the detailed CSV data.
        self.csv_writer.writerows([['Date', 'Time', 'Timer(min)'] + self.headers[3:]])
    def update_csv_file(self, csv_file_path=None):
        if csv_file_path is None:
            # Use reports folder for all CSV files
            reports_dir = os.path.join(os.getcwd(), "reports")
            if not os.path.exists(reports_dir):
                os.makedirs(reports_dir)
            csv_file_path = pool.config('csv_file_path', str, os.path.join(reports_dir, "cycle_report.csv"))
        if self.csv_update_locked:
            return
        self.csv_update_locked = True

        n_data = len(self.data_stack[0])
        temp_data = []
        for i in range(self.last_written_index, n_data):
            temp_rec = []
            temp_rec.append(self.data_stack[15][i].strftime("%Y/%m/%d"))
            temp_rec.append(self.data_stack[15][i].strftime("%H:%M:%S"))
            temp_rec.append(self.data_stack[0][i])
            for j in range(CHANNEL_COUNT):
                temp_rec.append(self.data_stack[j + 1][i])
            temp_data.append(temp_rec)
        
        try:
            with open(csv_file_path, 'w', newline='') as csv_file:
                import csv
                csv_writer = csv.writer(csv_file)
                csv_writer.writerows(temp_data)
        except Exception as e:
            self.csv_update_locked = False
            raise e

        self.last_written_index = n_data
        self.csv_update_locked = False
        return csv_file_path
    def finalize_cycle_report(self, reports_folder, template_file):
        """
        Finalize the cycle by generating both a CSV and PDF report.
        The CSV is generated by writing new data to a fresh file.
        The PDF is generated from an HTML template using pdfkit.
        Returns a tuple: (pdf_report_path, csv_file_path)
        """
        # Ensure the reports folder exists.
        if not os.path.exists(reports_folder):
            os.makedirs(reports_folder)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_file_path = os.path.join(reports_folder, f"cycle_report_{timestamp}.csv")
        pdf_report_path = os.path.join(reports_folder, f"cycle_report_{timestamp}.pdf")

        # Update the CSV report by writing the new data.
        try:
            self.update_csv_file(csv_file_path)
        except Exception as e:
            raise Exception(f"Error writing CSV report: {e}")

        # Build full path to the HTML template (assumed to reside relative to this file)
        html_template_path = os.path.join(os.path.dirname(__file__), template_file)
        try:
            pdfkit.from_file(html_template_path, pdf_report_path)
        except Exception as e:
            raise Exception(f"Error generating PDF report: {e}")

        return pdf_report_path, csv_file_path

    def show_error_and_stop(self, msg, parent=None):
        error_dialog = QErrorMessage(parent or self)
        error_dialog.showMessage(msg)
        self.start_cycle_form.stop_cycle()
        self.actionStart.setEnabled(True)
        self.actionStop.setEnabled(False)
        self.csv_file.close()

    def generate_html_report(self, image_path=None):
        report_data = {
            "order_id": pool.config("order_id") or "-",
            "cycle_id": pool.config("cycle_id") or "-",
            "quantity": pool.config("quantity") or "-",
            "cycle_location": pool.config("cycle_location") or "-",
            "dwell_time": int(pool.config("dwell_time")) or "-",
            "cool_down_temp": pool.config("cool_down_temp") or "-",
            "core_temp_setpoint": pool.config("core_temp_setpoint") or "-",
            "temp_ramp": pool.config("temp_ramp") or "-",
            "set_pressure": pool.config("set_pressure") or "-",
            "maintain_vacuum": pool.config("maintain_vacuum") or "-",
            "initial_set_cure_temp": pool.config("initial_set_cure_temp") or "-",
            "final_set_cure_temp": pool.config("final_set_cure_temp") or "-",
            "core_high_temp_time": round(self.start_cycle_form.core_temp_above_setpoint_time, 2) or "-",
            "release_temp": self.start_cycle_form.pressure_drop_core_temp or "-",
            "cycle_date": self.start_cycle_form.cycle_start_time.strftime("%Y/%m/%d") or "-",
            "cycle_start_time": self.start_cycle_form.cycle_start_time.strftime("%H:%M:%S") or "-",
            "cycle_end_time": self.start_cycle_form.cycle_end_time.strftime("%H:%M:%S") or "-",
            "image_path": image_path,
            "logo_path": os.path.join(os.getcwd(), 'ui\\logo.jpg'),
        }

        self.render_print_template(template_file='result_template.html',
                                   data=report_data,
                                   )

    def render_print_template(self, *args, template_file=None, **kwargs):
        templateLoader = jinja2.FileSystemLoader(searchpath=os.path.join(os.getcwd(), "ui"))
        templateEnv = jinja2.Environment(loader=templateLoader, extensions=['jinja2.ext.loopcontrols'])
        template = templateEnv.get_template(template_file)
        html = template.render(**kwargs)
        with tempfile.NamedTemporaryFile('w', delete=False, suffix='.html') as f:
            fname = f.name
            f.write(html)
        file_extension = '.pdf'
        pdf_full_path = os.path.join(self.start_cycle_form.folder_path,
                                     self.start_cycle_form.file_name + file_extension)
        self.html2pdf(fname, pdf_full_path)

    def html2pdf(self, html_path, pdf_path):
        self.pdf_path = pdf_path
        options = {
            'page-size': 'A4',
            'dpi': 2000,
            'margin-top': '0.35in',
            'margin-right': '0.75in',
            'margin-bottom': '0.75in',
            'margin-left': '0.75in',
            'encoding': "UTF-8",
            'no-outline': None,
            'enable-local-file-access': None
        }
        path_wkhtmltopdf = os.path.join(os.getcwd(), 'wkhtmltopdf.exe')
        config = pdfkit.configuration(wkhtmltopdf=path_wkhtmltopdf)
        with open(html_path) as f:
            pdfkit.from_file(f, pdf_path, options=options, configuration=config)
        webbrowser.open('file://' + pdf_path)

    def open_pdf(self):
        webbrowser.open('file://' + self.pdf_path)

    def test_onedrive_connection(self):
        msg = QMessageBox()
        try:
            onedrive_api = OneDriveAPI()
            onedrive_api.authenticate(
                pool.config('onedrive_client_id'),
                pool.config('onedrive_client_secret'),
                pool.config('onedrive_tenant_id')
            )
            if onedrive_api.check_connection():
                msg.setIcon(QMessageBox.Information)
                msg.setText("OneDrive connection OK.")
                msg.setStandardButtons(QMessageBox.Ok)
                msg.exec_()
                self.update_status_bar_signal.emit('OneDrive connection OK.', 15000, 'green')
            else:
                raise Exception("Connection failed")
        except Exception as e:
            msg.setIcon(QMessageBox.Critical)
            msg.setText("Connection failed.\n" + str(e))
            msg.setStandardButtons(QMessageBox.Ok)
            msg.exec_()
            self.update_status_bar_signal.emit('OneDrive connection failed.', 0, 'red')

    def _sync_onedrive(self, *args, upload_csv=True, upload_pdf=True, show_message=True, delete_existing=True):
        try:
            # Check if settings are configured
            client_id = pool.config("onedrive_client_id")
            client_secret = pool.config("onedrive_client_secret")
            tenant_id = pool.config("onedrive_tenant_id")
            
            if not all([client_id, client_secret, tenant_id]):
                if show_message:
                    QMessageBox.warning(self, "OneDrive Not Configured", 
                                    "Please configure OneDrive settings first.")
                return False
                
            # Create OneDrive API instance
            onedrive_api = OneDriveAPI()
            onedrive_api.authenticate(client_id, client_secret, tenant_id)
            
            # Create folder for reports
            folder_name = f"PLC_Reports_{datetime.now().strftime('%Y-%m-%d')}"
            try:
                folder_response = onedrive_api.create_folder(folder_name)
                folder_id = folder_response.get('id')
                # Use logger instead of print for consistent logging
                logger.info(f"Created OneDrive folder: {folder_name}")
            except Exception as e:
                logger.warning(f"Could not create OneDrive folder: {e}")
                folder_id = None
                
            # Upload CSV file if requested
            if upload_csv:
                csv_file_path = self.csv_path
                if csv_file_path and os.path.exists(csv_file_path):  # Added null check
                    file_resp = onedrive_api.upload_file(csv_file_path, folder_id)
                    logger.info(f"CSV uploaded to OneDrive: {os.path.basename(csv_file_path)}")
                    self.update_status_bar_signal.emit(f"CSV uploaded to OneDrive", 10000, 'green')
            
            # Upload PDF file if requested
            if upload_pdf:
                pdf_file_path = self.pdf_path
                if pdf_file_path and os.path.exists(pdf_file_path):  # Added null check
                    file_resp = onedrive_api.upload_file(pdf_file_path, folder_id)
                    logger.info(f"PDF uploaded to OneDrive: {os.path.basename(pdf_file_path)}")
                    self.update_status_bar_signal.emit(f"PDF uploaded to OneDrive", 10000, 'green')
            
            if show_message:
                QMessageBox.information(self, "Success", "Files uploaded to OneDrive successfully")
            return True
            
        except Exception as e:
            logger.error(f"OneDrive upload failed: {e}")
            if show_message:
                QMessageBox.critical(self, "Error", f"OneDrive upload failed: {str(e)}")
            else:
                self.update_status_bar_signal.emit(f"OneDrive upload failed: {str(e)}", 5000, 'red')
            return False

    def closeEvent(self, event):
        if hasattr(self, 'start_cycle_form') \
                and hasattr(self.start_cycle_form, 'running') \
                and self.start_cycle_form.running:
            quit_msg = "Are you Sure?\nCSV data may be not be saved."
        else:
            quit_msg = "Are you sure?"
        reply = QMessageBox.question(self, 'Exiting app ...',
                                     quit_msg, (QMessageBox.Yes | QMessageBox.Cancel))
        if reply == QMessageBox.Yes:
            event.accept()
        elif reply == QMessageBox.Cancel:
            event.ignore()

    def update_status_bar(self, msg, ms_timeout, color):
        self.statusbar.showMessage(msg, ms_timeout)
        self.statusbar.setStyleSheet("color: {}".format(color.lower()))
        self.statusBar().setFont(QFont('Times', 12))
    
    