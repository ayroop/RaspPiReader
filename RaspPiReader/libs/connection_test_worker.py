import logging
import time
import socket
import os
try:
    from pymodbus.client import ModbusTcpClient
except ImportError:
    from pymodbus.client.sync import ModbusTcpClient
from PyQt5.QtCore import QThread, pyqtSignal
from RaspPiReader import pool

logger = logging.getLogger(__name__)

# This worker runs the test connection off the main thread.
class TestConnectionWorker(QThread):
    """Worker thread that tests PLC connection without blocking the UI thread"""
    # The worker emits a signal with a bool (success) and an optional error message.
    testResult = pyqtSignal(bool, str)

    def __init__(self, connection_type, params, parent=None):
        super(TestConnectionWorker, self).__init__(parent)
        self.connection_type = connection_type
        self.params = params.copy()
        # For testing, use a more reasonable timeout that balances speed and reliability
        # Use user-specified timeout but cap at 5 seconds for testing
        if self.connection_type == 'tcp':
            self.params['timeout'] = min(self.params.get('timeout', 6.0), 5.0)

    def run(self):
        """Test the connection based on connection type"""
        logger.debug(f"Connection test thread started: {self.connection_type}")
        try:
            if self.connection_type == 'tcp':
                self._test_tcp_connection()
            elif self.connection_type == 'rtu':
                self._test_rtu_connection()
            else:
                self.testResult.emit(False, f"Unsupported connection type: {self.connection_type}")
        except Exception as e:
            logger.error(f"Connection test error: {str(e)}")
            self.testResult.emit(False, str(e))
            
    def _test_tcp_connection(self):
        """Test TCP connection"""
        host = self.params.get('host', '127.0.0.1')
        port = int(self.params.get('port', 502))
        timeout = min(float(self.params.get('timeout', 6.0)), 5.0)
        logger.info(f"TestConnectionWorker: Testing TCP connection to {host}:{port} with timeout {timeout}")
        
        # First establish a raw socket connection to verify network connectivity
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(min(timeout, 2.0))  # Use a shorter timeout for the socket test
            logger.info(f"TestConnectionWorker: Testing TCP socket connection to {host}:{port}")
            
            # Try to connect
            start_time = time.time()
            s.connect((host, port))
            connect_time = time.time() - start_time
            
            logger.info(f"TestConnectionWorker: TCP socket connection successful to {host}:{port} in {connect_time:.3f}s")
            
            # Try sending a basic packet (this may fail with some devices,
            # but that's OK since we just want to check basic connectivity)
            try:
                s.send(b"\x00\x00")
                s.settimeout(0.5)
                s.recv(1)
            except (socket.timeout, ConnectionResetError):
                # This is often expected
                pass
                
            s.close()
            
            # If we only want to test basic connectivity, we could stop here
            # self.testResult.emit(True, f"Connected to {host}:{port} in {connect_time:.3f}s")
            # return
            
        except socket.timeout:
            self.testResult.emit(False, f"Socket connection to {host}:{port} timed out")
            return
        except ConnectionRefusedError:
            self.testResult.emit(False, f"Connection to {host}:{port} refused - check if the PLC server is running")
            return
        except Exception as e:
            self.testResult.emit(False, f"Socket connection error: {str(e)}")
            return
                
        # Now test the Modbus connection
        try:
            client = ModbusTcpClient(
                host=host, 
                port=port, 
                timeout=timeout,
                retries=1,               # Limit retries for faster feedback
                retry_on_empty=False,    # Don't retry on empty responses
                close_comm_on_error=True # Close connection on any error
            )
            
            try:
                connected = client.connect()
                if not connected:
                    self.testResult.emit(False, "Client connect() returned False")
                    client.close()
                    return
                    
                # Perform a test read with unit ID 1
                logger.info(f"TestConnectionWorker: Connected to {host}:{port}, performing test read")
                response = client.read_holding_registers(address=0, count=1, unit=1)
                
                if response is None:
                    self.testResult.emit(False, "Test read returned None")
                elif response.isError():
                    error_msg = str(response)
                    logger.warning(f"TestConnectionWorker: Test read returned error: {error_msg}")
                    
                    # Check if this is actually a valid response from the simulator
                    # Some simulators return errors for valid addresses that just aren't configured
                    if hasattr(response, 'function_code') and response.function_code > 0:
                        # This is a valid Modbus exception response, not a connection error
                        logger.info("TestConnectionWorker: Received valid Modbus exception response")
                        self.testResult.emit(True, f"Connected to {host}:{port} (with expected Modbus exception)")
                    else:
                        self.testResult.emit(False, f"Test read returned error: {error_msg}")
                else:
                    # Successful read
                    logger.info(f"TestConnectionWorker: Test read successful: {response.registers}")
                    self.testResult.emit(True, f"Connected to {host}:{port} and read successful")
            except Exception as e:
                logger.error(f"TestConnectionWorker: Error during Modbus test: {str(e)}")
                self.testResult.emit(False, str(e))
            finally:
                try:
                    client.close()
                except:
                    pass
        except Exception as e:
            logger.error(f"TestConnectionWorker: Error creating Modbus client: {str(e)}")
            self.testResult.emit(False, str(e))
            
    def _test_rtu_connection(self):
        """Test RTU connection"""
        try:
            # For RTU we need to import serial library
            import serial
        except ImportError:
            self.testResult.emit(False, "PySerial library not installed. Please install it using: pip install pyserial")
            return
            
        port = self.params.get('port', 'COM1')
        baudrate = int(self.params.get('baudrate', 9600))
        bytesize = int(self.params.get('bytesize', 8))
        parity = self.params.get('parity', 'N')
        stopbits = float(self.params.get('stopbits', 1))
        
        # First check if the port exists (for non-Windows systems)
        if not port.upper().startswith('COM') and not os.path.exists(port):
            self.testResult.emit(False, f"Serial port {port} does not exist")
            return
            
        # Try to open the port
        ser = None
        try:
            ser = serial.Serial(
                port=port,
                baudrate=baudrate,
                bytesize=bytesize,
                parity=parity,
                stopbits=stopbits,
                timeout=1
            )
            
            # Port opened successfully
            logger.info(f"Serial port test successful: {port} at {baudrate} baud")
            self.testResult.emit(True, f"Successfully opened port {port} at {baudrate} baud")
        except serial.SerialException as e:
            logger.error(f"Serial port error: {str(e)}")
            self.testResult.emit(False, f"Serial port error: {str(e)}")
        finally:
            # Always close the serial port
            if ser:
                try:
                    ser.close()
                except:
                    pass

def test_connection_sync(connection_type, params):
    """
    Synchronous version of test connection with a reduced timeout.
    Returns (True, "") on success or (False, error_message) on failure.
    """
    if connection_type == 'tcp':
        host = params.get('host', '127.0.0.1')
        port = int(params.get('port', 502))
        timeout = min(float(params.get('timeout', 6.0)), 5.0)
        logger.info(f"test_connection_sync: Testing TCP connection to {host}:{port} with timeout {timeout}")
        
        # First test raw socket connection
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(min(timeout, 2.0))
            
            # Try to connect
            start_time = time.time()
            s.connect((host, port))
            connect_time = time.time() - start_time
            
            logger.info(f"test_connection_sync: Socket connection successful to {host}:{port} in {connect_time:.3f}s")
            
            # Try sending a basic packet
            try:
                s.send(b"\x00\x00")
                s.settimeout(0.5)
                s.recv(1)
            except (socket.timeout, ConnectionResetError):
                # This is often expected
                pass
                
            s.close()
        except Exception as e:
            error = f"Socket connection error: {str(e)}"
            logger.error(f"test_connection_sync: {error}")
            return (False, error)
            
        # Then test Modbus connection
        try:
            client = ModbusTcpClient(
                host=host, 
                port=port, 
                timeout=timeout, 
                retries=1,
                retry_on_empty=False
            )
            
            t0 = time.time()
            if client.connect():
                logger.info(f"test_connection_sync: Connection established in {time.time()-t0:.3f} seconds, performing test read")
                try:
                    rr = client.read_holding_registers(1, 1, unit=1)
                    
                    # Check response
                    if rr is None:
                        error = "Test read returned None"
                        logger.error(f"test_connection_sync: {error}")
                        client.close()
                        return (False, error)
                    elif rr.isError():
                        # Check if it's a valid exception response
                        if hasattr(rr, 'function_code') and rr.function_code > 0:
                            logger.info("test_connection_sync: Received valid Modbus exception response")
                            client.close()
                            return (True, "Connected with expected Modbus exception")
                        else:
                            error = f"Test read error: {rr}"
                            logger.error(f"test_connection_sync: {error}")
                            client.close()
                            return (False, error)
                    else:
                        client.close()
                        return (True, "Connected successfully")
                except Exception as e:
                    error = f"Error during test read: {str(e)}"
                    logger.error(f"test_connection_sync: {error}")
                    try:
                        client.close()
                    except:
                        pass
                    return (False, error)
            else:
                error = "Failed to connect with client"
                logger.error(f"test_connection_sync: {error}")
                return (False, error)
        except Exception as e:
            error = str(e)
            logger.error(f"test_connection_sync: Exception: {error}")
            return (False, error)
    elif connection_type == 'rtu':
        try:
            # For RTU we need to import serial library
            import serial
        except ImportError:
            return (False, "PySerial library not installed. Please install it using: pip install pyserial")
            
        port = params.get('port', 'COM1')
        baudrate = int(params.get('baudrate', 9600))
        bytesize = int(params.get('bytesize', 8))
        parity = params.get('parity', 'N')
        stopbits = float(params.get('stopbits', 1))
        
        # First check if the port exists (for non-Windows systems)
        if not port.upper().startswith('COM') and not os.path.exists(port):
            return (False, f"Serial port {port} does not exist")
            
        # Try to open the port
        ser = None
        try:
            ser = serial.Serial(
                port=port,
                baudrate=baudrate,
                bytesize=bytesize,
                parity=parity,
                stopbits=stopbits,
                timeout=1
            )
            
            # Port opened successfully
            logger.info(f"Serial port test successful: {port} at {baudrate} baud")
            ser.close()
            return (True, f"Successfully opened port {port} at {baudrate} baud")
        except serial.SerialException as e:
            logger.error(f"Serial port error: {str(e)}")
            return (False, f"Serial port error: {str(e)}")
        finally:
            if ser:
                try:
                    ser.close()
                except:
                    pass
    else:
        return (False, f"Unsupported connection type: {connection_type}")
