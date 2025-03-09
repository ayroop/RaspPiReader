import re
import os

def fix_qt_ui_file(file_path):
    print(f"Fixing Qt enum syntax in {file_path}")
    
    with open(file_path, 'r', encoding='utf-8') as file:
        content = file.read()
    
    # Fix Qt::Orientation::Horizontal pattern
    content = re.sub(r'Qt::Orientation::', r'Qt::', content)
    
    # Fix QFrame::Shape::Box pattern
    content = re.sub(r'QFrame::Shape::', r'QFrame::', content)
    
    # Fix Qt::FocusPolicy::NoFocus pattern
    content = re.sub(r'Qt::FocusPolicy::', r'Qt::', content)
    
    # Fix Qt::AlignmentFlag:: patterns
    content = re.sub(r'Qt::AlignmentFlag::', r'Qt::', content)
    
    # Fix Qt::LayoutDirection:: patterns
    content = re.sub(r'Qt::LayoutDirection::', r'Qt::', content)
    
    # Fix Qt::TextFormat:: patterns
    content = re.sub(r'Qt::TextFormat::', r'Qt::', content)
    
    # Fix any other remaining double-colon enum patterns
    content = re.sub(r'Qt::([\w]+)::', r'Qt::', content)
    
    with open(file_path, 'w', encoding='utf-8') as file:
        file.write(content)
    
    print("✓ Fixed Qt enum syntax!")
    
    # Now regenerate the Python file
    output_file = os.path.join(
        "RaspPiReader/ui",
        os.path.basename(file_path).replace(".ui", ".py")
    )
    cmd = f"pyuic5 {file_path} -o {output_file}"
    print(f"Running: {cmd}")
    os.system(cmd)

if __name__ == "__main__":
    fix_qt_ui_file("RaspPiReader/qt/main.ui")
    
    # Uncomment to fix all UI files:
    # ui_files = [f for f in os.listdir("RaspPiReader/qt") if f.endswith(".ui")]
    # for ui_file in ui_files:
    #     fix_qt_ui_file(os.path.join("RaspPiReader/qt", ui_file))