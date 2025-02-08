import logging
from pymodbus.client.sync import ModbusSerialClient as ModbusRTUClient
from RaspPiReader import pool

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  # Adjust level as needed

class PLCCommunicatorTCP:
    def __init__(self):
        self.client = None

    def connect(self):
        try:
            host = pool.config('tcp_host', str, '127.0.0.1')
            port = pool.config('tcp_port', int, 502)
            self.client = ModbusTCPClient(host=host, port=port, timeout=0.5)
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
            logger.error("Client not connected. Cannot read holding registers.")
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
            logger.error("Client not connected. Cannot read input registers.")
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
            logger.error("Client not connected. Cannot write register.")
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

class PLCCommunicator:
    def __init__(self):
        self.client = None
        self.comm_mode = pool.config("comm_mode", default_val="rs485")

    def connect(self):
        if self.comm_mode == "rs485":
            self.client = ModbusRTUClient(
                method='rtu',
                port=pool.config('port'),
                baudrate=pool.config('baudrate', int, 9600),
                bytesize=pool.config('databits', int, 8),
                parity=pool.config('parity', str, 'N'),
                stopbits=pool.config('stopbits', int, 1),
                timeout=0.5
            )
        elif self.comm_mode == "tcp":
            self.client = PLCCommunicatorTCP()
        return self.client.connect()

    def disconnect(self):
        if self.client:
            self.client.disconnect()

    def read_holding_registers(self, unit, address, count=1):
        if not self.client:
            raise Exception("Client not connected")
        return self.client.read_holding_registers(unit, address, count)

    def read_input_registers(self, unit, address, count=1):
        if not self.client:
            raise Exception("Client not connected")
        return self.client.read_input_registers(unit, address, count)

    def write_register(self, unit, address, value):
        if not self.client:
            raise Exception("Client not connected")
        return self.client.write_register(unit, address, value)