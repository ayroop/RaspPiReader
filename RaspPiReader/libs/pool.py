from PyQt5.QtCore import QSettings

class Pool:
    def __init__(self):
        self._registry = dict()
        self._setting = QSettings('RaspPiHandler', 'RaspPiModbusReader')
        # Initialize default active channels
        self._registry["active_channels"] = list(range(1, 15))  # For 14 channels

    def get(self, key):
        return self._registry.get(key, None)

    def set(self, key, val):
        self._registry[key] = val
        return self._registry.get(key)

    def erase(self):
        self._registry = dict()
        return True

    def config(self, key, return_type=str, default_val=None):
        if key in self._registry:
            return self._registry[key]
        val = self._setting.value(key, default_val)
        if val in [None, '']:
            return default_val
        try:
            return return_type(val)
        except Exception as e:
            print(f"Error converting {key} = {val} to {return_type}: {e}")
            return default_val

    def set_config(self, key, value):
        self._registry[key] = value
        self._setting.setValue(key, value)

pool = Pool()