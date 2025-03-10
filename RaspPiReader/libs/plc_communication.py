import logging
import time
from pymodbus.client.sync import ModbusSerialClient, ModbusTcpClient
from pymodbus.exceptions import ConnectionException, ModbusException
from RaspPiReader import pool
from RaspPiReader.libs.communication import ModbusCommunication
from PyQt5.QtCore import QSettings

# Configure logger
logger = logging.getLogger(__name__)

# Global Modbus communication object
modbus_comm = ModbusCommunication()

def initialize_plc_communication():
    """Initialize PLC communication with settings from the application configuration"""
    global modbus_comm

    # Get connection type from settings
    connection_type = pool.config('plc/connection_type', str, 'rtu')

    # Always use real mode (simulation removed)
    is_simulation = False

    logger.info(f"Initializing PLC communication - Connection type: {connection_type}, Simulation: {is_simulation}")

    # Configure client based on connection type
    if connection_type == 'tcp':
        host = pool.config('plc/host', str, 'localhost')
        port = pool.config('plc/tcp_port', int, 502)
        timeout = pool.config('plc/timeout', float, 1.0)

        logger.info(f"Initializing PLC with TCP host: {host}")
        config_params = {
            'simulation_mode': is_simulation,
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
            'simulation_mode': is_simulation,
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
    """
    Check if there is an active connection to the PLC.
    Returns True if the connection is active; otherwise, False.
    """
    global modbus_comm
    # In demo mode, we assume the connection is always active.
    if pool.config('demo', bool, False):
        logger.debug("Connection status: DEMO (always on)")
        return True

    # Ensure the modbus_comm object exists and has a client.
    if not modbus_comm or not hasattr(modbus_comm, 'client'):
        logger.debug("Connection status: OFF (no client)")
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
    global modbus_comm
    # If the PLC communication object does not exist, initialize communication.
    if modbus_comm is None:
        logger.warning("No PLC communication object exists, initializing now.")
        return initialize_plc_communication()  # Ensure this function returns a boolean.

    # If not connected, attempt to reconnect.
    if not is_connected():
        logger.warning("PLC not connected, trying to reconnect.")
        try:
            if modbus_comm.connect():
                logger.debug("Reconnection successful.")
                return True
            else:
                logger.error("Reconnection failed.")
                return False
        except Exception as e:
            logger.error(f"Error reconnecting to PLC: {e}")
            return False

    # If the connection is active, return True.
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
    """Test a connection with given parameters without affecting the current connection.
    Simulation mode parameter is ignored; always testing a real connection."""
    logger.info("Testing connection (simulation mode parameter ignored, using real connection)")
    
    # Remove any simulation_mode influence by forcing it to False
    params['simulation_mode'] = False

    # Create a temporary communication object just for testing
    test_comm = ModbusCommunication()
    
    # If connection_type is not specified, use the currently configured type
    if connection_type is None:
        connection_type = pool.config('plc/connection_type', str, 'rtu')
    
    # Configure parameters based on connection type
    if connection_type == 'tcp':
        required_params = ['host', 'port', 'timeout']
        for param in required_params:
            if param not in params:
                params[param] = pool.config(f'plc/{param}', str if param == 'host' else (float if param == 'timeout' else int))
        logger.info(f"Testing REAL TCP connection to {params.get('host')}:{params.get('port')}")
    else:
        required_params = ['port', 'baudrate', 'bytesize', 'parity', 'stopbits', 'timeout']
        for param in required_params:
            if param not in params:
                params[param] = pool.config(f'plc/{param}', 
                                            float if param in ['stopbits', 'timeout'] else 
                                            (str if param in ['port', 'parity'] else int))
        logger.info(f"Testing REAL RTU connection to {params.get('port')}")
    
    try:
        if not test_comm.configure(connection_type, **params):
            logger.error("Failed to configure test connection - invalid parameters")
            return False
            
        if not test_comm.connect():
            logger.error(f"Connection failed - could not connect to {connection_type.upper()} device")
            return False
            
        try:
            register_value = test_comm.read_registers(0, 1, 1, 'holding')
            success = register_value is not None
            if success:
                logger.info(f"REAL connection test successful - register read returned: {register_value}")
            else:
                logger.error("REAL connection test failed - register read returned None")
            return success
        except Exception as e:
            logger.error(f"REAL connection test failed during read operation: {str(e)}")
            return False
        finally:
            test_comm.disconnect()
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