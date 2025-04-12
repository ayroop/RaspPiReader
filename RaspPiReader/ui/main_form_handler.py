import os
import csv
import pdfkit
from datetime import datetime
import logging
from colorama import Fore
import webbrowser
import tempfile
import jinja2
from PyQt5 import QtWidgets, uic, QtCore
from PyQt5.QtCore import QTimer, pyqtSignal, QSettings
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QMainWindow, QErrorMessage, QMessageBox, QApplication, QLabel, QAction, QSizePolicy
from RaspPiReader import pool
from .mainForm import MainForm
from RaspPiReader.ui.mainForm import MainForm
from .setting_form_handler import SettingFormHandler, CHANNEL_COUNT
from .user_management_form_handler import UserManagementFormHandler
from RaspPiReader.ui.one_drive_settings_form_handler import OneDriveSettingsFormHandler
from RaspPiReader.libs.onedrive_api import OneDriveAPI
from .plc_comm_settings_form_handler import PLCCommSettingsFormHandler
from RaspPiReader.ui.database_settings_form_handler import DatabaseSettingsFormHandler
from PyQt5 import sip
import pyqtgraph as pg

# New imports for new cycle workflow
from RaspPiReader.libs.communication import dataReader
from RaspPiReader.libs.configuration import config

from RaspPiReader.libs.database import Database
from RaspPiReader.ui.new_cycle_handler import NewCycleHandler
from RaspPiReader.ui.default_program_form import DefaultProgramForm
from RaspPiReader.ui.work_order_form_handler import WorkOrderFormHandler  # For work order flow

# Add default program settings
from RaspPiReader.ui.default_program_form import DefaultProgramForm
# New Cycle logic
from RaspPiReader.ui.work_order_form_handler import WorkOrderFormHandler
# Add Alarm settings
from RaspPiReader.ui.alarm_settings_form_handler import AlarmSettingsFormHandler
from RaspPiReader.libs.models import Alarm
# Add PLC connection status
from RaspPiReader.libs import plc_communication
from RaspPiReader.libs.cycle_finalization import finalize_cycle
from RaspPiReader.libs.plc_communication import read_holding_register
from RaspPiReader.libs.visualization_manager import VisualizationManager
from .boolean_data_display_handler import BooleanDataDisplayHandler
from PyQt5.QtWidgets import QVBoxLayout, QGroupBox
from RaspPiReader.libs.models import CycleSerialNumber

logger = logging.getLogger(__name__)


def timedelta2str(td):
    total_seconds = int(td.total_seconds())
    h, rem = divmod(total_seconds, 3600)
    m, s = divmod(rem, 60)

    def zp(val):
        return str(val).zfill(2)

    return f"{zp(h)}:{zp(m)}:{zp(s)}"


class MainFormHandler(QtWidgets.QMainWindow):
    update_status_bar_signal = pyqtSignal(str, int, str)

    def __init__(self, user_record=None):
        super(MainFormHandler, self).__init__()
        self.user_record = user_record

        # Build an absolute path to the UI file in the 'qt' folder.
        ui_path = os.path.join(os.path.dirname(__file__), "..", "qt", "main.ui")
        ui_path = os.path.abspath(ui_path)
        # Load the UI from the .ui file
        uic.loadUi(ui_path, self)

        # Setup UI via the MainForm class.
        self.form_obj = MainForm()
        self.form_obj.setupUi(self)
        self.immediate_panel_update_locked = False

        # Immediately assign cycle timer labels via findChild.
        self.run_duration = self.findChild(QtWidgets.QLabel, "run_duration")
        self.d6 = self.findChild(QtWidgets.QLabel, "d6")
        if self.run_duration is None or self.d6 is None:
            logger.warning("Cycle timer labels (run_duration and d6) not found on main window.")
        else:
            logger.info("Cycle timer labels successfully identified.")

        # Initialize the alarm label to None.
        self.labelAlarm = None

        # New code – initialize new cycle widget.

        self.new_cycle_handler = NewCycleHandler(self)
        self.new_cycle_handler.show()
        logger.info("Initialized NewCycleHandler for new cycle workflow")

        # Set main_form in the pool.
        pool.set("main_form", self)

        # Define headers used for CSV file creation.
        self.headers = ['Date', 'Time', 'Timer(min)', 'CycleID', 'OrderID', 'Quantity', 'CycleLocation']
        self.file_name = None
        self.folder_name = None
        self.csv_path = None
        self.pdf_path = None
        self.username = self.user_record.username if self.user_record else ''

        self.cycle_timer = QTimer()

        # Initialize the data stacks (data_stack and test_data_stack)
        self.create_stack()

        # Initialize connections, user display, and (optional) stacks.
        self.set_connections()
        self.display_username()

        # Setup additional menus.
        self.setup_access_controls()
        self.connect_menu_actions()
        self.add_one_drive_menu()
        self.add_plc_comm_menu()
        self.add_database_menu()

        self.db = Database("sqlite:///local_database.db")
        self.integrate_new_cycle_widget()

        # Start timers.
        self.status_timer = QTimer(self)
        self.status_timer.start(5000)
        self.add_default_program_menu()
        self.add_alarm_settings_menu()
        self.connectionTimer = QTimer(self)
        self.connectionTimer.timeout.connect(self.update_connection_status_display)
        self.connectionTimer.start(5000)
        self.live_update_timer = QTimer(self)
        self.live_update_timer.timeout.connect(self.update_live_data)
        
        # Start the alarm timer to update the alarm status.
        self.alarmTimer = QTimer(self)
        self.alarmTimer.timeout.connect(self.update_alarm_status)
        self.alarmTimer.start(1000)

        # UI visualization
        self.init_visualization()
    
        # Create Boolean Data Display widget but don't start reading data yet
        self.boolean_data_display = BooleanDataDisplayHandler(self)
        self.integrate_boolean_data_display()
        
        # Flag to track if boolean reading is active
        self.boolean_reading_active = False
        
        # Initialize the direct boolean reader but don't start it yet
        from RaspPiReader.libs.direct_boolean_reader import get_instance
        self.boolean_reader = get_instance()
        
        # Connect to the new_cycle_handler's signals to start/stop boolean reading
        if hasattr(self.new_cycle_handler, "cycle_started_signal"):
            self.new_cycle_handler.cycle_started_signal.connect(self.start_boolean_reading)
        if hasattr(self.new_cycle_handler, "cycle_stopped_signal"):
            self.new_cycle_handler.cycle_stopped_signal.connect(self.stop_boolean_reading)
        # Connect to the green Start Cycle button in the program selection step
        if hasattr(self.new_cycle_handler, "start_cycle_signal"):
            self.new_cycle_handler.start_cycle_signal.connect(self.start_boolean_reading)

        logger.info("Live update timer started.")
        self.showMaximized()
        logger.info("MainFormHandler initialized.")

        
    def start_boolean_reading(self):
        """
        Start reading boolean addresses when the green Start Cycle button is clicked
        in the default program selection step.
        """
        if not self.boolean_reading_active:
            logger.info("Starting boolean address reading")
            self.boolean_reading_active = True
            
            # Start the direct boolean reader
            if hasattr(self, 'boolean_reader'):
                self.boolean_reader.start_reading()
            
            # Enable boolean data display updates
            if hasattr(self.boolean_data_display, "start_reading"):
                self.boolean_data_display.start_reading()
            else:
                # If no dedicated method exists, start the timer directly
                if hasattr(self.boolean_data_display, "update_timer"):
                    self.boolean_data_display.update_timer.start(1000)  # Update every second
            
            # Update group box title if it exists
            if hasattr(self, 'boolean_group_box'):
                self.boolean_group_box.setTitle("Boolean Data (Reading Active)")
                
            # Show visual indication that boolean reading is active
            self.update_status_bar("Boolean address reading active", 5000, "green")
    
    def stop_boolean_reading(self):
        """
        Stop reading boolean addresses when the cycle ends.
        This method is called when the user clicks Stop Cycle or when the cycle finishes.
        """
        if self.boolean_reading_active:
            logger.info("Stopping boolean address reading")
            self.boolean_reading_active = False
            
            # Stop the direct boolean reader
            if hasattr(self, 'boolean_reader'):
                self.boolean_reader.stop_reading()
            
            # Disable boolean data display updates
            if hasattr(self.boolean_data_display, "stop_reading"):
                self.boolean_data_display.stop_reading()
            else:
                # If no dedicated method exists, stop the timer directly
                if hasattr(self.boolean_data_display, "update_timer"):
                    self.boolean_data_display.update_timer.stop()
            
            # Update group box title if it exists
            if hasattr(self, 'boolean_group_box'):
                self.boolean_group_box.setTitle("Boolean Data (Waiting for Cycle Start)")
                
            # Show visual indication that boolean reading is stopped
            self.update_status_bar("Boolean address reading stopped", 5000, "blue")
        
    # Method to integrate the BooleanDataDisplayHandler into the main UI.
    def integrate_boolean_data_display(self):
        """
        Integrate the BooleanDataDisplayHandler widget into the main form.
        First, attempt to locate a placeholder widget with objectName "booleanWidgetPlaceholder".
        If found, add the Boolean widget to its layout. Otherwise, create a new group box
        and add it to the central widget's layout.
        """
        # Try to find a placeholder widget by name.
        placeholder = self.findChild(QtWidgets.QWidget, "booleanWidgetPlaceholder")
        if placeholder is not None:
            layout = placeholder.layout()
            if layout is None:
                layout = QVBoxLayout(placeholder)
                placeholder.setLayout(layout)
            layout.addWidget(self.boolean_data_display)
            logger.info("BooleanDataDisplayHandler added to existing placeholder 'booleanWidgetPlaceholder'.")
        else:
            # If no placeholder found, create a new group box to contain the Boolean data display.
            group_box = QGroupBox("Boolean Data (Waiting for Cycle Start)", self)
            group_layout = QVBoxLayout(group_box)
            group_layout.addWidget(self.boolean_data_display)
            # Add the group box to the central widget's layout.
            central_widget = self.centralWidget()
            central_layout = central_widget.layout()
            if central_layout is None:
                central_layout = QVBoxLayout(central_widget)
                central_widget.setLayout(central_layout)
            central_layout.addWidget(group_box)
            self.boolean_group_box = group_box
            logger.info("BooleanDataDisplayHandler added to a new group box in central widget.")
    
    def update_boolean_display(self, boolean_values):
        """
        Update the boolean display with new values.
        This is called by the direct_boolean_reader when new data is available.
        """
        if hasattr(self.boolean_data_display, "update_values"):
            self.boolean_data_display.update_values(boolean_values)

    def init_visualization(self):
        """Initialize visualization components"""
        # Get visualization manager instance
        self.viz_manager = VisualizationManager.instance()
        
        # Set up the dashboard with this form as parent
        self.viz_manager.setup_dashboard(self)
        
        # Add visualization menu
        self.add_visualization_menu()
        logger.info("Visualization initialized in MainFormHandler")

    def add_visualization_menu(self):
        """Add visualization menu to the main form"""
        # Create visualization menu
        viz_menu = self.menuBar().addMenu("Visualization")
        
        # Add show/hide action
        toggle_action = QtWidgets.QAction("Show/Hide Dashboard", self)
        toggle_action.triggered.connect(self.toggle_visualization)
        viz_menu.addAction(toggle_action)
        
        # Add reset action
        reset_action = QtWidgets.QAction("Reset Visualization", self)
        reset_action.triggered.connect(self.reset_visualization)
        viz_menu.addAction(reset_action)
        
        logger.info("Visualization menu added")

    def toggle_visualization(self):
        """Toggle visualization dashboard visibility"""
        self.viz_manager.toggle_dashboard_visibility()

    def reset_visualization(self):
        """Reset visualization dashboard"""
        self.viz_manager.reset_visualization()

    def start_live_data(self):
        """Start reading live data every 2 seconds."""
        if not self.live_update_timer.isActive():
            self.live_update_timer.start(2000)
            logger.info("Live data update timer started.")

    def stop_live_data(self):
        """Stop reading live data."""
        if self.live_update_timer.isActive():
            self.live_update_timer.stop()
            logger.info("Live data update timer stopped.")
            
    def update_data(self, new_data):
        """
        Update UI elements based on the new_data dictionary and live PLC channel readings.
        
        Expected keys in new_data:
        - temperature, pressure
        - vacuum: dict with keys 'CH1'..'CH8' (vacuum gauge values in KPa)
        - cycle_info: dict with keys such as 'maintain_vacuum', 'set_cure_temp', etc.

        Additionally, live channel values from the PLC (using read_holding_register)
        are read and can be used to update dedicated UI labels.
        """
        
        logger.info(f"MainForm received update: {new_data}")
        try:
            # Update Temperature and Pressure from simulation data
            temperature = new_data.get('temperature', 'N/A')
            pressure = new_data.get('pressure', 'N/A')
            self.form_obj.temperatureLabel.setText(f"Temperature: {temperature} °C")
            self.form_obj.pressureLabel.setText(f"Pressure: {pressure} KPa")
            
            # Read PLC channel values (e.g., CH1 to CH8) using holding registers
            channel_values = {}
            for ch in range(1, CHANNEL_COUNT + 1):
                addr_key = f'channel_{ch}_address'
                channel_addr = pool.config(addr_key, int, 0)
                # Read the value from the PLC register; if error, default to zero
                channel_value = read_holding_register(channel_addr, 1)
                channel_values[f"CH{ch}"] = channel_value if channel_value is not None else 0
                # Optionally update dedicated UI labels for each channel; for example:
                # getattr(self.form_obj, f"channel{ch}Label").setText(str(channel_values[f'CH{ch}']))
            
            # Update Vacuum Gauge channels from simulation data
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
            
            # Update Cycle Info fields from simulation data
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
            
        except Exception as e:
            logger.error(f"Error updating main form data: {e}")

    def update_plc_settings(self):
        """
        Reload channel configuration and update live UI views.
        This re-reads addresses, labels and any other dynamic settings.
        """
        # Reload settings from QSettings / database
        pool.reload_config()

        # Retrieve updated Boolean config and update boolean widgets if they exist.
        self.boolean_config = pool.config('boolean_config', dict, {})
        if hasattr(self, 'boolean_channel_widgets'):
            for channel, widget in self.boolean_channel_widgets.items():
                new_value = self.boolean_config.get(channel)
                if new_value is not None:
                    widget.setTitle(f"{channel} (Addr {new_value})")
                    logging.getLogger(__name__).info(
                        f"Updated Boolean widget '{channel}' to address {new_value}"
                    )
                else:
                    logging.getLogger(__name__).debug(
                        f"No new address found for Boolean channel '{channel}'"
                    )
        else:
            logging.getLogger(__name__).warning(
                "Attribute 'boolean_channel_widgets' not found in MainFormHandler."
            )

        # Update numeric channels as before
        self._reload_channel_configurations()

        # Refresh connection status display
        self.update_connection_status_display()

        # Force a refresh of the live plot visualization.
        if hasattr(self, 'viz_manager') and self.viz_manager.dashboard is not None:
            # Option 1: Reset data buffers and update plots
            self.viz_manager.dashboard.visualization.reset_data()
            self.viz_manager.dashboard.update_plots()
            # Option 2: Alternatively, if a dedicated refresh method exists:
            # self.viz_manager.dashboard.refresh_configuration()


    def _reload_channel_configurations(self):
        """
        Internal helper method to reinitialize channels.
        Update Numeric channels (if applicable).
        (Boolean channels are handled in update_plc_settings above.)
        """
        # Update Numeric channels (if applicable)
        numeric_config = pool.config('numeric_config', dict, {})
        if hasattr(self, 'numeric_channel_widgets'):
            for channel, widget in self.numeric_channel_widgets.items():
                new_label = numeric_config.get(channel)
                if new_label is not None:
                    widget.setTitle(f"{channel} (Label: {new_label})")
                    logging.getLogger(__name__).info(
                        f"Updated Numeric widget '{channel}' with label '{new_label}'"
                    )
                else:
                    logging.getLogger(__name__).debug(
                        f"No new configuration for Numeric channel '{channel}'"
                    )
        else:
            logging.getLogger(__name__).info(
                "No numeric_channel_widgets attribute defined; skipping numeric channel update."
            )

    def refresh_configuration(self):
        """
        Refresh channel configuration for the live plots.
        Re-read configuration (addresses, labels, colors, etc.) and update the plots.
        """
        # Reload configuration if needed
        pool.reload_config()

        # Update plots titles and properties based on new settings.
        for idx, config in self.boolean_config.items():
            if idx in self.plots:
                plot_widget = self.plots[idx]
                new_title = f"{config['label']} (Addr {config['address']})"
                plot_widget.setTitle(new_title)
        # Force a replot if needed.
        self.update_plots()

    def _calculate_cycle_duration(self):
        if hasattr(self.new_cycle_handler, "cycle_start_time"):
            duration = datetime.now() - self.new_cycle_handler.cycle_start_time
            return str(duration).split('.')[0]
        return "N/A"


    def start_cycle_timer(self, cycle_start):
        self.cycle_start = cycle_start
        self.cycle_timer = QTimer(self)
        self.cycle_timer.timeout.connect(self.update_cycle_timer)
        self.cycle_timer.start(1000)

    def safe_set_label_text(self, label, text):
        """Safely update a label's text, checking if it exists first"""
        if label is not None and not sip.isdeleted(label):
            try:
                label.setText(text)
            except RuntimeError:
                # Label was deleted, get a new reference
                if label == self.d6:
                    self.d6 = self.findChild(QtWidgets.QLabel, "d6")
                    if self.d6:
                        self.d6.setText(text)
                elif label == self.run_duration:
                    self.run_duration = self.findChild(QtWidgets.QLabel, "run_duration")
                    if self.run_duration:
                        self.run_duration.setText(text)

    def update_cycle_timer(self):
        start_time = self.new_cycle_handler.cycle_start_time
        if start_time is not None:
            if self.new_cycle_handler.cycle_end_time is not None:
                elapsed = self.new_cycle_handler.cycle_end_time - start_time
                end_time_str = self.new_cycle_handler.cycle_end_time.strftime("%H:%M:%S")
            else:
                elapsed = datetime.now() - start_time
                end_time_str = "N/A"
            self.safe_set_label_text(self.run_duration, str(elapsed).split('.')[0])
            self.safe_set_label_text(self.d6, end_time_str)
        else:
            self.safe_set_label_text(self.run_duration, "0:00:00")
            self.safe_set_label_text(self.d6, "N/A")
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
    def integrate_new_cycle_widget(self):
        """
        Integrate the new cycle widget and Boolean status widget into the main window layout.
        After adding the new cycle widget, hide its Start/Stop buttons.
        """
        central_widget = self.centralWidget()
        central_layout = central_widget.layout()
        if central_layout is None:
            central_layout = QtWidgets.QVBoxLayout(central_widget)
            central_widget.setLayout(central_layout)

        # Ensure new cycle widget is re-parented to the central widget.
        if self.new_cycle_handler.parent() is not central_widget:
            self.new_cycle_handler.setParent(central_widget)
            
        # Hide the new cycle widget buttons
        if hasattr(self.new_cycle_handler, "ui"):
            self.new_cycle_handler.ui.startCycleButton.hide()
            self.new_cycle_handler.ui.stopCycleButton.hide()
            
        self.new_cycle_handler.hide()  # Initially hide before integration if needed.

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
        
    def update_alarm_status(self):
        """
        Read the alarm register values using read_holding_register and map numeric codes
        to alarm text using the AlarmMapping model.
        
        This method checks both:
        1. Configured alarm addresses from pool.config
        2. Channel-based alarms from the database
        
        For each alarm, if its value is nonzero, the corresponding text is displayed.
        """
        active_alarms = []
        
        # PART 1: Check address-based alarms from configuration
        alarm_addresses = pool.config("alarm_addresses", list, [300])
        for addr in alarm_addresses:
            # Read the alarm value from the designated holding register
            alarm_value = plc_communication.read_holding_register(addr, 1)
            if alarm_value is None or alarm_value == 0:
                continue
                
            try:
                code = int(alarm_value)
            except (ValueError, TypeError):
                continue
                
            # Retrieve the mapping for this alarm address from configuration
            mapping = pool.config("alarm_mapping", dict, {}).get(str(addr), "")
            if mapping:
                mapping_lines = mapping.splitlines()
                # Use the code as index to grab the corresponding alarm text
                if 0 < code <= len(mapping_lines):
                    alarm_text = mapping_lines[code-1]  # Adjust index (code 1 = first line)
                else:
                    alarm_text = f"Unknown alarm code {code}"
                active_alarms.append(f"Address {addr}: {alarm_text}")
        
        # PART 2: Check channel-based alarms from database
        try:
            # Get channel to address mapping from configuration
            alarm_channels = {
                "CH1": pool.config('alarm/CH1_address', int, 0),
                "CH2": pool.config('alarm/CH2_address', int, 0),
                "CH3": pool.config('alarm/CH3_address', int, 0),
                "CH4": pool.config('alarm/CH4_address', int, 0),
                # Add more channels as needed
            }
            
            # Filter out channels with no configured address
            alarm_channels = {ch: addr for ch, addr in alarm_channels.items() if addr > 0}
            
            # Check each channel
            for channel, address in alarm_channels.items():
                value = plc_communication.read_holding_register(address, 1)
                if value is not None and value != 0:
                    # Query the Alarm record by channel
                    db = Database("sqlite:///local_database.db")
                    alarm_obj = db.session.query(Alarm).filter_by(channel=channel).first()
                    
                    if alarm_obj:
                        # Check if there are specific mappings for this value
                        if hasattr(alarm_obj, 'mappings') and alarm_obj.mappings:
                            # Find mapping with matching value
                            mapping = next((m for m in alarm_obj.mappings if m.value == value), None)
                            if mapping:
                                display_message = mapping.message
                            else:
                                display_message = f"{alarm_obj.alarm_text} (Code: {value})"
                        else:
                            # Use default alarm text if no mappings exist
                            display_message = alarm_obj.alarm_text
                            
                        active_alarms.append(f"{channel}: {display_message}")
                    else:
                        # No alarm configuration found, use generic message
                        active_alarms.append(f"{channel}: Unknown alarm (Code: {value})")
        except Exception as e:
            logger.error(f"Error checking channel alarms: {e}")
            active_alarms.append(f"Error checking channel alarms: {str(e)}")

        # Create or update the alarm label
        if self.labelAlarm is None:
            self.labelAlarm = QLabel(self)
            self.labelAlarm.setFont(QFont("Segoe UI", 10))
            self.labelAlarm.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
            # Insert the label in gridLayout_11 at the next available row
            row = self.gridLayout_11.rowCount()
            self.gridLayout_11.addWidget(self.labelAlarm, row, 0, 1, -1)
        
        # Update the label text
        if active_alarms:
            self.labelAlarm.setText("ALARMS:\n" + "\n".join(active_alarms))
            self.labelAlarm.setStyleSheet("color: red; font-weight: bold;")
        else:
            self.labelAlarm.setText("No Alarms")
            self.labelAlarm.setStyleSheet("color: green;")

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
        self.actionSetting.triggered.connect(self.handle_settings)
        self.actionStart.triggered.connect(self._start)
        self.actionStop.triggered.connect(self._stop)
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
        """
        Create data stacks for channel readings and test data.
        Initialize with empty lists for each channel to prevent index out of range errors.
        """
        # Initialize data_stack: one list for process_time and one for each channel plus one for sampling time.
        data_stack = [[] for _ in range(CHANNEL_COUNT + 2)]
        test_data_stack = [[] for _ in range(CHANNEL_COUNT + 2)]
        
        # Ensure we have at least CHANNEL_COUNT + 2 elements in each stack
        while len(data_stack) < CHANNEL_COUNT + 2:
            data_stack.append([])
        while len(test_data_stack) < CHANNEL_COUNT + 2:
            test_data_stack.append([])
            
        pool.set("data_stack", data_stack)
        pool.set("test_data_stack", test_data_stack)
        self.data_stack = data_stack
        self.test_data_stack = test_data_stack
        logger.debug(f"Data stacks initialized with {len(data_stack)} elements")
    def load_active_channels(self):
        self.active_channels = []
        for i in range(CHANNEL_COUNT):
            if pool.config('active' + str(i + 1), bool):
                self.active_channels.append(i + 1)
        return pool.set('active_channels', self.active_channels)
        pass
    def _start(self):
        # Reset data stack and UI panels
        self.create_stack()
        self.active_channels = self.load_active_channels()
        self.initialize_ui_panels()
        # Start a new cycle using the new cycle handler
        self.new_cycle_handler.start_cycle()
  
        if hasattr(self, "actionStart"):
            self.actionStart.setEnabled(False)
        if hasattr(self, "actionStop"):
            self.actionStop.setEnabled(True)

    def _stop(self):
        try:
            # Stop live update and connection timers as before.
            if hasattr(self, 'live_update_timer') and self.live_update_timer.isActive():
                self.live_update_timer.stop()
            if hasattr(self, 'connectionTimer') and self.connectionTimer.isActive():
                self.connectionTimer.stop()
            if hasattr(self, 'status_timer') and self.status_timer.isActive():
                self.status_timer.stop()
            
            # Delegate stop action to the new cycle handler.
            if self.new_cycle_handler and hasattr(self.new_cycle_handler, "stop_cycle"):
                logger.info("Using new_cycle_handler to stop cycle")
                self.new_cycle_handler.stop_cycle()
            else:
                logger.warning("No active new_cycle_handler found; unable to stop cycle properly.")
            
            if hasattr(self, 'actionStart'):
                self.actionStart.setEnabled(True)
            if hasattr(self, 'actionStop'):
                self.actionStop.setEnabled(False)
            if hasattr(self, 'actionPrint_results'):
                self.actionPrint_results.setEnabled(True)
            
            if hasattr(self, 'close_csv_file'):
                QTimer.singleShot(1000, self.close_csv_file)
            
            # Stop boolean data reading
            self.stop_boolean_reading()
        
            # Update visualization
            self.viz_manager.stop_visualization()
            
            logger.info("Cycle stopping completed successfully")
        except Exception as e:
            logger.error(f"Error stopping cycle: {str(e)}")
            QtWidgets.QMessageBox.critical(
                self,
                "Error",
                f"Failed to stop cycle: {str(e)}"
            )
        
        # Stop visualization
        self.viz_manager.stop_visualization()
        logger.info("Cycle and visualization stopped")

    def _print_result(self):
        pass

    def _show_cycle_info(self, checked):
        self.cycle_infoGroupBox.setVisible(checked)

    def _save(self):
        pass

    def _save_as(self):
        pass

    def _show_setting_form(self):
        self.setting_form = SettingFormHandler()

    def _exit(self):
        pass

    def cleanup(self):
        """Clean up all resources used by the plot"""
        # Remove any timers
        if hasattr(self, 'update_timer') and self.update_timer:
            self.update_timer.stop()

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
        
        # Use a short timer instead of processEvents()
        QTimer.singleShot(10, update_ui)

    def update_immediate_test_values_panel(self):
        for i in self.active_channels:
            spin_widget = getattr(self, 'ch' + str(i) + 'Value')
            if self.test_data_stack[i]:
                spin_widget.setValue(self.test_data_stack[i][-1])
            self.test_data_stack[i] = []

    def update_immediate_values_panel(self):
        """
        Update the values displayed in the immediate values panel.
        Called on a timer to keep the display up to date.
        """
        if self.immediate_panel_update_locked:
            return
        
        try:
            self.immediate_panel_update_locked = True
            for i in range(CHANNEL_COUNT):
                try:
                    spin_widget = getattr(self, 'ch' + str(i + 1) + 'Value')
                    if spin_widget is None:
                        continue
                    
                    # Only update if data is available for this channel
                    if len(self.data_stack) > i + 1 and len(self.data_stack[i + 1]) > 0:
                        spin_widget.setValue(self.data_stack[i + 1][-1])
                except (AttributeError, IndexError) as e:
                    logger.debug(f"Skipping update for channel {i+1}: {e}")
                    
            # Replace legacy values with new_cycle_handler attributes
            if hasattr(self.new_cycle_handler, "core_temp_above_setpoint_time"):
                self.o1.setText(str(self.new_cycle_handler.core_temp_above_setpoint_time or 'N/A'))
            else:
                self.o1.setText("N/A")
            if hasattr(self.new_cycle_handler, "pressure_drop_core_temp"):
                self.o2.setText(str(self.new_cycle_handler.pressure_drop_core_temp or 'N/A'))
            else:
                self.o2.setText("N/A")
        except Exception as e:
            logger.error(f"Error updating immediate values panel: {e}")
        finally:
            self.immediate_panel_update_locked = False

    def cycle_timer_update(self):
        if hasattr(self.new_cycle_handler, "cycle_start_time"):
            self.run_duration.setText(timedelta2str(datetime.now() - self.new_cycle_handler.cycle_start_time))
        else:
            self.run_duration.setText("00:00:00")
        # Optionally, if a cycle_end_time is already set, display it:
        if hasattr(self.new_cycle_handler, "cycle_end_time"):
            self.d6.setText(self.new_cycle_handler.cycle_end_time.strftime("%H:%M:%S"))
        else:
            self.d6.setText(datetime.now().strftime("%H:%M:%S"))



    def update_cycle_info_pannel(self, program=None):
        # Cycle Info Panel – basic data:
        self.d1.setText(
            str(program.cycle_id) if program and program.cycle_id else pool.config("cycle_id", str, "")
        )
        self.d2.setText(pool.config("order_id", str, ""))
        # Retrieve quantity using pool.get instead of pool.config
        qty = pool.get("quantity")
        if qty is None:
            qty = 0
        self.d3.setText(str(qty))
        
        if self.new_cycle_handler and hasattr(self.new_cycle_handler, 'cycle_start_time'):
            self.d4.setText(self.new_cycle_handler.cycle_start_time.strftime("%Y/%m/%d"))
            self.d5.setText(self.new_cycle_handler.cycle_start_time.strftime("%H:%M:%S"))
        else:
            self.d4.setText("N/A")
            self.d5.setText("N/A")
        
        self.d7.setText(
            str(program.cycle_location) if program and program.cycle_location else pool.config("cycle_location", str, "")
        )

        # Cycle Set Parameters Panel:
        self.p1.setText(
            str(program.maintain_vacuum) if program and program.maintain_vacuum is not None else str(pool.config("maintain_vacuum", float, 0.0))
        )
        self.p2.setText(
            str(program.initial_set_cure_temp) if program and program.initial_set_cure_temp is not None else str(pool.config("initial_set_cure_temp", float, 0.0))
        )
        self.p3.setText(
            str(program.temp_ramp) if program and program.temp_ramp is not None else str(pool.config("temp_ramp", float, 0.0))
        )
        self.p4.setText(
            str(program.set_pressure) if program and program.set_pressure is not None else str(pool.config("set_pressure", float, 0.0))
        )
        self.p5.setText(
            str(program.dwell_time) if program and program.dwell_time is not None else str(pool.config("dwell_time", float, 0.0))
        )
        self.p6.setText(
            str(program.cool_down_temp) if program and program.cool_down_temp is not None else str(pool.config("cool_down_temp", float, 0.0))
        )
        
        self.cH1Label_36.setText(
            f"TIME (min) CORE TEMP ≥ {str(program.core_temp_setpoint) if (program and program.core_temp_setpoint is not None) else str(pool.config('core_temp_setpoint', float, 0.0))} °C:"
        )
    
    def update_live_data(self):
        """
        Enhanced version of update_live_data that updates both UI spinboxes.
        This version handles the data stack updates correctly.
        """
        try:
            if not plc_communication.is_connected():
                return
            
            # Store data points to add to the plot
            plot_data_points = []
            
            # Calculate current time index for the data stack
            current_time = len(self.data_stack[0]) if self.data_stack and len(self.data_stack) > 0 and len(self.data_stack[0]) > 0 else 0
            
            # Flag to track if we've incremented the time already
            time_incremented = False
            
            # --- UPDATE ALL CHANNELS (1-14) ---
            for ch in range(1, 15):
                try:
                    addr_key = f'channel_{ch}_address'
                    channel_addr = pool.config(addr_key, int, 0)
                    if channel_addr > 0:
                        channel_value = read_holding_register(channel_addr, 1)
                        scale_enabled = pool.config(f'scale{ch}', bool, False)
                        decimal_places = pool.config(f'decimal_point{ch}', int, 0)
                        
                        # Process the value
                        if channel_value is not None:
                            if scale_enabled and decimal_places > 0:
                                value = channel_value / (10 ** decimal_places)
                            else:
                                try:
                                    value = float(channel_value)
                                except Exception:
                                    value = 0.0
                        else:
                            value = 0.0
                        
                        # Update UI spinbox
                        spinbox = self.centralWidget().findChild(QtWidgets.QDoubleSpinBox, f"ch{ch}Value")
                        if spinbox:
                            spinbox.setValue(value)
                        else:
                            logger.debug(f"Spinbox ch{ch}Value not found in UI.")
                        
                        # Check if this is an active channel
                        is_active = hasattr(self, 'active_channels') and ch in self.active_channels
                        
                        if is_active:
                            # Ensure data stack is initialized properly
                            while len(self.data_stack) <= ch:
                                self.data_stack.append([])
                            
                            # Add value to stack
                            self.data_stack[ch].append(value)
                            
                            # Add to plot data points
                            plot_data_points.append({
                                'channel': f'CH{ch}',
                                'value': value
                            })
                            
                            # Only increment time once per update cycle
                            if not time_incremented:
                                # Ensure time stack exists
                                if len(self.data_stack) == 0:
                                    self.data_stack = [[]] + self.data_stack  # Ensure index 0 exists
                                
                                # Add to time stack (index 0)
                                self.data_stack[0].append(current_time)
                                
                                # Add datetime stamp (index CHANNEL_COUNT+1)
                                while len(self.data_stack) <= CHANNEL_COUNT + 1:
                                    self.data_stack.append([])
                                self.data_stack[CHANNEL_COUNT + 1].append(datetime.now())
                                
                                time_incremented = True
                    else:
                        logger.debug(f"Channel {ch} address not configured")
                except Exception as e:
                    logger.error(f"Error reading CH{ch}: {e}")            
        except Exception as e:
            logger.error(f"Error in update_live_data: {e}")
    def create_csv_file(self):
        self.csv_update_locked = False
        self.last_written_index = 0
        file_extension = '.csv'
        # Use new_cycle_handler properties if available; otherwise use fallback path.
        if hasattr(self.new_cycle_handler, 'folder_path') and hasattr(self.new_cycle_handler, 'file_name'):
            csv_full_path = os.path.join(self.new_cycle_handler.folder_path,
                                        self.new_cycle_handler.file_name + file_extension)
            self.csv_path = csv_full_path
        else:
            reports_dir = os.path.join(os.getcwd(), "reports")
            if not os.path.exists(reports_dir):
                os.makedirs(reports_dir)
            self.csv_path = os.path.join(reports_dir, "cycle_report.csv")
        delimiter = pool.config('csv_delimiter') or ' '
        csv.register_dialect('unixpwd', delimiter=delimiter)
        self.open_csv_file(mode='w')
        self.write_cycle_info_to_csv()

    def open_csv_file(self, mode='a'):
        self.csv_file = open(self.csv_path, mode, newline='')
        self.csv_writer = csv.writer(self.csv_file)

    def close_csv_file(self):
        if hasattr(self, 'csv_file') and self.csv_file:
            self.csv_file.close()
    def write_cycle_info_to_csv(self):
        if self.new_cycle_handler and hasattr(self.new_cycle_handler, "cycle_start_time"):
            start_time_str = self.new_cycle_handler.cycle_start_time.strftime("%Y-%m-%d %H:%M:%S")
        else:
            start_time_str = "N/A"
        data = [
            ["Work Order", pool.config("order_id")],
            ["Cycle Number", pool.config("cycle_id")],
            ["Quantity", pool.config("quantity")],
            ["Process Start Time", start_time_str]
        ]
        self.csv_writer.writerows(data)
        if not hasattr(self, 'headers') or not self.headers:
            self.headers = ['Date', 'Time', 'Timer(min)', 'CycleID', 'OrderID', 'Quantity', 'CycleLocation']
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
        # Call new_cycle_handler.stop_cycle() instead of legacy start_cycle_form.stop_cycle()
        if self.new_cycle_handler and hasattr(self.new_cycle_handler, "stop_cycle"):
            self.new_cycle_handler.stop_cycle()
        self.actionStart.setEnabled(True)
        self.actionStop.setEnabled(False)
        if hasattr(self, 'csv_file'):
            self.csv_file.close()

    def generate_html_report(self, image_path=None):
        # Retrieve cycle times, using new_cycle_handler if available
        if (self.new_cycle_handler and hasattr(self.new_cycle_handler, "cycle_start_time") and 
                hasattr(self.new_cycle_handler, "cycle_end_time")):
            cycle_date = self.new_cycle_handler.cycle_start_time.strftime("%Y/%m/%d")
            cycle_start = self.new_cycle_handler.cycle_start_time.strftime("%H:%M:%S")
            cycle_end = self.new_cycle_handler.cycle_end_time.strftime("%H:%M:%S")
            core_high_temp_time = round(getattr(self.new_cycle_handler, "core_temp_above_setpoint_time", 0), 2)
            if not core_high_temp_time:
                core_high_temp_time = "-"
            release_temp = getattr(self.new_cycle_handler, "pressure_drop_core_temp", "-")
        else:
            cycle_date = cycle_start = cycle_end = core_high_temp_time = release_temp = "-"

        # Retrieve current cycle id from pool configuration.
        current_cycle_id = pool.config("cycle_id")
        serial_numbers = "No serial numbers recorded"
        try:
            # Query the database for serial numbers associated with the current cycle,
            # filtering out placeholder values.
            if current_cycle_id:
                from RaspPiReader.libs.models import CycleSerialNumber
                serial_records = self.db.session.query(CycleSerialNumber).filter_by(cycle_id=current_cycle_id).all()
                valid_serials = [rec.serial_number for rec in serial_records 
                                 if rec.serial_number and not rec.serial_number.startswith("PLACEHOLDER_")]
                if valid_serials:
                    serial_numbers = ", ".join(valid_serials)
        except Exception as e:
            logger.error(f"Error retrieving serial numbers for cycle {current_cycle_id}: {e}")
            serial_numbers = f"Error: {e}"

        report_data = {
            "order_id": pool.config("order_id") or "-",
            "cycle_id": current_cycle_id or "-",
            "quantity": pool.config("quantity") or "-",
            "cycle_location": pool.config("cycle_location") or "-",
            "dwell_time": int(pool.config("dwell_time")) if pool.config("dwell_time") else "-",
            "cool_down_temp": pool.config("cool_down_temp") or "-",
            "core_temp_setpoint": pool.config("core_temp_setpoint") or "-",
            "temp_ramp": pool.config("temp_ramp") or "-",
            "set_pressure": pool.config("set_pressure") or "-",
            "maintain_vacuum": pool.config("maintain_vacuum") or "-",
            "initial_set_cure_temp": pool.config("initial_set_cure_temp") or "-",
            "final_set_cure_temp": pool.config("final_set_cure_temp") or "-",
            "core_high_temp_time": core_high_temp_time,
            "release_temp": release_temp,
            "cycle_date": cycle_date,
            "cycle_start_time": cycle_start,
            "cycle_end_time": cycle_end,
            "image_path": image_path,
            "logo_path": os.path.join(os.getcwd(), 'ui\\logo.jpg'),
            "serial_numbers": serial_numbers    # <-- Added key for serial numbers
        }
        self.render_print_template(template_file='result_template.html', data=report_data)

    def render_print_template(self, *args, template_file=None, **kwargs):
        templateLoader = jinja2.FileSystemLoader(searchpath=os.path.join(os.getcwd(), "ui"))
        templateEnv = jinja2.Environment(loader=templateLoader, extensions=['jinja2.ext.loopcontrols'])
        template = templateEnv.get_template(template_file)
        html = template.render(**kwargs.get("data", {}))
        import tempfile
        with tempfile.NamedTemporaryFile('w', delete=False, suffix='.html') as f:
            fname = f.name
            f.write(html)
        file_extension = '.pdf'
        if hasattr(self.new_cycle_handler, 'folder_path') and hasattr(self.new_cycle_handler, 'file_name'):
            pdf_full_path = os.path.join(self.new_cycle_handler.folder_path,
                                        self.new_cycle_handler.file_name + file_extension)
        else:
            reports_dir = os.path.join(os.getcwd(), "reports")
            if not os.path.exists(reports_dir):
                os.makedirs(reports_dir)
            pdf_full_path = os.path.join(reports_dir, "cycle_report.pdf")
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
        if pool.get("current_cycle"):
            quit_msg = "Are you Sure?\nCSV data may not be saved."
        else:
            quit_msg = "Are you sure?"

        reply = QMessageBox.question(self, 'Exiting app ...',
                                     quit_msg, (QMessageBox.Yes | QMessageBox.Cancel))
        if reply == QMessageBox.Yes:
            event.accept()
        elif reply == QMessageBox.Cancel:
            event.ignore()
        # Call the original closeEvent implementation
        super().closeEvent(event)
    def update_status_bar(self, msg, ms_timeout, color):
        self.statusbar.showMessage(msg, ms_timeout)
        self.statusbar.setStyleSheet("color: {}".format(color.lower()))
        self.statusBar().setFont(QFont('Times', 12))
    
    def enable_channel_updates(self):
        """
        Enable continuous updating of channel labels and boolean displays.
        This method starts a dedicated timer that calls update_immediate_values_panel()
        (or similar) at a regular interval without starting the cycle duration timer.
        It ensures that while the cycle has been initiated (showing channel labels),
        the cycle timer does not yet count until the full input is provided.
        """
        if not hasattr(self, 'channel_update_timer') or not self.channel_update_timer.isActive():
            self.channel_update_timer = QTimer(self)
            self.channel_update_timer.timeout.connect(self.update_immediate_values_panel)
            # Refresh channel labels values every second (adjust as needed)
            self.channel_update_timer.start(1000)
            logger.info("Channel updates enabled: Timer started for updating immediate channel values.")
        else:
            logger.info("Channel update timer is already active.")

    def start_cycle_timer(self, start_time):
        """
        Start the cycle timer which updates the cycle duration display and logs cycle time.
        This method is called only after the full cycle input (work order, serial numbers, program selection)
        has been completed via the final green 'Start Cycle' button.
        It also optionally triggers live data logging via start_live_data().
        """
        # Set the cycle start time in the new cycle handler
        self.new_cycle_handler.cycle_start_time = start_time
        # Stop any pre-existing cycle timer if running.
        if hasattr(self, "cycle_timer") and self.cycle_timer.isActive():
            self.cycle_timer.stop()
        self.cycle_timer = QTimer(self)
        self.cycle_timer.timeout.connect(self.update_cycle_timer)
        # Start the cycle duration timer (updates every second)
        self.cycle_timer.start(1000)
        logger.info(f"Cycle timer started at {start_time}.")
        # Optionally start live data logging
        if hasattr(self, "start_live_data"):
            self.start_live_data()
        else:
            logger.info("start_live_data() not defined; live data logging not initiated.")

    def set_cycle_start_register(self, value):
        """
        Write the specified value to the cycle start register on the PLC.
        For our workflow, writing '1' indicates that the cycle has finally started.
        Adjust the register address as needed via pool configuration.
        """
        try:
            # Retrieve the PLC register address from settings; default to 1000 if not set.
            reg_addr = pool.config('cycle_start_register_address', int, 1000)
            # Call the PLC comm write_register method (ensure this method exists in your plc_communication API)
            result = plc_communication.write_register(reg_addr, value)
            logger.info(f"Cycle start register at address {reg_addr} set to {value} (write result: {result}).")
        except Exception as e:
            logger.error(f"Error setting cycle start register: {e}")

    def init_cycle_outcomes(self):
        """
        Initialize the Cycle Outcomes display in the main form.
        The text for the core temperature threshold (e.g. 'CORE TEMP ≥ 2 C')
        is set dynamically from the user configuration.
        """
        # Retrieve the dynamically set threshold; default to 2 if not configured
        threshold = pool.config('core_temp_setpoint', int, 2)
        self.labelCycleOutcomesTime = QLabel(f"TIME (min) CORE TEMP ≥ {threshold} C: N/A", self)
        self.labelCycleOutcomesTime.setFont(QFont("Segoe UI", 10))
        self.labelCycleOutcomesTime.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        
        self.labelCycleOutcomesPressure = QLabel("CORE TEMP WHEN PRESSURE RELEASED (C): N/A", self)
        self.labelCycleOutcomesPressure.setFont(QFont("Segoe UI", 10))
        self.labelCycleOutcomesPressure.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        
        # Add labels to your designated layout (adjust as needed)
        if hasattr(self, "outcomesLayout"):
            self.outcomesLayout.addWidget(self.labelCycleOutcomesTime)
            self.outcomesLayout.addWidget(self.labelCycleOutcomesPressure)
        else:
            self.mainLayout.addWidget(self.labelCycleOutcomesTime)
            self.mainLayout.addWidget(self.labelCycleOutcomesPressure)
        
        # Start a timer to update these values periodically
        self.cycleOutcomesTimer = QTimer(self)
        self.cycleOutcomesTimer.timeout.connect(self.update_cycle_outcomes)
        self.cycleOutcomesTimer.start(1000)  # update every second

    def update_cycle_outcomes(self):
        """
        Update the Cycle Outcomes labels with the latest cycle data.
        Uses properties from the new cycle handler:
         - core_temp_above_setpoint_time (elapsed minutes core temp was above the threshold)
         - pressure_drop_core_temp (the core temp value when a pressure drop occurred)
        If no valid value exists, "N/A" is displayed.
        """
        # Retrieve the dynamic core temperature setpoint as a float (default: 100.0)
        threshold = pool.config('core_temp_setpoint', float, 100.0)
        logger.debug(f"Current core_temp_setpoint: {threshold}")

        # Check for the accumulated time above setpoint
        if hasattr(self.new_cycle_handler, 'core_temp_above_setpoint_time'):
            time_value = self.new_cycle_handler.core_temp_above_setpoint_time
            logger.debug(f"core_temp_above_setpoint_time: {time_value}")
            time_str = f"{time_value:.2f}" if time_value and time_value > 0 else "N/A"
        else:
            logger.warning("new_cycle_handler is missing core_temp_above_setpoint_time attribute")
            time_str = "N/A"

        # Check for the pressure drop core temperature
        if hasattr(self.new_cycle_handler, 'pressure_drop_core_temp'):
            pressure_value = self.new_cycle_handler.pressure_drop_core_temp
            logger.debug(f"pressure_drop_core_temp: {pressure_value}")
            pressure_str = f"{pressure_value:.1f}" if pressure_value is not None else "N/A"
        else:
            logger.warning("new_cycle_handler is missing pressure_drop_core_temp attribute")
            pressure_str = "N/A"

        # Update the UI labels with formatted outputs
        self.labelCycleOutcomesTime.setText(f"TIME (min) CORE TEMP ≥ {threshold:.1f} °C: {time_str}")
        self.labelCycleOutcomesPressure.setText(f"CORE TEMP WHEN PRESSURE RELEASED (°C): {pressure_str}")

    
