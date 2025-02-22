from PyQt5 import QtWidgets
from RaspPiReader.ui.new_cycle import Ui_NewCycle

class NewCycleHandler(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(NewCycleHandler, self).__init__(parent)
        self.ui = Ui_NewCycle()
        self.ui.setupUi(self)
        self.ui.startCycleButton.clicked.connect(self.start_cycle)
        self.ui.stopCycleButton.clicked.connect(self.stop_cycle)

    def start_cycle(self):
        print("Start Cycle button clicked")
        # Add your start cycle logic here

    def stop_cycle(self):
        print("Stop Cycle button clicked")
        # Add your stop cycle logic here