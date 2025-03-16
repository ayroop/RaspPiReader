
import logging
import sqlite3
import sys
import os
import threading
from PyQt5 import QtWidgets, QtCore, QtSerialPort
from PyQt5.QtCore import QSettings, QTimer
from PyQt5.QtWidgets import QApplication, QDialog
from PyQt5.QtGui import QFont
from RaspPiReader import pool
from RaspPiReader.libs import plc_communication
from RaspPiReader.libs.database import Database
from RaspPiReader.libs.models import PLCCommSettings

# Import the asynchronous test connection worker
from RaspPiReader.libs.connection_test_worker import TestConnectionWorker

logger = logging.getLogger(__name__)

class PLCCommSettingsFormHandler(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super(PLCCommSettingsFormHandler, self).__init__(parent)
        
        # Set up the dialog
        self.setWindowTitle("PLC Communication Settings")
        self.setModal(True)
        self.plc_init_worker = None   # Worker to initialize the PLC connection
        self.test_worker = None       # Worker to perform test connection (from button)
        self.status_worker = None     # Worker to update connection status asynchronously
        
        # Build UI and connect signals
        self._create_ui_elements()
        self._connect_signals()
        
        # After creation, initialize serial ports, load saved settings, and update UI
        self._initialize_serial_ports()
        self._initialize_form_values()
        self._update_settings_visibility()
        self._update_connection_status()
        self.resize(450, 380)
        
        logger.info("PLC Communication Settings dialog initialized")
    
    def _create_ui_elements(self):
        """Create all UI elements (organized into groups and stacked widgets)."""
        self.layout = QtWidgets.QVBoxLayout(self)
        
        # Communication Mode
        self.modeGroupBox = QtWidgets.QGroupBox("Communication Mode")
        self.modeLayout = QtWidgets.QHBoxLayout(self.modeGroupBox)
        self.tcpRadio = QtWidgets.QRadioButton("TCP/IP")
        self.rtuRadio = QtWidgets.QRadioButton("RTU (Serial)")
        self.modeLayout.addWidget(self.tcpRadio)
        self.modeLayout.addWidget(self.rtuRadio)
        self.layout.addWidget(self.modeGroupBox)
        
        # Stacked layout: one for TCP settings, one for RTU settings
        self.stackedLayout = QtWidgets.QStackedLayout()
        # TCP settings
        self.tcpWidget = QtWidgets.QWidget()
        self.tcpLayout = QtWidgets.QFormLayout(self.tcpWidget)
        self.hostLabel = QtWidgets.QLabel("Host:")
        self.hostLineEdit = QtWidgets.QLineEdit()
        self.tcpLayout.addRow(self.hostLabel, self.hostLineEdit)
        self.tcpPortLabel = QtWidgets.QLabel("Port:")
        self.tcpPortSpinBox = QtWidgets.QSpinBox()
        self.tcpPortSpinBox.setRange(1, 65535)
        self.tcpPortSpinBox.setValue(502)
        self.tcpLayout.addRow(self.tcpPortLabel, self.tcpPortSpinBox)
        self.stackedLayout.addWidget(self.tcpWidget)
        # RTU settings
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
        
        # Common Settings (timeout value)
        self.commonGroupBox = QtWidgets.QGroupBox("Common Settings")
        self.commonLayout = QtWidgets.QFormLayout(self.commonGroupBox)
        self.timeoutLabel = QtWidgets.QLabel("Timeout (seconds):")
        self.timeoutSpinBox = QtWidgets.QDoubleSpinBox()
        self.timeoutSpinBox.setRange(0.1, 10.0)
        self.timeoutSpinBox.setSingleStep(0.1)
        # Use a default timeout value suitable for your environment (6 seconds here)
        self.timeoutSpinBox.setValue(6.0)
        self.commonLayout.addRow(self.timeoutLabel, self.timeoutSpinBox)
        self.layout.addWidget(self.commonGroupBox)
        
        # Connection Status indicator
        self.statusGroupBox = QtWidgets.QGroupBox("Connection Status")
        self.statusLayout = QtWidgets.QHBoxLayout(self.statusGroupBox)
        self.statusLabel = QtWidgets.QLabel("Not Connected")
        self.statusLabel.setStyleSheet("color: red; font-weight: bold;")
        self.statusLayout.addWidget(self.statusLabel)
        self.layout.addWidget(self.statusGroupBox)
        
        # Action buttons
        self.buttonLayout = QtWidgets.QHBoxLayout()
        self.testButton = QtWidgets.QPushButton("Test Connection")
        self.saveButton = QtWidgets.QPushButton("Save")
        self.cancelButton = QtWidgets.QPushButton("Cancel")
        self.buttonLayout.addWidget(self.testButton)
        self.buttonLayout.addWidget(self.saveButton)
        self.buttonLayout.addWidget(self.cancelButton)
        self.layout.addLayout(self.buttonLayout)
    
    def _connect_signals(self):
        """Connect UI signals to corresponding methods."""
        self.testButton.clicked.connect(self._test_connection)
        self.saveButton.clicked.connect(self.save_and_close)
        self.cancelButton.clicked.connect(self.reject)
        self.tcpRadio.toggled.connect(self._update_settings_visibility)
    
    def _initialize_serial_ports(self):
        """Populate the serial ports combobox with available ports, or fall back to defaults."""
        self.portComboBox.clear()
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
        """Load saved connection settings from QSettings or pool default."""
        settings = QSettings('RaspPiHandler', 'RaspPiModbusReader')
        connection_type = settings.value('plc/connection_type') or pool.config('plc/connection_type', str, 'tcp')
        logger.info(f"Loading connection type: {connection_type}")
        if connection_type == 'tcp':
            self.tcpRadio.setChecked(True)
        else:
            self.rtuRadio.setChecked(True)
        
        # TCP settings
        host = settings.value('plc/host') or pool.config('plc/host', str, '127.0.0.1')
        tcp_port = settings.value('plc/tcp_port') or pool.config('plc/tcp_port', int, 502)
        self.hostLineEdit.setText(host)
        self.tcpPortSpinBox.setValue(int(tcp_port))
        # Timeout
        timeout = settings.value('plc/timeout') or pool.config('plc/timeout', float, 6.0)
        self.timeoutSpinBox.setValue(float(timeout))
        
        # RTU settings (if applicable)
        port = settings.value('plc/port') or pool.config('plc/port', str, 'COM1')
        baudrate = settings.value('plc/baudrate') or pool.config('plc/baudrate', int, 9600)
        bytesize = settings.value('plc/bytesize') or pool.config('plc/bytesize', int, 8)
        parity = settings.value('plc/parity') or pool.config('plc/parity', str, 'N')
        stopbits = settings.value('plc/stopbits') or pool.config('plc/stopbits', float, 1.0)
        port_index = self.portComboBox.findText(port)
        if port_index >= 0:
            self.portComboBox.setCurrentIndex(port_index)
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
        
        logger.info(f"Form initialized with connection type: {connection_type}")
    
    def _update_settings_visibility(self):
        """Switch the displayed settings based on the selected connection mode."""
        if self.tcpRadio.isChecked():
            self.stackedLayout.setCurrentIndex(0)
        else:
            self.stackedLayout.setCurrentIndex(1)
    
    def _update_connection_status(self):
        """Update connection status asynchronously using TestConnectionWorker.
           This method fires off an asynchronous check without blocking the UI.
        """
        try:
            connection_type = 'tcp' if self.tcpRadio.isChecked() else 'rtu'
            params = self._get_current_connection_params()
            self.statusLabel.setText("Testing connection...")
            self.statusLabel.setStyleSheet("color: blue; font-weight: bold;")
            QApplication.processEvents()
            
            # Use a longer timeout for the background status check
            # This avoids false negatives during form initialization
            if 'timeout' in params:
                # Make a copy to avoid modifying the original
                params = params.copy()
                # Use a slightly longer timeout for status checks
                params['timeout'] = min(params['timeout'] * 1.5, 10.0)
                
            logger.debug(f"Updating connection status with params: {params}")
            self.status_worker = TestConnectionWorker(connection_type, params, parent=self)
            self.status_worker.testResult.connect(self._handle_status_result)
            self.status_worker.start()
        except Exception as e:
            logger.error(f"Connection status test error: {e}")
            self.statusLabel.setText("Connection Error")
            self.statusLabel.setStyleSheet("color: red; font-weight: bold;")
    
    def _handle_status_result(self, success, error_msg):
        if success:
            self.statusLabel.setText("Connected")
            self.statusLabel.setStyleSheet("color: green; font-weight: bold;")
        else:
            self.statusLabel.setText("Not Connected")
            self.statusLabel.setStyleSheet("color: red; font-weight: bold;")
    
    def _get_current_connection_params(self):
        """Retrieve current connection parameters from the form fields."""
        params = {}
        params['timeout'] = self.timeoutSpinBox.value()
        if self.tcpRadio.isChecked():
            params['host'] = self.hostLineEdit.text().strip()
            params['port'] = self.tcpPortSpinBox.value()
        else:
            params['port'] = self.portComboBox.currentText()
            params['baudrate'] = int(self.baudrateComboBox.currentText())
            params['bytesize'] = int(self.bytesizeComboBox.currentText())
            params['parity'] = self.parityComboBox.currentText()
            params['stopbits'] = float(self.stopbitsComboBox.currentText())
        return params
    
    def _test_connection(self):
        """Test the connection asynchronously using TestConnectionWorker.
           The overall test timeout is set to the configured timeout plus a buffer.
        """
        try:
            self._set_buttons_enabled(False)
            self._update_status_label("Testing connection...", "blue")
            self._show_progress_bar()

            self.test_timeout_timer = QTimer(self)
            self.test_timeout_timer.setSingleShot(True)
            self.test_timeout_timer.timeout.connect(self._handle_test_timeout)

            connection_type = 'tcp' if self.tcpRadio.isChecked() else 'rtu'
            params = self._get_current_connection_params()
            logger.info(f"Performing CONNECTION TEST with: {connection_type}, params: {params}")

            # Use the actual timeout from the form, add a buffer (+3000ms) to ensure worker has time to complete
            self.test_worker = TestConnectionWorker(connection_type, params, parent=self)
            self.test_worker.testResult.connect(self._handle_test_result)
            timeout_value = params.get('timeout', 6.0)
            test_timeout = int(timeout_value * 1000 + 3000)  # Increased buffer time
            
            # Set a minimum test timeout to avoid premature timeouts
            test_timeout = max(test_timeout, 8000)  # At least 8 seconds
            
            logger.info(f"Starting connection test with timeout of {test_timeout}ms")
            self.test_timeout_timer.start(test_timeout)
            self.test_worker.start()
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
        logger.error("PLC connection test timed out")
        self._cleanup_after_test()
        self._update_status_label("Test Timeout", "red")
        
        # Get the current timeout value for better error reporting
        timeout_value = self.timeoutSpinBox.value()
        connection_type = 'TCP' if self.tcpRadio.isChecked() else 'RTU'
        
        QtWidgets.QMessageBox.warning(
            self,
            "Test Timeout",
            f"The connection test timed out after {timeout_value + 3.0} seconds.\n\n"
            f"This may indicate that the PLC is not responding or the {connection_type} "
            f"connection parameters are incorrect.\n\n"
            "Please check your settings and ensure the PLC is reachable."
        )
    
    def _handle_test_result(self, success, error_msg=None):
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
            
            # Prepare a more detailed error message based on the connection type
            connection_type = 'TCP/IP' if self.tcpRadio.isChecked() else 'Serial RTU'
            
            if self.tcpRadio.isChecked():
                host = self.hostLineEdit.text().strip()
                port = self.tcpPortSpinBox.value()
                message = f"Failed to connect to PLC using {connection_type} at {host}:{port}.\n\n"
            else:
                port = self.portComboBox.currentText()
                baudrate = self.baudrateComboBox.currentText()
                message = f"Failed to connect to PLC using {connection_type} on port {port} at {baudrate} baud.\n\n"
                
            message += "Please check your settings and ensure the device is connected and powered on."
            
            # Add specific troubleshooting tips based on error message
            if error_msg:
                message += f"\n\nError details: {error_msg}"
                
                # Add specific troubleshooting tips based on common errors
                if "Connection refused" in error_msg:
                    message += "\n\nTroubleshooting tips:\n" \
                              "- Verify the PLC is powered on and connected to the network\n" \
                              "- Check if the IP address and port are correct\n" \
                              "- Ensure no firewall is blocking the connection"
                elif "timed out" in error_msg.lower():
                    message += "\n\nTroubleshooting tips:\n" \
                              "- Try increasing the timeout value\n" \
                              "- Check network connectivity to the PLC\n" \
                              "- Verify the PLC is responding to Modbus requests"
            
            QtWidgets.QMessageBox.warning(
                self,
                "Connection Test Failed",
                message
            )
    
    def _set_buttons_enabled(self, enabled):
        self.testButton.setEnabled(enabled)
        self.saveButton.setEnabled(enabled)
        self.cancelButton.setEnabled(enabled)
    
    def _update_status_label(self, text, color):
        self.statusLabel.setText(text)
        self.statusLabel.setStyleSheet(f"color: {color}; font-weight: bold;")
    
    def _show_progress_bar(self):
        self.progressBar = QtWidgets.QProgressBar(self)
        self.progressBar.setRange(0, 0)
        self.progressBar.setTextVisible(False)
        self.statusLayout.addWidget(self.progressBar)
        QApplication.processEvents()
    
    def _cleanup_after_test(self):
        if hasattr(self, 'progressBar') and self.progressBar is not None:
            self.progressBar.setParent(None)
            self.progressBar = None
        self._set_buttons_enabled(True)
    
    def _save_settings_simple(self, test_only=False):
        try:
            connection_type = 'tcp' if self.tcpRadio.isChecked() else 'rtu'
            logger.info(f"Saving settings - Connection Type: {connection_type}")
            settings = QSettings('RaspPiHandler', 'RaspPiModbusReader')
            settings.setValue('plc/connection_type', connection_type)
            
            if connection_type == 'rtu':
                port_value = self.portComboBox.currentText()
                settings.setValue('plc/port', port_value)
                settings.setValue('plc/baudrate', int(self.baudrateComboBox.currentText()))
                settings.setValue('plc/bytesize', int(self.bytesizeComboBox.currentText()))
                settings.setValue('plc/parity', self.parityComboBox.currentText())
                settings.setValue('plc/stopbits', float(self.stopbitsComboBox.currentText()))
            else:
                tcp_host = self.hostLineEdit.text().strip()
                tcp_port = self.tcpPortSpinBox.value()
                settings.setValue('plc/host', tcp_host)
                settings.setValue('plc/tcp_port', tcp_port)
            
            settings.setValue('plc/timeout', self.timeoutSpinBox.value())
            settings.sync()
            
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
            
            if not test_only:
                try:
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
                                VALUES (?, NULL, NULL, ?, ?, ?, ?, ?)
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
        if self._save_settings_simple(test_only=False):
            self.saveButton.setEnabled(False)
            self.cancelButton.setEnabled(False)
            self.testButton.setEnabled(False)
            self.statusLabel.setText("Connecting...")
            self.statusLabel.setStyleSheet("color: blue; font-weight: bold;")
            self.progressBar = QtWidgets.QProgressBar(self)
            self.progressBar.setRange(0, 0)
            self.progressBar.setTextVisible(False)
            self.statusLayout.addWidget(self.progressBar)
            QApplication.processEvents()
            
            self.connection_timeout_timer = QTimer(self)
            self.connection_timeout_timer.setSingleShot(True)
            self.connection_timeout_timer.timeout.connect(self._handle_connection_timeout)
            
            def init_callback(success, error):
                if not success:
                    logger.error(f"PLC initialization error: {error}")
                QTimer.singleShot(0, lambda: self._handle_init_result(success))
                QTimer.singleShot(0, self.connection_timeout_timer.stop)
            
            logger.info("Initializing PLC communication with new settings (async)")
            self.plc_init_worker = plc_communication.initialize_plc_communication_async(callback=init_callback)
            
            timeout_value = self.timeoutSpinBox.value()
            connection_timeout = max(int(timeout_value * 1000) + 2000, 5000)
            self.connection_timeout_timer.start(connection_timeout)
    
    def _handle_connection_timeout(self):
        logger.error("PLC connection initialization timed out")
        self.saveButton.setEnabled(True)
        self.cancelButton.setEnabled(True)
        self.testButton.setEnabled(True)
        if hasattr(self, 'progressBar') and self.progressBar is not None:
            self.progressBar.setParent(None)
            self.progressBar = None
        self.statusLabel.setText("Connection Timeout")
        self.statusLabel.setStyleSheet("color: red; font-weight: bold;")
        
        # Get the current timeout value for better error reporting
        timeout_value = self.timeoutSpinBox.value()
        connection_type = 'TCP/IP' if self.tcpRadio.isChecked() else 'Serial RTU'
        
        if self.tcpRadio.isChecked():
            host = self.hostLineEdit.text().strip()
            port = self.tcpPortSpinBox.value()
            details = f"Host: {host}, Port: {port}"
        else:
            port = self.portComboBox.currentText()
            baudrate = self.baudrateComboBox.currentText()
            details = f"Port: {port}, Baudrate: {baudrate}"
        
        QtWidgets.QMessageBox.warning(
            self,
            "Connection Timeout",
            f"The connection attempt timed out after {timeout_value + 2.0} seconds.\n\n"
            f"Connection type: {connection_type}\n"
            f"Connection details: {details}\n\n"
            "Please check your settings and ensure the PLC is reachable. "
            "You may need to increase the timeout value if the PLC has a slow response time."
        )
    
    def _handle_init_result(self, success):
        self.saveButton.setEnabled(True)
        self.cancelButton.setEnabled(True)
        self.testButton.setEnabled(True)
        if hasattr(self, 'progressBar') and self.progressBar is not None:
            self.progressBar.setParent(None)
            self.progressBar = None
        self.plc_init_worker = None
        if success:
            logger.info("PLC communication initialized successfully")
            from RaspPiReader.libs import plc_communication
            if plc_communication.connection_monitor is None:
                plc_communication.connection_monitor = plc_communication.ConnectionMonitor(self)
            plc_communication.connection_monitor.start(30000)
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
            
if __name__ == "__main__":
    app = QApplication(sys.argv)
    dlg = PLCCommSettingsFormHandler()
    dlg.show()
    sys.exit(app.exec_())
