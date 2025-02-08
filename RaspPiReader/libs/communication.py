import serial
from pymodbus.client.sync import ModbusSerialClient as ModbusClient

from RaspPiReader import pool
from RaspPiReader.ui.setting_form_handler import READ_HOLDING_REGISTERS, READ_INPUT_REGISTERS


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

        self.client.connect()
        read_type = pool.config('register_read_type')
        if read_type == READ_HOLDING_REGISTERS:
            self.read_method = self._read_holding_registers
        elif read_type == READ_INPUT_REGISTERS:
            self.read_method = self._read_input_registers




    def stop(self):
        self.client.close()

    def reload(self):
        try:
            self.stop()
        except Exception as e:
            print('failed to stop data reader.' + str(e))
        self.start()

    def _read_holding_registers(self, dev, addr):
        reg = self.client.read_holding_registers(unit=dev, address=addr)
        return reg.registers[0]

    def _read_input_registers(self, dev, addr):
        reg = self.client.read_input_registers(unit=dev, address=addr)
        return reg.registers[0]

    def readData(self, dev, addr):
        return self.read_method(dev, addr)

    def writeData(self, dev, addr, data):
        self.client.write_register(unit=dev, address=addr, value=data)


dataReader = DataReader()
