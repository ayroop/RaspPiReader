"""
Direct Boolean Reader module for reliable reading of PLC coils/booleans.
This module provides a simplified, direct approach to reading boolean values
from a PLC using the ModbusTcpClient with improved error handling and diagnostics.
Supports dynamic start/stop functionality for on-demand reading.
"""

import logging
import time
from threading import Thread, Event
from datetime import datetime
from pymodbus.client.sync import ModbusTcpClient
from pymodbus.exceptions import ConnectionException, ModbusException

logger = logging.getLogger(__name__)

class DirectBooleanReader:
    """
    A lightweight class that directly reads booleans using ModbusTcpClient
    without the complexity of the full-featured PLCBooleanReader.
    
    This class uses the exact same approach that works in your test script,
    with added support for continuous reading in a background thread.
    """
    
    def __init__(self, host='127.0.0.1', port=502, timeout=3):
        """
        Initialize the reader with connection parameters
        
        Args:
            host (str): PLC IP address 
            port (int): TCP port
            timeout (int): Connection timeout in seconds
        """
        self.host = host
        self.port = port
        self.timeout = timeout
        self.client = None
        self.connection_attempts = 0
        self.last_connection_time = 0
        
        # Thread control attributes
        self.reading_thread = None
        self.stop_event = Event()
        self.is_reading = False
        self.read_interval = 1.0  # seconds between reads
        self.boolean_values = {}
        self.last_read_time = None
        self.addresses_to_read = []
        self.unit_id = 1
    
    def connect(self):
        """
        Connect to the PLC
        
        Returns:
            bool: True if successful, False otherwise
        """
        # Limit connection attempts (avoid hammering the connection)
        current_time = time.time()
        if (current_time - self.last_connection_time) < 2 and self.connection_attempts > 3:
            logger.warning("Too many connection attempts in a short time, backing off")
            return False
            
        self.last_connection_time = current_time
        self.connection_attempts += 1
        
        try:
            if self.client:
                self.client.close()
                
            logger.debug(f"Connecting to PLC at {self.host}:{self.port}")
            self.client = ModbusTcpClient(
                host=self.host, 
                port=self.port,
                timeout=self.timeout,
                retry_on_empty=True
            )
            
            if self.client.connect():
                logger.info(f"Successfully connected to PLC at {self.host}:{self.port}")
                self.connection_attempts = 0
                return True
            else:
                logger.error(f"Failed to connect to PLC at {self.host}:{self.port}")
                return False
        except Exception as e:
            logger.exception(f"Error connecting to PLC: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from the PLC"""
        if self.client:
            self.client.close()
            self.client = None
            
    def start_reading(self, addresses=None, unit=1, interval=1.0):
        """
        Start the boolean reading thread if not already running
        
        Args:
            addresses (list): List of addresses to read continuously
            unit (int): The slave unit ID
            interval (float): Time between reads in seconds
        """
        if self.is_reading:
            logger.warning("Boolean reader is already running")
            return
            
        # Set reading parameters
        self.addresses_to_read = addresses if addresses else []
        self.unit_id = unit
        self.read_interval = interval
        
        # Clear stop event if it was previously set
        self.stop_event.clear()
        
        # Set flag indicating reader is active
        self.is_reading = True
        
        # Start the reading thread
        self.reading_thread = Thread(target=self._read_loop, daemon=True)
        self.reading_thread.start()
        
        logger.info(f"Boolean reader started for addresses: {self.addresses_to_read}")
    
    def stop_reading(self):
        """Stop the boolean reading thread"""
        if not self.is_reading:
            logger.warning("Boolean reader is not running")
            return
        
        # Set the stop event to signal thread to exit
        self.stop_event.set()
        
        # Wait for thread to finish if it's running
        if self.reading_thread and self.reading_thread.is_alive():
            self.reading_thread.join(timeout=2.0)
        
        # Reset flags
        self.is_reading = False
        self.reading_thread = None
        
        logger.info("Boolean reader stopped")
        
    def _read_loop(self):
        """Main reading loop that runs until stop_event is set"""
        logger.info("Boolean reading loop started")
        
        while not self.stop_event.is_set():
            try:
                # Make sure we're connected
                if not self.client or not self.client.is_socket_open():
                    if not self.connect():
                        logger.error("Failed to connect to PLC in reading loop")
                        self.stop_event.wait(self.read_interval)
                        continue
                
                # Read all configured addresses
                if self.addresses_to_read:
                    results = self.read_multiple_booleans(self.addresses_to_read, self.unit_id)
                    
                    # Store the values with timestamp
                    timestamp = datetime.now()
                    for address, value in results.items():
                        self.boolean_values[address] = {
                            'value': value,
                            'timestamp': timestamp,
                            'address': address
                        }
                    
                    # Update last read time
                    self.last_read_time = timestamp
                    
                    # Notify any listeners that new data is available
                    self._notify_data_updated()
                
                # Wait for the next read interval or until stop_event is set
                self.stop_event.wait(self.read_interval)
                
            except Exception as e:
                logger.error(f"Error in boolean reading loop: {e}")
                # Don't exit the loop on error, just try again after waiting
                self.stop_event.wait(self.read_interval)
        
        logger.info("Boolean reading loop exited")
    
    def _notify_data_updated(self):
        """
        Notify listeners that boolean data has been updated
        Override this method in subclasses to implement custom notification logic
        """
        pass
    
    def get_value(self, address):
        """
        Get the most recent value for a specific boolean address
        
        Args:
            address (int): The address to get the value for
            
        Returns:
            dict: Value data including the value and timestamp, or None if not available
        """
        return self.boolean_values.get(address)
    
    def get_all_values(self):
        """
        Get all current boolean values with their timestamps
        
        Returns:
            dict: Dictionary mapping addresses to value data
        """
        return self.boolean_values.copy()
    
    def is_active(self):
        """
        Check if the boolean reader is currently active
        
        Returns:
            bool: True if the reader is running, False otherwise
        """
        return self.is_reading
    
    def read_boolean(self, address, unit=1):
        """
        Read a boolean/coil value from the PLC
        
        Args:
            address (int): The address to read (1-based addressing)
            unit (int): The slave unit ID
            
        Returns:
            bool or None: The boolean value, or None if error
        """
        # Make sure we're connected
        if not self.client or not self.client.is_socket_open():
            if not self.connect():
                logger.error(f"Failed to connect to PLC when reading boolean {address}")
                return None
        
        try:
            # Convert to 0-based addressing for Modbus
            modbus_address = address - 1
            
            logger.debug(f"Reading boolean from address {address} (Modbus address {modbus_address})")
            response = self.client.read_coils(modbus_address, count=1, unit=unit)
            
            if response and not response.isError():
                value = response.bits[0]
                logger.debug(f"Successfully read boolean from address {address}: {value}")
                return value
            else:
                error_msg = str(response) if response else "No response"
                logger.error(f"Error reading boolean from address {address}: {error_msg}")
                
                # Force reconnection on next attempt
                self.client.close()
                return None
        except ConnectionException as e:
            logger.error(f"Connection error reading boolean from address {address}: {e}")
            self.client.close()
            return None
        except ModbusException as e:
            logger.error(f"Modbus error reading boolean from address {address}: {e}")
            return None
        except Exception as e:
            logger.exception(f"Exception reading boolean from address {address}: {e}")
            return None
    
    def read_multiple_booleans(self, addresses, unit=1):
        """
        Read multiple boolean values from the PLC
        
        Args:
            addresses (list): List of addresses to read
            unit (int): The slave unit ID
            
        Returns:
            dict: Dictionary mapping addresses to values
        """
        results = {}
        
        # Make sure we're connected
        if not self.client or not self.client.is_socket_open():
            if not self.connect():
                logger.error("Failed to connect to PLC")
                return {addr: None for addr in addresses}
        
        # Try to read each address individually for maximum reliability
        for address in addresses:
            results[address] = self.read_boolean(address, unit)
            
        return results

# Helper functions for direct use without instantiating the class

def read_boolean(address, host='127.0.0.1', port=502, unit=1, timeout=3):
    """
    Read a boolean value directly (one-shot function)
    
    Args:
        address (int): The address to read (1-based)
        host (str): PLC IP address
        port (int): TCP port
        unit (int): Slave unit ID
        timeout (int): Connection timeout in seconds
        
    Returns:
        bool or None: The boolean value or None
    """
    client = ModbusTcpClient(host=host, port=port, timeout=timeout, retry_on_empty=True)
    if not client.connect():
        logger.error(f"Failed to connect to Modbus server at {host}:{port}")
        return None
    
    try:
        # Convert to 0-based addressing
        modbus_address = address - 1
        
        response = client.read_coils(modbus_address, count=1, unit=unit)
        if response and not response.isError():
            return response.bits[0]
        else:
            error_msg = str(response) if response else "No response"
            logger.error(f"Error reading boolean address {address}: {error_msg}")
            return None
    except ConnectionException as e:
        logger.error(f"Connection error reading boolean address {address}: {e}")
        return None
    except ModbusException as e:
        logger.error(f"Modbus error reading boolean address {address}: {e}")
        return None
    except Exception as e:
        logger.exception(f"Exception reading boolean address {address}: {e}")
        return None
    finally:
        client.close()

def read_multiple_booleans(addresses, host='127.0.0.1', port=502, unit=1, timeout=3):
    """
    Read multiple boolean values directly (one-shot function)
    
    Args:
        addresses (list): List of addresses to read
        host (str): PLC IP address
        port (int): TCP port
        unit (int): Slave unit ID
        timeout (int): Connection timeout in seconds
        
    Returns:
        dict: Dictionary mapping addresses to values
    """
    results = {}
    client = ModbusTcpClient(host=host, port=port, timeout=timeout, retry_on_empty=True)
    
    if not client.connect():
        logger.error(f"Failed to connect to Modbus server at {host}:{port}")
        return {addr: None for addr in addresses}
    
    try:
        for address in addresses:
            # Convert to 0-based addressing
            modbus_address = address - 1
            
            response = client.read_coils(modbus_address, count=1, unit=unit)
            if response and not response.isError():
                results[address] = response.bits[0]
            else:
                error_msg = str(response) if response else "No response"
                logger.error(f"Error reading boolean address {address}: {error_msg}")
                results[address] = None
    except ConnectionException as e:
        logger.error(f"Connection error reading multiple boolean addresses: {e}")
        # Fill in None for any addresses we haven't read yet
        for addr in addresses:
            if addr not in results:
                results[addr] = None
    except ModbusException as e:
        logger.error(f"Modbus error reading multiple boolean addresses: {e}")
        # Fill in None for any addresses we haven't read yet
        for addr in addresses:
            if addr not in results:
                results[addr] = None
    except Exception as e:
        logger.exception(f"Exception reading multiple boolean addresses: {e}")
        # Fill in None for any addresses we haven't read yet
        for addr in addresses:
            if addr not in results:
                results[addr] = None
    finally:
        client.close()
    
    return results

# Singleton instance for global access
_instance = None

def get_instance(host='127.0.0.1', port=502, timeout=3):
    """
    Get or create the singleton instance of DirectBooleanReader
    
    Args:
        host (str): PLC IP address
        port (int): TCP port
        timeout (int): Connection timeout in seconds
        
    Returns:
        DirectBooleanReader: The singleton instance
    """
    global _instance
    if _instance is None:
        _instance = DirectBooleanReader(host=host, port=port, timeout=timeout)
    return _instance
