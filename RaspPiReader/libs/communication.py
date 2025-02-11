import serial
import logging
from pymodbus.client.sync import ModbusSerialClient as ModbusClient

from RaspPiReader import pool
from RaspPiReader.ui.setting_form_handler import READ_HOLDING_REGISTERS, READ_INPUT_REGISTERS

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

class DataReader:
    def start(self):
        port = pool.config('port')
        baudrate = pool.config('baudrate', int, 9600)      # default baudrate 9600
        bytesize = pool.config('databits', int, 8)         # default databits: 8
        parity = [k for k in serial.PARITY_NAMES if serial.PARITY_NAMES[k] == pool.config('parity')][0]
        stopbits = pool.config('stopbits', float)
        if stopbits % 1 == 0:
            stopbits = int(stopbits)

        self.client = ModbusClient(method='rtu',
                                   port=port,
                                   baudrate=baudrate,
                                   bytesize=bytesize,
                                   parity=parity,
                                   stopbits=stopbits,
                                   timeout=0.1
                                   )

        if self.client.connect():
            logger.info("Connected to MODBUS device on port %s", port)
        else:
            logger.error("Failed to connect to MODBUS device on port %s", port)

        read_type = pool.config('register_read_type')
        if read_type == READ_HOLDING_REGISTERS:
            self.read_method = self._read_holding_registers
        elif read_type == READ_INPUT_REGISTERS:
            self.read_method = self._read_input_registers

    def stop(self):
        try:
            self.client.close()
            logger.info("Disconnected from MODBUS device.")
        except Exception as e:
            logger.exception("Error disconnecting: %s", e)

    def reload(self):
        try:
            self.stop()
        except Exception as e:
            logger.error("Failed to stop data reader: %s", e)
        self.start()

    def _read_holding_registers(self, dev, addr):
        try:
            reg = self.client.read_holding_registers(unit=dev, address=addr)
            if reg.isError():
                logger.error("Error reading holding registers (dev=%s, addr=%s)", dev, addr)
                return None
            return reg.registers[0]
        except Exception as e:
            logger.exception("Exception during holding register read: %s", e)
            return None

    def _read_input_registers(self, dev, addr):
        try:
            reg = self.client.read_input_registers(unit=dev, address=addr)
            if reg.isError():
                logger.error("Error reading input registers (dev=%s, addr=%s)", dev, addr)
                return None
            return reg.registers[0]
        except Exception as e:
            logger.exception("Exception during input register read: %s", e)
            return None

    def read_bool_addresses(self, dev, addr, count=6):
        """Read a block of boolean coil values starting at the given address.
        Returns a list of booleans or None on error."""
        try:
            result = self.client.read_coils(unit=dev, address=addr, count=count)
            if result.isError():
                logger.error("Error reading boolean coils (dev=%s, addr=%s)", dev, addr)
                return None
            logger.debug("Boolean coils read (dev=%s, addr=%s): %s", dev, addr, result.bits)
            return result.bits
        except Exception as e:
            logger.exception("Exception during coil read: %s", e)
            return None

    def readData(self, dev, addr):
        return self.read_method(dev, addr)

    def writeData(self, dev, addr, data):
        try:
            response = self.client.write_register(unit=dev, address=addr, value=data)
            if response.isError():
                logger.error("Error writing data %s to dev=%s at addr=%s", data, dev, addr)
            return response
        except Exception as e:
            logger.exception("Exception during write: %s", e)
            return None

dataReader = DataReader()