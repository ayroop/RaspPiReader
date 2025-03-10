import logging
import time
import os
import socket 
from pymodbus.client.sync import ModbusSerialClient, ModbusTcpClient
from PyQt5.QtCore import QSettings
from RaspPiReader import pool
from RaspPiReader.ui.setting_form_handler import READ_HOLDING_REGISTERS, READ_INPUT_REGISTERS

# Configure logger
logger = logging.getLogger(__name__)

class ModbusCommunication:
    def write_bool_address(self, addr, value, dev=1):
        """Write a boolean value to a coil"""
        if not self.client:
            self.last_error = "Modbus client not configured"
            logger.error(self.last_error)
            return False

        if not self.connected:
            logger.info("Not connected, attempting to connect...")
            if not self.connect():
                return False

        try:
            result = self.client.write_coil(addr, value, unit=dev)
            if result and not result.isError():
                return True
            else:
                self.last_error = f"Error writing coil: {result}"
                logger.error(self.last_error)
                return False
        except Exception as e:
            self.last_error = f"Exception during coil write: {str(e)}"
            logger.error(self.last_error)
            return False
    
    def configure(self, connection_type=None, **kwargs):
        """Configure the Modbus client with the specified parameters
        
        Args:
            connection_type (str): 'rtu' or 'tcp'
            **kwargs: Configuration parameters specific to the connection type
        """
        self.connection_type = connection_type
        # Remove simulation_mode parameter entirely; always use real connection
        
        # Validate required parameters
        if connection_type == 'rtu':
            port = kwargs.get('port')
            if not port:
                self.last_error = "Serial port not specified"
                logger.error(self.last_error)
                return False
                
            baudrate = kwargs.get('baudrate', 9600)
            bytesize = kwargs.get('bytesize', 8)
            parity = kwargs.get('parity', 'N')
            stopbits = kwargs.get('stopbits', 1)
            timeout = kwargs.get('timeout', 1)
            
            logger.info(f"Configuring RTU client on port {port} with baudrate {baudrate}")
            
            # Create RTU client
            self.client = ModbusSerialClient(
                method='rtu',
                port=port,
                baudrate=int(baudrate),
                bytesize=int(bytesize),
                parity=parity,
                stopbits=float(stopbits),  # Use float for stopbits to support 1.5
                timeout=float(timeout),
                retry_on_empty=True,
                retries=3
            )
        
        elif connection_type == 'tcp':
            host = kwargs.get('host')
            if not host:
                self.last_error = "TCP host not specified"
                logger.error(self.last_error)
                return False
                
            port = kwargs.get('port', 502)
            timeout = kwargs.get('timeout', 1)
            
            logger.info(f"Configuring TCP client with host {host} and port {port}")
            
            # Create TCP client
            self.client = ModbusTcpClient(
                host=host,
                port=int(port),
                timeout=float(timeout),
                retry_on_empty=True,
                retries=3
            )
        else:
            self.last_error = f"Invalid connection type: {connection_type}"
            logger.error(self.last_error)
            return False
            
        return True
    
    def connect(self):
        """Connect to the Modbus device"""
        if not self.client:
            self.last_error = "Modbus client not configured"
            logger.error(self.last_error)
            return False
            
        try:
            # For RTU connections, check if the port exists first
            if self.connection_type == 'rtu' and hasattr(self.client, 'port'):
                port = self.client.port
                if not os.path.exists(port) and not port.startswith('COM'):
                    self.last_error = f"Serial port {port} does not exist"
                    logger.error(self.last_error)
                    self.connected = False
                    return False
            
            # For TCP connections, perform a pre-check if host is reachable
            if self.connection_type == 'tcp':
                host = self.client.host
                port = self.client.port
                try:
                    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    s.settimeout(2.0)  # 2 seconds timeout
                    logger.info(f"Testing TCP connection to {host}:{port}")
                    s.connect((host, port))
                    s.close()
                    logger.info(f"TCP connection test successful for {host}:{port}")
                except Exception as e:
                    self.last_error = f"Failed to connect to {host}:{port}: {str(e)}"
                    logger.error(self.last_error)
                    self.connected = False
                    return False
            
            # Try to connect with the Modbus client
            self.connected = self.client.connect()
            
            if self.connected:
                # For TCP connections, verify we can actually communicate
                if self.connection_type == 'tcp':
                    try:
                        test_result = self.client.read_holding_registers(0, 1, unit=1)
                        if test_result is None or test_result.isError():
                            self.last_error = f"Connection test failed: {test_result}"
                            logger.error(self.last_error)
                            self.connected = False
                            return False
                    except Exception as e:
                        self.last_error = f"Connection test failed: {str(e)}"
                        logger.error(self.last_error)
                        self.connected = False
                        return False
                
                logger.info(f"Successfully connected to Modbus device via {self.connection_type}")
            else:
                self.last_error = f"Failed to connect to Modbus device with {self.connection_type} connection"
                logger.error(self.last_error)
            
            return self.connected
        except Exception as e:
            self.last_error = f"Exception during connection attempt: {str(e)}"
            logger.error(self.last_error)
            self.connected = False
            return False
    
    def disconnect(self):
        """Disconnect from the Modbus device"""
        if self.client:
            self.client.close()
            self.connected = False
            logger.info("Disconnected from Modbus device")
            return True
        return False
    
    def read_bool_addresses(self, addr, count=1, dev=1):
        """Read boolean values from coils"""
        if not self.client:
            self.last_error = "Modbus client not configured"
            logger.error(self.last_error)
            return None
            
        if not self.connected:
            logger.info("Not connected, attempting to connect...")
            if not self.connect():
                return None
                
        try:
            result = self.client.read_coils(addr, count, unit=dev)
            if result and not result.isError():
                return result.bits[:count]
            else:
                self.last_error = f"Error reading coils: {result}"
                logger.error(self.last_error)
                return None
        except Exception as e:
            self.last_error = f"Exception during coil read: {str(e)}"
            logger.error(self.last_error)
            return None
    
    def write_bool_address(self, addr, value, dev=1):
        """Write a boolean value to a coil"""
        if not self.client:
            self.last_error = "Modbus client not configured"
            logger.error(self.last_error)
            return False
            
        if not self.connected:
            logger.info("Not connected, attempting to connect...")
            if not self.connect():
                return False
                
        try:
            result = self.client.write_coil(addr, value, unit=dev)
            if result and not result.isError():
                return True
            else:
                self.last_error = f"Error writing coil: {result}"
                logger.error(self.last_error)
                return False
        except Exception as e:
            self.last_error = f"Exception during coil write: {str(e)}"
            logger.error(self.last_error)
            return False
    
    def read_registers(self, addr, count=1, dev=1, read_type='holding'):
        """Read registers (holding or input)"""
        if not self.client:
            self.last_error = "Modbus client not configured"
            logger.error(self.last_error)
            return None
            
        if not self.connected:
            logger.info("Not connected, attempting to connect...")
            if not self.connect():
                return None
                
        try:
            if read_type == 'holding':
                result = self.client.read_holding_registers(addr, count, unit=dev)
            elif read_type == 'input':
                result = self.client.read_input_registers(addr, count, unit=dev)
            else:
                self.last_error = f"Invalid register read type: {read_type}"
                logger.error(self.last_error)
                return None
                
            if result and not result.isError():
                return result.registers
            else:
                self.last_error = f"Error reading registers: {result}"
                logger.error(self.last_error)
                return None
        except Exception as e:
            self.last_error = f"Exception during register read: {str(e)}"
            logger.error(self.last_error)
            return None
    
    def write_register(self, addr, value, dev=1):
        """Write a value to a holding register"""
        if not self.client:
            self.last_error = "Modbus client not configured"
            logger.error(self.last_error)
            return False
            
        if not self.connected:
            logger.info("Not connected, attempting to connect...")
            if not self.connect():
                return False
                
        try:
            result = self.client.write_register(addr, value, unit=dev)
            if result and not result.isError():
                return True
            else:
                self.last_error = f"Error writing register: {result}"
                logger.error(self.last_error)
                return False
        except Exception as e:
            self.last_error = f"Exception during register write: {str(e)}"
            logger.error(self.last_error)
            return False

class DataReader:
    def __init__(self):
        self.running = False
        self.modbus_comm = ModbusCommunication()
        self.read_type = None
        self.connected = False
        
    def start(self):
        """Start the data reader"""
        self.running = True
        # Make sure we're properly connected
        self.reload()
        self.connected = True
        logger.info("Data reader started")
        
    def stop(self):
        """Stop the data reader"""
        self.running = False
        self.connected = False
        logger.info("Data reader stopped")
        
    def reload(self):
        """Reload configuration and reconnect"""
        # Completely disconnect first
        self.modbus_comm.disconnect()
        
        # Clear any previous state
        self.modbus_comm = ModbusCommunication()
        
        # Get current settings
        self.read_type = pool.config('read_type', str, READ_HOLDING_REGISTERS)
        
        # Check if we're in demo mode
        demo_mode = pool.config('demo', bool, False)
        
        if demo_mode:
            logger.info("DataReader reloading in DEMO mode")
            # In demo mode we now do not use simulation; demo mode logic is handled externally.
            self.connected = True
            return
        
        # Get settings directly from QSettings for consistency
        settings = QSettings('RaspPiHandler', 'RaspPiModbusReader')
        
        connection_type = pool.config('plc/connection_type', str, 'rtu')
        logger.info(f"DataReader reloading with connection type: {connection_type}")
        
        config_params = {}
        
        if connection_type == 'rtu':
            config_params.update({
                'port': pool.config('plc/port', str, None),
                'baudrate': pool.config('plc/baudrate', int, 9600),
                'bytesize': pool.config('plc/bytesize', int, 8),
                'parity': pool.config('plc/parity', str, 'N'),
                'stopbits': pool.config('plc/stopbits', float, 1),
                'timeout': pool.config('plc/timeout', float, 1.0)
            })
        else:  # TCP
            config_params.update({
                'host': pool.config('plc/host', str, None),
                'port': pool.config('plc/tcp_port', int, 502),
                'timeout': pool.config('plc/timeout', float, 1.0)
            })
        
        logger.info(f"Configuring with: {config_params}")
        self.modbus_comm.configure(connection_type, **config_params)
        self.connected = self.modbus_comm.connect()
    
    def _read_holding_registers(self, dev, addr):
        """Read holding registers"""
        return self.modbus_comm.read_registers(addr, 1, dev, 'holding')
        
    def _read_input_registers(self, dev, addr):
        """Read input registers"""
        return self.modbus_comm.read_registers(addr, 1, dev, 'input')
        
    def read_bool_addresses(self, dev, addr, count=6):
        """Read boolean addresses (coils)"""
        return self.modbus_comm.read_bool_addresses(addr, count, dev)
        
    def readData(self, dev, addr):
        """Read data based on configured read type"""
        if not self.running:
            return None
            
        if not self.read_type:
            self.read_type = pool.config('read_type', str, READ_HOLDING_REGISTERS)
            
        if self.read_type == READ_HOLDING_REGISTERS:
            return self._read_holding_registers(dev, addr)
        elif self.read_type == READ_INPUT_REGISTERS:
            return self._read_input_registers(dev, addr)
        else:
            logger.error(f"Invalid register read type: {self.read_type}")
            return None

    def read_bool_address(self, address, dev=1):
        """Read a single boolean value (coil) from the PLC.
        Returns True, False, or None on error.
        """
        values = self.modbus_comm.read_bool_addresses(address, count=1, dev=dev)
        if values is not None and len(values) > 0:
            return values[0]
        return None

# Create a singleton instance
dataReader = DataReader()