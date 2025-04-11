from RaspPiReader.ui.boolean_data_display import Ui_BooleanDataDisplay
from PyQt5.QtWidgets import QLabel
from PyQt5.QtGui import QPainter, QColor, QBrush

class BooleanIndicator(QLabel):
    """
    A custom widget that behaves like a colored square indicator.
    It subclasses QLabel so that we don't alter the auto‑generated UI file,
    and adds a setState method and a custom paintEvent.
    """
    def __init__(self, state=0, parent=None):
        super().__init__(parent)
        self._state = state  # 0 for False, 1 for True
        self.setFixedSize(40, 40)

    def setState(self, state):
        """
        Update the widget's state and trigger a redraw.
        """
        self._state = state
        self.update()

    def paintEvent(self, event):
        """
        Paint a colored square: green for 0, red for 1.
        """
        painter = QPainter(self)
        color = QColor("green") if self._state == 0 else QColor("red")
        painter.fillRect(self.rect(), QBrush(color))

def update_boolean_indicator(widget, new_value):
    """
    Update a given BooleanIndicator widget with a new boolean value.
    """
    widget.setState(1 if new_value else 0)
    
# Export the auto‑generated UI class as well
__all__ = ['Ui_BooleanDataDisplay', 'BooleanIndicator', 'update_boolean_indicator']