from PyQt5.QtWidgets import QLabel, QColorDialog, QFrame
from PyQt5 import QtGui, QtCore

class ColorLabel(QLabel):
    def __init__(self, parent=None, **kwargs):
        super(ColorLabel, self).__init__(parent, **kwargs)
        self.setAutoFillBackground(True)
        self._color = "#FFFFFF"  # default color
        self.setStyleSheet(f"background-color: {self._color};")
        self.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        self.setFrameShape(QFrame.Box)
        
    def mousePressEvent(self, event):
        self.open_color_picker(event)

    def setValue(self, val):
        self._color = val
        self.setStyleSheet(f"background-color: {self._color};")

    def value(self):
        return self._color

    def open_color_picker(self, event):
        color = QColorDialog.getColor()
        if color.isValid():
            self.setValue(color.name())