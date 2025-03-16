import logging
import time
import threading
from threading import Lock
import pymodbus
from pymodbus.client.sync import ModbusTcpClient, ModbusSerialClient
from pymodbus.exceptions import ConnectionException, ModbusIOException, ModbusException
from RaspPiReader import pool
from RaspPiReader.libs.communication import ModbusCommunication, dataReader, plc_lock
from PyQt5.QtCore import QSettings, QTimer, QObject, pyqtSignal
from PyQt5 import QtCore
from PyQt5.QtWidgets import QApplication

# Configure logger
logger = logging.getLogger(__name__)

# Global Modbus communication object - properly initialized
modbus_comm = ModbusCommunication(name="PLCCommunication")

# Flag to indicate if we're currently in the process of initializing
_initializing = False

# Global connection monitor timer
connection_monitor = None

# Connection retry settings
CONNECTION_RETRY_ATTEMPTS = 3
CONNECTION_RETRY_DELAY = 1  # seconds

class PLCInitWorker(QtCore.QThread):
    # Signal to deliver (success: bool, error message: str)
    result = QtCore.pyqtSignal(bool, str)

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
                port = self.config_params.get('port', 502)
                timeout = self.config_params.get('timeout', 6.0)
                client = ModbusTcpClient(host=host, port=port, timeout=timeout)
            else:
                client = ModbusSerialClient(**self.config_params)
            t0 = time.time()
            if client.connect():
                logger.info(f"[PLCInitWorker] Connection established in {time.time()-t0:.3f} seconds")
                # Example test read from register address 0 (changed from 100 to match your PLC's behavior)
                rr = client.read_holding_registers(0, 1, unit=1)  # Always use unit=1, never 0
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
    """
    connection_changed = pyqtSignal(bool)
    
    def __init__(self, parent=None):
        super(ConnectionMonitor, self).__init__(parent)
        self.timer = None
        self.last_connection_state = False
        
    def start(self, interval=10000):  # Default 10 seconds
        """
        Start the connection monitor. Must be called from the main/GUI thread.
        """
        # Make sure we're in the main thread
        if QtCore.QThread.currentThread() != QtCore.QCoreApplication.instance().thread():
            logger.error("ConnectionMonitor.start() must be called from the main thread")
            return False
            
        if self.timer is None:
            self.timer = QTimer()
            self.timer.timeout.connect(self.check_connection)
            
        self.timer.start(interval)
        logger.info(f"PLC connection monitor started with interval {interval}ms")
        return True
        
    def stop(self):
        """Stop the connection monitor."""
        if self.timer is not None:
            self.timer.stop()
            logger.info("PLC connection monitor stopped")
        
    def check_connection(self):
        """Check the connection state and emit signal if it changes"""
        global modbus_comm, _initializing
        
        # Check connection state in a non-blocking way
        current_state = is_connected()
        
        if current_state != self.last_connection_state:
            logger.info(f"PLC connection state changed: {current_state}")
            self.connection_changed.emit(current_state)
            
        # If connection is lost, attempt to reconnect in a separate thread
        if not current_state and not _initializing:
            logger.warning("Connection lost, attempting to reconnect...")
            # Use a worker thread to avoid blocking the GUI
            self._reconnect_in_thread()
            
        self.last_connection_state = current_state
            
    def _reconnect_in_thread(self):
        """Attempt reconnection in a background thread"""
        reconnect_thread = threading.Thread(
            target=ensure_connection,
            name="PLCReconnectThread"
        )
        reconnect_thread.daemon = True
        reconnect_thread.start()


def initialize_plc_communication():
    """Initialize PLC communication based on current settings.
       This function ensures that the modbus_comm is configured and connected.
    """
    global modbus_comm, _initializing
    with plc_lock:
        _initializing = True
        try:
            # (Optional) Stop any running data reader here to avoid conflicts
            if dataReader.running:
                logger.info("Stopping DataReader before PLC initialization")
                dataReader.stop()

            # Load connection type and parameters from pool/settings
            connection_type = pool.config('plc/connection_type', str, 'tcp')
            logger.info(f"Initializing PLC communication -Connection type: {connection_type}")
    
            if connection_type == 'tcp':
                host = pool.config('plc/host', str, '127.0.0.1')
                port = pool.config('plc/tcp_port', int, 502)
                timeout = pool.config('plc/timeout', float, 1.0)
                config_params = {'host': host, 'port': port, 'timeout': timeout}
            else:
                port_val = pool.config('plc/port', str, 'COM1')
                baudrate = pool.config('plc/baudrate', int, 9600)
                bytesize = pool.config('plc/bytesize', int, 8)
                parity = pool.config('plc/parity', str, 'N')
                stopbits = pool.config('plc/stopbits', float, 1.0)
                timeout = pool.config('plc/timeout', float, 1.0)
                config_params = {
                    'port': port_val,
                    'baudrate': baudrate,
                    'bytesize': bytesize,
                    'parity': parity,
                    'stopbits': stopbits,
                    'timeout': timeout
                }
    
            # Disconnect any previous connection and reconfigure
            modbus_comm.disconnect()
            if not modbus_comm.configure(connection_type, **config_params):
                logger.error(f"Failed to configure PLC communication: {modbus_comm.get_error()}")
                return False
            # Attempt connection now
            if modbus_comm.connect():
                logger.info("Successfully connected to PLC")
                # (Optionally) restart dataReader here if not in demo mode
                return True
            else:
                logger.error(f"Failed to connect to PLC: {modbus_comm.get_error()}")
                return False
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
                # Store the port in configuration for future use
                pool.set_config('plc/port', port)
                logger.info(f"Serial port set to {port}")
                return True
            except Exception as e:
                logger.error(f"Error setting serial port: {e}")
        return False


def is_connected():
    """
    Check if there is an active connection to the PLC.
    Returns True if the connection is active; otherwise, False.
    """
    global modbus_comm
    
    # In demo mode, we assume the connection is always active.
    if pool.config('demo', bool, False):
        logger.debug("Connection status: DEMO (always on)")
        return True

    with plc_lock:  # Lock during connection check to prevent concurrent operations
        # Ensure the modbus_comm object exists and is configured
        if not modbus_comm or not modbus_comm.is_configured():
            logger.debug("Connection status: OFF (no client or not configured)")
            return False
            
        # Check the client's connection flag.
        if not modbus_comm.connected:
            logger.debug("Connection status: OFF (client reports not connected)")
            return False
            
        # Try a quick read to verify that the connection is alive.
        try:
            # Always use device ID 1 for connection test
            result = modbus_comm.read_registers(0, 1, 1, 'holding')
            connection_ok = (result is not None)
            logger.debug(f"{modbus_comm.connection_type.upper()} connection status check: {'OK' if connection_ok else 'FAILED'}")
            return connection_ok
        except Exception as e:
            logger.debug(f"{modbus_comm.connection_type.upper()} connection test error: {e}")
            return False


def ensure_connection():
    """
    Ensure that a valid connection exists.
    If the modbus_comm is not configured or connected, reinitialize it.
    Returns:
         bool: True if connection is established, False otherwise.
    """
    global modbus_comm
    # Check that we have a configured Modbus client
    if modbus_comm is None or not modbus_comm.is_configured():
        logger.info("Modbus client not configured. Re-initializing...")
        modbus_comm = ModbusCommunication(name="PLCCommunication")
        if not initialize_plc_communication():
            logger.error("Unable to configure Modbus client.")
            return False

    # Check connection status; if not connected, attempt reconnection
    if not getattr(modbus_comm, 'connected', False):
        logger.warning("Modbus client not connected. Attempting to reconnect...")
        modbus_comm.disconnect()  # Ensure any stale connection is closed
        for attempt in range(CONNECTION_RETRY_ATTEMPTS):
            logger.info(f"Reconnection attempt {attempt + 1} of {CONNECTION_RETRY_ATTEMPTS}")
            if modbus_comm.connect():
                logger.info("Reconnected to PLC successfully.")
                return True
            time.sleep(CONNECTION_RETRY_DELAY)
        logger.error("Failed to reconnect after retrying.")
        return False

    # Connection is active
    return True

def validate_device_id(device_id):
    """
    Validate that the device ID is in the valid range for Modbus (1-247)
    
    Args:
        device_id (int): The device ID to validate
        
    Returns:
        int: A valid device ID (defaults to 1 if invalid)
    """
    if not isinstance(device_id, int):
        logger.warning(f"Invalid device ID type: {type(device_id)}. Using default ID 1")
        return 1
    if device_id < 1 or device_id > 247:
        logger.warning(f"Invalid device ID value: {device_id}. Using default ID 1")
        return 1
    return device_id

# Enable non-blocking initialization
def initialize_plc_communication_async(callback=None):
    """
    Initialize PLC communication asynchronously using a QThread worker.
    Reads connection parameters from pool and starts the worker.
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
        config_params = {
            'port': port_val,
            'baudrate': baudrate,
            'bytesize': bytesize,
            'parity': parity,
            'stopbits': stopbits,
            'timeout': timeout
        }
        logger.info(f"Initializing PLC with Serial port: {port_val}")

    # Create the worker and assign its parent to the application instance.
    worker = PLCInitWorker(connection_type, config_params, parent=QApplication.instance())
    if callback:
        worker.result.connect(lambda success, error: 
            QtCore.QTimer.singleShot(0, lambda: callback(success, error))
        )
    worker.start()
    return worker

def _initialize_plc_thread(callback=None):
    """
    Thread function to perform PLC initialization without blocking.
    Used internally by initialize_plc_communication_async.
    """
    success = initialize_plc_communication()
    
    if callback:
        # If we have a callback, call it with the result
        try:
            callback(success)
        except Exception as e:
            logger.error(f"Error in PLC initialization callback: {e}")
            
    return success

def read_coil(address, device_id=1):
    """Read a single coil from the PLC"""
    global modbus_comm
    
    # Always validate device ID to avoid 'Station #0' errors
    device_id = validate_device_id(device_id)
    
    with plc_lock:
        if not ensure_connection():
            logger.error("Cannot read coil: No connection to PLC")
            return False
        
        try:
            result = modbus_comm.read_bool_addresses(address, 1, device_id)
            if result and len(result) > 0:
                return result[0]
            return False
        except Exception as e:
            logger.error(f"Error reading coil at address {address}: {e}")
            return False


def read_coils(address, count=1, device_id=1):
    """Read multiple coils from the PLC"""
    global modbus_comm
    
    # Always validate device ID to avoid 'Station #0' errors
    device_id = validate_device_id(device_id)
    
    with plc_lock:
        if not ensure_connection():
            logger.error("Cannot read coils: No connection to PLC")
            return [False] * count
        
        try:
            result = modbus_comm.read_bool_addresses(address, count, device_id)
            if result:
                return result
            return [False] * count
        except Exception as e:
            logger.error(f"Error reading {count} coils from address {address}: {e}")
            return [False] * count


def write_coil(address, value, device_id=1):
    """Write a boolean value to a coil"""
    global modbus_comm
    
    # Always validate device ID to avoid 'Station #0' errors
    device_id = validate_device_id(device_id)
    
    with plc_lock:
        if not ensure_connection():
            logger.error("Cannot write coil: No connection to PLC")
            return False
        
        try:
            return modbus_comm.write_bool_address(address, value, device_id)
        except Exception as e:
            logger.error(f"Error writing value {value} to coil at address {address}: {e}")
            return False


def read_holding_register(address, device_id=1):
    """Read a single holding register from the PLC"""
    global modbus_comm
    
    # Always validate device ID to avoid 'Station #0' errors
    device_id = validate_device_id(device_id)
    
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


def read_holding_registers(address, count=1, device_id=1):
    """
    Read multiple holding registers from the PLC with improved error handling
    
    Args:
        address (int): Starting register address
        count (int): Number of registers to read
        device_id (int): Slave/Unit ID of the device (1-247)
        
    Returns:
        list: Register values or None if error
    """
    global modbus_comm
    
    # Validate device ID
    device_id = validate_device_id(device_id)
    
    with plc_lock:
        if not ensure_connection():
            logger.error("Cannot read registers: No connection to PLC")
            return None
        
        try:
            # Log the request details for debugging
            logger.debug(f"Reading {count} holding registers from address {address} with device ID {device_id}")
            
            # Attempt to read the registers
            result = modbus_comm.read_registers(address, count, device_id, 'holding')
            
            # Check if the result is valid
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
    """Read a single input register from the PLC"""
    global modbus_comm
    
    # Always validate device ID to avoid 'Station #0' errors
    device_id = validate_device_id(device_id)
    
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
    """
    Read multiple input registers from the PLC with improved error handling
    
    Args:
        address (int): Starting register address
        count (int): Number of registers to read
        device_id (int): Slave/Unit ID of the device (1-247)
        
    Returns:
        list: Register values or None if error
    """
    global modbus_comm
    
    # Validate device ID to prevent the "Station #0 so no response allowed" error
    device_id = validate_device_id(device_id)
    
    with plc_lock:
        if not ensure_connection():
            logger.error("Cannot read registers: No connection to PLC")
            return None
        
        try:
            # Log the request details for debugging
            logger.debug(f"Reading {count} input registers from address {address} with device ID {device_id}")
            
            # Attempt to read the registers
            result = modbus_comm.read_registers(address, count, device_id, 'input')
            
            # Check if the result is valid
            if result is not None:
                logger.debug(f"Successfully read registers: {result}")
                return result
            else:
                logger.error("Unknown error reading input registers")
                return None
                
        except ModbusIOException as e:
            logger.error(f"IO error reading input registers: {e}")
            # Connection might be lost, try to reconnect next time
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
    """Write a value to a holding register"""
    global modbus_comm
    
    # Always validate device ID to avoid 'Station #0' errors
    device_id = validate_device_id(device_id)
    
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
    """Write multiple values to consecutive holding registers"""
    global modbus_comm
    
    # Always validate device ID to avoid 'Station #0' errors
    device_id = validate_device_id(device_id)
    
    with plc_lock:
        if not ensure_connection():
            logger.error("Cannot write registers: No connection to PLC")
            return False
        
        try:
            # Ensure values is a list or tuple
            if not isinstance(values, (list, tuple)):
                values = [values]
            
            return modbus_comm.write_registers(address, values, device_id)
        except Exception as e:
            logger.error(f"Error writing values {values} to registers starting at address {address}: {e}")
            return False


def disconnect():
    """Disconnect from the PLC"""
    global modbus_comm, connection_monitor
    
    with plc_lock:
        # Stop connection monitor if running
        if connection_monitor is not None:
            connection_monitor.stop()
            connection_monitor = None
        
        # Stop the dataReader first
        if dataReader.running:
            logger.info("Stopping DataReader before disconnecting PLC")
            dataReader.stop()
        
        try:
            if modbus_comm:
                result = modbus_comm.disconnect()
                
                if result:
                    logger.info("Successfully disconnected from PLC")
                return result
            return True
        except Exception as e:
            logger.error(f"Error disconnecting from PLC: {e}")
            return False


# Shorthand function for compatibility with other code
def write_bool_address(address, value, unit=1):
    """Write a boolean value to a coil (compatibility function)"""
    return write_coil(address, value, unit)


# Additional utility functions

def test_connection(connection_type=None, simulation_mode=False, **params):
    """
    Test a connection with given parameters without affecting the current connection.
    Has improved timeout handling to avoid freezing the UI.
    
    Args:
        connection_type: 'tcp' or 'rtu'
        simulation_mode: Ignored parameter (kept for backwards compatibility)
        **params: Connection parameters
        
    Returns:
        bool: True if connection succeeds, False otherwise
    """
    logger.info("Testing connection (simulation_mode parameter ignored, using real connection)")
    
    # Create a temporary communication object just for testing
    test_comm = ModbusCommunication(name="ConnectionTest")
    
    # If connection_type is not specified, use the currently configured type
    if connection_type is None:
        connection_type = pool.config('plc/connection_type', str, 'rtu')
    
    # Configure parameters based on connection type
    if connection_type == 'tcp':
        required_params = ['host', 'port', 'timeout']
        for param in required_params:
            if param not in params:
                params[param] = pool.config(f'plc/{param if param != "port" else "tcp_port"}', 
                                          str if param == 'host' else (float if param == 'timeout' else int))
        logger.info(f"Testing REAL TCP connection to {params.get('host')}:{params.get('port')}")
        
        # Enforce a minimum timeout for testing
        if 'timeout' in params and params['timeout'] < 2.0:
            logger.info(f"Increasing timeout from {params['timeout']} to 2.0 seconds for testing")
            params['timeout'] = 2.0
            
    else:  # RTU
        required_params = ['port', 'baudrate', 'bytesize', 'parity', 'stopbits', 'timeout']
        for param in required_params:
            if param not in params:
                params[param] = pool.config(f'plc/{param}', 
                                           float if param in ['stopbits', 'timeout'] else 
                                           (str if param in ['port', 'parity'] else int))
        logger.info(f"Testing REAL RTU connection to {params.get('port')}")
        
        # Enforce a minimum timeout for testing
        if 'timeout' in params and params['timeout'] < 2.0:
            logger.info(f"Increasing timeout from {params['timeout']} to 2.0 seconds for testing")
            params['timeout'] = 2.0
            
    # Log the configuration for debugging
    logger.info(f"Configuring test connection with params: {params}")
    
    t0 = time.time()
    success = test_comm.configure(connection_type, **params)
    logger.info(f"Test connection configured in {time.time()-t0:.3f} seconds")
    
    if not success:
        logger.error(f"Failed to configure test connection: {test_comm.get_error()}")
        return False
        
    # Now try to connect with the test client
    try:
        t0 = time.time()
        if not test_comm.connect():
            logger.error(f"Connection failed after {time.time()-t0:.3f} seconds - could not connect to {connection_type.upper()} device: {test_comm.get_error()}")
            return False
            
        logger.info(f"Connection established in {time.time()-t0:.3f} seconds, performing test read")
        
        # Try to read a register to verify the connection works properly
        try:
            # Always use device ID 1 for testing, never 0
            t0 = time.time()
            if connection_type == 'tcp':
                result = test_comm.read_registers(0, 1, 1, 'holding')
            else:
                result = test_comm.read_registers(0, 1, 1, 'holding')
                
            if result is not None:
                logger.info(f"REAL connection test successful - register read returned: {result} in {time.time()-t0:.3f} seconds")
            else:
                logger.error(f"REAL connection test failed - register read returned None")
                test_comm.disconnect()
                return False
                
        except Exception as e:
            logger.error(f"REAL connection test failed - register read failed with error: {e}")
            test_comm.disconnect()
            return False
            
        # Disconnect the test client before returning
        t0 = time.time()
        test_comm.disconnect()
        logger.info(f"Test connection disconnected in {time.time()-t0:.3f} seconds")
        
        return True
        
    except Exception as e:
        logger.error(f"Error during connection test: {e}")
        return False

def start_connection_monitor(interval=30000):  # Default 30 seconds
    """Start the connection monitor timer"""
    global connection_monitor
    
    # Create a new monitor if needed
    if connection_monitor is None:
        connection_monitor = ConnectionMonitor(parent=QApplication.instance())
        
    # Start the timer
    if connection_monitor.start(interval):
        logger.info(f"PLC connection monitor started with interval {interval}ms")
        return True
        
    return False