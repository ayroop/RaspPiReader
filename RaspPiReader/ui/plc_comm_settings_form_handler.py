from PyQt5 import QtWidgets, QtCore, QtSerialPort
from PyQt5.QtCore import QSettings
from PyQt5.QtWidgets import QApplication, QDialog
from PyQt5.QtGui import QFont
import logging
import sqlite3
import sys
import os

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
        """Test the connection with current settings"""
        try:
            # Get demo mode from pool configuration
            current_demo_mode = pool.config('demo', bool, False)
            
            # Show a "Testing..." status
            self.statusLabel.setText("Testing connection...")
            self.statusLabel.setStyleSheet("color: blue; font-weight: bold;")
            QApplication.processEvents()  # Ensure UI updates
            
            # For real testing, get current params
            connection_type = 'tcp' if self.tcpRadio.isChecked() else 'rtu'
            params = self._get_current_connection_params()
                    
            logger.info(f"Performing REAL CONNECTION TEST with: {connection_type}, params: {params}")
                    
            # Call test_connection with explicit simulation_mode=False
            success = plc_communication.test_connection(
                connection_type=connection_type,
                simulation_mode=False,
                **params
            )
            
            # Show result
            if success:
                self.statusLabel.setText("Connected")
                self.statusLabel.setStyleSheet("color: green; font-weight: bold;")
                QtWidgets.QMessageBox.information(
                    self,
                    "Connection Test",
                    "Successfully connected to PLC using REAL connection."
                )
            else:
                self.statusLabel.setText("Connection Failed")
                self.statusLabel.setStyleSheet("color: red; font-weight: bold;")
                QtWidgets.QMessageBox.warning(
                    self,
                    "Connection Test",
                    "Failed to connect to PLC. Check your settings and ensure the device is connected."
                )
        
        except Exception as e:
            logger.error(f"Error testing connection: {e}")
            self.statusLabel.setText("Connection Error")
            self.statusLabel.setStyleSheet("color: red; font-weight: bold;")
            QtWidgets.QMessageBox.critical(
                self,
                "Connection Test Error",
                f"An error occurred while testing the connection: {str(e)}"
            )
        
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
        """Save settings and initialize PLC communication"""
        if self._save_settings_simple(test_only=False):
            # Initialize the PLC communication with new settings
            logger.info("Initializing PLC communication with new settings")
            success = plc_communication.initialize_plc_communication()
            
            if success:
                logger.info("PLC communication initialized successfully")
                # Accept the dialog only if initialization succeeds
                self.accept()
            else:
                logger.error("Failed to initialize PLC communication")
                QtWidgets.QMessageBox.warning(
                    self,
                    "PLC Communication Error",
                    "Failed to initialize PLC communication with new settings."
                )