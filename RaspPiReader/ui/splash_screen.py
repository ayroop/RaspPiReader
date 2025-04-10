import os
from PyQt5 import QtWidgets, QtGui, QtCore
from RaspPiReader.libs.resource_path import resource_path


class SplashScreen(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(SplashScreen, self).__init__(parent)
        # Remove window borders and set splash style.
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint | QtCore.Qt.WindowStaysOnTopHint)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        
        # Use resource_path to obtain the correct path to the splash image.
        splash_file = resource_path("RaspPiReader/ui/Rasp-Splash.png")

        # Load the splash image.
        pixmap = QtGui.QPixmap(splash_file)
        if pixmap.isNull():
            # Falling back to a white pixmap if the image is missing.
            pixmap = QtGui.QPixmap(400, 300)
            pixmap.fill(QtCore.Qt.white)

        # Scale the pixmap responsively based on primary screen geometry.
        screen_geom = QtWidgets.QApplication.primaryScreen().availableGeometry()
        target_width = screen_geom.width() // 3
        target_height = screen_geom.height() // 3
        scaled_pixmap = pixmap.scaled(target_width, target_height, 
                                      QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
                                      
        # The background label to show the image.
        self.bg_label = QtWidgets.QLabel(self)
        self.bg_label.setPixmap(scaled_pixmap)
        self.bg_label.setFixedSize(scaled_pixmap.size())
        self.bg_label.setScaledContents(True)

        # Create a transparent overlay widget for progress bar and label.
        self.overlay = QtWidgets.QWidget(self.bg_label)
        self.overlay.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents)
        self.overlay.setFixedSize(scaled_pixmap.size())
        # Use a vertical layout to center the progress and percentage message.
        layout = QtWidgets.QVBoxLayout(self.overlay)
        layout.setContentsMargins(20, scaled_pixmap.height() - 80, 20, 20)
        layout.setSpacing(10)

        # Percentage label.
        self.percentage_label = QtWidgets.QLabel("Loading 0%", self.overlay)
        self.percentage_label.setAlignment(QtCore.Qt.AlignCenter)
        self.percentage_label.setStyleSheet("color: #2196F3; font: bold 16px;")
        layout.addWidget(self.percentage_label)

        # Progress bar.
        self.progress_bar = QtWidgets.QProgressBar(self.overlay)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setAlignment(QtCore.Qt.AlignCenter)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid #2196F3;
                border-radius: 10px;
                background-color: #e0e0e0;
                color: white;
                font: bold 12px;
            }
            QProgressBar::chunk {
                border-radius: 10px;
                background-color: qlineargradient(
                    spread:pad, x1:0, y1:0, x2:1, y2:0, stop:0 #2196F3, stop:1 #21CBF3
                );
            }
        """)
        layout.addWidget(self.progress_bar)

        # Set the overall widget size to that of the splash image.
        self.setFixedSize(scaled_pixmap.size())

        # Create a fade-in animation for the splash screen.
        self.opacity_effect = QtWidgets.QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)
        self.animation = QtCore.QPropertyAnimation(self.opacity_effect, b"opacity")
        self.animation.setDuration(1000)
        self.animation.setStartValue(0.0)
        self.animation.setEndValue(1.0)

    def showEvent(self, event):
        # Start fade-in animation when the splash screen is shown.
        self.animation.start()
        super(SplashScreen, self).showEvent(event)

    def update_progress(self, value):
        """Update the progress bar and percentage label."""
        self.progress_bar.setValue(value)
        self.percentage_label.setText(f"Loading {value}%")
        # Ensure that UI updates are visible immediately.
        QtWidgets.QApplication.processEvents()

    def finish(self, target_widget):
        """
        Fade-out the splash screen and display the target widget.
        
        Parameters:
            target_widget (QWidget): The widget to be shown after the splash screen.
        """
        fade_duration = 500  # Fade-out duration in milliseconds.
        self.fade_out_anim = QtCore.QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_out_anim.setDuration(fade_duration)
        self.fade_out_anim.setStartValue(1.0)
        self.fade_out_anim.setEndValue(0.0)
        # Once the fade-out is complete, show the target widget and close the splash screen.
        self.fade_out_anim.finished.connect(lambda: self._on_fade_finished(target_widget))
        self.fade_out_anim.start()

    def _on_fade_finished(self, target_widget):
        target_widget.show()
        self.close()


# Example usage within your application:
if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    splash = SplashScreen()
    splash.show()
    
    # Simulate a loading process.
    for i in range(101):
        splash.update_progress(i)
        QtCore.QThread.msleep(20)  # simulate workload
    
    # After work is done, continue to start your main window.
    window = QtWidgets.QMainWindow()
    window.setWindowTitle("Main Application")
    window.resize(800, 600)
    
    # Use the new finish method to fade out the splash screen and show the main window.
    splash.finish(window)
    sys.exit(app.exec_())
