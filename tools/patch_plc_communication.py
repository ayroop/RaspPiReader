"""
Patch script for modifying plc_communication.py to use the shared PLC connection.

This script will create a backup of the original file and then add code to use
the shared connection instead of creating a new one.
"""
import os
import re
import shutil
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
PLC_COMMUNICATION = PROJECT_ROOT / "RaspPiReader" / "libs" / "plc_communication.py"
BACKUP_FILE = PLC_COMMUNICATION.with_suffix(".py.bak")

def backup_file():
    """Create a backup of the plc_communication.py file."""
    shutil.copy2(PLC_COMMUNICATION, BACKUP_FILE)
    print(f"Created backup: {BACKUP_FILE}")

def add_import_statement(content):
    """Add the import statement for the connection coordinator."""
    if "from RaspPiReader.libs.plc_connection_coordinator import" not in content:
        import_statement = "\nfrom RaspPiReader.libs.plc_connection_coordinator import get_plc_client, is_connected, update_connection_settings\n"
        # Find where imports end
        match = re.search(r'(import.*\n)+', content)
        if match:
            end_of_imports = match.end()
            content = content[:end_of_imports] + import_statement + content[end_of_imports:]
        else:
            # If we can't find the imports, just add it to the top
            content = import_statement + content
    return content

def modify_simplified_modbus_tcp(content):
    """
    Modify the SimplifiedModbusTcp class to use the shared connection.
    This is a more complex modification that might require manual adjustments.
    """
    # This is a placeholder for the actual implementation
    print("WARNING: SimplifiedModbusTcp class needs manual modifications.")
    print("1. Find the class definition.")
    print("2. Modify methods to use get_plc_client() instead of creating new connections.")
    print("3. Redirect connect(), disconnect() methods to use the shared connection.")
    return content

def apply_patch():
    """Apply the patch to plc_communication.py."""
    if not PLC_COMMUNICATION.exists():
        print(f"Error: {PLC_COMMUNICATION} does not exist!")
        return False
        
    backup_file()
    
    with open(PLC_COMMUNICATION, 'r') as f:
        content = f.read()
        
    # Apply modifications
    content = add_import_statement(content)
    content = modify_simplified_modbus_tcp(content)
    
    with open(PLC_COMMUNICATION, 'w') as f:
        f.write(content)
        
    print(f"Applied patch to {PLC_COMMUNICATION}")
    print("\nManual modifications required:")
    print("1. Replace the implementation of SimplifiedModbusTcp.connect() to use get_plc_client()")
    print("2. Replace the implementation of SimplifiedModbusTcp.disconnect() to use the shared connection")
    print("3. Modify read/write methods to use the client from get_plc_client()")
    print("4. Update the connection monitor to use is_connected() from the coordinator")
    
    return True

if __name__ == "__main__":
    if not apply_patch():
        print("Failed to apply patch.")
    else:
        print("Patch application complete. Remember to make the necessary manual modifications.")