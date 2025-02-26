import logging
import time
from pymodbus.client.sync import ModbusSerialClient, ModbusTcpClient
from pymodbus.exceptions import ConnectionException, ModbusException
from RaspPiReader import pool
from RaspPiReader.libs.communication import ModbusCommunication

# Configure logger
logger = logging.getLogger(__name__)

# Global Modbus communication object
modbus_comm = ModbusCommunication()

def initialize_plc_communication():
    """Initialize PLC communication with settings from the application configuration"""
    global modbus_comm
    
    # Get connection type from settings
    connection_type = pool.config('plc/connection_type', str, 'rtu')
    
    # Check if we're in demo mode or simulation mode
    is_demo = pool.config('demo', bool, False)
    is_simulation = pool.config('plc/simulation_mode', bool, False)
    
    if is_demo:
        logger.warning("DEMO MODE: Using simulated PLC communication")
    
    if is_simulation:
        logger.warning("*** SIMULATION MODE ACTIVE - No real PLC connection will be established ***")
    
    # Configure client based on connection type
    if connection_type == 'tcp':
        host = pool.config('plc/host', str, 'localhost')
        port = pool.config('plc/tcp_port', int, 502)
        timeout = pool.config('plc/timeout', float, 1.0)
        
        logger.info(f"Initializing PLC with TCP host: {host}")
        config_params = {
            'simulation_mode': is_simulation or is_demo,
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
            'simulation_mode': is_simulation or is_demo,
            'port': port,
            'baudrate': baudrate,
            'bytesize': bytesize, 
            'parity': parity,
            'stopbits': stopbits,
            'timeout': timeout
        }
    
    logger.info(f"Configuring PLC communication with {connection_type} and parameters: {config_params}")
    
    # Configure and connect
    try:
        success = modbus_comm.configure(connection_type, **config_params)
        if success:
            logger.info(f"PLC communication configured with {connection_type}")
            success = modbus_comm.connect()
            if success:
                logger.info("Successfully connected to PLC")
            else:
                logger.error("Failed to connect to PLC")
        else:
            logger.error(f"Failed to configure PLC communication with {connection_type}")
            success = False
    except Exception as e:
        logger.error(f"Error initializing PLC communication: {e}")
        success = False
    
    return success

def set_port(port):
    """Set the serial port for the PLC connection"""
    global modbus_comm
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
    """Check if the PLC is connected"""
    global modbus_comm
    
    # If in demo or simulation mode, show connection status based on configuration
    is_demo = pool.config('demo', bool, False)
    is_simulation = pool.config('plc/simulation_mode', bool, False)
    
    if is_demo or is_simulation:
        logger.debug("SIMULATION MODE: Connection status check")
        return True  # Always return True in simulation mode
    
    # Real connection check for actual hardware
    if modbus_comm and hasattr(modbus_comm, 'connected'):
        try:
            # For TCP clients, explicitly check if socket is open
            if hasattr(modbus_comm.client, 'is_socket_open'):
                return modbus_comm.client.is_socket_open()
            # For RTU/Serial clients, return stored connection status
            return modbus_comm.connected
        except Exception as e:
            logger.error(f"Error checking connection status: {e}")
            return False
    return False

def ensure_connection():
    """Ensure that we have a connection to the PLC"""
    global modbus_comm
    if not modbus_comm:
        logger.warning("No PLC communication object exists, initializing now")
        return initialize_plc_communication()
    
    if not is_connected():
        logger.warning("PLC not connected, trying to reconnect")
        try:
            return modbus_comm.connect()
        except Exception as e:
            logger.error(f"Error reconnecting to PLC: {e}")
            return False
    
    return True

def read_coil(address, device_id=1):
    """Read a single coil from the PLC"""
    global modbus_comm
    if not ensure_connection():
        logger.error("Cannot read coil: No connection to PLC")
        return False
    
    try:
        return modbus_comm.read_bool_addresses(address, 1, device_id)[0]
    except Exception as e:
        logger.error(f"Error reading coil at address {address}: {e}")
        return False

def read_coils(address, count=1, device_id=1):
    """Read multiple coils from the PLC"""
    global modbus_comm
    if not ensure_connection():
        logger.error("Cannot read coils: No connection to PLC")
        return [False] * count
    
    try:
        return modbus_comm.read_bool_addresses(address, count, device_id)
    except Exception as e:
        logger.error(f"Error reading {count} coils from address {address}: {e}")
        return [False] * count

def write_coil(address, value, device_id=1):
    """Write a boolean value to a coil"""
    global modbus_comm
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
    global modbus_comm
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
    """Test a connection with given parameters without affecting the current connection"""
    # Save existing communication settings
    global modbus_comm
    existing_comm = modbus_comm
    
    # Create a temporary communication object just for testing
    test_comm = ModbusCommunication()
    
    # If connection_type is not specified, use the currently configured type
    if connection_type is None:
        connection_type = pool.config('plc/connection_type', str, 'rtu')
    
    # Configure the test connection
    if connection_type == 'tcp':
        # Ensure required TCP parameters exist
        required_params = ['host', 'port', 'timeout']
        for param in required_params:
            if param not in params:
                params[param] = pool.config(f'plc/{param}', str if param == 'host' else (float if param == 'timeout' else int))
    else:
        # Ensure required RTU parameters exist
        required_params = ['port', 'baudrate', 'bytesize', 'parity', 'stopbits', 'timeout']
        for param in required_params:
            if param not in params:
                params[param] = pool.config(f'plc/{param}', 
                                           float if param in ['stopbits', 'timeout'] else 
                                           (str if param in ['port', 'parity'] else int))
    
    # Set simulation mode for testing
    params['simulation_mode'] = simulation_mode
    
    try:
        # Configure the test connection
        if test_comm.configure(connection_type, **params):
            # Try to connect
            if test_comm.connect():
                # Try a simple read operation to verify connection works
                try:
                    # For simulation mode, we don't need to read anything
                    if simulation_mode:
                        return True
                    
                    # For real mode, try to read a register to ensure communication works
                    if connection_type == 'tcp':
                        result = test_comm.read_registers(0, 1, 1, 'holding')
                    else:
                        result = test_comm.read_registers(0, 1, 1, 'holding')
                    
                    # If we got a result (even empty), the connection is working
                    return result is not None
                except Exception as e:
                    logger.error(f"Test connection failed during read test: {e}")
                    return False
                finally:
                    # Always disconnect the test connection
                    test_comm.disconnect()
            else:
                logger.error("Test connection failed - could not connect")
                return False
        else:
            logger.error("Test connection failed - could not configure")
            return False
    except Exception as e:
        logger.error(f"Error during connection test: {e}")
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
    is_simulation = pool.config('plc/simulation_mode', bool, False)
    connection_type = pool.config('plc/connection_type', str, 'rtu')
    
    params = {
        'demo_mode': is_demo,
        'simulation_mode': is_simulation,
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