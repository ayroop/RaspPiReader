from PyQt5 import QtWidgets
from RaspPiReader import pool
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
        # Get the main form instance from the pool 
        main_form = pool.get('main_form')
        if main_form and hasattr(main_form, 'new_cycle_start'):
            main_form.new_cycle_start()  # call the new workflow method
        else:
            print("Main form not found or new_cycle_start() not available. Cannot start new cycle.")

    def stop_cycle(self):
        print("Stop Cycle button clicked")
        # Get the main form instance from the pool 
        main_form = pool.get('main_form')
        if main_form and hasattr(main_form, '_stop'):
            main_form._stop()  # call the shared stop cycle method
        else:
            print("Main form not found, or stop method not available. Cannot stop cycle.")