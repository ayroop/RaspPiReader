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
        self.ui.gridLayout.setHorizontalSpacing(2)
        self.ui.gridLayout.setVerticalSpacing(2)
        self.ui.gridLayout.setContentsMargins(2, 2, 2, 2)
        # Set column stretch factors to force closer grouping
        self.ui.gridLayout.setColumnStretch(0, 0)
        self.ui.gridLayout.setColumnStretch(1, 0)
        
        # Capture the original widgets
        self.labels = [
            self.ui.label_1,
            self.ui.label_2,
            self.ui.label_3,
            self.ui.label_4,
            self.ui.label_5,
            self.ui.label_6
        ]
        # The auto-generated UI put the boolean status widgets as QLabels in column1.
        # We discard those (they will be replaced by our custom indicator).
        self.original_values = [
            self.ui.value_1,
            self.ui.value_2,
            self.ui.value_3,
            self.ui.value_4,
            self.ui.value_5,
            self.ui.value_6
        ]
        
        self.values = []  # This will hold the new BooleanIndicator instances
        # Rebuild the grid layout for each row
        self.rebuildRows()
        
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
        
    def rebuildRows(self):
        """
        Rebuild each row in the gridLayout so that the new BooleanIndicator widget is placed in column 0
        and the corresponding label widget is placed in column 1.
        """
        layout = self.ui.gridLayout
        # Remove existing widgets from the layout in case they are still there
        for widget in self.original_values + self.labels:
            layout.removeWidget(widget)
        # Delete the old value widgets
        for widget in self.original_values:
            widget.deleteLater()
            
        self.values = []
        # Re-add each row in the new order.
        # For each row index (0 through 5), add indicator in col0, then label in col1.
        for idx in range(6):
            # Create a new BooleanIndicator widget
            indicator = BooleanIndicator(0, parent=self)
            self.values.append(indicator)
            # Add indicator to column 0, and then add the label to column 1
            layout.addWidget(indicator, idx, 0, 1, 1)
            layout.addWidget(self.labels[idx], idx, 1, 1, 1)

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
