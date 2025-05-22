import logging, os, time, socket, threading
from pymodbus.client.sync import ModbusSerialClient, ModbusTcpClient
from pymodbus.exceptions import ConnectionException, ModbusException
from PyQt5.QtCore import QSettings, QObject, pyqtSignal, QThread, QTimer
from PyQt5 import QtCore
from RaspPiReader import pool
from RaspPiReader.ui.setting_form_handler import READ_HOLDING_REGISTERS, READ_INPUT_REGISTERS

logger = logging.getLogger(__name__)

# Global lock for PLC communication to prevent multiple simultaneous connections
plc_lock = threading.RLock()

class ConnectionWorker(QObject):
    """Worker class to handle PLC connection in a separate thread"""
    connectionFinished = pyqtSignal(bool, str)
    
    def __init__(self, modbus_comm):
        super().__init__()
        self.modbus_comm = modbus_comm
        
    def connect(self):
        """Perform the connection process in a background thread"""
        success = False
        error_msg = ""
        
        try:
            success = self.modbus_comm._connect_internal()
            if not success:
                error_msg = self.modbus_comm.last_error
        except Exception as e:
            error_msg = f"Exception during connection: {str(e)}"
            logger.error(f"[{self.modbus_comm.name}] {error_msg}")
            
        self.connectionFinished.emit(success, error_msg)

class ModbusCommunication:
    def __init__(self, name="unnamed"):
        self.client = None
        self.connected = False
        self.last_error = ""
        self.connection_type = None  # Should be 'tcp' or 'rtu'
        self._configured = False
        self.name = name  # Identifier for logging
        self._connection_thread = None
        self._connection_worker = None
        self._connection_timeout = 10  # Default timeout in seconds
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
            timeout = float(timeout)  # Ensure timeout is always float
            self._connection_timeout = timeout
            
            logger.info(f"[{self.name}] Configuring RTU client on port {port} with baudrate {baudrate}")
            
            try:
                self.client = ModbusSerialClient(
                    method='rtu',
                    port=port,
                    baudrate=int(baudrate),
                    bytesize=int(bytesize),
                    parity=parity,
                    stopbits=float(stopbits),
                    timeout=timeout,  # Already float
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
            timeout = float(timeout)  # Ensure timeout is always float
            self._connection_timeout = timeout
            
            logger.info(f"[{self.name}] Configuring TCP client with host {host} and port {port}")
            
            try:
                self.client = ModbusTcpClient(
                    host=host,
                    port=int(port),
                    timeout=timeout,  # Already float
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

    def _connect_internal(self):
        """Internal method to perform the actual connection process"""
        if (not self._configured) or (not self.client):
            self.connection_type = pool.config("plc/comm_mode", str, "tcp").lower()
            if self.connection_type == "tcp":
                host = pool.config("plc/host", str, "192.168.1.185")
                port = pool.config("plc/tcp_port", int, 502)
                timeout = pool.config("plc/timeout", float, 6.0)
                timeout = float(timeout)  # Ensure timeout is always float
                self.client = ModbusTcpClient(host, port=port, timeout=timeout)
                self._configured = True
                self._connection_timeout = timeout
                logger.info(f"[{self.name}] Client configured with host={host}, port={port}, timeout={timeout}")
            elif self.connection_type == "rtu":
                port = pool.config("plc/com_port", str, "COM1")
                baudrate = pool.config("plc/baudrate", int, 9600)
                timeout = pool.config("plc/timeout", float, 6.0)
                timeout = float(timeout)  # Ensure timeout is always float
                self.client = ModbusSerialClient(method='rtu', port=port, baudrate=baudrate, timeout=timeout)
                self._configured = True
                self._connection_timeout = timeout
                logger.info(f"[{self.name}] Client configured for RTU with port={port}, baudrate={baudrate}, timeout={timeout}")
            else:
                self.last_error = "Unsupported communication type"
                logger.error(f"[{self.name}] {self.last_error}")
                self.connected = False
                return False

        with plc_lock:
            logger.debug(f"[{self.name}] Acquiring PLC connection lock")
            try:
                if self.connection_type == 'rtu' and hasattr(self.client, 'port'):
                    serial_port = self.client.port
                    if not os.path.exists(serial_port) and not serial_port.upper().startswith('COM'):
                        self.last_error = f"Serial port {serial_port} does not exist"
                        logger.error(f"[{self.name}] {self.last_error}")
                        self.connected = False
                        return False
                if self.connection_type == 'tcp':
                    host = self.client.host
                    port = self.client.port
                    # Defensive: always cast to float for socket timeout
                    socket_timeout = min(float(self.client.timeout), 2.0)
                    try:
                        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        s.settimeout(socket_timeout)
                        logger.info(f"[{self.name}] Testing TCP connection to {host}:{port}")
                        start = time.time()
                        s.connect((host, port))
                        logger.info(f"[{self.name}] TCP socket connected in {time.time()-start:.3f} seconds")
                        try:
                            s.send(b"\x00\x00")
                            s.settimeout(0.5)
                            s.recv(1)
                        except (socket.timeout, ConnectionResetError):
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

                logger.info(f"[{self.name}] Establishing Modbus {self.connection_type} connection")
                start = time.time()
                self.connected = self.client.connect()
                logger.info(f"[{self.name}] Modbus client connect() took {time.time()-start:.3f} seconds")
                if self.connected:
                    if self.connection_type == 'tcp':
                        try:
                            logger.info(f"[{self.name}] Performing test read to verify connection")
                            start_read = time.time()
                            
                            # Set a timeout for test read
                            read_timeout = min(5.0, self._connection_timeout)  # No more than 5 seconds for test read
                            original_timeout = self.client.timeout
                            self.client.timeout = read_timeout
                            
                            result = self.client.read_holding_registers(1, 1, unit=1)
                            
                            # Restore original timeout
                            self.client.timeout = original_timeout
                            
                            logger.info(f"[{self.name}] Test read completed in {time.time()-start_read:.3f} seconds")
                            if result is None or result.isError():
                                self.last_error = f"Test read error: {result}"
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
            except Exception as e:
                self.last_error = f"Exception during connection attempt: {str(e)}"
                logger.error(f"[{self.name}] {self.last_error}")
                self.connected = False
                return False
            finally:
                logger.debug(f"[{self.name}] Releasing PLC connection lock")

    def connect(self):
        """Connect to the Modbus device, with option to use async mode"""
        # For synchronous operation, just call the internal connect method
        return self._connect_internal()

    def connect_async(self, callback=None):
        """
        Connect to the Modbus device asynchronously in a separate thread.
        
        Args:
            callback: Optional function to call when connection is complete
            
        Returns:
            bool: True if connection process was started, False otherwise
        """
        if self._connection_thread and self._connection_thread.isRunning():
            logger.warning(f"[{self.name}] Connection already in progress")
            return False
            
        # Create a new thread
        self._connection_thread = QThread()
        
        # Create the worker (must be created after the thread but before moving to thread)
        self._connection_worker = ConnectionWorker(self)
        
        # Store callback before moving worker to thread
        self._connection_callback = callback
        
        # Move worker to thread - all signals should be connected AFTER this
        self._connection_worker.moveToThread(self._connection_thread)
        
        # Connect signals AFTER moving to thread
        self._connection_thread.started.connect(self._connection_worker.connect)
        self._connection_worker.connectionFinished.connect(self._on_connection_finished)
        self._connection_worker.connectionFinished.connect(self._connection_thread.quit)
        self._connection_thread.finished.connect(self._cleanup_connection_thread)
        
        # Start the thread
        logger.info(f"[{self.name}] Starting async connection thread")
        self._connection_thread.start()
        return True
        
    def _on_connection_finished(self, success, error_msg):
        """Handle connection completion"""
        self.connected = success
        if not success:
            self.last_error = error_msg
            
        logger.info(f"[{self.name}] Async connection finished: {'success' if success else 'failed'}")
        
        # Call the callback if provided
        if hasattr(self, '_connection_callback') and self._connection_callback:
            try:
                self._connection_callback(success)
            except Exception as e:
                logger.error(f"[{self.name}] Error in connection callback: {str(e)}")
                
    def _cleanup_connection_thread(self):
        """Clean up thread resources"""
        # We need to be careful about thread cleanup to prevent Qt threading issues
        if hasattr(self, '_connection_thread') and self._connection_thread:
            if hasattr(self, '_connection_worker') and self._connection_worker:
                # Disconnect all signals before deletion
                try:
                    self._connection_thread.started.disconnect(self._connection_worker.connect)
                    self._connection_worker.connectionFinished.disconnect()
                except (TypeError, RuntimeError):
                    # Signals might already be disconnected
                    pass
                
                self._connection_worker.deleteLater()
                self._connection_worker = None
                
            self._connection_thread.quit()
            if not self._connection_thread.wait(3000):  # Wait up to 3 seconds
                logger.warning(f"[{self.name}] Thread did not terminate properly, forcing termination")
                self._connection_thread.terminate()
                
            self._connection_thread.deleteLater()
            self._connection_thread = None

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
                elif read_type == 'coil':
                    result = self.client.read_coils(addr - 1, count, unit=dev)
                    if result and not result.isError():
                        return result.bits
                    else:
                        self.last_error = f"Error reading coils: {result}"
                        logger.error(f"[{self.name}] {self.last_error}")
                        return None
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

    def write_coil(self, address, value, unit=1):
        """
        Write a value to a coil in the PLC.
        
        Args:
            address (int): The coil address to write to
            value (bool): The value to write (True/False)
            unit (int): The unit ID (default: 1)
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not self._ensure_connected():
            return False
            
        try:
            with plc_lock:
                result = self.client.write_coil(address, value, unit=unit)
                if result.isError():
                    self.last_error = f"Error writing coil: {result}"
                    logger.error(f"[{self.name}] {self.last_error}")
                    return False
                return True
        except Exception as e:
            self.last_error = f"Exception writing coil: {str(e)}"
            logger.error(f"[{self.name}] {self.last_error}")
            return False

class DataReader:
    def __init__(self):
        self.running = False
        self.modbus_comm = ModbusCommunication(name="DataReader")
        self.read_type = None
        self.connected = False
        self.client = None
        self._connection_in_progress = False
        self._connection_attempt_count = 0
        self._max_connection_attempts = 3
        self._reload_in_progress = False
        
    def _on_connection_completed(self, success):
        """Handle connection completion callback - this runs in the main thread"""
        self._connection_in_progress = False
        self.connected = success
        if success:
            logger.info("DataReader successfully connected to PLC")
            self._connection_attempt_count = 0
        else:
            logger.error(f"DataReader failed to connect: {self.modbus_comm.get_error()}")
            self._connection_attempt_count += 1
            
            # If we've tried multiple times and still failed, implement a delay
            # before the next attempt to prevent rapid connection attempts
            if self._connection_attempt_count >= self._max_connection_attempts:
                logger.warning(f"DataReader reached maximum connection attempts ({self._max_connection_attempts}), will delay further attempts")
                
                # We could implement a timer here to delay next connection attempt
                # but for now we'll just reset the counter
                self._connection_attempt_count = 0

    def start(self):
        """Start the data reader."""
        # Only start if not already running
        if not self.running:
            self.running = True
            # We'll use a small delay to ensure the UI thread isn't blocked
            # by any initialization work
            QTimer.singleShot(0, self.reload)
            logger.info("Data reader started")

    def stop(self):
        """Stop the data reader."""
        if self.running:
            self.running = False
            self.connected = False
            self._connection_in_progress = False
            
            # Ensure we disconnect the modbus client
            if self.modbus_comm:
                # Use a try-except to prevent any errors during disconnection
                try:
                    self.modbus_comm.disconnect()
                except Exception as e:
                    logger.error(f"Error during modbus disconnection: {str(e)}")
                    
            logger.info("Data reader stopped")

    def reload(self):
        """
        Reload configuration and reconnect.
        This version includes better handling for multiple reload calls.
        """
        # Prevent multiple simultaneous reload operations
        if self._reload_in_progress:
            logger.debug("Reload already in progress, skipping")
            return
            
        self._reload_in_progress = True
        
        try:
            # Ensure we disconnect any existing connection
            if self.modbus_comm:
                try:
                    self.modbus_comm.disconnect()
                except Exception as e:
                    logger.error(f"Error disconnecting during reload: {str(e)}")
                
            # Get configuration settings
            self.read_type = pool.config('read_type', str, READ_HOLDING_REGISTERS)
            demo_mode = pool.config('demo', bool, False)
            
            if demo_mode:
                logger.info("DataReader reloading in DEMO mode")
                self.connected = True
                self._reload_in_progress = False
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
            
            # Configure and connect with proper error handling
            try:
                if self.modbus_comm.configure(connection_type, **config_params):
                    # Use asynchronous connection to prevent UI freezing for TCP
                    if connection_type == 'tcp':
                        self._connection_in_progress = True
                        # Delay the actual connection to avoid UI freezing
                        QTimer.singleShot(10, self._start_async_connection)
                    else:
                        # For RTU connections, we can use synchronous connection
                        # but still with a small delay
                        QTimer.singleShot(10, self._start_sync_connection)
                else:
                    logger.error(f"DataReader failed to configure: {self.modbus_comm.get_error()}")
                    self.connected = False
            except Exception as e:
                logger.error(f"Exception during DataReader configuration: {str(e)}")
                self.connected = False
        finally:
            # Clear the reload flag after a slight delay to prevent rapid
            # multiple reloads that might happen if there are multiple
            # settings being saved in quick succession
            QTimer.singleShot(500, self._clear_reload_flag)
    
    def _clear_reload_flag(self):
        """Clear the reload in progress flag after a delay"""
        self._reload_in_progress = False
            
    def _start_async_connection(self):
        """Start the asynchronous connection process"""
        try:
            # Check if we still should connect (might have been stopped)
            if not self.running:
                self._connection_in_progress = False
                logger.debug("DataReader no longer running, skipping async connection")
                return
                
            logger.debug("Starting async connection for DataReader")
            success = self.modbus_comm.connect_async(callback=self._on_connection_completed)
            if not success:
                logger.error("Failed to start async connection")
                self._connection_in_progress = False
                self.connected = False
        except Exception as e:
            logger.error(f"Exception starting async connection: {str(e)}")
            self._connection_in_progress = False
            self.connected = False
    
    def _start_sync_connection(self):
        """Start synchronous connection for RTU"""
        try:
            # Check if we still should connect (might have been stopped)
            if not self.running:
                logger.debug("DataReader no longer running, skipping sync connection")
                return
                
            logger.debug("Starting synchronous connection for DataReader")
            self.connected = self.modbus_comm.connect()
            if self.connected:
                logger.info("DataReader successfully connected to PLC")
            else:
                logger.error(f"DataReader failed to connect: {self.modbus_comm.get_error()}")
        except Exception as e:
            logger.error(f"Exception during synchronous connection: {str(e)}")
            self.connected = False

    # ... other methods remain the same ...
    
    def _read_holding_registers(self, dev, addr):
        """Read holding registers."""
        return self.modbus_comm.read_registers(addr, 1, dev, 'holding')

    def _read_input_registers(self, dev, addr):
        """Read input registers."""
        return self.modbus_comm.read_registers(addr, 1, dev, 'input')

    def read_bool_addresses(self, start_address, quantity, unit=1):
        """Read multiple boolean addresses (coils) from the PLC."""
        with plc_lock:  # Use the global lock for all operations
            if not self._ensure_connected():
                return None
            try:
                result = self.client.read_coils(start_address -1, quantity, unit=unit)
                if result and not result.isError():
                    return result.bits
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

    def readData(self, dev, addr):
        """Read data based on configured read type."""
        if not self.running:
            return None
            
        # If connection is still in progress, don't try to read yet
        if self._connection_in_progress:
            logger.debug("DataReader connection in progress, deferring read operation")
            return None
            
        # Make sure we're connected before attempting to read
        if not self.connected:
            logger.debug("DataReader not connected during readData, attempting to reconnect...")
            # Don't trigger a reload if one is already in progress
            if not self._reload_in_progress:
                # Use a timer to reload in the background to avoid blocking the UI
                QTimer.singleShot(0, self.reload)
            return None
                
        if not self.read_type:
            self.read_type = pool.config('read_type', str, READ_HOLDING_REGISTERS)
            
        try:
            if self.read_type == READ_HOLDING_REGISTERS:
                return self._read_holding_registers(dev, addr)
            elif self.read_type == READ_INPUT_REGISTERS:
                return self._read_input_registers(dev, addr)
            else:
                logger.error(f"Invalid register read type: {self.read_type}")
                return None
        except Exception as e:
            logger.error(f"Exception during readData: {str(e)}")
            return None

    def read_bool_address(self, address, dev=1):
        """Read a single boolean value (coil) from the PLC."""
        # Make sure we're connected before attempting to read
        if not self.running:
            return None
        
        # If connection is still in progress, don't try to read yet
        if self._connection_in_progress:
            logger.debug("DataReader connection in progress, deferring bool read operation")
            return None
            
        if not self.connected:
            logger.debug("DataReader not connected during read_bool_address, attempting to reconnect...")
            # Don't trigger a reload if one is already in progress
            if not self._reload_in_progress:
                # Use a timer to reload in the background to avoid blocking the UI
                QTimer.singleShot(0, self.reload)
            return None
        
        try:
            values = self.modbus_comm.read_bool_addresses(address, count=1, dev=dev)
            if values and len(values) > 0:
                return values[0]
            return None
        except Exception as e:
            logger.error(f"Exception during read_bool_address: {str(e)}")
            return None
        
    def writeData(self, addr, value, dev=1):
        """Write data to a register."""
        if not self.running:
            return False
        
        # If connection is still in progress, don't try to write yet
        if self._connection_in_progress:
            logger.debug("DataReader connection in progress, deferring write operation")
            return False
            
        # Make sure we're connected before attempting to write
        if not self.connected:
            logger.debug("DataReader not connected during writeData, attempting to reconnect...")
            # Don't trigger a reload if one is already in progress
            if not self._reload_in_progress:
                # Use a timer to reload in the background to avoid blocking the UI
                QTimer.singleShot(0, self.reload)
            return False
        
        try:
            return self.modbus_comm.write_register(addr, value, dev)
        except Exception as e:
            logger.error(f"Exception during writeData: {str(e)}")
            return False
        
    def write_bool_address(self, addr, value, dev=1):
        """Write a boolean value to a coil."""
        if not self.running:
            return False
        
        # If connection is still in progress, don't try to write yet
        if self._connection_in_progress:
            logger.debug("DataReader connection in progress, deferring bool write operation")
            return False
            
        # Make sure we're connected before attempting to write
        if not self.connected:
            logger.debug("DataReader not connected during write_bool_address, attempting to reconnect...")
            # Don't trigger a reload if one is already in progress
            if not self._reload_in_progress:
                # Use a timer to reload in the background to avoid blocking the UI
                QTimer.singleShot(0, self.reload)
            return False
        
        try:
            return self.modbus_comm.write_bool_address(addr, value, dev)
        except Exception as e:
            logger.error(f"Exception during write_bool_address: {str(e)}")
            return False
        
    def is_connected(self):
        """Check if the data reader is connected to the PLC."""
        if not self.running:
            return False
            
        # For demo mode, always return True
        if pool.config('demo', bool, False):
            return True
            
        # If connection is in progress, report as not yet connected
        if self._connection_in_progress:
            return False
            
        # Check the connection status
        return self.connected and (self.modbus_comm and self.modbus_comm.connected)


# Create and expose a singleton instance
dataReader = DataReader()
