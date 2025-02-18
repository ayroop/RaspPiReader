from PyQt5.QtWidgets import QLabel, QColorDialog

class ColorLabel(QLabel):
    def __init__(self, parent=None, **kwargs):
        super(ColorLabel, self).__init__(parent, **kwargs)
        self.setAutoFillBackground(True)
        self.setStyleSheet("background-color: #FFFFFF;")  # Default color
        self.mousePressEvent = self.open_color_picker

    def setValue(self, val):
        self.setStyleSheet(f"background-color:{val}")

    def value(self):
        palette = self.palette()
        return palette.color(palette.Window).name()

    def open_color_picker(self, event):
        color = QColorDialog.getColor()
        if color.isValid():
            self.setValue(color.name())