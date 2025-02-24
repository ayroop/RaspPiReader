import os
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtWidgets import QColorDialog, QFileDialog
from PyQt5.QtCore import QSettings

class BackgroundSettingsForm(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super(BackgroundSettingsForm, self).__init__(parent)
        self.setWindowTitle("Background Settings")
        self.resize(400, 200)
        self.settings = QSettings("RaspPiHandler", "RaspPiReader")
        self.selected_color = ""
        self.image_path = ""
        self.setupUi()
        self.load_settings()

    def setupUi(self):
        layout = QtWidgets.QVBoxLayout(self)
        
        self.colorButton = QtWidgets.QPushButton("Select Background Color", self)
        self.colorButton.clicked.connect(self.select_color)
        layout.addWidget(self.colorButton)
        
        self.imageButton = QtWidgets.QPushButton("Select Background Image", self)
        self.imageButton.clicked.connect(self.select_image)
        layout.addWidget(self.imageButton)
        
        self.previewLabel = QtWidgets.QLabel("", self)
        self.previewLabel.setFixedHeight(100)
        self.previewLabel.setStyleSheet("border: 1px solid gray;")
        self.previewLabel.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(self.previewLabel)
        
        btnLayout = QtWidgets.QHBoxLayout()
        self.saveButton = QtWidgets.QPushButton("Save", self)
        self.saveButton.clicked.connect(self.save_settings)
        btnLayout.addWidget(self.saveButton)
        
        self.cancelButton = QtWidgets.QPushButton("Cancel", self)
        self.cancelButton.clicked.connect(self.reject)
        btnLayout.addWidget(self.cancelButton)
        layout.addLayout(btnLayout)

    def select_color(self):
        color = QColorDialog.getColor()
        if color.isValid():
            self.selected_color = color.name()
            self.image_path = ""  # Clear any image selection.
            # Show a simple preview: fill the label with the color.
            self.previewLabel.setStyleSheet(f"background-color: {self.selected_color}; border: 1px solid gray;")
            self.previewLabel.setText("")

    def select_image(self):
        options = QFileDialog.Options()
        file_name, _ = QFileDialog.getOpenFileName(self, "Select Background Image", "",
                                                   "Images (*.png *.jpg *.jpeg *.bmp)", options=options)
        if file_name:
            self.image_path = file_name
            self.selected_color = ""  # Clear color setting
            # Use QImageReader to efficiently load a scaled image.
            reader = QtGui.QImageReader(file_name)
            # Calculate a scaled size that fits in previewLabel (e.g. its size multiplied by a factor if needed)
            desired_size = self.previewLabel.size()
            reader.setScaledSize(desired_size)
            image = reader.read()
            if not image.isNull():
                pixmap = QtGui.QPixmap.fromImage(image)
                self.previewLabel.setPixmap(pixmap)
            else:
                self.previewLabel.setText("Failed to load image.")

    def load_settings(self):
        # Load settings; default to empty strings (no style) if not set.
        self.selected_color = self.settings.value("background/color", "")
        self.image_path = self.settings.value("background/image", "")
        # If settings exist, update preview; otherwise clear
        if self.selected_color:
            self.previewLabel.setStyleSheet(f"background-color: {self.selected_color}; border: 1px solid gray;")
            self.previewLabel.setText("")
        elif self.image_path and os.path.exists(self.image_path):
            reader = QtGui.QImageReader(self.image_path)
            reader.setScaledSize(self.previewLabel.size())
            image = reader.read()
            if not image.isNull():
                pixmap = QtGui.QPixmap.fromImage(image)
                self.previewLabel.setPixmap(pixmap)
            else:
                self.previewLabel.setText("Failed to load saved image.")
        else:
            self.previewLabel.setText("")

    def save_settings(self):
        if self.selected_color:
            self.settings.setValue("background/color", self.selected_color)
            self.settings.setValue("background/image", "")
        elif self.image_path:
            self.settings.setValue("background/image", self.image_path)
            self.settings.setValue("background/color", "")
        else:
            # If no selection, clear the settings
            self.settings.setValue("background/color", "")
            self.settings.setValue("background/image", "")
        self.accept()