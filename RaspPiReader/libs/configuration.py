import json

import serial
from PyQt5.QtGui import QColor

TermoCount = 8

class Configuration(object):
    filename = 'config.json'
    
    colors = [
        QColor(32, 159, 223), QColor(153, 202, 83), QColor(246, 166, 37), QColor(109, 95, 213), 
        QColor(255, 0, 0), QColor(0, 255, 0), QColor(0, 0, 255), QColor(255, 255, 0), 
        ]
        
    # Six Boolean addresses (adjust these addresses as required)
    bool_addresses = [1101, 1102, 1103, 1104, 1105, 1106]

    info = {
        'AddrLabel' : ["Temp-1", "Temp-2", "Temp-3", "Temp-4", "Temp-5", "Temp-6", "Temp-7", "Temp-8"],
        'PV' : [0x1000] * TermoCount,
        'SV' : [0x500] * TermoCount,
        'SetPoint' : [120] * TermoCount,
        'LowLimit' : [20] * TermoCount,
        'HighLimit' : [200] * TermoCount,
        'DecPoint' : [0] * TermoCount,
        'Scale' : [False] * TermoCount,
        'YLabel' : "Temperature",
        'XMax' : 10,
        'YMax' : 100,
        'ScaleRange' : 1000,
        'SampleTime' : 5.0,
        'Baudrate' : 9600,
        'Parity' : serial.PARITY_NONE,
        'DataBits' : serial.EIGHTBITS,
        'StopBits' : serial.STOPBITS_ONE,
        'ReadingAddr' : 0x0000,
    }
    
    def __init__(self):
        self.LoadFromFile()

    def LoadFromFile(self):
        try:
            with open(self.filename, 'r') as fp:
                 info = json.load(fp)

                 if self.info.keys() == info.keys():
                    self.info = info
        except:
            pass
        
    def SaveToFile(self):
        try:
            if self.info['SampleTime'] <= 0:
                self.info['SampleTime'] = 1.0

            if self.info['ReadingAddr'] <= 0:
                self.info['ReadingAddr'] = 0x0000
                
            if self.info['XMax'] <= 1:
                self.info['XMax'] = 1

            if self.info['YMax'] <= 20:
                self.info['YMax'] = 20
            
            if self.info['ScaleRange'] <= 100:
                self.info['ScaleRange'] = 100
            
            with open(self.filename, 'w') as fp:
                json.dump(self.info, fp)
        except:
            pass

config = Configuration()
