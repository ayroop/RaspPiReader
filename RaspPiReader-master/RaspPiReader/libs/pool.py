from PyQt5.QtCore import QSettings


class Pool:

    def __init__(self):
        self._registry = dict()
        self._setting = QSettings('RaspPiHandler', 'RaspPiModbusReader')

    def get(self, key):
        return self._registry.get(key, None)

    def set(self, key, val):
        self._registry[key] = val
        return self._registry.get(key)

    def erase(self):
        self._registry = dict()
        return True

    def config(self, key, return_type=str):
        try:
            val =  self._setting.value(key, str(), return_type)
        except Exception as e:
            val = None
            print(key, ' - ', str(return_type))
        return val

    def set_config(self, key, value):
        return self._setting.setValue(key, value)


pool = Pool()
