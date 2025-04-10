import logging
import time
import threading
import socket
from threading import Lock
import pymodbus

# Global flag to track if boolean read success has been logged
boolean_data_success_logged = False
try:
    # Try to import from the new path structure (pymodbus 2.5.0+)
    from pymodbus.client import ModbusTcpClient, ModbusSerialClient
except ImportError:
    # Fall back to old import path for backward compatibility
    from pymodbus.client.sync import ModbusTcpClient, ModbusSerialClient
from pymodbus.exceptions import ConnectionException, ModbusIOException, ModbusException
from RaspPiReader import pool
from RaspPiReader.libs.communication import ModbusCommunication, dataReader, plc_lock
from PyQt5.QtCore import QSettings, QTimer, QObject, pyqtSignal, QThread, QCoreApplication, pyqtSlot
from PyQt5 import QtCore
from PyQt5.QtWidgets import QApplication

# Configure logger
logger = logging.getLogger(__name__)

# Global Modbus communication object - properly initialized
modbus_comm = ModbusCommunication(name="PLCCommunication")

# Direct Modbus client for more reliable communication
direct_client = None

# Flag to indicate if we're currently in the process of initializing
_initializing = False

# Global connection monitor instance
connection_monitor = None

# Connection retry settings
CONNECTION_RETRY_ATTEMPTS = 3
CONNECTION_RETRY_DELAY = 1  # seconds

class SimplifiedModbusTcp:
    """
    A simplified wrapper for ModbusTcpClient.
    Optimized for performance with fewer retries and minimal blocking.
    """
    def __init__(self, host="127.0.0.1", port=502, timeout=3.0, unit=1):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.unit = unit
        self.client = None
        self.connected = False
        self._create_client()
        
    def _create_client(self):
        try:
            # Try to import from the new path structure (pymodbus 2.5.0+)
            from pymodbus.client import ModbusTcpClient
        except ImportError:
            # Fall back to old import path for backward compatibility
            from pymodbus.client.sync import ModbusTcpClient
            
        self.client = ModbusTcpClient(
            host=self.host,
            port=self.port,
            timeout=self.timeout,
            retries=1,
            retry_on_empty=False,  # Avoid long waits for empty responses
            close_comm_on_error=False  # Keep connection open for recovery
        )
        
    def connect(self):
        with plc_lock:  # protect simultaneous attempts
            try:
                # Load current settings
                host = pool.config("plc/host", str, "127.0.0.1")
                port = pool.config("plc/tcp_port", int, 502)
                timeout = pool.config("plc/timeout", float, 6.0)
                logger.debug(f"Attempting connection with host={host}, port={port}, timeout={timeout}")
                
                # If client is missing or parameters differ, reinitialize
                if (not self.client) or (self.client.host != host) or (self.client.port != port) or (not self.connected):
                    # First, close any existing connection
                    if self.client and self.connected:
                        try:
                            self.client.close()
                        except:
                            pass
                            
                    # Try socket connection first to verify network connectivity
                    try:
                        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        sock.settimeout(min(timeout, 2.0))  # Use shorter timeout for initial test
                        logger.debug(f"Testing socket connection to {host}:{port}")
                        sock.connect((host, port))
                        sock.close()
                        logger.debug(f"Socket connection to {host}:{port} successful")
                    except Exception as se:
                        logger.error(f"Socket connection test failed: {se}")
                        self.connected = False
                        return False
                    
                    # Create new client
                    self.client = ModbusTcpClient(host, port=port, timeout=timeout)
                    logger.info(f"Modbus client reinitialized with {host}:{port} and timeout {timeout}")
                
                # Attempt connection every time so that stale connection is not used
                connected = self.client.connect()
                self.connected = connected
                if connected:
                    logger.info("Modbus client connected successfully.")
                    
                    # Perform a quick test read to verify connection is working
                    try:
                        result = self.client.read_holding_registers(1, 1, unit=1)
                        if result is None:
                            logger.warning("Test read after connect returned None")
                        elif result.isError():
                            logger.debug(f"Test read returned error (may be normal): {result}")
                            # Some errors are acceptable if they're valid Modbus exceptions
                            if hasattr(result, 'function_code') and result.function_code > 0:
                                logger.info("Received valid Modbus exception response, connection OK")
                            else:
                                logger.warning("Invalid response during test read")
                        else:
                            logger.debug(f"Test read successful: {result.registers}")
                    except Exception as e:
                        logger.warning(f"Test read after connect failed: {e}")
                        # We still consider the connection successful if connect() returned True,
                        # even if the test read failed
                else:
                    logger.warning("Modbus client connection failed.")
                    # Reset the client so that next attempt reinitializes it
                    self.client = None
                return connected
            except Exception as e:
                logger.error(f"Error during connect: {e}")
                self.connected = False
                self.client = None
                return False
            
    def disconnect(self):
        if self.client and self.connected:
            self.client.close()
            self.connected = False
            return True
        return False
        
    def read_holding_registers(self, address, count=1, unit=None):
        if not self.connected:
            if not self.connect():
                return None
        try:
            if unit is None:
                unit = self.unit
            response = self.client.read_holding_registers(address=address, count=count, unit=unit)
            if response and not response.isError():
                return response.registers
            else:
                # Don't log certain expected exception codes (gateway path unavailable, etc.)
                if not (hasattr(response, 'exception_code') and response.exception_code in [10, 11]):
                    logger.error(f"Error reading holding registers: {response}")
                return None
        except (socket.timeout, TimeoutError) as te:
            # Timeout errors are common enough to handle specifically
            logger.warning(f"Timeout reading holding registers at address {address}: {te}")
            self.connected = False
            return None
        except Exception as e:
            if not isinstance(e, (socket.timeout, TimeoutError)):
                logger.error(f"Exception during read_holding_registers: {e}")
            self.connected = False
            return None
            
    def read_input_registers(self, address, count=1, unit=None):
        if not self.connected:
            if not self.connect():
                return None
        try:
            if unit is None:
                unit = self.unit
            response = self.client.read_input_registers(address=address, count=count, unit=unit)
            if response and not response.isError():
                return response.registers
            else:
                if not (hasattr(response, 'exception_code') and response.exception_code in [10, 11]):
                    logger.error(f"Error reading input registers: {response}")
                return None
        except Exception as e:
            if not isinstance(e, (socket.timeout, TimeoutError)):
                logger.error(f"Exception during read_input_registers: {e}")
            self.connected = False
            return None
            
    def read_coils(self, address, count=1, unit=None):
        if not self.connected:
            if not self.connect():
                return None
        try:
            if unit is None:
                unit = self.unit
            response = self.client.read_coils(address=address, count=count, unit=unit)
            if response and not response.isError():
                return response.bits[:count]
            else:
                if not (hasattr(response, 'exception_code') and response.exception_code in [10, 11]):
                    logger.error(f"Error reading coils: {response}")
                return None
        except Exception as e:
            if not isinstance(e, (socket.timeout, TimeoutError)):
                logger.error(f"Exception during read_coils: {e}")
            self.connected = False
            return None
            
    def write_coil(self, address, value, unit=None):
        if not self.connected:
            if not self.connect():
                return False
        try:
            if unit is None:
                unit = self.unit
            response = self.client.write_coil(address=address, value=value, unit=unit)
            if response and not response.isError():
                return True
            else:
                if not (hasattr(response, 'exception_code') and response.exception_code in [10, 11]):
                    logger.error(f"Error writing coil: {response}")
                return False
        except Exception as e:
            if not isinstance(e, (socket.timeout, TimeoutError)):
                logger.error(f"Exception during write_coil: {e}")
            self.connected = False
            return False
            
    def write_register(self, address, value, unit=None):
        if not self.connected:
            if not self.connect():
                return False
        try:
            if unit is None:
                unit = self.unit
            response = self.client.write_register(address=address, value=value, unit=unit)
            if response and not response.isError():
                return True
            else:
                logger.error(f"Error writing register: {response}")
                return False
        except Exception as e:
            logger.error(f"Exception during write_register: {e}")
            self.connected = False
            return False
            
    def write_registers(self, address, values, unit=None):
        if not self.connected:
            if not self.connect():
                return False
        try:
            if unit is None:
                unit = self.unit
            response = self.client.write_registers(address=address, values=values, unit=unit)
            if response and not response.isError():
                return True
            else:
                logger.error(f"Error writing registers: {response}")
                return False
        except Exception as e:
            logger.error(f"Exception during write_registers: {e}")
            self.connected = False
            return False

class PLCInitWorker(QThread):
    # Signal to deliver (success: bool, error message: str)
    result = pyqtSignal(bool, str)

    def __init__(self, connection_type, config_params, parent=None):
        super(PLCInitWorker, self).__init__(parent)
        self.connection_type = connection_type
        self.config_params = config_params

    def run(self):
        success = False
        error_msg = ""
        try:
            if self.connection_type == 'tcp':
                host = self.config_params.get('host', '127.0.0.1')
                port = int(self.config_params.get('port', 502))
                timeout = float(self.config_params.get('timeout', 6.0))
                client = ModbusTcpClient(host=host, port=port, timeout=timeout)
                t0 = time.time()
                if client.connect():
                    logger.info(f"[PLCInitWorker] Connection established in {time.time()-t0:.3f} seconds")
                    rr = client.read_holding_registers(1, 1, unit=1)
                    if rr.isError():
                        error_msg = f"Test read error: {rr}"
                    else:
                        success = True
                    client.close()
                else:
                    error_msg = "Failed to connect with client"
            else:
                client = ModbusSerialClient(**self.config_params)
                t0 = time.time()
                if client.connect():
                    logger.info(f"[PLCInitWorker] Connection established in {time.time()-t0:.3f} seconds")
                    rr = client.read_holding_registers(1, 1, unit=1)
                    if rr.isError():
                        error_msg = f"Test read error: {rr}"
                    else:
                        success = True
                    client.close()
                else:
                    error_msg = "Failed to connect with client"
        except Exception as e:
            error_msg = str(e)
        self.result.emit(success, error_msg)

class ConnectionMonitor(QObject):
    """
    Connection monitor for the PLC communication.
    Periodically checks the connection and attempts to reconnect if necessary.
    All blocking reconnection attempts are offloaded using a background thread.
    """
    connection_changed = pyqtSignal(bool)
    
    def __init__(self, parent=None):
        super(ConnectionMonitor, self).__init__(parent)
        self.timer = None
        self.last_connection_state = False
        self.reconnection_in_progress = False
        self.consecutive_failures = 0
        self.check_interval = 10000  # Default: 10 seconds
        
    def start(self, interval=10000):
        if QThread.currentThread() != QCoreApplication.instance().thread():
            logger.error("ConnectionMonitor.start() must be called from the main (GUI) thread")
            return False
        self.check_interval = interval
        if self.timer is None:
            self.timer = QTimer()
            self.timer.timeout.connect(self.check_connection)
        # Use a shorter interval for initial verification:
        self.timer.start(min(2000, interval))
        logger.info(f"PLC connection monitor started with interval {interval}ms")
        return True
        
    def stop(self):
        if self.timer is not None:
            self.timer.stop()
            self.reconnection_in_progress = False
            self.consecutive_failures = 0
            logger.info("PLC connection monitor stopped")
        
    def check_connection(self):
        global _initializing
        if _initializing:
            return
        if self.reconnection_in_progress:
            return
        current_state = is_connected()
        if current_state != self.last_connection_state:
            logger.info(f"PLC connection state changed: {current_state}")
            self.connection_changed.emit(current_state)
            if current_state:
                self.consecutive_failures = 0
                if self.timer.interval() != self.check_interval:
                    self.timer.setInterval(self.check_interval)
                    logger.debug(f"Connection restored, resuming normal interval: {self.check_interval}ms")
        if not current_state:
            self.consecutive_failures += 1
            logger.warning(f"Connection lost (failure count: {self.consecutive_failures})")
            if self.consecutive_failures > 5:
                new_interval = min(self.check_interval * 2, 60000)
                if self.timer.interval() != new_interval:
                    logger.info(f"Multiple failures, extending check interval to {new_interval}ms")
                    self.timer.setInterval(new_interval)
            self._reconnect_in_thread()
        self.last_connection_state = current_state
            
    def _reconnect_in_thread(self):
        if self.reconnection_in_progress:
            logger.debug("Reconnection already in progress, skipping new attempt")
            return
        self.reconnection_in_progress = True
        def reconnect_and_clear_flag():
            try:
                result = ensure_connection()
                self.reconnection_in_progress = False
                return result
            except Exception as e:
                logger.error(f"Error in reconnection thread: {e}")
                self.reconnection_in_progress = False
                return False
        reconnect_thread = threading.Thread(target=reconnect_and_clear_flag, name="PLCReconnectThread", daemon=True)
        reconnect_thread.start()

def initialize_plc_communication():
    """Initialize PLC communication using configuration from pool"""
    global modbus_comm, _initializing, connection_monitor, direct_client
    with plc_lock:
        _initializing = True
        try:
            if dataReader.running:
                logger.info("Stopping DataReader before PLC initialization")
                dataReader.stop()
            connection_type = pool.config('plc/connection_type', str, 'tcp')
            logger.info(f"Initializing PLC communication - Connection type: {connection_type}")
            if connection_type == 'tcp':
                host = pool.config('plc/host', str, '127.0.0.1')
                port = pool.config('plc/tcp_port', int, 502)
                timeout = pool.config('plc/timeout', float, 6.0)
                logger.info(f"Initializing PLC with TCP host: {host}, port: {port}")
                config_params = {'host': host, 'port': port, 'timeout': timeout}
                if modbus_comm is None:
                    modbus_comm = ModbusCommunication(name="PLCCommunication")
                direct_client = SimplifiedModbusTcp(host=host, port=port, timeout=timeout, unit=1)
                logger.info("Attempting to connect with direct client")
                if direct_client.connect():
                    logger.info("Successfully connected with direct client")
                    modbus_comm.disconnect()
                    success = modbus_comm.configure(connection_type, **config_params)
                    if success:
                        modbus_comm.connect()
                        logger.info("Legacy client configured and connected successfully")
                    if not pool.config('demo', bool, False):
                        logger.info("Starting DataReader after successful PLC connection")
                        dataReader.start()
                    return True
                else:
                    logger.warning("Direct client connection failed, falling back to legacy approach")
            else:
                port_val = pool.config('plc/port', str, 'COM1')
                baudrate = pool.config('plc/baudrate', int, 9600)
                bytesize = pool.config('plc/bytesize', int, 8)
                parity = pool.config('plc/parity', str, 'N')
                stopbits = pool.config('plc/stopbits', float, 1.0)
                timeout = pool.config('plc/timeout', float, 6.0)
                logger.info(f"Initializing PLC with serial port: {port_val}")
                config_params = {'port': port_val, 'baudrate': baudrate, 'bytesize': bytesize, 'parity': parity, 'stopbits': stopbits, 'timeout': timeout}
                if modbus_comm is None:
                    modbus_comm = ModbusCommunication(name="PLCCommunication")
            logger.info("Using legacy approach for PLC communication")
            modbus_comm.disconnect()
            success = modbus_comm.configure(connection_type, **config_params)
            if success:
                logger.info(f"PLC communication configured with {connection_type}")
                success = modbus_comm.connect()
                if success:
                    logger.info("Successfully connected to PLC")
                    if not pool.config('demo', bool, False):
                        logger.info("Starting DataReader after successful PLC connection")
                        dataReader.start()
                else:
                    logger.error(f"Failed to connect to PLC: {modbus_comm.get_error()}")
            else:
                logger.error(f"Failed to configure PLC communication: {modbus_comm.get_error()}")
                success = False
            return success
        except Exception as e:
            logger.error(f"Error initializing PLC communication: {e}")
            return False
        finally:
            _initializing = False

def set_port(port):
    """Set the serial port for the PLC connection"""
    global modbus_comm
    with plc_lock:
        if modbus_comm:
            try:
                pool.set_config('plc/port', port)
                logger.info(f"Serial port set to {port}")
                return True
            except Exception as e:
                logger.error(f"Error setting serial port: {e}")
        return False

def is_connected():
    """
    Check if there is an active connection to the PLC.
    Returns True if active; otherwise, False.
    """
    global modbus_comm, direct_client
    if pool.config('demo', bool, False):
        logger.debug("Connection status: DEMO (always on)")
        return True
    with plc_lock:
        if direct_client is not None:
            try:
                result = direct_client.read_holding_registers(0, 1, 1)
                if result is not None:
                    logger.debug("Direct TCP connection status: OK")
                    return True
            except Exception as e:
                logger.debug(f"Direct connection test error: {e}")
        if not modbus_comm or not modbus_comm.is_configured():
            logger.debug("Connection status: OFF (no client or not configured)")
            return False
        if not modbus_comm.connected:
            logger.debug("Connection status: OFF (client reports not connected)")
            return False
        try:
            result = modbus_comm.read_registers(0, 1, 1, 'holding')
            connection_ok = (result is not None)
            logger.debug(f"{modbus_comm.connection_type.upper()} connection status check: {'OK' if connection_ok else 'FAILED'}")
            return connection_ok
        except Exception as e:
            logger.debug(f"{modbus_comm.connection_type.upper()} connection test error: {e}")
            return False

def ensure_connection():
    """
    Ensure that a connection to the PLC is available.
    This version avoids blocking the UI thread by skipping blocking reconnection attempts.
    """
    global modbus_comm, direct_client
    from PyQt5.QtCore import QCoreApplication, QThread

    # If demo mode is active, skip actual PLC connection.
    if pool.config('demo', bool, False):
        logger.info("Demo mode active; skipping PLC connection check.")
        return True

    # First, try using direct_client if available.
    if direct_client is not None:
        try:
            if direct_client.connect():
                logger.info("Successfully reconnected using direct client")
                return True
        except Exception as e:
            logger.error(f"Error during direct client reconnection: {e}")

    # Run reconnection attempts only if not on the UI thread.
    if QThread.currentThread() == QCoreApplication.instance().thread():
        logger.debug("ensure_connection() called on UI thread, skipping blocking reconnection attempts.")
        return getattr(modbus_comm, 'connected', False)

    # Now, use the modbus_comm with plc_lock.
    with plc_lock:
        if modbus_comm is None:
            logger.error("Modbus client not initialized; reinitializing now.")
            from RaspPiReader.libs.communication import ModbusCommunication
            modbus_comm = ModbusCommunication(name="PLCCommunication")
        # If already connected, simply return True.
        if getattr(modbus_comm, 'connected', False):
            return True
        # Not connected: proceed with reconnection attempts.
        logger.warning("Connection lost, attempting to reconnect...")
        for attempt in range(CONNECTION_RETRY_ATTEMPTS):
            if modbus_comm.connect():
                logger.info(f"Reconnection successful on attempt {attempt+1}")
                return True
            else:
                logger.warning(f"Reconnection attempt {attempt+1} failed; resetting client pointer.")
                modbus_comm.client = None
                time.sleep(CONNECTION_RETRY_DELAY)
        logger.error("Failed to reconnect after maximum attempts.")
        return False

def validate_device_id(device_id):
    """
    Validate that the device ID for Modbus (1-247) is proper.
    Defaults to 1 if invalid.
    """
    if not isinstance(device_id, int):
        logger.warning(f"Invalid device ID type: {type(device_id)}. Using default ID 1")
        return 1
    if device_id < 1 or device_id > 247:
        logger.warning(f"Invalid device ID value: {device_id}. Using default ID 1")
        return 1
    return device_id

def initialize_plc_communication_async(callback=None):
    """
    Initialize PLC communication asynchronously using a QThread worker.
    Reads parameters from pool and starts the worker.
    """
    connection_type = pool.config('plc/connection_type', str, 'tcp')
    if connection_type == 'tcp':
        host = pool.config('plc/host', str, '127.0.0.1')
        port = pool.config('plc/tcp_port', int, 502)
        timeout = pool.config('plc/timeout', float, 6.0)
        config_params = {'host': host, 'port': port, 'timeout': timeout}
        logger.info(f"Initializing PLC with TCP host: {host}, port: {port}")
    else:
        port_val = pool.config('plc/port', str, 'COM1')
        baudrate = pool.config('plc/baudrate', int, 9600)
        bytesize = pool.config('plc/bytesize', int, 8)
        parity = pool.config('plc/parity', str, 'N')
        stopbits = pool.config('plc/stopbits', float, 1.0)
        timeout = pool.config('plc/timeout', float, 6.0)
        config_params = {'port': port_val, 'baudrate': baudrate, 'bytesize': bytesize, 'parity': parity, 'stopbits': stopbits, 'timeout': timeout}
        logger.info(f"Initializing PLC with Serial port: {port_val}")
    worker = PLCInitWorker(connection_type, config_params, parent=QApplication.instance())
    if callback:
        worker.result.connect(lambda success, error: QTimer.singleShot(0, lambda: callback(success, error)))
    worker.start()
    return worker

def _initialize_plc_thread(callback=None):
    success = initialize_plc_communication()
    if callback:
        try:
            callback(success)
        except Exception as e:
            logger.error(f"Error in PLC initialization callback: {e}")
    return success

def read_coil(address, device_id=1):
    global modbus_comm, direct_client, boolean_data_success_logged
    device_id = validate_device_id(device_id)
    if direct_client is not None:
        try:
            coils = direct_client.read_coils(address, 1, device_id)
            if coils and len(coils) > 0:
                # Log success message only once
                if not boolean_data_success_logged:
                    logger.info("Boolean data is working!")
                    boolean_data_success_logged = True
                return coils[0]
        except Exception as e:
            logger.debug(f"Direct client read_coil error: {e}")
    with plc_lock:
        if not ensure_connection():
            logger.error("Cannot read coil: No connection to PLC")
            return False
        try:
            result = modbus_comm.read_bool_addresses(address, 1, device_id)
            if result and len(result) > 0:
                # Log success message only once
                if not boolean_data_success_logged:
                    logger.info("Boolean data is working!")
                    boolean_data_success_logged = True
                return result[0]
            return False
        except Exception as e:
            logger.error(f"Error reading coil at address {address}: {e}")
            return False

def read_coils(address, count=1, device_id=1):
    global modbus_comm, direct_client, boolean_data_success_logged
    device_id = validate_device_id(device_id)
    if direct_client is not None:
        try:
            coils = direct_client.read_coils(address, count, device_id)
            if coils and len(coils) >= count:
                # Log success message only once
                if not boolean_data_success_logged:
                    logger.info("Boolean data is working!")
                    boolean_data_success_logged = True
                return coils[:count]
        except Exception as e:
            logger.debug(f"Direct client read_coils error: {e}")
    with plc_lock:
        if not ensure_connection():
            logger.error("Cannot read coils: No connection to PLC")
            return [False] * count
        try:
            result = modbus_comm.read_bool_addresses(address, count, device_id)
            if result:
                # Log success message only once
                if not boolean_data_success_logged:
                    logger.info("Boolean data is working!")
                    boolean_data_success_logged = True
                return result
            return [False] * count
        except Exception as e:
            logger.error(f"Error reading {count} coils from address {address}: {e}")
            return [False] * count

def read_holding_register(address, device_id=1):
    global modbus_comm, direct_client
    device_id = validate_device_id(device_id)
    if direct_client is not None:
        try:
            registers = direct_client.read_holding_registers(address, 1, device_id)
            if registers and len(registers) > 0:
                return registers[0]
        except Exception as e:
            logger.debug(f"Direct client read_holding_register error: {e}")
    with plc_lock:
        if not ensure_connection():
            logger.error("Cannot read holding register: No connection to PLC")
            return None
        try:
            result = modbus_comm.read_registers(address, 1, device_id, 'holding')
            if result and len(result) > 0:
                return result[0]
            return None
        except Exception as e:
            logger.error(f"Error reading holding register at address {address}: {e}")
            return None

def write_coil(address, value, device_id=1):
    global modbus_comm, direct_client
    device_id = validate_device_id(device_id)
    if direct_client is not None:
        try:
            success = direct_client.write_coil(address, value, device_id)
            if success:
                return True
        except Exception as e:
            logger.debug(f"Direct client write_coil error: {e}")
    with plc_lock:
        if not ensure_connection():
            logger.error("Cannot write coil: No connection to PLC")
            return False
        try:
            return modbus_comm.write_bool_address(address, value, device_id)
        except Exception as e:
            logger.error(f"Error writing value {value} to coil at address {address}: {e}")
            return False

def read_holding_registers(address, count=1, device_id=1):
    global modbus_comm, direct_client
    device_id = validate_device_id(device_id)
    if direct_client is not None:
        try:
            registers = direct_client.read_holding_registers(address, count, device_id)
            if registers and len(registers) >= count:
                return registers
        except Exception as e:
            logger.debug(f"Direct client read_holding_registers error: {e}")
    with plc_lock:
        if not ensure_connection():
            logger.error("Cannot read registers: No connection to PLC")
            return None
        try:
            logger.debug(f"Reading {count} holding registers from address {address} with device ID {device_id}")
            result = modbus_comm.read_registers(address, count, device_id, 'holding')
            if result is not None:
                logger.debug(f"Successfully read registers: {result}")
                return result
            else:
                logger.error("Unknown error reading holding registers")
                return None
        except ModbusIOException as e:
            logger.error(f"IO error reading holding registers: {e}")
            if hasattr(modbus_comm, 'connected'):
                modbus_comm.connected = False
            return None
        except ConnectionException as e:
            logger.error(f"Connection error reading holding registers: {e}")
            if hasattr(modbus_comm, 'connected'):
                modbus_comm.connected = False
            return None
        except ModbusException as e:
            logger.error(f"Modbus protocol error reading holding registers: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error reading holding registers: {e}")
            return None

def read_input_register(address, device_id=1):
    global modbus_comm, direct_client
    device_id = validate_device_id(device_id)
    if direct_client is not None:
        try:
            registers = direct_client.read_input_registers(address, 1, device_id)
            if registers and len(registers) > 0:
                return registers[0]
        except Exception as e:
            logger.debug(f"Direct client read_input_register error: {e}")
    with plc_lock:
        if not ensure_connection():
            logger.error("Cannot read input register: No connection to PLC")
            return None
        try:
            result = modbus_comm.read_registers(address, 1, device_id, 'input')
            if result and len(result) > 0:
                return result[0]
            return None
        except Exception as e:
            logger.error(f"Error reading input register at address {address}: {e}")
            return None

def read_input_registers(address, count=1, device_id=1):
    global modbus_comm, direct_client
    device_id = validate_device_id(device_id)
    if direct_client is not None:
        try:
            registers = direct_client.read_input_registers(address, count, device_id)
            if registers and len(registers) >= count:
                return registers
        except Exception as e:
            logger.debug(f"Direct client read_input_registers error: {e}")
    with plc_lock:
        if not ensure_connection():
            logger.error("Cannot read registers: No connection to PLC")
            return None
        try:
            logger.debug(f"Reading {count} input registers from address {address} with device ID {device_id}")
            result = modbus_comm.read_registers(address, count, device_id, 'input')
            if result is not None:
                logger.debug(f"Successfully read registers: {result}")
                return result
            else:
                logger.error("Unknown error reading input registers")
                return None
        except ModbusIOException as e:
            logger.error(f"IO error reading input registers: {e}")
            if hasattr(modbus_comm, 'connected'):
                modbus_comm.connected = False
            return None
        except ConnectionException as e:
            logger.error(f"Connection error reading input registers: {e}")
            if hasattr(modbus_comm, 'connected'):
                modbus_comm.connected = False
            return None
        except ModbusException as e:
            logger.error(f"Modbus protocol error reading input registers: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error reading input registers: {e}")
            return None

def write_register(address, value, device_id=1):
    global modbus_comm, direct_client
    device_id = validate_device_id(device_id)
    if direct_client is not None:
        try:
            success = direct_client.write_register(address, value, device_id)
            if success:
                return True
        except Exception as e:
            logger.debug(f"Direct client write_register error: {e}")
    with plc_lock:
        if not ensure_connection():
            logger.error("Cannot write register: No connection to PLC")
            return False
        try:
            return modbus_comm.write_register(address, value, device_id)
        except Exception as e:
            logger.error(f"Error writing value {value} to register at address {address}: {e}")
            return False

def write_registers(address, values, device_id=1):
    global modbus_comm, direct_client
    device_id = validate_device_id(device_id)
    if direct_client is not None:
        try:
            if not isinstance(values, (list, tuple)):
                values = [values]
            success = direct_client.write_registers(address, values, device_id)
            if success:
                return True
        except Exception as e:
            logger.debug(f"Direct client write_registers error: {e}")
    with plc_lock:
        if not ensure_connection():
            logger.error("Cannot write registers: No connection to PLC")
            return False
        try:
            if not isinstance(values, (list, tuple)):
                values = [values]
            return modbus_comm.write_registers(address, values, device_id)
        except Exception as e:
            logger.error(f"Error writing values {values} to registers starting at address {address}: {e}")
            return False

def read_boolean(address, device_id=1):
    """
    Read a boolean value (coil) from the PLC using the shared Modbus client.
    This method leverages the PLCConnectionManager for connection management.
    
    Args:
        address (int): Address of the coil (1-based addressing)
        device_id (int): Unit ID of the slave
        
    Returns:
        bool or None: The boolean value, or None if an error occurred.
    """
    global modbus_comm, boolean_data_success_logged  # Access the global objects
    device_id = validate_device_id(device_id)

    with plc_lock:
        if not ensure_connection():
            logger.error("Cannot read boolean: No connection to PLC")
            return None

        try:
            # Use read_coils method to read boolean value
            result = modbus_comm.read_registers(address, 1, device_id, 'coil')
            if result and len(result) > 0:
                # Log success message only once
                if not boolean_data_success_logged:
                    logger.info("Boolean data is working!")
                    boolean_data_success_logged = True
                return result[0]
            else:
                logger.error(f"Error reading boolean from address {address}: {result}")
                return None
        except Exception as e:
            logger.exception(f"Exception reading boolean from address {address}: {e}")
            return None

def disconnect():
    """Disconnect from the PLC"""
    global modbus_comm, direct_client, connection_monitor
    with plc_lock:
        if connection_monitor is not None:
            connection_monitor.stop()
            connection_monitor = None
        if dataReader.running:
            logger.info("Stopping DataReader before disconnecting PLC")
            dataReader.stop()
        if direct_client is not None:
            try:
                direct_client.disconnect()
                logger.info("Successfully disconnected direct client")
            except Exception as e:
                logger.error(f"Error disconnecting direct client: {e}")
        try:
            if modbus_comm:
                result = modbus_comm.disconnect()
                if result:
                    logger.info("Successfully disconnected legacy client")
                return result
            return True
        except Exception as e:
            logger.error(f"Error disconnecting legacy client: {e}")
            return False

def write_bool_address(address, value, unit=1):
    """Write a boolean value to a coil (compatibility function)"""
    return write_coil(address, value, unit)

def read_bool_address(address, unit=1):
    """Read a boolean value from a coil (compatibility function)"""
    return read_boolean(address, unit)

def read_multiple_booleans(addresses, device_id=1):
    """
    Read multiple boolean values from the PLC in a single call.
    
    Args:
        addresses (list): List of addresses to read
        device_id (int): Unit ID of the slave
        
    Returns:
        dict: Dictionary mapping addresses to boolean values
    """
    device_id = validate_device_id(device_id)
    results = {}
    
    # If addresses are not sequential, read them individually
    if not all(addresses[i+1] == addresses[i]+1 for i in range(len(addresses)-1)):
        for address in addresses:
            results[address] = read_boolean(address, device_id)
        return results
    
    # For sequential addresses, try to read them in one request
    try:
        start_address = min(addresses)
        count = max(addresses) - start_address + 1
        
        # Try with direct_client first
        if direct_client is not None:
            try:
                coils = direct_client.read_coils(start_address, count, device_id)
                if coils and len(coils) >= count:
                    for i, address in enumerate(range(start_address, start_address + count)):
                        if address in addresses:
                            results[address] = coils[i]
                    return results
            except Exception as e:
                logger.debug(f"Direct client read_multiple_booleans error: {e}")
        
        # If direct client failed, try with a fresh ModbusTcpClient
        from RaspPiReader import pool
        host = pool.config('plc/host', str, '127.0.0.1')
        port = pool.config('plc/tcp_port', int, 502)
        timeout = pool.config('plc/timeout', float, 3.0)
        
        try:
            # Try to import from the new path structure (pymodbus 2.5.0+)
            from pymodbus.client import ModbusTcpClient
        except ImportError:
            # Fall back to old import path for backward compatibility
            from pymodbus.client.sync import ModbusTcpClient
            
        client = ModbusTcpClient(host=host, port=port, timeout=timeout)
        if not client.connect():
            logger.error(f"Failed to connect to Modbus server when reading multiple booleans")
            return {addr: None for addr in addresses}
        
        try:
            response = client.read_coils(start_address, count=count, unit=device_id)
            
            if response and not response.isError():
                for i, address in enumerate(range(start_address, start_address + count)):
                    if address in addresses:
                        results[address] = response.bits[i]
                return results
            else:
                logger.error(f"Error reading multiple booleans: {response}")
                return {addr: None for addr in addresses}
        finally:
            client.close()
    except Exception as e:
        logger.exception(f"Exception reading multiple booleans: {e}")
        # Fall back to individual reads if batch read fails
        for address in addresses:
            results[address] = read_boolean(address, device_id)
        return results

def test_connection(connection_type=None, simulation_mode=False, **params):
    global modbus_comm, direct_client
    logger.info("Testing connection (simulation_mode parameter ignored, using real connection)")
    if connection_type is None:
        connection_type = pool.config('plc/connection_type', str, 'tcp')
    if connection_type == 'tcp':
        required_params = ['host', 'port', 'timeout']
        for param in required_params:
            if param not in params:
                params[param] = pool.config(f'plc/{param if param!="port" else "tcp_port"}', str if param=='host' else (float if param=='timeout' else int))
        logger.info(f"Testing REAL TCP connection to {params.get('host')}:{params.get('port')}")
        if 'timeout' in params and params['timeout'] < 5.0:
            logger.info(f"Increasing timeout from {params['timeout']} to 5.0 seconds for testing")
            params['timeout'] = 5.0
    else:
        required_params = ['port', 'baudrate', 'bytesize', 'parity', 'stopbits', 'timeout']
        for param in required_params:
            if param not in params:
                params[param] = pool.config(f'plc/{param}', float if param in ['stopbits','timeout'] else (str if param in ['port','parity'] else int))
        logger.info(f"Testing REAL RTU connection to {params.get('port')}")
        if 'timeout' in params and params['timeout'] < 5.0:
            logger.info(f"Increasing timeout from {params['timeout']} to 5.0 seconds for testing")
            params['timeout'] = 5.0
    logger.info(f"Configuring test connection with params: {params}")
    if connection_type == 'tcp':
        host = params.get('host')
        port = int(params.get('port',502))
        timeout = float(params.get('timeout', 6.0))
        
        # First try a basic socket connection to verify network connectivity
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(min(timeout, 2.0))  # Use shorter timeout for socket test
            logger.info(f"Testing socket connection to {host}:{port}")
            sock.connect((host, port))
            sock.close()
            logger.info(f"Socket connection to {host}:{port} successful")
        except Exception as se:
            logger.error(f"Socket connection test failed: {se}")
            return False
            
        try:
            client = ModbusTcpClient(host=host, port=port, timeout=timeout, retries=1, retry_on_empty=False)
            t0 = time.time()
            if client.connect():
                logger.info(f"Connection established in {time.time()-t0:.3f} seconds, performing test read")
                try:
                    read_start = time.time()
                    result = client.read_holding_registers(1, 1, unit=1)
                    read_time = time.time()-read_start
                    
                    if result is None:
                        logger.error("REAL connection test failed - register read returned None")
                        client.close()
                        return False
                    elif result.isError():
                        # Check if this is a valid Modbus exception response
                        if hasattr(result, 'function_code') and result.function_code > 0:
                            logger.info("Received valid Modbus exception response, connection OK")
                            # Initialize the direct client
                            if direct_client is None:
                                direct_client = SimplifiedModbusTcp(host=host, port=port, timeout=timeout, unit=1)
                            else:
                                direct_client.host = host
                                direct_client.port = port
                                direct_client.timeout = timeout
                            direct_client.connect()
                            
                            # Initialize the legacy client
                            if modbus_comm is None:
                                modbus_comm = ModbusCommunication(name="PLCCommunication")
                            if modbus_comm:
                                config_params = {'host': host, 'port': port, 'timeout': timeout}
                                modbus_comm.disconnect()
                                modbus_comm.configure('tcp', **config_params)
                                modbus_comm.connect()
                            client.close()
                            return True
                        else:
                            logger.error(f"REAL connection test failed - register read returned error: {result}")
                            client.close()
                            return False
                    else:
                        logger.info(f"REAL connection test successful - register read returned: {result.registers} in {read_time:.3f} seconds")
                        if direct_client is None:
                            direct_client = SimplifiedModbusTcp(host=host, port=port, timeout=timeout, unit=1)
                        else:
                            direct_client.host = host
                            direct_client.port = port
                            direct_client.timeout = timeout
                        direct_client.connect()
                        if modbus_comm is None:
                            modbus_comm = ModbusCommunication(name="PLCCommunication")
                        if modbus_comm:
                            config_params = {'host': host, 'port': port, 'timeout': timeout}
                            modbus_comm.disconnect()
                            modbus_comm.configure('tcp', **config_params)
                            modbus_comm.connect()
                        client.close()
                        return True
                except Exception as e:
                    logger.error(f"REAL connection test failed - register read failed with error: {e}")
                    client.close()
                    return False
            else:
                logger.error(f"Connection failed after {time.time()-t0:.3f} seconds - could not connect to TCP device")
                return False
        except Exception as e:
            logger.error(f"Error during TCP connection test: {e}")
            return False
    else:
        test_comm = ModbusCommunication(name="ConnectionTest")
        t0 = time.time()
        success = test_comm.configure(connection_type, **params)
        logger.info(f"Test connection configured in {time.time()-t0:.3f} seconds")
        if not success:
            logger.error(f"Failed to configure test connection: {test_comm.get_error()}")
            return False
        try:
            t0 = time.time()
            if not test_comm.connect():
                logger.error(f"Connection failed after {time.time()-t0:.3f} seconds - could not connect to {connection_type.upper()} device: {test_comm.get_error()}")
                return False
            logger.info(f"Connection established in {time.time()-t0:.3f} seconds, performing test read")
            try:
                t0 = time.time()
                result = test_comm.read_registers(0, 1, 1, 'holding')
                if result is not None:
                    logger.info(f"REAL connection test successful - register read returned: {result} in {time.time()-t0:.3f} seconds")
                    if modbus_comm is None:
                        modbus_comm = ModbusCommunication(name="PLCCommunication")
                    modbus_comm.disconnect()
                    modbus_comm.configure(connection_type, **params)
                    modbus_comm.connect()
                    test_comm.disconnect()
                    return True
                else:
                    logger.error("REAL connection test failed - register read returned None")
                    test_comm.disconnect()
                    return False
            except Exception as e:
                logger.error(f"REAL connection test failed - register read failed with error: {e}")
                test_comm.disconnect()
                return False
            t0 = time.time()
            test_comm.disconnect()
            logger.info(f"Test connection disconnected in {time.time()-t0:.3f} seconds")
            return True
        except Exception as e:
            logger.error(f"Error during connection test: {e}")
            return False

def start_connection_monitor(interval=30000):
    global connection_monitor
    if connection_monitor is None:
        connection_monitor = ConnectionMonitor(parent=QApplication.instance())
    if connection_monitor.start(interval):
        logger.info(f"PLC connection monitor started with interval {interval}ms")
        return True
    return False
