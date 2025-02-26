from PyQt5 import QtWidgets, QtCore, QtSerialPort
from PyQt5.QtCore import QSettings
from PyQt5.QtWidgets import QApplication
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
        self.setWindowTitle("PLC Communication Settings")
        self.resize(450, 380)
        
        # Create UI layout
        self.layout = QtWidgets.QVBoxLayout(self)
        
        # Add connection mode selector at the top
        self.modeGroupBox = QtWidgets.QGroupBox("Communication Mode")
        self.modeLayout = QtWidgets.QHBoxLayout(self.modeGroupBox)
        
        # Add radio buttons for connection type
        self.tcpRadio = QtWidgets.QRadioButton("TCP/IP")
        self.rtuRadio = QtWidgets.QRadioButton("RTU (Serial)")
        self.modeLayout.addWidget(self.tcpRadio)
        self.modeLayout.addWidget(self.rtuRadio)
        self.layout.addWidget(self.modeGroupBox)
        
        # Create stacked layout for different connection types
        self.stackedLayout = QtWidgets.QStackedLayout()
        
        # TCP Settings
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
        
        # RTU Settings
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
        
        # Common settings
        self.commonGroupBox = QtWidgets.QGroupBox("Common Settings")
        self.commonLayout = QtWidgets.QFormLayout(self.commonGroupBox)
        
        self.timeoutLabel = QtWidgets.QLabel("Timeout (seconds):")
        self.timeoutSpinBox = QtWidgets.QDoubleSpinBox()
        self.timeoutSpinBox.setRange(0.1, 10.0)
        self.timeoutSpinBox.setSingleStep(0.1)
        self.timeoutSpinBox.setValue(1.0)
        self.commonLayout.addRow(self.timeoutLabel, self.timeoutSpinBox)
        
        self.simulationModeCheckBox = QtWidgets.QCheckBox("Simulation Mode")
        self.commonLayout.addRow("", self.simulationModeCheckBox)
        
        self.layout.addWidget(self.commonGroupBox)
        
        # Status indicator
        self.statusGroupBox = QtWidgets.QGroupBox("Connection Status")
        self.statusLayout = QtWidgets.QHBoxLayout(self.statusGroupBox)
        
        self.statusLabel = QtWidgets.QLabel("Not Connected")
        self.statusLabel.setStyleSheet("color: red; font-weight: bold;")
        self.statusLayout.addWidget(self.statusLabel)
        
        self.layout.addWidget(self.statusGroupBox)
        
        # Create button layout - ONLY ONCE
        self.buttonLayout = QtWidgets.QHBoxLayout()
        self.testButton = QtWidgets.QPushButton("Test Connection")
        self.saveButton = QtWidgets.QPushButton("Save")
        self.cancelButton = QtWidgets.QPushButton("Cancel")
        
        self.buttonLayout.addWidget(self.testButton)
        self.buttonLayout.addWidget(self.saveButton)
        self.buttonLayout.addWidget(self.cancelButton)
        
        # Add the buttons to the main layout
        self.layout.addLayout(self.buttonLayout)
        
        # Connect the buttons to methods
        self.testButton.clicked.connect(self._test_connection)
        self.saveButton.clicked.connect(self._save_settings_simple)
        self.cancelButton.clicked.connect(self.reject)
        
        # Connect radio buttons to update settings visibility
        self.tcpRadio.toggled.connect(self._update_settings_visibility)
        
        # Initialize form
        self._initialize_serial_ports()
        self._initialize_form_values()
    
    def _initialize_serial_ports(self):
        """Populate serial ports dropdown"""
        ports = QtSerialPort.QSerialPortInfo.availablePorts()
        if ports:
            for port in ports:
                self.portComboBox.addItem(port.portName())
        else:
            logger.warning("No serial ports detected. Adding default COM port options.")
            for i in range(1, 10):
                self.portComboBox.addItem(f"COM{i}")
    
    def _initialize_form_values(self):
        """Load current settings into form"""
        # Set connection type
        connection_type = pool.config('plc/connection_type', str, 'rtu')
        if connection_type == 'tcp':
            self.tcpRadio.setChecked(True)
        else:
            self.rtuRadio.setChecked(True)
        
        # Set RTU-specific values
        self.portComboBox.setCurrentText(pool.config('plc/port', str, 'COM1'))
        self.baudrateComboBox.setCurrentText(str(pool.config('plc/baudrate', int, 9600)))
        self.bytesizeComboBox.setCurrentText(str(pool.config('plc/bytesize', int, 8)))
        self.parityComboBox.setCurrentText(pool.config('plc/parity', str, 'N'))
        self.stopbitsComboBox.setCurrentText(str(pool.config('plc/stopbits', float, 1.0)))
        
        # Set TCP-specific values
        self.hostLineEdit.setText(pool.config('plc/host', str, 'localhost'))
        self.tcpPortSpinBox.setValue(pool.config('plc/tcp_port', int, 502))
        
        # Set common values
        self.timeoutSpinBox.setValue(pool.config('plc/timeout', float, 1.0))
        self.simulationModeCheckBox.setChecked(pool.config('plc/simulation_mode', bool, False))
        
        # Update connection status
        self._update_connection_status()
    
    def _update_settings_visibility(self):
        """Show appropriate settings based on connection type"""
        if self.tcpRadio.isChecked():
            self.stackedLayout.setCurrentIndex(0)
        else:
            self.stackedLayout.setCurrentIndex(1)
    
    def _update_connection_status(self):
        """Update the connection status indicator"""
        # Check if we're in simulation mode
        is_demo = pool.config('demo', bool, False)
        is_simulation = pool.config('plc/simulation_mode', bool, False)
        
        if is_demo or is_simulation:
            self.statusLabel.setText("SIMULATION MODE (No real connection)")
            self.statusLabel.setStyleSheet("color: orange; font-weight: bold;")
        elif plc_communication.is_connected():
            self.statusLabel.setText("Connected")
            self.statusLabel.setStyleSheet("color: green; font-weight: bold;")
        else:
            self.statusLabel.setText("Not Connected")
            self.statusLabel.setStyleSheet("color: red; font-weight: bold;")
    
    def _test_connection(self):
        """Test the connection with current settings"""
        try:
            # Temporarily save current simulation status
            current_simulation_mode = pool.config('plc/simulation_mode', bool, False)
            current_demo_mode = pool.config('demo', bool, False)
            
            # Show a "Testing..." status
            self.statusLabel.setText("Testing connection...")
            self.statusLabel.setStyleSheet("color: blue; font-weight: bold;")
            QApplication.processEvents()  # Ensure UI updates
            
            # Save settings but just for testing
            self._save_settings_simple(test_only=True)
            
            # Temporarily disable simulation for a real connection test
            # Only if we're not in demo mode
            if not current_demo_mode:
                pool.set_config('plc/simulation_mode', False)
            
            # Try to connect with the test settings
            success = plc_communication.initialize_plc_communication()
            
            # Restore the original simulation mode setting
            pool.set_config('plc/simulation_mode', current_simulation_mode)
            
            # Show result
            if success:
                self.statusLabel.setText("Connected successfully")
                self.statusLabel.setStyleSheet("color: green; font-weight: bold;")
                
                # Add connection details to the message
                if current_demo_mode or current_simulation_mode:
                    QtWidgets.QMessageBox.information(
                        self,
                        "Connection Test",
                        "Connection test passed in SIMULATION mode.\n\n" +
                        "Note: This is not testing a physical connection."
                    )
                else:
                    QtWidgets.QMessageBox.information(
                        self,
                        "Connection Test",
                        "Successfully connected to PLC."
                    )
            else:
                self.statusLabel.setText("Connection failed")
                self.statusLabel.setStyleSheet("color: red; font-weight: bold;")
                QtWidgets.QMessageBox.warning(
                    self,
                    "Connection Test",
                    "Failed to connect to PLC. Check your settings."
                )
        
        except Exception as e:
            logger.error(f"Error testing connection: {e}")
            self.statusLabel.setText("Connection error")
            self.statusLabel.setStyleSheet("color: red; font-weight: bold;")
            QtWidgets.QMessageBox.critical(
                self,
                "Connection Test Error",
                f"An error occurred while testing the connection: {str(e)}"
            )
            
            # Make sure simulation status is restored on error
            pool.set_config('plc/simulation_mode', current_simulation_mode)
    
    def _save_settings_simple(self, test_only=False):
        """Save settings directly to config without triggering recursion"""
        try:
            # Get connection type based on radio button instead of tabs
            connection_type = 'tcp' if self.tcpRadio.isChecked() else 'rtu'
            
            # Direct settings update using QSettings
            settings = QSettings('RaspPiHandler', 'RaspPiModbusReader')
            
            # Save connection type
            settings.setValue('plc/connection_type', connection_type)
            
            # Save simulation mode
            settings.setValue('plc/simulation_mode', self.simulationModeCheckBox.isChecked())
            
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
            settings.sync()
            
            # Update the database directly using SQLite
            if not test_only:
                try:
                    # Connect directly to the database
                    conn = sqlite3.connect("local_database.db")
                    cursor = conn.cursor()
                    
                    # Check if the plc_comm_settings table exists
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='plc_comm_settings'")
                    if not cursor.fetchone():
                        # Create the table if it doesn't exist
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
            
            # Initialize the PLC communication with new settings
            if not test_only:
                success = plc_communication.initialize_plc_communication()
                if success:
                    self.accept()
                else:
                    QtWidgets.QMessageBox.warning(
                        self,
                        "PLC Communication Error",
                        "Failed to initialize PLC communication with new settings."
                    )
            
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