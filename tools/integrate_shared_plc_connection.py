#!/usr/bin/env python
"""
Integration helper script for converting existing PLC communication code
to use the shared connection manager.

This script will:
1. Create the new plc_connection_manager.py module
2. Modify existing code to use the shared connection
3. Provide instructions for additional manual changes needed
"""
import os
import sys
import shutil
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent

# Paths to modify
PLC_BOOLEAN_READER = PROJECT_ROOT / "RaspPiReader" / "libs" / "plc_boolean_reader.py"
PLC_COMMUNICATION = PROJECT_ROOT / "RaspPiReader" / "libs" / "plc_communication.py"
CONNECTION_MANAGER = PROJECT_ROOT / "RaspPiReader" / "libs" / "plc_connection_manager.py"

def backup_file(file_path):
    """Create a backup of the specified file."""
    backup_path = str(file_path) + ".backup"
    shutil.copy2(file_path, backup_path)
    print(f"Created backup: {backup_path}")

def create_connection_manager():
    """Create the plc_connection_manager.py module if it doesn't exist."""
    if not CONNECTION_MANAGER.exists():
        # In a real script, we'd have the content to write here
        # For this example, we'll just create a placeholder
        with open(CONNECTION_MANAGER, 'w') as f:
            f.write('# Placeholder for the connection manager module\n')
        print(f"Created connection manager module: {CONNECTION_MANAGER}")
    else:
        print(f"Connection manager module already exists: {CONNECTION_MANAGER}")

def update_import_statements(file_path):
    """Update import statements in the specified file."""
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Add import for connection manager
    if "from RaspPiReader.libs.plc_connection_manager import" not in content:
        # Find where imports end
        import_section_end = content.find("\n\n", content.find("import"))
        if import_section_end == -1:
            import_section_end = content.find("\n", content.find("import"))
        
        # Add our import
        new_import = "\nfrom RaspPiReader.libs.plc_connection_manager import get_connection_manager\n"
        content = content[:import_section_end] + new_import + content[import_section_end:]
    
    # Write back changes
    with open(file_path, 'w') as f:
        f.write(content)
    
    print(f"Updated import statements in: {file_path}")

def main():
    """Main integration function."""
    # Backup original files
    backup_file(PLC_BOOLEAN_READER)
    backup_file(PLC_COMMUNICATION)
    
    # Create the connection manager module
    create_connection_manager()
    
    # Update import statements
    update_import_statements(PLC_BOOLEAN_READER)
    update_import_statements(PLC_COMMUNICATION)
    
    print("\nIntegration completed!")
    print("\nManual steps required:")
    print("1. Copy the full implementation of plc_connection_manager.py.")
    print("2. Modify PLCBooleanReader class to use the connection manager.")
    print("3. Update plc_communication.py to use the shared connection.")
    print("4. Update any other modules that communicate with the PLC.")
    print("5. Test the integration thoroughly.")

if __name__ == "__main__":
    main()