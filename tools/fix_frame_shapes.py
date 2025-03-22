import re

def fix_frame_shapes(file_path):
    print(f"Fixing frame shapes in {file_path}")
    
    with open(file_path, 'r', encoding='utf-8') as file:
        content = file.read()
    
    # Replace Qt.Box with QtWidgets.QFrame.Box
    content = re.sub(r'QtCore\.Qt\.Box', 'QtWidgets.QFrame.Box', content)
    
    # Other possible frame shape replacements
    content = re.sub(r'QtCore\.Qt\.Panel', 'QtWidgets.QFrame.Panel', content)
    content = re.sub(r'QtCore\.Qt\.StyledPanel', 'QtWidgets.QFrame.StyledPanel', content)
    content = re.sub(r'QtCore\.Qt\.HLine', 'QtWidgets.QFrame.HLine', content)
    content = re.sub(r'QtCore\.Qt\.VLine', 'QtWidgets.QFrame.VLine', content)
    
    with open(file_path, 'w', encoding='utf-8') as file:
        file.write(content)
    
    print("✓ Fixed frame shapes!")

if __name__ == "__main__":
    fix_frame_shapes("RaspPiReader/ui/settingForm.py")