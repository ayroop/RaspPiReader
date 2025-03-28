from PyQt5 import QtWidgets, QtCore
from .boolean_data_display import Ui_BooleanDataDisplay
from RaspPiReader.libs.plc_communication import read_boolean
import logging

logger = logging.getLogger(__name__)

class BooleanDataDisplayHandler(QtWidgets.QWidget):
    """
    Handles the display of boolean data in the UI.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_BooleanDataDisplay()
        self.ui.setupUi(self)
        self.labels = [
            self.ui.label_1,
            self.ui.label_2,
            self.ui.label_3,
            self.ui.label_4,
            self.ui.label_5,
            self.ui.label_6
        ]
        self.values = [
            self.ui.value_1,
            self.ui.value_2,
            self.ui.value_3,
            self.ui.value_4,
            self.ui.value_5,
            self.ui.value_6
        ]
        self.boolean_config = {}
        self.previous_values = {}  # Store previous boolean values
        self.load_boolean_config()
        self.update_boolean_data()

        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.update_boolean_data)
        self.timer.start(1000)  # Update every 1000 ms (1 second)

    def load_boolean_config(self):
        """Load Boolean address configurations from the database"""
        try:
            from RaspPiReader.libs.database import Database
            from RaspPiReader.libs.models import BooleanAddress
            db = Database("sqlite:///local_database.db")
            boolean_entries = db.session.query(BooleanAddress).all()
            if boolean_entries:
                for i, entry in enumerate(boolean_entries[:6]):
                    self.boolean_config[i+1] = {
                        'id': entry.id,
                        'address': entry.address,
                        'label': entry.label
                    }
                    self.labels[i].setText(entry.label)
                    self.previous_values[i+1] = None  # Initialize previous values
            else:
                for i in range(1, 7):
                    self.boolean_config[i] = {
                        'id': i,
                        'address': 400 + i,  # Example fallback address
                        'label': f"LA {i}"
                    }
                    self.labels[i-1].setText(f"LA {i}")
                    self.previous_values[i] = None  # Initialize previous values
        except Exception as e:
            print(f"Error loading boolean config: {e}")
            for i in range(1, 7):
                self.boolean_config[i] = {
                    'id': i,
                    'address': 400 + i,
                    'label': f"LA {i}"
                }
                self.labels[i-1].setText(f"LA {i}")
                self.previous_values[i] = None  # Initialize previous values

    def update_boolean_data(self):
        """Update the boolean data display only when the value changes."""
        for i in range(6):
            config = self.boolean_config.get(i+1)
            if config:
                try:
                    value = read_boolean(config['address'])
                    if value is not None:
                        if value != self.previous_values.get(i+1):  # Compare with previous value
                            self.values[i].setText(str(value))
                            self.previous_values[i+1] = value  # Update previous value
                    else:
                        self.values[i].setText("Error")
                except Exception as e:
                    logger.error(f"Error reading boolean data: {e}")
                    self.values[i].setText("Error")
            else:
                self.values[i].setText("N/A")