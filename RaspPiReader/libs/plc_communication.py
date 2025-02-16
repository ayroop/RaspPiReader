import logging
from pymodbus.client.sync import ModbusSerialClient as ModbusRTUClient
from pymodbus.client.sync import ModbusTcpClient
from RaspPiReader import pool
from RaspPiReader.database import Database  # Assumed import for the Database class

# Configure logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  # Adjust log level if necessary

class PLCCommunicatorTCP:
    """
    Communicator implementation for TCP connections using Modbus.
    """
    def __init__(self):
        self.client = None

    def connect(self):
        try:
            host = pool.config('tcp_host', str, '127.0.0.1')
            port = pool.config('tcp_port', int, 502)
            self.client = ModbusTcpClient(host=host, port=port, timeout=0.5)
            connection = self.client.connect()
            if connection:
                logger.info("Connected to Modbus TCP server at %s:%s", host, port)
            else:
                logger.error("Failed to connect to Modbus TCP server at %s:%s", host, port)
            return connection
        except Exception as e:
            logger.exception("Exception while connecting to Modbus TCP: %s", e)
            return False

    def disconnect(self):
        try:
            if self.client:
                self.client.close()
                logger.info("Disconnected from Modbus TCP server.")
        except Exception as e:
            logger.exception("Exception while disconnecting: %s", e)

    def read_holding_registers(self, unit, address, count=1):
        if not self.client:
            logger.error("TCP client not connected. Cannot read holding registers.")
            return None
        try:
            response = self.client.read_holding_registers(address, count, unit=unit)
            if response.isError():
                logger.error("Error reading holding registers at address %s for unit %s", address, unit)
                return None
            logger.debug("Holding registers read: %s", response.registers)
            return response.registers
        except Exception as e:
            logger.exception("Exception in read_holding_registers: %s", e)
            return None

    def read_input_registers(self, unit, address, count=1):
        if not self.client:
            logger.error("TCP client not connected. Cannot read input registers.")
            return None
        try:
            response = self.client.read_input_registers(address, count, unit=unit)
            if response.isError():
                logger.error("Error reading input registers at address %s for unit %s", address, unit)
                return None
            logger.debug("Input registers read: %s", response.registers)
            return response.registers
        except Exception as e:
            logger.exception("Exception in read_input_registers: %s", e)
            return None

    def write_register(self, unit, address, value):
        if not self.client:
            logger.error("TCP client not connected. Cannot write register.")
            return False
        try:
            response = self.client.write_register(address, value, unit=unit)
            if response.isError():
                logger.error("Error writing value %s to register at address %s for unit %s", value, address, unit)
                return False
            logger.debug("Wrote value %s to register at address %s for unit %s", value, address, unit)
            return True
        except Exception as e:
            logger.exception("Exception in write_register: %s", e)
            return False

    def read_bool_addresses(self, unit, address, count=6):
        if not self.client:
            logger.error("TCP client not connected. Cannot read boolean coils.")
            return None
        try:
            response = self.client.read_coils(address, count, unit=unit)
            if response.isError():
                logger.error("Error reading boolean coils at address %s for unit %s", address, unit)
                return None
            logger.debug("Boolean coils read at address %s for unit %s: %s", address, unit, response.bits)
            return response.bits
        except Exception as e:
            logger.exception("Exception in read_bool_addresses: %s", e)
            return None

class PLCCommunicator:
    """
    Integrated PLCCommunicator supporting both RS485 and TCP modes.
    Incorporates local database functionality.
    """
    def __init__(self):
        self.client = None
        # Initialize local database for persistence operations
        self.local_db = Database("sqlite:///local_database.db")
        self.local_db.create_tables()
        self.comm_mode = pool.config("commMode", str, "RS485")

    def connect(self):
        """
        Establish connection based on the communication mode.
        For RS485, connects using Modbus RTU.
        For TCP, delegates connection to PLCCommunicatorTCP.
        """
        if self.comm_mode.upper() == "RS485":
            try:
                self.client = ModbusRTUClient(
                    method='rtu',
                    port=pool.config('port'),
                    baudrate=pool.config('baudrate', int, 9600),
                    bytesize=pool.config('databits', int, 8),
                    parity=pool.config('parity', str, 'N'),
                    stopbits=pool.config('stopbits', int, 1),
                    timeout=0.5
                )
                connection = self.client.connect()
                if connection:
                    logger.info("Connected via RS485 on port %s at baudrate %s", pool.config('port'), pool.config('baudrate', int, 9600))
                else:
                    logger.error("Failed to connect via RS485 on port %s", pool.config('port'))
                return connection
            except Exception as e:
                logger.exception("Exception while connecting via RS485: %s", e)
                return False
        elif self.comm_mode.upper() == "TCP":
            # When TCP is selected, use the dedicated TCP communicator.
            self.client = PLCCommunicatorTCP()
            return self.client.connect()
        else:
            logger.error("Unsupported communication mode: %s", self.comm_mode)
            raise ValueError("Unsupported communication mode")

    def disconnect(self):
        """
        Disconnects the client if connected.
        """
        if self.client:
            # If the client has the disconnect method (TCP), use it; otherwise call close()
            if hasattr(self.client, 'disconnect'):
                self.client.disconnect()
            else:
                self.client.close()
            logger.info("Disconnected client.")

    def read_holding_registers(self, unit, address, count=1):
        if not self.client:
            raise Exception("Client not connected")
        return self.client.read_holding_registers(unit=unit, address=address, count=count)

    def read_input_registers(self, unit, address, count=1):
        if not self.client:
            raise Exception("Client not connected")
        return self.client.read_input_registers(unit=unit, address=address, count=count)

    def write_register(self, unit, address, value):
        if not self.client:
            raise Exception("Client not connected")
        return self.client.write_register(unit=unit, address=address, value=value)

    def read_bool_addresses(self, unit, address, count=6):
        if not self.client:
            raise Exception("Client not connected")
        return self.client.read_bool_addresses(unit=unit, address=address, count=count)

    def save_user(self, user):
        """
        Save user information to the local database.
        """
        try:
            self.local_db.add_user(user)
            logger.info("User saved successfully: %s", user)
        except Exception as e:
            logger.exception("Failed to save user %s: %s", user, e)