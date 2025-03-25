import logging
from pymodbus.client.sync import ModbusTcpClient, ModbusSerialClient
from pymodbus.exceptions import ModbusException, ConnectionException

logger = logging.getLogger(__name__)

class PLCBooleanReader:
    """
    A dedicated class for reading boolean values (coils) from PLCs
    """
    
    def __init__(self, client=None, connection_type='tcp', connection_params=None):
        """
        Initialize the PLC Boolean Reader
        
        Args:
            client: An existing Modbus client instance (optional)
            connection_type: 'tcp' or 'rtu'
            connection_params: Dict with connection parameters
        """
        self.client = client
        self.connection_type = connection_type
        self.connection_params = connection_params or {}
        self.connected = False
        
    def connect(self):
        """
        Connect to the PLC if not already connected
        
        Returns:
            bool: True if connected successfully, False otherwise
        """
        if self.client and self.client.connected:
            return True
            
        try:
            if self.connection_type == 'tcp':
                if not self.connection_params.get('host'):
                    logger.error("Missing host parameter for TCP connection")
                    return False
                    
                self.client = ModbusTcpClient(
                    host=self.connection_params.get('host'),
                    port=self.connection_params.get('port', 502),
                    timeout=self.connection_params.get('timeout', 3)
                )
            else:  # RTU/Serial
                if not self.connection_params.get('port'):
                    logger.error("Missing port parameter for RTU connection")
                    return False
                    
                self.client = ModbusSerialClient(
                    method='rtu',
                    port=self.connection_params.get('port'),
                    baudrate=self.connection_params.get('baudrate', 9600),
                    bytesize=self.connection_params.get('bytesize', 8),
                    parity=self.connection_params.get('parity', 'N'),
                    stopbits=self.connection_params.get('stopbits', 1),
                    timeout=self.connection_params.get('timeout', 3)
                )
                
            self.connected = self.client.connect()
            return self.connected
            
        except Exception as e:
            logger.error(f"Error connecting to PLC: {e}")
            self.connected = False
            return False
            
    def disconnect(self):
        """
        Disconnect from the PLC
        """
        if self.client and self.client.connected:
            self.client.close()
        self.connected = False
            
    def read_boolean_values(self, addresses, unit=1):
        """
        Read boolean values (coils) from the PLC
        
        Args:
            addresses (list): List of coil addresses to read
            unit (int): Unit ID of the slave device
            
        Returns:
            dict: Dictionary with address as key and boolean value as value
        """
        results = {}
        
        if not addresses:
            return results
            
        if not self.connect():
            logger.error("Failed to connect to PLC")
            return results
            
        try:
            for address in addresses:
                # Convert address to zero-based (Modbus protocol expects zero-based addressing)
                # If your addresses are already zero-based, remove this subtraction
                modbus_address = address - 1
                
                # Read a single coil
                response = self.client.read_coils(address=modbus_address, count=1, unit=unit)
                
                if not response.isError():
                    # Get the boolean value (first bit in response)
                    results[address] = response.bits[0]
                else:
                    logger.error(f"Error reading coil at address {address}: {response}")
                    results[address] = None
                    
            return results
        
        except ConnectionException as ce:
            logger.error(f"Connection error reading boolean values: {ce}")
            return results
        except ModbusException as me:
            logger.error(f"Modbus error reading boolean values: {me}")
            return results
        except Exception as e:
            logger.error(f"Unexpected error reading boolean values: {e}")
            return results
        finally:
            # Optional: You may want to keep the connection open if reading frequently
            # self.disconnect()
            pass
            
    def read_boolean_value(self, address, unit=1):
        """
        Read a single boolean value (coil) from the PLC
        
        Args:
            address (int): Coil address to read
            unit (int): Unit ID of the slave device
            
        Returns:
            bool or None: The coil value or None if there was an error
        """
        results = self.read_boolean_values([address], unit)
        return results.get(address)
        
    def write_boolean_value(self, address, value, unit=1):
        """
        Write a boolean value (coil) to the PLC
        
        Args:
            address (int): Coil address to write to
            value (bool): Boolean value to write
            unit (int): Unit ID of the slave device
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.connect():
            logger.error("Failed to connect to PLC")
            return False
            
        try:
            # Convert address to zero-based (Modbus protocol expects zero-based addressing)
            modbus_address = address - 1
            
            # Write the coil value
            response = self.client.write_coil(address=modbus_address, value=value, unit=unit)
            
            if not response.isError():
                return True
            else:
                logger.error(f"Error writing to coil at address {address}: {response}")
                return False
                
        except Exception as e:
            logger.error(f"Error writing boolean value: {e}")
            return False
        finally:
            # Optional: You may want to keep the connection open if writing frequently
            # self.disconnect()
            pass
