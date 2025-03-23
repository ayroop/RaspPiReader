from PyQt5.QtCore import QSettings

class Pool:
    def __init__(self):
        self._registry = dict()
        self._setting = QSettings('RaspPiHandler', 'RaspPiModbusReader')
        self._registry["active_channels"] = list(range(1, 15))  # For 14 channels

    def get(self, key):
        return self._registry.get(key, None)

    def set(self, key, val):
        self._registry[key] = val
        return self._registry.get(key)

    def erase(self):
        self._registry = dict()
        return True

    def config(self, key, return_type=str, default_val=None, base=10):
        """
        Get configuration value with proper type conversion.
        
        Args:
            key: The configuration key.
            return_type: Type to convert value to.
            default_val: Default value if key doesn't exist.
            base: Base for int conversion (if return_type is int).
            
        Returns:
            Converted value or default value if conversion fails.
        """
        if key in self._registry:
            return self._registry[key]
        
        val = self._setting.value(key, default_val)
        # Ensure we work with a string representation for checking
        val_str = str(val).strip()
        if val is None or val_str.lower() == "none" or val_str == "":
            return default_val

        try:
            if return_type == int:
                if base != 10:
                    # Use the stripped string for conversion
                    return int(val_str, base)
                else:
                    return int(val_str)
            else:
                return return_type(val)
        except Exception as e:
            print(f"Error converting {key} = {val} to {return_type}: {e}")
            return default_val

    def set_config(self, key, value):
        self._registry[key] = value
        self._setting.setValue(key, value)

pool = Pool()