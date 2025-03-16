import logging
import time
import threading
from pymodbus.client.sync import ModbusSerialClient, ModbusTcpClient
from pymodbus.exceptions import ConnectionException, ModbusException
from RaspPiReader import pool
from RaspPiReader.libs.communication import ModbusCommunication, dataReader, plc_lock
from PyQt5.QtCore import QSettings, QTimer, QObject, pyqtSignal
from PyQt5 import QtCore
from PyQt5.QtWidgets import QApplication

# Configure logger
logger = logging.getLogger(__name__)

# Global Modbus communication object
modbus_comm = ModbusCommunication(name="PLCCommunication")

# Flag to indicate if we're currently in the process of initializing
_initializing = False

# Global connection monitor timer
connection_monitor = None

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
                # Example test read from register address 100 (adjust as required)
                rr = client.read_holding_registers(100, 1, unit=1)
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
    """Initialize PLC communication with settings from the application configuration"""
    global modbus_comm, _initializing, connection_monitor

    with plc_lock:  # Use the global lock to ensure exclusive access
        # Set flag to prevent concurrent initialization
        _initializing = True
        
        try:
            # First, stop the data reader to prevent conflicts
            if dataReader.running:
                logger.info("Stopping DataReader before PLC initialization")
                dataReader.stop()
            
            # Get connection type from settings
            connection_type = pool.config('plc/connection_type', str, 'rtu')
            
            logger.info(f"Initializing PLC communication - Connection type: {connection_type}")
            
            # Configure client based on connection type
            if connection_type == 'tcp':
                host = pool.config('plc/host', str, 'localhost')
                port = pool.config('plc/tcp_port', int, 502)
                timeout = pool.config('plc/timeout', float, 1.0)
                
                logger.info(f"Initializing PLC with TCP host: {host}")
                config_params = {
                    'host': host,
                    'port': port,
                    'timeout': timeout
                }
            else:
                port = pool.config('plc/port', str, 'COM1')
                baudrate = pool.config('plc/baudrate', int, 9600)
                bytesize = pool.config('plc/bytesize', int, 8)
                parity = pool.config('plc/parity', str, 'N')
                stopbits = pool.config('plc/stopbits', float, 1.0)
                timeout = pool.config('plc/timeout', float, 1.0)
                
                logger.info(f"Initializing PLC with serial port: {port}")
                config_params = {
                    'port': port,
                    'baudrate': baudrate,
                    'bytesize': bytesize,
                    'parity': parity,
                    'stopbits': stopbits,
                    'timeout': timeout
                }
                
            logger.info(f"Configuring PLC communication with {connection_type} and parameters: {config_params}")
            
            # Disconnect if already connected
            modbus_comm.disconnect()
            
            # Configure and connect
            success = modbus_comm.configure(connection_type, **config_params)
            if success:
                logger.info(f"PLC communication configured with {connection_type}")
                success = modbus_comm.connect()
                if success:
                    logger.info("Successfully connected to PLC")
                    
                    # Only now start the DataReader to avoid conflicts
                    if not pool.config('demo', bool, False):
                        # We use the same configuration parameters for DataReader
                        logger.info("Starting DataReader after successful PLC connection")
                        dataReader.start()
                    
                    # Note: The connection monitor timer is now started in the main Qt thread
                    # by the calling code to avoid thread issues
                else:
                    logger.error(f"Failed to connect to PLC: {modbus_comm.get_error()}")
            else:
                logger.error(f"Failed to configure PLC communication with {connection_type}: {modbus_comm.get_error()}")
                success = False
        except Exception as e:
            logger.error(f"Error initializing PLC communication: {e}")
            success = False
        finally:
            _initializing = False
            
        return success


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
            result = modbus_comm.read_registers(0, 1, 1, 'holding')
            connection_ok = (result is not None)
            logger.debug(f"{modbus_comm.connection_type.upper()} connection status check: {'OK' if connection_ok else 'FAILED'}")
            return connection_ok
        except Exception as e:
            logger.debug(f"{modbus_comm.connection_type.upper()} connection test error: {e}")
            return False


def ensure_connection():
    """
    Ensure that the PLC connection is active.
    If no connection exists or the connection is lost,
    this will attempt to initialize or reconnect.
    Returns True if the connection is active after checking, otherwise False.
    """
    global modbus_comm, _initializing
    
    # Don't try to reconnect if we're already in the process of initializing
    if _initializing:
        logger.debug("Skip reconnection - already initializing")
        return False
    
    with plc_lock:  # Use the global lock to ensure exclusive access
        # If the PLC communication object does not exist or is not configured, initialize communication.
        if modbus_comm is None or not modbus_comm.is_configured():
            logger.warning("No PLC communication object exists or not configured, initializing now.")
            return initialize_plc_communication()
            
        # If not connected, attempt to reconnect.
        if not is_connected():
            logger.warning("PLC not connected, trying to reconnect.")
            try:
                if modbus_comm.connect():
                    logger.debug("Reconnection successful.")
                    return True
                else:
                    logger.error(f"Reconnection failed: {modbus_comm.get_error()}")
                    return False
            except Exception as e:
                logger.error(f"Error reconnecting to PLC: {e}")
                return False
            
        # If the connection is active, return True.
        return True

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
    """Read multiple holding registers from the PLC"""
    global modbus_comm
    with plc_lock:
        if not ensure_connection():
            logger.error("Cannot read holding registers: No connection to PLC")
            return [None] * count
        
        try:
            return modbus_comm.read_registers(address, count, device_id, 'holding')
        except Exception as e:
            logger.error(f"Error reading {count} holding registers from address {address}: {e}")
            return [None] * count


def read_input_register(address, device_id=1):
    """Read a single input register from the PLC"""
    global modbus_comm
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
    """Read multiple input registers from the PLC"""
    global modbus_comm
    with plc_lock:
        if not ensure_connection():
            logger.error("Cannot read input registers: No connection to PLC")
            return [None] * count
        
        try:
            return modbus_comm.read_registers(address, count, device_id, 'input')
        except Exception as e:
            logger.error(f"Error reading {count} input registers from address {address}: {e}")
            return [None] * count


def write_register(address, value, device_id=1):
    """Write a value to a holding register"""
    global modbus_comm
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
    with plc_lock:
        if not ensure_connection():
            logger.error("Cannot write registers: No connection to PLC")
            return False
        
        try:
            # Ensure values is a list or tuple
            if not isinstance(values, (list, tuple)):
                values = [values]
            
            if hasattr(modbus_comm, 'write_registers'):
                return modbus_comm.write_registers(address, values, device_id)
            else:
                # Fallback method: write registers one by one
                success = True
                for i, value in enumerate(values):
                    if not modbus_comm.write_register(address + i, value, device_id):
                        success = False
                return success
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
    
    # Remove any simulation_mode influence by forcing it to False
    if 'simulation_mode' in params:
        del params['simulation_mode']

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
    
    with plc_lock:  # Use global lock for testing to prevent other operations
        try:
            # Log the configuration attempt
            logger.info(f"Configuring test connection with params: {params}")
            config_start = time.time()
            
            if not test_comm.configure(connection_type, **params):
                logger.error(f"Failed to configure test connection - invalid parameters: {test_comm.get_error()}")
                return False
                
            config_time = time.time() - config_start
            logger.info(f"Test connection configured in {config_time:.3f} seconds")
            
            # Log the connection attempt
            connect_start = time.time()
            connection_success = test_comm.connect()
            connect_time = time.time() - connect_start
            
            if not connection_success:
                logger.error(f"Connection failed after {connect_time:.3f} seconds - could not connect to {connection_type.upper()} device: {test_comm.get_error()}")
                return False
                
            logger.info(f"Connection established in {connect_time:.3f} seconds, performing test read")
            
            # Now perform a test read
            try:
                read_start = time.time()
                register_value = test_comm.read_registers(0, 1, 1, 'holding')
                read_time = time.time() - read_start
                
                success = register_value is not None
                if success:
                    logger.info(f"REAL connection test successful - register read returned: {register_value} in {read_time:.3f} seconds")
                else:
                    logger.error(f"REAL connection test failed after {read_time:.3f} seconds - register read returned None")
                return success
            except Exception as e:
                read_time = time.time() - read_start
                logger.error(f"REAL connection test failed after {read_time:.3f} seconds during read operation: {str(e)}")
                return False
            finally:
                disconnect_start = time.time()
                test_comm.disconnect()
                disconnect_time = time.time() - disconnect_start
                logger.info(f"Test connection disconnected in {disconnect_time:.3f} seconds")
        except Exception as e:
            logger.error(f"REAL connection test exception: {str(e)}")
            return False

def get_available_ports():
    """Get a list of available serial ports"""
    try:
        from PyQt5 import QtSerialPort
        ports = QtSerialPort.QSerialPortInfo.availablePorts()
        return [port.portName() for port in ports]
    except Exception as e:
        logger.error(f"Error getting available serial ports: {e}")
        return []


def get_connection_parameters():
    """Get the current connection parameters as a dictionary"""
    is_demo = pool.config('demo', bool, False)
    connection_type = pool.config('plc/connection_type', str, 'rtu')
    
    params = {
        'demo_mode': is_demo,
        'connection_type': connection_type,
        'timeout': pool.config('plc/timeout', float, 1.0)
    }
    
    if connection_type == 'tcp':
        params.update({
            'host': pool.config('plc/host', str, 'localhost'),
            'port': pool.config('plc/tcp_port', int, 502)
        })
    else:
        params.update({
            'port': pool.config('plc/port', str, 'COM1'),
            'baudrate': pool.config('plc/baudrate', int, 9600),
            'bytesize': pool.config('plc/bytesize', int, 8),
            'parity': pool.config('plc/parity', str, 'N'),
            'stopbits': pool.config('plc/stopbits', float, 1.0)
        })
    
    return params


def sync_with_data_reader():
    """Synchronize the PLC communication with the data reader"""
    global modbus_comm
    
    # Check if both are already connected
    plc_connected = is_connected()
    data_reader_connected = dataReader.is_connected()
    
    if plc_connected and data_reader_connected:
        logger.info("Both PLC and DataReader are already connected - no sync needed")
        return True
    elif plc_connected and not data_reader_connected:
        # PLC is connected but DataReader is not, just start the DataReader
        logger.info("PLC is connected but DataReader is not - starting DataReader")
        dataReader.start()
        return True
    elif not plc_connected and data_reader_connected:
        # DataReader is connected but PLC is not - stop DataReader and initialize both
        logger.info("DataReader is connected but PLC is not - reinitializing both")
        dataReader.stop()
        return initialize_plc_communication()
    else:
        # Neither is connected - initialize both
        logger.info("Neither PLC nor DataReader are connected - initializing both")
        return initialize_plc_communication()