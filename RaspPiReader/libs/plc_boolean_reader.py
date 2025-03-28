import logging
import traceback
from pymodbus.exceptions import ModbusException, ConnectionException
from RaspPiReader import pool
from RaspPiReader.libs.plc_connection_manager import get_connection_manager

logger = logging.getLogger(__name__)

class PLCBooleanReader:
    """
    Class for handling boolean (coil) values from the PLC.
    
    This class uses the shared connection manager to read boolean coils and write boolean values.
    It supports a configurable address offset and loads the boolean addresses and
    labels from configuration settings so that users can update them via file>settings.
    """

    def __init__(self):
        """Initialize the PLC Boolean Reader."""
        # Get the shared connection manager
        self.connection_manager = get_connection_manager()
        
        # Configurable address offset (for example, if actual first coil is 8193, use offset 8192)
        self.address_offset = self.connection_manager.get_address_offset()

        # Load boolean addresses and labels from configuration.
        # The user can set settings keys "plc/bool_address_1" ... "plc/bool_address_6"
        # and "plc/bool_label_1" ... "plc/bool_label_6". Fallback to default mapping otherwise.
        self.boolean_addresses = {}
        self.boolean_labels = {}
        default_addresses = {1: 1, 2: 17, 3: 33, 4: 49, 5: 65, 6: 81}
        default_labels = {1: "LA 1", 2: "LA 2", 3: "LA 3", 4: "LA 4", 5: "LA 5", 6: "LA 6"}
        for i in range(1, 7):
            addr = pool.config(f'plc/bool_address_{i}', int, None)
            if addr is None:
                addr = default_addresses[i]
            self.boolean_addresses[i] = addr

            lbl = pool.config(f'plc/bool_label_{i}', str, None)
            if lbl is None:
                lbl = default_labels[i]
            self.boolean_labels[i] = lbl

        # Cache of last read values for display
        self.last_values = {}

        logger.info("PLCBooleanReader initialized with address_offset=%s", self.address_offset)
        logger.debug("Boolean addresses: %s", self.boolean_addresses)
        logger.debug("Boolean labels: %s", self.boolean_labels)

    def is_connected(self):
        """Return True if the connection to the PLC is established."""
        return self.connection_manager.is_connected()

    def connect(self):
        """
        Connect to the PLC if not already connected.
        
        Returns:
            bool: True if connected successfully, False otherwise.
        """
        return self.connection_manager.connect()

    def update_connection(self):
        """Force a reconnect to the PLC."""
        return self.connection_manager.connect(force_reconnect=True)

    def disconnect(self):
        """Disconnect from the PLC."""
        self.connection_manager.disconnect()

    def _get_actual_address(self, defined_address):
        """
        Calculate the actual PLC coil address.
        
        If the defined address is above 1000 it is assumed to be an absolute address,
        so only 0-based indexing is applied. Otherwise, the configured offset is added.
        
        Args:
            defined_address (int): The defined coil address (1-based).
            
        Returns:
            int: The actual coil address for the Modbus call.
        """
        if defined_address > 1000:
            actual_address = defined_address - 1
        else:
            actual_address = self.address_offset + defined_address - 1
        logger.debug("Calculated actual address: %s (defined: %s, offset: %s)",
                    actual_address, defined_address, self.address_offset)
        return actual_address

    def read_boolean_values(self, addresses, unit=1):
        """
        Read boolean coil values from the PLC.
        
        Args:
            addresses (list): List of coil addresses (1-based).
            unit (int): Slave unit ID.
        
        Returns:
            dict: Mapping of each address to its boolean value, or None if an error occurred.
        """
        results = {}
        if not addresses:
            return results

        if not self.connection_manager.is_connected():
            if not self.connection_manager.connect():
                logger.error("Failed to connect to PLC in read_boolean_values")
                return results

        for address in addresses:
            try:
                modbus_address = self._get_actual_address(address)
                logger.debug("Reading coil at defined address %s (actual address %s)", address, modbus_address)
                
                # Use the connection manager to read coils
                coil_values = self.connection_manager.read_coils(modbus_address, 1, unit)
                if coil_values is not None:
                    results[address] = coil_values[0]
                else:
                    logger.error("Error reading coil at address %s", address)
                    results[address] = None
                    
            except Exception as e:
                logger.error("Unexpected error reading boolean at address %s: %s", address, e)
                logger.debug(traceback.format_exc())
                results[address] = None

        return results

    def read_boolean_value(self, address, unit=1):
        """
        Read a single boolean value from the PLC.
        
        Args:
            address (int): Coil address (1-based).
            unit (int): Slave unit ID.
            
        Returns:
            bool or None: The boolean value or None if an error occurred.
        """
        try:
            modbus_address = self._get_actual_address(address)
            logger.debug("Reading coil from address %s (Modbus address %s)", address, modbus_address)
            
            # Use the connection manager to read the coil
            coil_values = self.connection_manager.read_coils(modbus_address, 1, unit)
            if coil_values is not None:
                value = coil_values[0]
                logger.debug("Successfully read coil from address %s: %s", address, value)
                return value
            else:
                logger.error("Error reading coil from address %s", address)
                return None
                
        except Exception as e:
            logger.exception("Unexpected error reading value from address %s: %s", address, str(e))
            return None

    def read_boolean_value_by_index(self, address_index, unit=1):
        """
        Read a boolean value by its configured index.
        
        Args:
            address_index (int): The index (1-based) of the boolean address.
            unit (int): Slave unit ID.
            
        Returns:
            bool or None: The read boolean value.
        """
        if address_index not in self.boolean_addresses:
            logger.warning("Boolean address index %s not configured", address_index)
            return None

        defined_address = self.boolean_addresses[address_index]
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
        Read all configured boolean values.
        
        Args:
            unit (int): Slave unit ID.
            
        Returns:
            dict: Mapping of boolean address indices to their values.
        """
        results = {}
        for address_index in self.boolean_addresses:
            results[address_index] = self.read_boolean_value_by_index(address_index, unit)
        return results

    def get_boolean_label(self, address_index):
        """Return the display label for the given boolean index."""
        return self.boolean_labels.get(address_index, f"Bool {address_index}")

    def get_boolean_status_text(self, address_index):
        """
        Get the status text for a boolean address.
        
        Args:
            address_index (int): The boolean address index.
            
        Returns:
            str: The status text (e.g. "LA 6: ON") or "UNKNOWN" if no value is cached.
        """
        label = self.get_boolean_label(address_index)
        value = self.last_values.get(address_index)
        status = "UNKNOWN" if value is None else ("ON" if value else "OFF")
        return f"{label}: {status}"

    def write_boolean_value(self, address, value, unit=1):
        """
        Write a boolean value to a PLC coil.
        
        Args:
            address (int): The coil address (1-based).
            value (bool): The value to write.
            unit (int): Slave unit ID.
            
        Returns:
            bool: True if successful, False otherwise.
        """
        try:
            modbus_address = self._get_actual_address(address)
            logger.debug("Writing coil at defined address %s (actual address %s) value: %s",
                         address, modbus_address, value)
                         
            # Use the connection manager to write the coil
            result = self.connection_manager.write_coil(modbus_address, value, unit)
            if result:
                logger.debug("Wrote value %s to coil at address %s", value, address)
                return True
            else:
                logger.error("Error writing to coil at address %s", address)
                return False
                
        except Exception as e:
            logger.error("Error writing boolean value to address %s: %s", address, e)
            logger.debug(traceback.format_exc())
            return False

    def write_boolean_value_by_index(self, address_index, value, unit=1):
        """
        Write a boolean value using the address index.
        
        Args:
            address_index (int): The boolean address index.
            value (bool): The value to write.
            unit (int): Slave unit ID.
            
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
