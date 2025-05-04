from PyQt5.QtCore import QSettings

class Pool:
    def __init__(self):
        self._registry = dict()
        self._setting = QSettings('RaspPiHandler', 'RaspPiModbusReader')
        self._registry["active_channels"] = list(range(1, 15))  # For 14 channels
        self.reload_config()  # Load initial settings

    def get(self, key):
        return self._registry.get(key, None)

    def set(self, key, val):
        self._registry[key] = val
        return self._registry.get(key)

    def erase(self):
        self._registry = dict()
        return True

    def config(self, key, return_type=str, default_val=None, base=10):
        if key in self._registry:
            return self._registry[key]
        val = self._setting.value(key, default_val)
        val_str = str(val).strip()
        if val is None or val_str.lower() == "none" or val_str == "":
            return default_val
        try:
            if return_type == int:
                if base != 10:
                    return int(val_str, base)
                else:
                    return int(val_str)
            else:
                return return_type(val)
        except Exception as e:
            print(f"Error converting {key} = {val} to {return_type}: {e}")
            return default_val

    def set_config(self, key, value):
        """Set a configuration value and ensure it's immediately available."""
        self._registry[key] = value
        self._setting.setValue(key, value)
        self._setting.sync()  # Ensure settings are written immediately
    
    def reload_config(self):
        """Reload configuration settings from QSettings into the internal registry."""
        # Retrieve all keys stored in QSettings
        keys = self._setting.allKeys()
        for key in keys:
            val = self._setting.value(key)
            if val is not None:
                self._registry[key] = val
        # Ensure any required defaults are in place (for example, active channels)
        self._registry["active_channels"] = list(range(1, 15))
        
    def force_reload_all(self):
        """Force reload all settings from both QSettings and database."""
        self.reload_config()
        # Add any additional reload logic here if needed

pool = Pool()