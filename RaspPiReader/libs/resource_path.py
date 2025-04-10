import os
import sys

def resource_path(relative_path):
    """
    Get absolute path to resource, works for dev and for PyInstaller onefile mode.
    """
    try:
        # PyInstaller creates a temporary folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# Example usage:
if __name__ == "__main__":
    print(resource_path("local_database.db"))