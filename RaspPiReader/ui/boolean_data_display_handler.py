from PyQt5 import QtWidgets, QtCore
from .boolean_data_display_custom import Ui_BooleanDataDisplay, update_boolean_indicator, BooleanIndicator
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
        
        # Adjust grid layout spacing and margins for better UI/UX
        self.ui.gridLayout.setHorizontalSpacing(5)
        self.ui.gridLayout.setVerticalSpacing(5)
        self.ui.gridLayout.setContentsMargins(5, 5, 5, 5)
        
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
        # Replace QLabel widgets with BooleanIndicator widgets
        self.replaceValueWidgets()
        
        self.boolean_config = {}
        self.previous_values = {}  # Store previous boolean values
        self.is_reading_active = False  # Flag to track if reading is active
        self.load_boolean_config()
        
        # Initialize all indicator widgets with default state
        for indicator in self.values:
            indicator.setState(0)
            indicator.setStyleSheet("")

        # Create timer but don't start it yet
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.update_boolean_data)
        
        logger.info("BooleanDataDisplayHandler initialized - waiting for cycle start")
        
    def replaceValueWidgets(self):
        """
        Replace the QLabel widgets created by the auto-generated UI with our custom BooleanIndicator widgets.
        This ensures that the values have the setState method.
        """
        new_widgets = []
        layout = self.ui.gridLayout  # assuming the layout is stored here
        for idx, old_widget in enumerate(self.values):
            # Get the row position from the layout; each indicator is in its own row (0..5)
            row = idx
            # Remove the old widget from the layout
            layout.removeWidget(old_widget)
            old_widget.deleteLater()
            # Create a new BooleanIndicator instance
            indicator = BooleanIndicator(0, parent=self)
            # Add the new widget in the same location (row, column 1)
            layout.addWidget(indicator, row, 1, 1, 1)
            new_widgets.append(indicator)
        self.values = new_widgets

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
            logger.error(f"Error loading boolean config: {e}")
            for i in range(1, 7):
                self.boolean_config[i] = {
                    'id': i,
                    'address': 400 + i,
                    'label': f"LA {i}"
                }
                self.labels[i-1].setText(f"LA {i}")
                self.previous_values[i] = None  # Initialize previous values

    def start_reading(self):
        """Start reading boolean values from PLC"""
        if not self.is_reading_active:
            self.is_reading_active = True
            self.timer.start(1000)  # Update every second
            logger.info("Started boolean address reading")
            
            # Update parent title if it exists
            if hasattr(self.parent(), "boolean_group_box"):
                self.parent().boolean_group_box.setTitle("Boolean Data (Reading Active)")
    
    def stop_reading(self):
        """Stop reading boolean values from PLC"""
        if self.is_reading_active:
            self.is_reading_active = False
            self.timer.stop()
            logger.info("Stopped boolean address reading")
            
            # Reset all indicator widgets to default state
            for indicator in self.values:
                indicator.setState(0)
                indicator.setStyleSheet("")
                
            # Update parent title if it exists
            if hasattr(self.parent(), "boolean_group_box"):
                self.parent().boolean_group_box.setTitle("Boolean Data (Waiting for Cycle Start)")
    
    def update_boolean_data(self):
        """Update the boolean data display only when the value changes."""
        if not self.is_reading_active:
            return
            
        for i in range(6):
            config = self.boolean_config.get(i+1)
            if config:
                try:
                    value = read_boolean(config['address'])
                    if value is not None:
                        if value != self.previous_values.get(i+1):  # Compare with previous value
                            update_boolean_indicator(self.values[i], value)
                            self.values[i].setStyleSheet("")
                            self.previous_values[i+1] = value  # Update previous value
                    else:
                        self.values[i].setStyleSheet("background-color: gray;")
                except Exception as e:
                    logger.error(f"Error reading boolean data: {e}")
                    self.values[i].setStyleSheet("background-color: gray;")
            else:
                self.values[i].setStyleSheet("background-color: gray;")
