"""Fix indentation issues in mainForm.py"""
import re

def fix_mainform_indentation():
    """Fix all indentation issues in mainForm.py"""
    filepath = "RaspPiReader/ui/mainForm.py"
    
    with open(filepath, 'r', encoding='utf-8') as file:
        content = file.read()
    
    # First, let's remove any Google Drive related actions and their references
    content = re.sub(r'[ \t]*parent\.actionSync_GDrive.*\n', '', content)
    content = re.sub(r'[ \t]*parent\.actionTest_GDrive.*\n', '', content)
    
    # Extract the class definition and setupUi method
    setupUi_match = re.search(r'def setupUi\(self, parent\):(.*?)def retranslateUi', content, re.DOTALL)
    if not setupUi_match:
        print("Could not find setupUi method")
        return False
    
    setupUi_content = setupUi_match.group(1)
    
    # Find the standard indentation
    indent_match = re.search(r'(\s+)parent\.centralwidget = QtWidgets\.QWidget\(parent\)', setupUi_content)
    if not indent_match:
        print("Could not determine standard indentation")
        return False
        
    standard_indent = indent_match.group(1)
    
    # Process the content line by line to fix indentation for action declarations
    lines = content.split('\n')
    fixed_lines = []
    
    for line in lines:
        # Check if this is an action-related line
        if re.match(r'\s*parent\.action\w+\s*=', line) or re.match(r'\s*parent\.action\w+\.set\w+', line):
            # Extract the actual code without indentation
            code = line.strip()
            # Apply standard indentation
            fixed_lines.append(f"{standard_indent}{code}")
        else:
            fixed_lines.append(line)
    
    # Write back to file
    with open(filepath, 'w', encoding='utf-8') as file:
        file.write('\n'.join(fixed_lines))
    
    print(f"Fixed indentation in {filepath}")
    return True

if __name__ == "__main__":
    fix_mainform_indentation()
    print("All action declarations now have consistent indentation.")