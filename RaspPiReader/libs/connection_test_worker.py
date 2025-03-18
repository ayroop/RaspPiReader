import logging
import time
import socket
try:
    from pymodbus.client import ModbusTcpClient
except ImportError:
    from pymodbus.client.sync import ModbusTcpClient
from PyQt5.QtCore import QThread, pyqtSignal
from RaspPiReader import pool

logger = logging.getLogger(__name__)

# This worker runs the test connection off the main thread.
class TestConnectionWorker(QThread):
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
        if self.connection_type == 'tcp':
            host = self.params.get('host', '127.0.0.1')
            port = int(self.params.get('port', 502))
            timeout = min(float(self.params.get('timeout', 6.0)), 5.0)
            logger.info(f"TestConnectionWorker: Testing TCP connection to {host}:{port} with timeout {timeout}")
            
            # First establish a raw socket connection to verify network connectivity
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(min(timeout, 2.0))  # Use a shorter timeout for the socket test
                logger.info(f"TestConnectionWorker: Testing TCP socket connection to {host}:{port}")
                s.connect((host, port))
                logger.info(f"TestConnectionWorker: TCP socket connection successful to {host}:{port}")
                s.close()
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
                            self.testResult.emit(True, "")
                        else:
                            self.testResult.emit(False, f"Test read returned error: {error_msg}")
                    else:
                        # Successful read
                        logger.info(f"TestConnectionWorker: Test read successful: {response.registers}")
                        self.testResult.emit(True, "")
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
            s.connect((host, port))
            s.close()
            logger.info(f"test_connection_sync: Socket connection successful to {host}:{port}")
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
                            return (True, "")
                        else:
                            error = f"Test read error: {rr}"
                            logger.error(f"test_connection_sync: {error}")
                            client.close()
                            return (False, error)
                    else:
                        client.close()
                        return (True, "")
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
    else:
        return (False, "RTU test connection not implemented")
