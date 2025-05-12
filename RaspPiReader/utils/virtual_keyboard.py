import os
import subprocess
from PyQt5.QtWidgets import QLineEdit, QSpinBox, QDoubleSpinBox
from PyQt5.QtCore import QObject, pyqtSignal

class VirtualKeyboardHandler(QObject):
    def __init__(self):
        super().__init__()
        self.keyboard_process = None

    def show_keyboard(self):
        """Show the Windows virtual keyboard"""
        try:
            # Check if keyboard is already running
            if self.keyboard_process and self.keyboard_process.poll() is None:
                return

            # Start the Windows virtual keyboard
            self.keyboard_process = subprocess.Popen(['osk.exe'])
        except Exception as e:
            print(f"Error showing virtual keyboard: {e}")

    def hide_keyboard(self):
        """Hide the Windows virtual keyboard"""
        try:
            if self.keyboard_process and self.keyboard_process.poll() is None:
                self.keyboard_process.terminate()
                self.keyboard_process = None
        except Exception as e:
            print(f"Error hiding virtual keyboard: {e}")

# Create a global instance
keyboard_handler = VirtualKeyboardHandler()

def setup_virtual_keyboard(widget):
    """Setup virtual keyboard for input widgets"""
    def on_focus_in():
        keyboard_handler.show_keyboard()

    def on_focus_out():
        keyboard_handler.hide_keyboard()

    if isinstance(widget, (QLineEdit, QSpinBox, QDoubleSpinBox)):
        widget.focusInEvent = lambda event: (on_focus_in(), widget.__class__.focusInEvent(widget, event))
        widget.focusOutEvent = lambda event: (on_focus_out(), widget.__class__.focusOutEvent(widget, event)) 