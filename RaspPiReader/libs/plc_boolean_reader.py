import logging
import traceback
from pymodbus.client.sync import ModbusTcpClient, ModbusSerialClient
from pymodbus.exceptions import ModbusException, ConnectionException

logger = logging.getLogger(__name__)

class PLCBooleanReader:
    """
    Class for handling boolean (coil) values from the PLC.
    
    This class is responsible for connecting to the PLC, reading boolean coils and writing boolean commands.
    It includes better error handling, reconnect attempts, and detailed debugging. A configurable address offset 
    is supported to adjust the coil addressing as required by your PLC configuration.
    """

    def __init__(self, client=None, connection_type='tcp', connection_params=None):
        """
        Initialize the PLC Boolean Reader

        Args:
            client: An existing Modbus client instance (optional)
            connection_type: 'tcp' or 'rtu'
            connection_params: Dict with connection parameters. Optionally include:
                - host: PLC IP (for TCP)
                - port: Port number (TCP) or serial port (RTU)
                - timeout: Timeout for connection
                - address_offset: (optional) Offset to be added to the coil addresses (default is 0)
        """
        self.client = client
        self.connection_type = connection_type
        self.connection_params = connection_params or {}
        self.connected = False

        # Configurable address offset: if your actual PLC coil addresses are high (e.g. first coil=8193) set offset=8192.
        self.address_offset = self.connection_params.get("address_offset", 0)

        # Define boolean address mappings (logical index -> PLC coil number without offset)
        # For example, current mapping: 1 maps to coil number 1, 2 maps to coil number 17, etc.
        # When reading/writing, the actual coil address is calculated as: actual_address = address_offset + defined_address - 1.
        self.boolean_addresses = {
            1: 1,    # Logical index 1, actual coil = address_offset + 1 - 1 = address_offset + 0
            2: 17,   # Logical index 2, actual coil = address_offset + 17 - 1 = address_offset + 16
            3: 33,   # Logical index 3 => address_offset + 32
            4: 49,   # Logical index 4 => address_offset + 48
            5: 65,   # Logical index 5 => address_offset + 64
            6: 81,   # Logical index 6 => address_offset + 80
            # Add more boolean addresses as needed
        }

        # Labels for each boolean value for display purposes
        self.boolean_labels = {
            1: "LA 1",
            2: "LA 2",
            3: "LA 3",
            4: "LA 4",
            5: "LA 5",
            6: "LA 6",
            # Add more labels as needed
        }

        # Cache of last read values to be used for display
        self.last_values = {}

        logger.info("PLCBooleanReader initialized with address_offset=%s", self.address_offset)

    def connect(self):
        """
        Connect to the PLC if not already connected.

        Returns:
            bool: True if connected successfully, False otherwise.
        """
        # If there's already a valid connection, return early
        if self.client and getattr(self.client, "connected", False):
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
            if not self.connected:
                logger.error("Connection attempt failed to the PLC")
            else:
                logger.info("Connected to the PLC")
            return self.connected

        except Exception as e:
            logger.error("Error connecting to PLC: %s", e)
            logger.debug(traceback.format_exc())
            self.connected = False
            return False

    def update_connection(self):
        """
        Force a disconnect and reconnect to the PLC. Useful in periodic update loops.
        """
        self.disconnect()
        return self.connect()

    def disconnect(self):
        """
        Disconnect from the PLC.
        """
        if self.client and getattr(self.client, "connected", False):
            self.client.close()
            logger.info("Disconnected from PLC")
        self.connected = False

    def _get_actual_address(self, defined_address):
        actual_address = self.address_offset + defined_address - 1
        logger.debug("Calculated actual address: %s (defined: %s, offset: %s)", actual_address, defined_address, self.address_offset)
        return actual_address

    def read_boolean_values(self, addresses, unit=1):
        """
        Read boolean values (coils) from the PLC.

        Tries to read each boolean coil in a loop so that failures on one
        do not prevent reading of the others.

        Args:
            addresses (list): List of coil addresses (one based) to read.
            unit (int): Unit ID of the slave device.

        Returns:
            dict: Dictionary with address as key and boolean value as value.
        """
        results = {}
        if not addresses:
            return results

        if not self.connect():
            logger.error("Failed to connect to PLC in read_boolean_values")
            return results

        for address in addresses:
            try:
                modbus_address = self._get_actual_address(address)
                logger.debug("Reading coil at defined address %s (actual address %s)", address, modbus_address)
                response = self.client.read_coils(address=modbus_address, count=1, unit=unit)
                if not response.isError():
                    results[address] = response.bits[0]
                else:
                    logger.error("Error reading coil at address %s: %s", address, response)
                    results[address] = None
            except ConnectionException as ce:
                logger.error("Connection error reading boolean value at address %s: %s", address, ce)
                results[address] = None
            except ModbusException as me:
                logger.error("Modbus error reading boolean value at address %s: %s", address, me)
                results[address] = None
            except Exception as e:
                logger.error("Unexpected error reading boolean value at address %s: %s", address, e)
                logger.debug(traceback.format_exc())
                results[address] = None

        return results

    def read_boolean_value(self, address, unit=1):
        """
        Read a boolean/coil value from the specified address.
        
        Args:
            address (int): The address to read from (1-based addressing)
            unit (int): The slave unit ID
            
        Returns:
            bool: The boolean value read from the address, or None if there was an error
        """
        try:
            # Convert to 0-based addressing if using 1-based addressing in the UI
            modbus_address = address - 1
            
            # Log the request
            self.logger.debug(f"Reading boolean from address {address} (Modbus address {modbus_address})")
            
            # Make sure we're connected
            if not self.is_connected():
                self.logger.error(f"Cannot read boolean from address {address}: Not connected")
                return None
                
            # Read the coil
            response = self.client.read_coils(address=modbus_address, count=1, unit=unit)
            
            # Check for valid response
            if response and not response.isError():
                value = response.bits[0]
                self.logger.debug(f"Successfully read boolean from address {address}: {value}")
                return value
            else:
                self.logger.error(f"Error reading boolean from address {address}: {response}")
                return None
                
        except Exception as e:
            self.logger.exception(f"Unexpected error reading boolean from address {address}: {str(e)}")
            return None

    def read_boolean_value_by_index(self, address_index, unit=1):
        """
        Read a single boolean value from the PLC using the address index

        Args:
            address_index (int): The index of the boolean address (1-based).
            unit (int): Unit ID of the slave device.

        Returns:
            bool or None: The boolean value read from the PLC.
        """
        if address_index not in self.boolean_addresses:
            logger.warning("Boolean address index %s not configured", address_index)
            return None

        # Get the defined address from the mapping
        defined_address = self.boolean_addresses[address_index]
        # Read the coil using the calculated actual address
        value = self.read_boolean_value(defined_address, unit)
        if value is not None:
            self.last_values[address_index] = value
            logger.debug("Read boolean index %s (defined: %s, actual: %s): %s = %s",
                         address_index, defined_address, self._get_actual_address(defined_address),
                         self.boolean_labels.get(address_index, 'N/A'), value)
        else:
            logger.error("Failed to read boolean value for index %s (defined: %s, actual: %s)",
                         address_index, defined_address, self._get_actual_address(defined_address))
        return value

    def read_all_boolean_values(self, unit=1):
        """
        Read all configured boolean values from the PLC.

        Each boolean address is read individually. This method ensures that even if one
        boolean (e.g., Boolean 6) fails, it will still attempt to read the others.

        Args:
            unit (int): Unit ID of the slave device.

        Returns:
            dict: Dictionary mapping address indices to their boolean values.
        """
        results = {}
        for address_index in self.boolean_addresses:
            results[address_index] = self.read_boolean_value_by_index(address_index, unit)
        return results

    def get_boolean_label(self, address_index):
        """
        Get the display label for a boolean address.

        Args:
            address_index (int): The index of the boolean address.

        Returns:
            str: The label for this boolean address.
        """
        return self.boolean_labels.get(address_index, f"Bool {address_index}")

    def get_boolean_status_text(self, address_index):
        """
        Get the status text for a boolean address with its current value.

        Args:
            address_index (int): The index of the boolean address.

        Returns:
            str: The status text (e.g., "LA 6: ON"). If no value is cached, returns "UNKNOWN".
        """
        label = self.get_boolean_label(address_index)
        value = self.last_values.get(address_index)
        status = "UNKNOWN" if value is None else ("ON" if value else "OFF")
        return f"{label}: {status}"

    def write_boolean_value(self, address, value, unit=1):
        """
        Write a boolean value (coil) to the PLC.

        Args:
            address (int): Coil address (one based) to write to.
            value (bool): Boolean value to write.
            unit (int): Unit ID of the slave device.

        Returns:
            bool: True if successful, False otherwise.
        """
        if not self.connect():
            logger.error("Failed to connect to PLC in write_boolean_value")
            return False

        try:
            modbus_address = self._get_actual_address(address)
            logger.debug("Writing coil at defined address %s (actual address %s) value: %s",
                         address, modbus_address, value)
            response = self.client.write_coil(address=modbus_address, value=value, unit=unit)
            if not response.isError():
                logger.debug("Wrote value %s to coil at address %s", value, address)
                return True
            else:
                logger.error("Error writing to coil at address %s: %s", address, response)
                return False

        except Exception as e:
            logger.error("Error writing boolean value to address %s: %s", address, e)
            logger.debug(traceback.format_exc())
            return False

    def write_boolean_value_by_index(self, address_index, value, unit=1):
        """
        Write a boolean value to the PLC using the address index.

        Args:
            address_index (int): The index of the boolean address to write to.
            value (bool): Boolean value to write.
            unit (int): Unit ID of the slave device.

        Returns:
            bool: True if successful, False otherwise.
        """
        if address_index not in self.boolean_addresses:
            logger.warning("Boolean address index %s not configured, cannot write value.", address_index)
            return False

        defined_address = self.boolean_addresses[address_index]
        result = self.write_boolean_value(defined_address, value, unit)
        if result:
            self.last_values[address_index] = value
            logger.debug("Successfully wrote %s to Boolean index %s (defined: %s, actual: %s)",
                         value, address_index, defined_address, self._get_actual_address(defined_address))
        else:
            logger.error("Error writing boolean value at index %s (defined: %s, actual: %s)",
                         address_index, defined_address, self._get_actual_address(defined_address))
        return result