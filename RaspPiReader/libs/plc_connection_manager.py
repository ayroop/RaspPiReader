import logging
import time
from threading import Lock
import socket

try:
    # Try to import from the new path structure (pymodbus 2.5.0+)
    from pymodbus.client import ModbusTcpClient, ModbusSerialClient
except ImportError:
    # Fall back to old import path for backward compatibility
    from pymodbus.client.sync import ModbusTcpClient, ModbusSerialClient

from RaspPiReader import pool

logger = logging.getLogger(__name__)

# Global connection lock to prevent concurrent connection attempts
connection_lock = Lock()

class PLCConnectionManager:
    """
    Singleton class to manage PLC connections and ensure a single shared connection
    is used across all PLC communication components (boolean readers and channel readers).
    """
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(PLCConnectionManager, cls).__new__(cls)
        return cls._instance
        
    def __init__(self):
        if PLCConnectionManager._initialized:
            return
            
        # Initialize connection attributes
        self.client = None
        self.connection_type = 'tcp'  # Default to TCP
        self.connection_params = {}
        self.connected = False
        self.last_connection_attempt = 0
        self.connection_retry_delay = 2  # seconds
        self.address_offset = 0
        
        # Load initial connection parameters
        self._load_connection_params()
        
        PLCConnectionManager._initialized = True
        logger.info("PLC Connection Manager initialized")
        
    def _load_connection_params(self):
        """Load connection parameters from configuration."""
        self.connection_type = pool.config('plc/connection_type', str, 'tcp')
        
        if self.connection_type == 'tcp':
            self.connection_params = {
                'host': pool.config('plc/host', str, '127.0.0.1'),
                'port': pool.config('plc/tcp_port', int, 502),
                'timeout': float(pool.config('plc/timeout', float, 3.0))
            }
        else:  # RTU/Serial
            self.connection_params = {
                'port': pool.config('plc/serial_port', str, 'COM1'),
                'baudrate': pool.config('plc/baudrate', int, 9600),
                'bytesize': pool.config('plc/bytesize', int, 8),
                'parity': pool.config('plc/parity', str, 'N'),
                'stopbits': pool.config('plc/stopbits', int, 1),
                'timeout': float(pool.config('plc/timeout', float, 3.0))
            }
            
        self.address_offset = pool.config('plc/address_offset', int, 0)
        logger.debug(f"Loaded PLC connection parameters: {self.connection_params}")
        
    def connect(self, force_reconnect=False):
        """
        Connect to the PLC if not already connected.
        
        Args:
            force_reconnect (bool): Force a reconnection even if already connected
            
        Returns:
            bool: True if connected successfully, False otherwise
        """
        with connection_lock:
            # Check if we need to reconnect
            if self.connected and self.client and not force_reconnect:
                return True
                
            # Check if we've attempted a connection too recently
            current_time = time.time()
            if current_time - self.last_connection_attempt < self.connection_retry_delay:
                logger.debug("Skipping connection attempt (too soon since last attempt)")
                return self.connected
                
            self.last_connection_attempt = current_time
            
            # Close any existing connection
            if self.client and hasattr(self.client, 'close'):
                try:
                    self.client.close()
                except Exception as e:
                    logger.debug(f"Error closing existing connection: {e}")
                self.client = None
                self.connected = False
            
            # Reload configuration in case it changed
            self._load_connection_params()
            
            try:
                logger.info(f"Attempting to connect to PLC with {self.connection_type} connection...")
                
                if self.connection_type == 'tcp':
                    # Test TCP connection with a socket first
                    host = self.connection_params.get('host')
                    port = self.connection_params.get('port')
                    try:
                        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        sock.settimeout(min(self.connection_params.get('timeout', 3), 2.0))
                        logger.debug(f"Testing socket connection to {host}:{port}")
                        sock.connect((host, port))
                        sock.close()
                        logger.debug(f"Socket connection to {host}:{port} successful")
                    except Exception as se:
                        logger.error(f"Socket connection test failed: {se}")
                        self.connected = False
                        return False
                        
                    # Create the actual ModbusTcpClient
                    self.client = ModbusTcpClient(
                        host=self.connection_params.get('host'),
                        port=self.connection_params.get('port'),
                        timeout=self.connection_params.get('timeout')
                    )
                else:  # RTU/Serial
                    self.client = ModbusSerialClient(
                        method='rtu',
                        port=self.connection_params.get('port'),
                        baudrate=self.connection_params.get('baudrate'),
                        bytesize=self.connection_params.get('bytesize'),
                        parity=self.connection_params.get('parity'),
                        stopbits=self.connection_params.get('stopbits'),
                        timeout=self.connection_params.get('timeout')
                    )
                
                # Perform the actual connection
                connection_result = self.client.connect()
                if connection_result:
                    # Test the connection with a simple read
                    try:
                        result = self.client.read_holding_registers(1, 1, unit=1)
                        if result is None:
                            logger.warning("Test read after connect returned None")
                        elif result.isError():
                            # Some errors are expected if the register doesn't exist
                            logger.debug(f"Test read returned error (may be normal): {result}")
                            if hasattr(result, 'function_code') and result.function_code > 0:
                                logger.info("Received valid Modbus exception response, connection OK")
                                self.connected = True
                            else:
                                logger.warning("Invalid response during test read")
                                self.connected = False
                        else:
                            logger.debug(f"Test read successful: {result.registers}")
                            self.connected = True
                    except Exception as e:
                        logger.warning(f"Test read after connect failed: {e}")
                        self.connected = False
                else:
                    logger.error("Failed to connect to PLC")
                    self.connected = False
                
                logger.info(f"PLC connection {'successful' if self.connected else 'failed'}")
                return self.connected
                
            except Exception as e:
                logger.error(f"Error connecting to PLC: {e}")
                self.connected = False
                return False
    
    def disconnect(self):
        """Disconnect from the PLC."""
        with connection_lock:
            if self.client and hasattr(self.client, 'close'):
                try:
                    self.client.close()
                    logger.info("Disconnected from PLC")
                except Exception as e:
                    logger.error(f"Error disconnecting from PLC: {e}")
                finally:
                    self.connected = False
                    self.client = None
    
    def get_client(self):
        """
        Get the current Modbus client, connecting if necessary.
        
        Returns:
            ModbusTcpClient or ModbusSerialClient: The connected client
            None: If connection failed
        """
        if not self.connected:
            if not self.connect():
                return None
        return self.client
    
    def is_connected(self):
        """Check if the PLC is currently connected."""
        return self.connected and self.client is not None
    
    def get_address_offset(self):
        """Get the configured address offset."""
        return self.address_offset
    
    # Convenience methods for common Modbus operations
    
    def read_holding_registers(self, address, count=1, unit=1):
        """
        Read holding registers from the PLC.
        
        Args:
            address (int): Register address
            count (int): Number of registers to read
            unit (int): Unit ID
            
        Returns:
            list: Register values or None if error
        """
        client = self.get_client()
        if not client:
            return None
            
        try:
            response = client.read_holding_registers(address=address, count=count, unit=unit)
            if response and not response.isError():
                return response.registers
            return None
        except Exception as e:
            logger.error(f"Error reading holding registers: {e}")
            self.connected = False
            return None
    
    def read_coils(self, address, count=1, unit=1):
        """
        Read coils from the PLC.
        
        Args:
            address (int): Coil address
            count (int): Number of coils to read
            unit (int): Unit ID
            
        Returns:
            list: Coil values (booleans) or None if error
        """
        client = self.get_client()
        if not client:
            return None
            
        try:
            response = client.read_coils(address=address, count=count, unit=unit)
            if response and not response.isError():
                return response.bits[:count]
            return None
        except Exception as e:
            logger.error(f"Error reading coils: {e}")
            self.connected = False
            return None
    
    def write_coil(self, address, value, unit=1):
        """
        Write a value to a coil.
        
        Args:
            address (int): Coil address
            value (bool): Value to write
            unit (int): Unit ID
            
        Returns:
            bool: True if successful, False otherwise
        """
        client = self.get_client()
        if not client:
            return False
            
        try:
            response = client.write_coil(address=address, value=value, unit=unit)
            return response and not response.isError()
        except Exception as e:
            logger.error(f"Error writing coil: {e}")
            self.connected = False
            return False
    
    def write_register(self, address, value, unit=1):
        """
        Write a value to a register.
        
        Args:
            address (int): Register address
            value (int): Value to write
            unit (int): Unit ID
            
        Returns:
            bool: True if successful, False otherwise
        """
        client = self.get_client()
        if not client:
            return False
            
        try:
            response = client.write_register(address=address, value=value, unit=unit)
            return response and not response.isError()
        except Exception as e:
            logger.error(f"Error writing register: {e}")
            self.connected = False
            return False

# Global singleton instance
connection_manager = PLCConnectionManager()

def get_connection_manager():
    """Get the global connection manager instance."""
    return connection_manager