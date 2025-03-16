from PyQt5 import QtWidgets, QtCore, QtSerialPort
from PyQt5.QtCore import QSettings, QTimer
from PyQt5.QtWidgets import QApplication, QDialog
from PyQt5.QtGui import QFont
import logging
import sqlite3
import sys
import os
import threading
from RaspPiReader import pool
from RaspPiReader.libs import plc_communication
from RaspPiReader.libs.database import Database
from RaspPiReader.libs.models import PLCCommSettings

logger = logging.getLogger(__name__)

class PLCCommSettingsFormHandler(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super(PLCCommSettingsFormHandler, self).__init__(parent)
        
        # First, ensure modal is set to avoid the window appearing/disappearing
        self.setWindowTitle("PLC Communication Settings")
        self.setModal(True)
        self.plc_init_worker = None  # Store the worker reference
        # Build UI components in logical sequence
        self._create_ui_elements()
        self._connect_signals()
        
        # Initialize form values AFTER UI is built
        self._initialize_serial_ports()
        self._initialize_form_values()
        self._update_settings_visibility()
        self._update_connection_status()
        
        # Set size after everything is initialized
        self.resize(450, 380)
        
        logger.info("PLC Communication Settings dialog initialized")
    
    def _create_ui_elements(self):
        """Create all UI elements in a single method for better organization"""
        # Main layout
        self.layout = QtWidgets.QVBoxLayout(self)

        # Connection mode group
        self.modeGroupBox = QtWidgets.QGroupBox("Communication Mode")
        self.modeLayout = QtWidgets.QHBoxLayout(self.modeGroupBox)

        # Radio buttons for connection type
        self.tcpRadio = QtWidgets.QRadioButton("TCP/IP")
        self.rtuRadio = QtWidgets.QRadioButton("RTU (Serial)")
        self.modeLayout.addWidget(self.tcpRadio)
        self.modeLayout.addWidget(self.rtuRadio)
        self.layout.addWidget(self.modeGroupBox)

        # Stacked layout for different connection types
        self.stackedLayout = QtWidgets.QStackedLayout()

        # TCP Settings widget
        self.tcpWidget = QtWidgets.QWidget()
        self.tcpLayout = QtWidgets.QFormLayout(self.tcpWidget)

        self.hostLabel = QtWidgets.QLabel("Host:")
        self.hostLineEdit = QtWidgets.QLineEdit()
        self.tcpLayout.addRow(self.hostLabel, self.hostLineEdit)

        self.tcpPortLabel = QtWidgets.QLabel("Port:")
        self.tcpPortSpinBox = QtWidgets.QSpinBox()
        self.tcpPortSpinBox.setRange(1, 65535)
        self.tcpPortSpinBox.setValue(502)  # Default Modbus TCP port
        self.tcpLayout.addRow(self.tcpPortLabel, self.tcpPortSpinBox)

        self.stackedLayout.addWidget(self.tcpWidget)

        # RTU Settings widget
        self.rtuWidget = QtWidgets.QWidget()
        self.rtuLayout = QtWidgets.QFormLayout(self.rtuWidget)

        self.portLabel = QtWidgets.QLabel("Port:")
        self.portComboBox = QtWidgets.QComboBox()
        self.rtuLayout.addRow(self.portLabel, self.portComboBox)

        self.baudrateLabel = QtWidgets.QLabel("Baudrate:")
        self.baudrateComboBox = QtWidgets.QComboBox()
        self.baudrateComboBox.addItems(["9600", "19200", "38400", "57600", "115200"])
        self.rtuLayout.addRow(self.baudrateLabel, self.baudrateComboBox)

        self.bytesizeLabel = QtWidgets.QLabel("Data Bits:")
        self.bytesizeComboBox = QtWidgets.QComboBox()
        self.bytesizeComboBox.addItems(["8", "7", "6", "5"])
        self.rtuLayout.addRow(self.bytesizeLabel, self.bytesizeComboBox)

        self.parityLabel = QtWidgets.QLabel("Parity:")
        self.parityComboBox = QtWidgets.QComboBox()
        self.parityComboBox.addItems(["N", "E", "O"])
        self.rtuLayout.addRow(self.parityLabel, self.parityComboBox)

        self.stopbitsLabel = QtWidgets.QLabel("Stop Bits:")
        self.stopbitsComboBox = QtWidgets.QComboBox()
        self.stopbitsComboBox.addItems(["1", "1.5", "2"])
        self.rtuLayout.addRow(self.stopbitsLabel, self.stopbitsComboBox)

        self.stackedLayout.addWidget(self.rtuWidget)
        self.layout.addLayout(self.stackedLayout)

        # Common settings group
        self.commonGroupBox = QtWidgets.QGroupBox("Common Settings")
        self.commonLayout = QtWidgets.QFormLayout(self.commonGroupBox)

        self.timeoutLabel = QtWidgets.QLabel("Timeout (seconds):")
        self.timeoutSpinBox = QtWidgets.QDoubleSpinBox()
        self.timeoutSpinBox.setRange(0.1, 10.0)
        self.timeoutSpinBox.setSingleStep(0.1)
        self.timeoutSpinBox.setValue(1.0)
        self.commonLayout.addRow(self.timeoutLabel, self.timeoutSpinBox)

        # Simulation mode feature removed completely

        self.layout.addWidget(self.commonGroupBox)

        # Status indicator group
        self.statusGroupBox = QtWidgets.QGroupBox("Connection Status")
        self.statusLayout = QtWidgets.QHBoxLayout(self.statusGroupBox)

        self.statusLabel = QtWidgets.QLabel("Not Connected")
        self.statusLabel.setStyleSheet("color: red; font-weight: bold;")
        self.statusLayout.addWidget(self.statusLabel)

        self.layout.addWidget(self.statusGroupBox)

        # Button layout
        self.buttonLayout = QtWidgets.QHBoxLayout()
        self.testButton = QtWidgets.QPushButton("Test Connection")
        self.saveButton = QtWidgets.QPushButton("Save")
        self.cancelButton = QtWidgets.QPushButton("Cancel")

        self.buttonLayout.addWidget(self.testButton)
        self.buttonLayout.addWidget(self.saveButton)
        self.buttonLayout.addWidget(self.cancelButton)

        self.layout.addLayout(self.buttonLayout)
    
    def _connect_signals(self):
        """Connect UI elements to their action methods"""
        # Connect button signals
        self.testButton.clicked.connect(self._test_connection)
        self.saveButton.clicked.connect(self.save_and_close)
        self.cancelButton.clicked.connect(self.reject)
        
        # Connect radio button toggle to update settings visibility
        self.tcpRadio.toggled.connect(self._update_settings_visibility)
    
    def _initialize_serial_ports(self):
        """Populate serial ports dropdown"""
        # Clear existing items first
        self.portComboBox.clear()
        
        # Get available ports
        ports = QtSerialPort.QSerialPortInfo.availablePorts()
        if ports:
            for port in ports:
                self.portComboBox.addItem(port.portName())
                logger.debug(f"Found serial port: {port.portName()}")
        else:
            logger.warning("No serial ports detected. Adding default COM port options.")
            for i in range(1, 10):
                self.portComboBox.addItem(f"COM{i}")
    
    def _initialize_form_values(self):
        """Load current settings into form"""
        # Load settings from QSettings first, then check pool
        settings = QSettings('RaspPiHandler', 'RaspPiModbusReader')
        
        # Set connection type
        connection_type = settings.value('plc/connection_type') or pool.config('plc/connection_type', str, 'rtu')
        logger.info(f"Loading connection type: {connection_type}")
        
        if connection_type == 'tcp':
            self.tcpRadio.setChecked(True)
        else:
            self.rtuRadio.setChecked(True)
        
        # Set RTU-specific values
        port = settings.value('plc/port') or pool.config('plc/port', str, 'COM1')
        baudrate = settings.value('plc/baudrate') or pool.config('plc/baudrate', int, 9600)
        bytesize = settings.value('plc/bytesize') or pool.config('plc/bytesize', int, 8)
        parity = settings.value('plc/parity') or pool.config('plc/parity', str, 'N')
        stopbits = settings.value('plc/stopbits') or pool.config('plc/stopbits', float, 1.0)
        
        # Find the port in the combobox
        port_index = self.portComboBox.findText(port)
        if port_index >= 0:
            self.portComboBox.setCurrentIndex(port_index)
        
        # Set other RTU values
        baudrate_index = self.baudrateComboBox.findText(str(baudrate))
        if baudrate_index >= 0:
            self.baudrateComboBox.setCurrentIndex(baudrate_index)
            
        bytesize_index = self.bytesizeComboBox.findText(str(bytesize))
        if bytesize_index >= 0:
            self.bytesizeComboBox.setCurrentIndex(bytesize_index)
            
        parity_index = self.parityComboBox.findText(parity)
        if parity_index >= 0:
            self.parityComboBox.setCurrentIndex(parity_index)
            
        stopbits_index = self.stopbitsComboBox.findText(str(stopbits))
        if stopbits_index >= 0:
            self.stopbitsComboBox.setCurrentIndex(stopbits_index)
        
        # Set TCP-specific values
        host = settings.value('plc/host') or pool.config('plc/host', str, 'localhost')
        tcp_port = settings.value('plc/tcp_port') or pool.config('plc/tcp_port', int, 502)
        
        self.hostLineEdit.setText(host)
        self.tcpPortSpinBox.setValue(int(tcp_port))
        
        # Set common values
        timeout = settings.value('plc/timeout') or pool.config('plc/timeout', float, 1.0)
        self.timeoutSpinBox.setValue(float(timeout))
        
        logger.info(f"Form initialized with connection type: {connection_type}")
    
    def _update_settings_visibility(self):
        """Show appropriate settings based on connection type"""
        if self.tcpRadio.isChecked():
            self.stackedLayout.setCurrentIndex(0)
        else:
            self.stackedLayout.setCurrentIndex(1)
    
    def _update_connection_status(self):
        """Update the connection status indicator with real connection status"""
        # For real mode, perform a connection test
        try:
            connection_type = 'tcp' if self.tcpRadio.isChecked() else 'rtu'
            params = self._get_current_connection_params()
            
            # Show testing status
            self.statusLabel.setText("Testing connection...")
            self.statusLabel.setStyleSheet("color: blue; font-weight: bold;")
            QApplication.processEvents()  # Update UI
            
            # Perform a quick real connection test
            logger.info(f"Testing REAL connection for status display with {connection_type}")
            connection_ok = plc_communication.test_connection(
                connection_type=connection_type,
                simulation_mode=False,  # Force real test
                **params
            )
            
            # Update UI based on real result
            if connection_ok:
                self.statusLabel.setText("Connected")
                self.statusLabel.setStyleSheet("color: green; font-weight: bold;")
            else:
                self.statusLabel.setText("Not Connected")
                self.statusLabel.setStyleSheet("color: red; font-weight: bold;")
        except Exception as e:
            logger.error(f"Connection status test error: {e}")
            self.statusLabel.setText("Connection Error")
            self.statusLabel.setStyleSheet("color: red; font-weight: bold;")
    
    def _get_current_connection_params(self):
        """Get current connection parameters from the UI"""
        params = {}
        
        # Get common parameters
        params['timeout'] = self.timeoutSpinBox.value()
        
        # Get connection-type specific parameters
        if self.tcpRadio.isChecked():  # TCP parameters
            params['host'] = self.hostLineEdit.text().strip()
            params['port'] = self.tcpPortSpinBox.value()
        else:  # RTU parameters
            params['port'] = self.portComboBox.currentText()
            params['baudrate'] = int(self.baudrateComboBox.currentText())
            params['bytesize'] = int(self.bytesizeComboBox.currentText())
            params['parity'] = self.parityComboBox.currentText()
            params['stopbits'] = float(self.stopbitsComboBox.currentText())
        
        return params
    
    def _test_connection(self):
        """Test the connection with current settings and improved timeout handling"""
        try:
            # Disable buttons during test
            self._set_buttons_enabled(False)
            
            # Show a "Testing..." status
            self._update_status_label("Testing connection...", "blue")
            
            # Create a progress indicator to show the user something is happening
            self._show_progress_bar()
            
            # Set up timeout handling
            self.test_timeout_timer = QTimer(self)
            self.test_timeout_timer.setSingleShot(True)
            self.test_timeout_timer.timeout.connect(self._handle_test_timeout)
            
            # Get connection parameters from UI
            connection_type = 'tcp' if self.tcpRadio.isChecked() else 'rtu'
            params = self._get_current_connection_params()
            
            logger.info(f"Performing CONNECTION TEST with: {connection_type}, params: {params}")
            
            # Make sure to include a sufficient timeout for testing
            if 'timeout' not in params or params['timeout'] < 2.0:
                params['timeout'] = 2.0
            
            # Define a worker function that runs in a thread
            def test_worker():
                try:
                    success = plc_communication.test_connection(
                        connection_type=connection_type,
                        **params
                    )
                    # Use singleShot timer to update UI safely from thread
                    QTimer.singleShot(0, lambda: self._handle_test_result(success))
                    # Stop timeout timer
                    QTimer.singleShot(0, self.test_timeout_timer.stop)
                except Exception as e:
                    logger.error(f"Error in test worker thread: {e}")
                    QTimer.singleShot(0, lambda: self._handle_test_result(False, str(e)))
                    QTimer.singleShot(0, self.test_timeout_timer.stop)
            
            # Create and start the test thread
            test_thread = threading.Thread(target=test_worker, name="ConnectionTestThread")
            test_thread.daemon = True
            
            # Calculate timeout based on timeout value in form
            timeout_value = params.get('timeout', 2.0)
            test_timeout = max(timeout_value * 1000 * 2, 5000)  # At least 5 seconds or 2x the timeout
            # Start the timeout timer 
            self.test_timeout_timer.start(int(test_timeout))
  
            
            # Start the test thread
            test_thread.start()
        
        except Exception as e:
            logger.error(f"Error setting up connection test: {e}")
            self._cleanup_after_test()
            self._update_status_label("Connection Error", "red")
            QtWidgets.QMessageBox.critical(
                self,
                "Connection Test Error",
                f"An error occurred while setting up the connection test: {str(e)}"
            )

    def _handle_test_timeout(self):
        """Handle the case when connection test times out"""
        logger.error("PLC connection test timed out")
        self._cleanup_after_test()
        self._update_status_label("Test Timeout", "red")
        QtWidgets.QMessageBox.warning(
            self,
            "Test Timeout",
            "The connection test timed out. Please check your settings and ensure the PLC is reachable."
        )

    def _handle_test_result(self, success, error_msg=None):
        """Handle the result of the connection test"""
        self._cleanup_after_test()
        if success:
            self._update_status_label("Connected", "green")
            QtWidgets.QMessageBox.information(
                self,
                "Connection Test",
                "Successfully connected to PLC."
            )
        else:
            self._update_status_label("Connection Failed", "red")
            message = "Failed to connect to PLC. Check your settings and ensure the device is connected."
            if error_msg:
                message += f"\n\nError details: {error_msg}"
            QtWidgets.QMessageBox.warning(
                self,
                "Connection Test",
                message
            )

    def _set_buttons_enabled(self, enabled):
        """Enable or disable buttons"""
        self.testButton.setEnabled(enabled)
        self.saveButton.setEnabled(enabled)
        self.cancelButton.setEnabled(enabled)

    def _update_status_label(self, text, color):
        """Update the status label with the given text and color"""
        self.statusLabel.setText(text)
        self.statusLabel.setStyleSheet(f"color: {color}; font-weight: bold;")

    def _show_progress_bar(self):
        """Show a progress bar to indicate ongoing operation"""
        self.progressBar = QtWidgets.QProgressBar(self)
        self.progressBar.setRange(0, 0)  # Indeterminate progress
        self.progressBar.setTextVisible(False)
        self.statusLayout.addWidget(self.progressBar)
        QApplication.processEvents()  # Ensure UI updates

    def _cleanup_after_test(self):
        """Cleanup UI elements and re-enable buttons after test"""
        if hasattr(self, 'progressBar') and self.progressBar is not None:
            self.progressBar.setParent(None)
            self.progressBar = None
        self._set_buttons_enabled(True)

    def _save_settings_simple(self, test_only=False):
        """Save settings directly to config without triggering recursion"""
        try:
            # Get connection type based on radio button
            connection_type = 'tcp' if self.tcpRadio.isChecked() else 'rtu'
            
            logger.info(f"Saving settings - Connection Type: {connection_type}")
            
            # Save to QSettings
            settings = QSettings('RaspPiHandler', 'RaspPiModbusReader')
            
            # Save connection type
            settings.setValue('plc/connection_type', connection_type)
            
            # Save RTU-specific settings
            if connection_type == 'rtu':
                port_value = self.portComboBox.currentText()
                settings.setValue('plc/port', port_value)
                settings.setValue('plc/baudrate', int(self.baudrateComboBox.currentText()))
                settings.setValue('plc/bytesize', int(self.bytesizeComboBox.currentText()))
                settings.setValue('plc/parity', self.parityComboBox.currentText())
                settings.setValue('plc/stopbits', float(self.stopbitsComboBox.currentText()))
            
            # Save TCP-specific settings
            else:
                tcp_host = self.hostLineEdit.text().strip()
                tcp_port = self.tcpPortSpinBox.value()
                settings.setValue('plc/host', tcp_host)
                settings.setValue('plc/tcp_port', tcp_port)
            
            # Save common settings
            settings.setValue('plc/timeout', self.timeoutSpinBox.value())
            settings.sync()  # Force settings to be written immediately
            
            # Also save to pool for immediate use
            pool.set_config('plc/connection_type', connection_type)
            
            if connection_type == 'rtu':
                pool.set_config('plc/port', self.portComboBox.currentText())
                pool.set_config('plc/baudrate', int(self.baudrateComboBox.currentText()))
                pool.set_config('plc/bytesize', int(self.bytesizeComboBox.currentText()))
                pool.set_config('plc/parity', self.parityComboBox.currentText())
                pool.set_config('plc/stopbits', float(self.stopbitsComboBox.currentText()))
            else:
                pool.set_config('plc/host', self.hostLineEdit.text().strip())
                pool.set_config('plc/tcp_port', self.tcpPortSpinBox.value())
                
            pool.set_config('plc/timeout', self.timeoutSpinBox.value())
            
            # Update the database directly using SQLite without simulation_mode column
            if not test_only:
                try:
                    # Check if the plc_comm_settings table exists
                    conn = sqlite3.connect("local_database.db")
                    cursor = conn.cursor()
                    
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='plc_comm_settings'")
                    if not cursor.fetchone():
                        cursor.execute("""
                            CREATE TABLE plc_comm_settings (
                                id INTEGER PRIMARY KEY,
                                comm_mode TEXT NOT NULL,
                                tcp_host TEXT,
                                tcp_port INTEGER,
                                com_port TEXT,
                                baudrate INTEGER,
                                bytesize INTEGER,
                                parity TEXT,
                                stopbits REAL,
                                timeout REAL
                            )
                        """)
                    
                    # Check if record exists
                    cursor.execute("SELECT id FROM plc_comm_settings LIMIT 1")
                    record = cursor.fetchone()
                    
                    if connection_type == 'rtu':
                        port_value = self.portComboBox.currentText()
                        baudrate = int(self.baudrateComboBox.currentText())
                        bytesize = int(self.bytesizeComboBox.currentText())
                        parity = self.parityComboBox.currentText()
                        stopbits = float(self.stopbitsComboBox.currentText())
                        timeout = self.timeoutSpinBox.value()
                        
                        if record:
                            cursor.execute("""
                                UPDATE plc_comm_settings SET 
                                comm_mode = ?, tcp_host = NULL, tcp_port = NULL, 
                                com_port = ?, baudrate = ?, bytesize = ?, 
                                parity = ?, stopbits = ?, timeout = ?
                                WHERE id = ?
                            """, (connection_type, port_value, baudrate, bytesize, 
                                parity, stopbits, timeout, record[0]))
                        else:
                            cursor.execute("""
                                INSERT INTO plc_comm_settings 
                                (comm_mode, tcp_host, tcp_port, com_port, baudrate, 
                                 bytesize, parity, stopbits, timeout)
                                VALUES (?, NULL, NULL, ?, ?, ?, ?, ?, ?)
                            """, (connection_type, port_value, baudrate, bytesize, 
                                parity, stopbits, timeout))
                    else:
                        tcp_host = self.hostLineEdit.text().strip()
                        tcp_port = self.tcpPortSpinBox.value()
                        timeout = self.timeoutSpinBox.value()
                        
                        if record:
                            cursor.execute("""
                                UPDATE plc_comm_settings SET 
                                comm_mode = ?, tcp_host = ?, tcp_port = ?, 
                                com_port = NULL, baudrate = NULL, bytesize = NULL, 
                                parity = NULL, stopbits = NULL, timeout = ?
                                WHERE id = ?
                            """, (connection_type, tcp_host, tcp_port, timeout, record[0]))
                        else:
                            cursor.execute("""
                                INSERT INTO plc_comm_settings 
                                (comm_mode, tcp_host, tcp_port, com_port, baudrate, 
                                 bytesize, parity, stopbits, timeout)
                                VALUES (?, ?, ?, NULL, NULL, NULL, NULL, NULL, ?)
                            """, (connection_type, tcp_host, tcp_port, timeout))
                    
                    conn.commit()
                    conn.close()
                    logger.info("PLC communication settings saved to database")
                    
                except Exception as e:
                    logger.error(f"Database error: {e}")
                    QtWidgets.QMessageBox.warning(
                        self, 
                        "Database Error", 
                        f"Failed to save settings to database: {str(e)}"
                    )
            
            # After successful save, update the connection status
            if not test_only:
                self._update_connection_status()
            
            return True
            
        except Exception as e:
            logger.error(f"Error in _save_settings_simple: {e}")
            if not test_only:
                QtWidgets.QMessageBox.critical(
                    self,
                    "Settings Error",
                    f"An error occurred while saving settings: {str(e)}"
                )
            return False
    
    def save_and_close(self):
        """Save settings and initialize PLC communication in a non-blocking way with timeout control"""
        if self._save_settings_simple(test_only=False):
            # Disable buttons to prevent multiple clicks
            self.saveButton.setEnabled(False)
            self.cancelButton.setEnabled(False)
            self.testButton.setEnabled(False)
            
            # Show a "connecting" status with progress indication
            self.statusLabel.setText("Connecting...")
            self.statusLabel.setStyleSheet("color: blue; font-weight: bold;")
            
            # Create a progress indicator to show that something is happening
            self.progressBar = QtWidgets.QProgressBar(self)
            self.progressBar.setRange(0, 0)  # Indeterminate progress
            self.progressBar.setTextVisible(False)
            self.statusLayout.addWidget(self.progressBar)
            QApplication.processEvents()  # Ensure UI updates
            
            # Set up timeout handling
            self.connection_timeout_timer = QTimer(self)
            self.connection_timeout_timer.setSingleShot(True)
            self.connection_timeout_timer.timeout.connect(self._handle_connection_timeout)
            
            # Define a callback function to handle the result of PLC initialization
            def init_callback(success, error):
                if not success:
                    logger.error(f"PLC initialization error: {error}")
                QTimer.singleShot(0, lambda: self._handle_init_result(success))
                QTimer.singleShot(0, self.connection_timeout_timer.stop)
            
            logger.info("Initializing PLC communication with new settings (async)")
            
            # IMPORTANT: Start initialization ONLY ONCE and store the worker reference
            self.plc_init_worker = plc_communication.initialize_plc_communication_async(callback=init_callback)
            
            # Get the timeout value from the form field and ensure it’s an int (milliseconds)
            timeout_value = self.timeoutSpinBox.value()
            connection_timeout = max(timeout_value * 1000 * 2, 5000)  # At least 5 sec or 2x the timeout setting
            self.connection_timeout_timer.start(int(connection_timeout))

    def _handle_connection_timeout(self):
        """Handle the case when connection initialization times out"""
        logger.error("PLC connection initialization timed out")
        
        # Re-enable buttons
        self.saveButton.setEnabled(True)
        self.cancelButton.setEnabled(True)
        self.testButton.setEnabled(True)
        
        # Remove progress indicator
        if hasattr(self, 'progressBar') and self.progressBar is not None:
            self.progressBar.setParent(None)
            self.progressBar = None
        
        # Update status label
        self.statusLabel.setText("Connection Timeout")
        self.statusLabel.setStyleSheet("color: red; font-weight: bold;")
        
        # Show error message
        QtWidgets.QMessageBox.warning(
            self,
            "Connection Timeout",
            "The connection attempt timed out. Please check your settings and ensure the PLC is reachable."
        )

    def _handle_init_result(self, success):
        """Handle the result of PLC initialization (called on the main thread)"""
        # Re-enable buttons
        self.saveButton.setEnabled(True)
        self.cancelButton.setEnabled(True)
        self.testButton.setEnabled(True)
        
        # Remove progress indicator
        if hasattr(self, 'progressBar') and self.progressBar is not None:
            self.progressBar.setParent(None)
            self.progressBar = None
        
        # Clear the stored worker reference now that we're done
        self.plc_init_worker = None
        
        if success:
            logger.info("PLC communication initialized successfully")
            # Create and start the connection monitor in the main thread
            from RaspPiReader.libs import plc_communication
            if plc_communication.connection_monitor is None:
                plc_communication.connection_monitor = plc_communication.ConnectionMonitor(self)
            plc_communication.connection_monitor.start(30000)  # 30 seconds interval
            
            # Accept the dialog
            self.accept()
        else:
            logger.error("Failed to initialize PLC communication")
            self.statusLabel.setText("Connection Failed")
            self.statusLabel.setStyleSheet("color: red; font-weight: bold;")
            QtWidgets.QMessageBox.warning(
                self,
                "PLC Communication Error",
                "Failed to initialize PLC communication with new settings. Check your connection parameters and ensure the PLC is properly connected."
            )