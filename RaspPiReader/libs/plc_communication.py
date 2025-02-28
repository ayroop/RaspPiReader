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
    
    # Check if we're in demo mode or simulation mode
    is_demo = pool.config('demo', bool, False)
    
    # CRITICAL FIX - Read simulation mode explicitly from QSettings to avoid cached values
    settings = QSettings('RaspPiHandler', 'RaspPiModbusReader')
    is_simulation = settings.value('plc/simulation_mode', False, type=bool)
    
    # Update pool with the correct simulation mode
    pool.set_config('plc/simulation_mode', is_simulation)
    
    logger.info(f"Initializing PLC communication - Connection type: {connection_type}, Demo: {is_demo}, Simulation: {is_simulation}")
    
    if is_demo:
        logger.warning("*** DEMO MODE ACTIVE - Using demo data instead of real PLC connection ***")
        return True  # In demo mode, we don't need real connection
    
    if is_simulation:
        logger.warning("*** SIMULATION MODE ACTIVE - No real PLC connection will be established ***")
        # Configure in simulation mode
        modbus_comm = ModbusCommunication()
        params = {
            'simulation_mode': is_simulation,  # FIX: USE ACTUAL SETTING instead of forcing True
            'host': pool.config('plc/host', str, '127.0.0.1'),
            'port': pool.config('plc/port', int, 502),
            'timeout': pool.config('plc/timeout', float, 1.2)
        }
        
        if modbus_comm.configure(connection_type, **params):
            return True
        return False
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
        """Check if we have an active PLC connection"""
        global modbus_comm
        
        # If in simulation mode, the "connection" is always considered active
        if pool.config('demo', bool, False) or pool.config('plc/simulation_mode', bool, False):
            logger.debug("Connection status: SIMULATED (always on)")
            return True
            
        # Check if we have a client object
        if modbus_comm is None or not hasattr(modbus_comm, 'client'):
            logger.debug("Connection status: OFF (no client)")
            return False
            
        # Check if client exists but isn't properly connected
        if not modbus_comm.connected:
            logger.debug("Connection status: OFF (client reports not connected)")
            return False
        
        # For TCP connections, try a quick read to verify connection is alive
        if modbus_comm.connection_type == 'tcp':
            try:
                result = modbus_comm.read_registers(0, 1, 1, 'holding')
                connection_ok = result is not None
                logger.debug(f"TCP connection status check: {'OK' if connection_ok else 'FAILED'}")
                return connection_ok
            except Exception as e:
                logger.debug(f"TCP connection test error: {e}")
                return False
        
        # For RTU connections, we trust the serial port status since testing can be slower
        # But we could add similar verification if needed
        return True

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
    # EXPLICITLY LOG the simulation mode to be clear
    logger.info(f"Testing connection with explicit simulation_mode={simulation_mode}")
    
    # If explicitly using simulation mode, return success without testing
    if simulation_mode:
        logger.warning("SIMULATION MODE: Connection test skipped - reporting success automatically")
        return True
    
    # Create a temporary communication object just for testing
    test_comm = ModbusCommunication()
    
    # If connection_type is not specified, use the currently configured type
    if connection_type is None:
        connection_type = pool.config('plc/connection_type', str, 'rtu')
    
    # Configure the test connection - keep the parameter handling
    if connection_type == 'tcp':
        # Ensure required TCP parameters exist
        required_params = ['host', 'port', 'timeout']
        for param in required_params:
            if param not in params:
                params[param] = pool.config(f'plc/{param}', str if param == 'host' else (float if param == 'timeout' else int))
        logger.info(f"Testing REAL TCP connection to {params.get('host')}:{params.get('port')}")
    else:
        # Ensure required RTU parameters exist
        required_params = ['port', 'baudrate', 'bytesize', 'parity', 'stopbits', 'timeout']
        for param in required_params:
            if param not in params:
                params[param] = pool.config(f'plc/{param}', 
                                          float if param in ['stopbits', 'timeout'] else 
                                          (str if param in ['port', 'parity'] else int))
        logger.info(f"Testing REAL RTU connection to {params.get('port')}")
    
    # FORCE simulation_mode to False for real testing regardless of system config
    params['simulation_mode'] = False
    
    try:
        # Clear flow for better error isolation
        if not test_comm.configure(connection_type, **params):
            logger.error("Failed to configure test connection - invalid parameters")
            return False
            
        if not test_comm.connect():
            logger.error(f"Connection failed - could not connect to {connection_type.upper()} device")
            return False
            
        # Try reading a register to verify communication works
        try:
            # Attempt to read the first register - this should work on any PLC
            register_value = test_comm.read_registers(0, 1, 1, 'holding')
            
            # Check if we got a valid response (not None)
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
            # Always disconnect the test connection
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