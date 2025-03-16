import logging
import time
import os
import socket
import threading
from pymodbus.client.sync import ModbusSerialClient, ModbusTcpClient
from pymodbus.exceptions import ConnectionException, ModbusException
from PyQt5.QtCore import QSettings
from RaspPiReader import pool
from RaspPiReader.ui.setting_form_handler import READ_HOLDING_REGISTERS, READ_INPUT_REGISTERS

logger = logging.getLogger(__name__)

# Global lock for PLC communication to prevent multiple simultaneous connections
plc_lock = threading.RLock()

class ModbusCommunication:
    def __init__(self, name="unnamed"):
        self.client = None
        self.connected = False
        self.last_error = ""
        self.connection_type = None
        self._configured = False
        self.name = name  # Name to identify this instance in logs
        logger.info(f"ModbusCommunication instance '{name}' created")

    def configure(self, connection_type=None, **kwargs):
        """
        Configure the Modbus client with the specified parameters.
        
        Args:
            connection_type (str): 'rtu' or 'tcp'
            **kwargs: Parameters for connection.
        """
        # We'll ignore simulation_mode parameter if it's passed
        if 'simulation_mode' in kwargs:
            del kwargs['simulation_mode']
            
        self.connection_type = connection_type
        if connection_type == 'rtu':
            port = kwargs.get('port')
            if not port:
                self.last_error = "Serial port not specified"
                logger.error(f"[{self.name}] {self.last_error}")
                self._configured = False
                return False
                
            baudrate = kwargs.get('baudrate', 9600)
            bytesize = kwargs.get('bytesize', 8)
            parity = kwargs.get('parity', 'N')
            stopbits = kwargs.get('stopbits', 1)
            timeout = kwargs.get('timeout', 1)
            
            logger.info(f"[{self.name}] Configuring RTU client on port {port} with baudrate {baudrate}")
            
            try:
                self.client = ModbusSerialClient(
                    method='rtu',
                    port=port,
                    baudrate=int(baudrate),
                    bytesize=int(bytesize),
                    parity=parity,
                    stopbits=float(stopbits),
                    timeout=float(timeout),
                    retry_on_empty=True,
                    retries=3
                )
                self._configured = True
            except Exception as e:
                self.last_error = f"Failed to configure RTU client: {str(e)}"
                logger.error(f"[{self.name}] {self.last_error}")
                self._configured = False
                return False
                
        elif connection_type == 'tcp':
            host = kwargs.get('host')
            if not host:
                self.last_error = "TCP host not specified"
                logger.error(f"[{self.name}] {self.last_error}")
                self._configured = False
                return False
                
            port = kwargs.get('port', 502)
            timeout = kwargs.get('timeout', 1)
            
            logger.info(f"[{self.name}] Configuring TCP client with host {host} and port {port}")
            
            try:
                self.client = ModbusTcpClient(
                    host=host,
                    port=int(port),
                    timeout=float(timeout),
                    retry_on_empty=True,
                    retries=3
                )
                self._configured = True
            except Exception as e:
                self.last_error = f"Failed to configure TCP client: {str(e)}"
                logger.error(f"[{self.name}] {self.last_error}")
                self._configured = False
                return False
        else:
            self.last_error = f"Invalid connection type: {connection_type}"
            logger.error(f"[{self.name}] {self.last_error}")
            self._configured = False
            return False
            
        return True

    def connect(self):
        """Connect to the Modbus device with improved timeout handling."""
        if not self._configured or not self.client:
            self.last_error = "Modbus client not configured"
            logger.error(f"[{self.name}] {self.last_error}")
            self.connected = False
            return False
            
        with plc_lock:  # Use the global lock to prevent multiple simultaneous connections
            logger.debug(f"[{self.name}] Acquiring PLC connection lock")
            try:
                # For RTU connections, verify port exists on non-Windows systems
                if self.connection_type == 'rtu' and hasattr(self.client, 'port'):
                    port = self.client.port
                    # For non-Windows systems, ensure the serial device exists.
                    if not os.path.exists(port) and not port.upper().startswith('COM'):
                        self.last_error = f"Serial port {port} does not exist"
                        logger.error(f"[{self.name}] {self.last_error}")
                        self.connected = False
                        return False
                        
                # For TCP connections, verify we can reach the host first with a quick socket test
                if self.connection_type == 'tcp':
                    host = self.client.host
                    port = self.client.port
                    
                    # Use a shorter socket timeout for the initial connection test
                    socket_timeout = min(self.client.timeout, 2.0)
                    
                    try:
                        # Create the socket with a brief timeout to check host reachability
                        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        s.settimeout(socket_timeout)
                        logger.info(f"[{self.name}] Testing TCP connection to {host}:{port}")
                        connection_start = time.time()
                        s.connect((host, port))
                        connection_time = time.time() - connection_start
                        logger.info(f"[{self.name}] TCP socket connected in {connection_time:.3f} seconds")
                        
                        # Try to send/receive data to confirm port is responsive
                        try:
                            s.send(b"\x00\x00")  # Minimal test packet
                            s.settimeout(0.5)    # Brief timeout for response check
                            s.recv(1)
                        except (socket.timeout, ConnectionResetError):
                            # We don't need this to succeed - it's just a liveness test
                            pass
                        
                        s.close()
                        logger.info(f"[{self.name}] TCP connection test successful for {host}:{port}")
                        
                    except socket.timeout:
                        self.last_error = f"Connection to {host}:{port} timed out"
                        logger.error(f"[{self.name}] {self.last_error}")
                        self.connected = False
                        return False
                    except ConnectionRefusedError:
                        self.last_error = f"Connection to {host}:{port} refused - check if the PLC server is running"
                        logger.error(f"[{self.name}] {self.last_error}")
                        self.connected = False
                        return False
                    except Exception as e:
                        self.last_error = f"Socket test to {host}:{port} failed: {str(e)}"
                        logger.error(f"[{self.name}] {self.last_error}")
                        self.connected = False
                        return False
                        
                # Attempt to establish the actual Modbus connection
                logger.info(f"[{self.name}] Establishing Modbus {self.connection_type} connection")
                connection_start = time.time()
                self.connected = self.client.connect()
                connection_time = time.time() - connection_start
                logger.info(f"[{self.name}] Modbus client connect() took {connection_time:.3f} seconds")
                
                if self.connected:
                    # For TCP connections, perform a test read to verify the connection
                    if self.connection_type == 'tcp':
                        try:
                            logger.info(f"[{self.name}] Performing test read to verify Modbus connection")
                            read_start = time.time()
                            test_result = self.client.read_holding_registers(0, 1, unit=1)
                            read_time = time.time() - read_start
                            logger.info(f"[{self.name}] Test read completed in {read_time:.3f} seconds")
                            
                            if test_result is None or test_result.isError():
                                self.last_error = f"Connection test failed: {test_result}"
                                logger.error(f"[{self.name}] {self.last_error}")
                                self.connected = False
                                return False
                        except ModbusException as me:
                            self.last_error = f"Modbus exception during connection test: {str(me)}"
                            logger.error(f"[{self.name}] {self.last_error}")
                            self.connected = False
                            return False
                        except Exception as e:
                            self.last_error = f"Exception during connection test: {str(e)}"
                            logger.error(f"[{self.name}] {self.last_error}")
                            self.connected = False
                            return False
                            
                    logger.info(f"[{self.name}] Successfully connected to Modbus device via {self.connection_type}")
                else:
                    self.last_error = f"Failed to connect to Modbus device with {self.connection_type} connection"
                    logger.error(f"[{self.name}] {self.last_error}")
                    
                return self.connected
                
            except ModbusException as me:
                self.last_error = f"Modbus exception during connection: {str(me)}"
                logger.error(f"[{self.name}] {self.last_error}")
                self.connected = False
                return False
            except Exception as e:
                self.last_error = f"Exception during connection attempt: {str(e)}"
                logger.error(f"[{self.name}] {self.last_error}")
                self.connected = False
                return False
            finally:
                logger.debug(f"[{self.name}] Releasing PLC connection lock")

    def disconnect(self):
        """Disconnect from the Modbus device."""
        if self.client and self.connected:
            with plc_lock:  # Use the global lock when disconnecting
                logger.debug(f"[{self.name}] Acquiring PLC lock for disconnect")
                try:
                    self.client.close()
                except ModbusException as me:
                    logger.error(f"[{self.name}] Modbus exception while disconnecting: {str(me)}")
                except Exception as e:
                    logger.error(f"[{self.name}] Exception while disconnecting: {str(e)}")
                finally:
                    self.connected = False
                    logger.info(f"[{self.name}] Disconnected from Modbus device")
                    logger.debug(f"[{self.name}] Releasing PLC lock after disconnect")
                return True
        elif self.client:
            # If we have a client but it's not connected, just mark as disconnected
            self.connected = False
            return True
        return False

    def _ensure_connected(self):
        """
        Ensure the client is connected before performing operations.
        Returns True if connected or reconnected successfully, False otherwise.
        """
        if not self._configured or not self.client:
            self.last_error = "Modbus client not configured"
            logger.error(f"[{self.name}] {self.last_error}")
            return False
            
        if not self.connected:
            logger.info(f"[{self.name}] Not connected, attempting to reconnect...")
            return self.connect()
            
        return True

    def read_bool_addresses(self, addr, count=1, dev=1):
        """Read boolean coil values."""
        with plc_lock:  # Use the global lock for all operations
            if not self._ensure_connected():
                return None
                
            try:
                result = self.client.read_coils(addr, count, unit=dev)
                if result and not result.isError():
                    return result.bits[:count]
                else:
                    self.last_error = f"Error reading coils: {result}"
                    logger.error(f"[{self.name}] {self.last_error}")
                    return None
            except ModbusException as me:
                self.last_error = f"Modbus exception during coil read: {str(me)}"
                logger.error(f"[{self.name}] {self.last_error}")
                self.connected = False  # Mark as disconnected to trigger reconnect on next attempt
                return None
            except Exception as e:
                self.last_error = f"Exception during coil read: {str(e)}"
                logger.error(f"[{self.name}] {self.last_error}")
                return None

    def write_bool_address(self, addr, value, dev=1):
        """Write a boolean value to a coil."""
        with plc_lock:  # Use the global lock for all operations
            if not self._ensure_connected():
                return False
                
            try:
                result = self.client.write_coil(addr, value, unit=dev)
                if result and not result.isError():
                    return True
                else:
                    self.last_error = f"Error writing coil: {result}"
                    logger.error(f"[{self.name}] {self.last_error}")
                    return False
            except ModbusException as me:
                self.last_error = f"Modbus exception during coil write: {str(me)}"
                logger.error(f"[{self.name}] {self.last_error}")
                self.connected = False  # Mark as disconnected to trigger reconnect on next attempt
                return False
            except Exception as e:
                self.last_error = f"Exception during coil write: {str(e)}"
                logger.error(f"[{self.name}] {self.last_error}")
                return False

    def read_registers(self, addr, count=1, dev=1, read_type='holding'):
        """Read registers (holding or input)."""
        with plc_lock:  # Use the global lock for all operations
            if not self._ensure_connected():
                return None
                
            try:
                if read_type == 'holding':
                    result = self.client.read_holding_registers(addr, count, unit=dev)
                elif read_type == 'input':
                    result = self.client.read_input_registers(addr, count, unit=dev)
                else:
                    self.last_error = f"Invalid register read type: {read_type}"
                    logger.error(f"[{self.name}] {self.last_error}")
                    return None
                    
                if result and not result.isError():
                    return result.registers
                else:
                    self.last_error = f"Error reading registers: {result}"
                    logger.error(f"[{self.name}] {self.last_error}")
                    return None
            except ModbusException as me:
                self.last_error = f"Modbus exception during register read: {str(me)}"
                logger.error(f"[{self.name}] {self.last_error}")
                self.connected = False  # Mark as disconnected to trigger reconnect on next attempt
                return None
            except Exception as e:
                self.last_error = f"Exception during register read: {str(e)}"
                logger.error(f"[{self.name}] {self.last_error}")
                return None

    def write_register(self, addr, value, dev=1):
        """Write a value to a holding register."""
        with plc_lock:  # Use the global lock for all operations
            if not self._ensure_connected():
                return False
                
            try:
                result = self.client.write_register(addr, value, unit=dev)
                if result and not result.isError():
                    return True
                else:
                    self.last_error = f"Error writing register: {result}"
                    logger.error(f"[{self.name}] {self.last_error}")
                    return False
            except ModbusException as me:
                self.last_error = f"Modbus exception during register write: {str(me)}"
                logger.error(f"[{self.name}] {self.last_error}")
                self.connected = False  # Mark as disconnected to trigger reconnect on next attempt
                return False
            except Exception as e:
                self.last_error = f"Exception during register write: {str(e)}"
                logger.error(f"[{self.name}] {self.last_error}")
                return False
            
    def write_registers(self, addr, values, dev=1):
        """Write multiple values to consecutive holding registers."""
        with plc_lock:  # Use the global lock for all operations
            if not self._ensure_connected():
                return False
                
            try:
                result = self.client.write_registers(addr, values, unit=dev)
                if result and not result.isError():
                    return True
                else:
                    self.last_error = f"Error writing registers: {result}"
                    logger.error(f"[{self.name}] {self.last_error}")
                    return False
            except ModbusException as me:
                self.last_error = f"Modbus exception during registers write: {str(me)}"
                logger.error(f"[{self.name}] {self.last_error}")
                self.connected = False  # Mark as disconnected to trigger reconnect on next attempt
                return False
            except Exception as e:
                self.last_error = f"Exception during registers write: {str(e)}"
                logger.error(f"[{self.name}] {self.last_error}")
                return False

    def is_configured(self):
        """Check if the client is configured."""
        return self._configured

    def get_error(self):
        """Get the last error message."""
        return self.last_error


class DataReader:
    def __init__(self):
        self.running = False
        self.modbus_comm = ModbusCommunication(name="DataReader")
        self.read_type = None
        self.connected = False
        self.client = None

    def start(self):
        """Start the data reader."""
        # Only start if not already running
        if not self.running:
            self.running = True
            self.reload()
            logger.info("Data reader started")

    def stop(self):
        """Stop the data reader."""
        if self.running:
            self.running = False
            self.connected = False
            # Ensure we disconnect the modbus client
            if self.modbus_comm:
                self.modbus_comm.disconnect()
            logger.info("Data reader stopped")

    def reload(self):
        """Reload configuration and reconnect."""
        # Ensure we disconnect any existing connection
        if self.modbus_comm:
            self.modbus_comm.disconnect()
            
        # Get configuration settings
        self.read_type = pool.config('read_type', str, READ_HOLDING_REGISTERS)
        demo_mode = pool.config('demo', bool, False)
        
        if demo_mode:
            logger.info("DataReader reloading in DEMO mode")
            self.connected = True
            return
            
        # Configure the communication object with settings from pool
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
            
        logger.info(f"Configuring DataReader with: {config_params}")
        
        # Configure and connect
        if self.modbus_comm.configure(connection_type, **config_params):
            self.connected = self.modbus_comm.connect()
            if self.connected:
                logger.info("DataReader successfully connected to PLC")
            else:
                logger.error(f"DataReader failed to connect: {self.modbus_comm.get_error()}")
        else:
            logger.error(f"DataReader failed to configure: {self.modbus_comm.get_error()}")
            self.connected = False

    def _read_holding_registers(self, dev, addr):
        """Read holding registers."""
        return self.modbus_comm.read_registers(addr, 1, dev, 'holding')

    def _read_input_registers(self, dev, addr):
        """Read input registers."""
        return self.modbus_comm.read_registers(addr, 1, dev, 'input')

    def read_bool_addresses(self, dev, addr, count=6):
        """Read boolean addresses (coils)."""
        return self.modbus_comm.read_bool_addresses(addr, count, dev)

    def readData(self, dev, addr):
        """Read data based on configured read type."""
        if not self.running:
            return None
            
        # Make sure we're connected before attempting to read
        if not self.connected:
            logger.debug("DataReader not connected during readData, attempting to reconnect...")
            self.reload()
            if not self.connected:
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
        """Read a single boolean value (coil) from the PLC."""
        # Make sure we're connected before attempting to read
        if not self.running:
            return None
            
        if not self.connected:
            logger.debug("DataReader not connected during read_bool_address, attempting to reconnect...")
            self.reload()
            if not self.connected:
                return None
                
        values = self.modbus_comm.read_bool_addresses(address, count=1, dev=dev)
        if values and len(values) > 0:
            return values[0]
        return None
        
    def writeData(self, addr, value, dev=1):
        """Write data to a register."""
        if not self.running:
            return False
            
        # Make sure we're connected before attempting to write
        if not self.connected:
            logger.debug("DataReader not connected during writeData, attempting to reconnect...")
            self.reload()
            if not self.connected:
                return False
                
        return self.modbus_comm.write_register(addr, value, dev)
        
    def write_bool_address(self, addr, value, dev=1):
        """Write a boolean value to a coil."""
        if not self.running:
            return False
            
        # Make sure we're connected before attempting to write
        if not self.connected:
            logger.debug("DataReader not connected during write_bool_address, attempting to reconnect...")
            self.reload()
            if not self.connected:
                return False
                
        return self.modbus_comm.write_bool_address(addr, value, dev)
        
    def is_connected(self):
        """Check if the data reader is connected to the PLC."""
        if not self.running:
            return False
            
        # For demo mode, always return True
        if pool.config('demo', bool, False):
            return True
            
        # Check the connection status
        return self.connected and (self.modbus_comm and self.modbus_comm.connected)


# Create and expose a singleton instance
dataReader = DataReader()