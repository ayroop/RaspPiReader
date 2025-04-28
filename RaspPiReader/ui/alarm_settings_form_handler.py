import logging
from PyQt5 import QtWidgets
from RaspPiReader.libs.database import Database
from RaspPiReader.libs.models import Alarm, AlarmMapping
from RaspPiReader.ui.alarm_settings_form import AlarmSettingsForm
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

class AlarmSettingsFormHandler(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super(AlarmSettingsFormHandler, self).__init__(parent)
        self.setWindowTitle("Alarm Settings")
        
        # Initialize database
        self.db = Database("sqlite:///local_database.db")
        
        # Create form first
        self.form = AlarmSettingsForm()
        
        # Setup UI
        self.setup_ui()
        
        # Load alarms
        self.load_alarms()
        
        # Set a reasonable size for the dialog
        self.resize(500, 400)
        
        # Connect buttons to their actions
        self.form.addButton.clicked.connect(self.add_alarm)
        self.form.editButton.clicked.connect(self.edit_alarm)
        self.form.removeButton.clicked.connect(self.remove_alarm)

    def setup_ui(self):
        """Setup the UI elements"""
        # Create main layout
        layout = QtWidgets.QVBoxLayout()
        
        # Add header
        header = QtWidgets.QLabel("Alarm Settings")
        header.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(header)
        
        # Add explanation
        explanation = QtWidgets.QLabel("Set up alarms by selecting a channel, threshold value, and alarm message. You can add multiple alarms per channel.")
        explanation.setWordWrap(True)
        layout.addWidget(explanation)
        
        # Create form layout for alarm settings
        form_layout = QtWidgets.QFormLayout()
        
        # Channel selection
        self.form.channel_combo = QtWidgets.QComboBox()
        for i in range(1, 15):  # CH1 to CH14
            self.form.channel_combo.addItem(f"CH{i}")
        form_layout.addRow("Channel:", self.form.channel_combo)
        
        # Alarm type selection
        self.form.alarm_type_combo = QtWidgets.QComboBox()
        self.form.alarm_type_combo.addItems(["Low Threshold", "High Threshold"])
        form_layout.addRow("Alarm Type:", self.form.alarm_type_combo)
        
        # Threshold value
        self.form.threshold_spin = QtWidgets.QDoubleSpinBox()
        self.form.threshold_spin.setRange(-999999, 999999)
        self.form.threshold_spin.setDecimals(2)
        form_layout.addRow("Threshold Value:", self.form.threshold_spin)
        
        # Alarm message
        self.form.message_edit = QtWidgets.QLineEdit()
        self.form.message_edit.setPlaceholderText("Enter alarm message")
        form_layout.addRow("Alarm Message:", self.form.message_edit)
        
        layout.addLayout(form_layout)
        
        # Add buttons
        button_layout = QtWidgets.QHBoxLayout()
        
        self.form.addButton = QtWidgets.QPushButton("Add Alarm")
        button_layout.addWidget(self.form.addButton)
        
        self.form.editButton = QtWidgets.QPushButton("Edit Selected")
        button_layout.addWidget(self.form.editButton)
        
        self.form.removeButton = QtWidgets.QPushButton("Remove Selected")
        button_layout.addWidget(self.form.removeButton)
        
        layout.addLayout(button_layout)
        
        # Add alarm table
        self.form.tableWidget = QtWidgets.QTableWidget()
        self.form.tableWidget.setColumnCount(2)
        self.form.tableWidget.setHorizontalHeaderLabels(["Channel", "Alarm Settings"])
        self.form.tableWidget.setSelectionBehavior(QtWidgets.QTableWidget.SelectRows)
        self.form.tableWidget.setSelectionMode(QtWidgets.QTableWidget.SingleSelection)
        layout.addWidget(self.form.tableWidget)
        
        # Set the layout
        self.setLayout(layout)

    def load_alarms(self):
        """Load alarms from database and display them"""
        try:
            with Session(self.db.engine) as session:
                # Get all channels that have alarms
                channels = session.query(Alarm.channel).distinct().all()
                self.form.tableWidget.setRowCount(len(channels))
                
                for row, (channel,) in enumerate(channels):
                    # Get all active mappings for this channel
                    alarm = session.query(Alarm).filter_by(channel=channel).first()
                    mappings = session.query(AlarmMapping).filter_by(
                        alarm_id=alarm.id,
                        active=True
                    ).all()
                    
                    if mappings:
                        # Create a formatted string showing all thresholds and messages
                        alarm_info = []
                        for mapping in mappings:
                            threshold_type = "Low" if mapping.value == 1 else "High"
                            alarm_info.append(f"{threshold_type} Threshold ({mapping.threshold:.2f}): {mapping.message}")
                        
                        # Add to table with channel info
                        self.form.tableWidget.setItem(row, 0, QtWidgets.QTableWidgetItem(str(channel)))
                        self.form.tableWidget.setItem(row, 1, QtWidgets.QTableWidgetItem("\n".join(alarm_info)))
                        
                        # Set row height to accommodate multiple lines
                        self.form.tableWidget.setRowHeight(row, len(alarm_info) * 25)  # 25 pixels per line
                    else:
                        # Show channel with no active alarms
                        self.form.tableWidget.setItem(row, 0, QtWidgets.QTableWidgetItem(str(channel)))
                        self.form.tableWidget.setItem(row, 1, QtWidgets.QTableWidgetItem("No active alarms"))
                        self.form.tableWidget.setRowHeight(row, 25)  # Default height for single line
                
            # Resize columns and rows to fit content
            self.form.tableWidget.resizeColumnsToContents()
            self.form.tableWidget.resizeRowsToContents()
            
            # Set word wrap for the alarm settings column
            self.form.tableWidget.setWordWrap(True)
            
        except Exception as e:
            logger.error(f"Error loading alarm settings: {e}")
            QtWidgets.QMessageBox.critical(self, "Error", f"Failed to load alarm settings: {str(e)}")

    def add_alarm(self):
        """Add a new alarm"""
        try:
            channel = self.form.channel_combo.currentText()
            threshold = float(self.form.threshold_spin.value())
            message = self.form.message_edit.text()
            alarm_type = self.form.alarm_type_combo.currentText()  # "Low Threshold" or "High Threshold"
            
            if not message:
                QtWidgets.QMessageBox.warning(self, "Error", "Please enter an alarm message")
                return
                
            with Session(self.db.engine) as session:
                # Check if alarm exists for this channel
                alarm = session.query(Alarm).filter_by(channel=channel).first()
                if not alarm:
                    # Create new alarm
                    alarm = Alarm(channel=channel)
                    session.add(alarm)
                    session.flush()  # Get the alarm ID
                
                # Create new mapping
                mapping = AlarmMapping(
                    alarm_id=alarm.id,
                    value=1 if alarm_type == "Low Threshold" else 2,  # 1 for low, 2 for high
                    threshold=threshold,
                    message=message,
                    active=True
                )
                session.add(mapping)
                session.commit()
                
                # Reload alarms
                self.load_alarms()
                
                # Clear inputs
                self.form.message_edit.clear()
                
        except Exception as e:
            logger.error(f"Error adding alarm: {e}")
            QtWidgets.QMessageBox.critical(self, "Error", f"Failed to add alarm: {str(e)}")

    def edit_alarm(self):
        table = self.form.tableWidget
        row = table.currentRow()
        if row < 0:
            QtWidgets.QMessageBox.warning(self, "Edit Alarm", "Please select an alarm to edit.")
            return
        current_channel = table.item(row, 0).text()
        current_mapping = table.item(row, 1).text()
        # Use multi-line text input for editing the alarm mapping
        new_mapping, ok = QtWidgets.QInputDialog.getMultiLineText(
            self, "Edit Alarm Mapping",
            "Modify alarm mapping (one line per level 1 to 8):",
            current_mapping
        )
        if ok and new_mapping:
            with Session(self.db.engine) as session:
                # Find the alarm for this channel
                alarm = session.query(Alarm).filter_by(channel=current_channel).first()
                if alarm:
                    # Deactivate all mappings for this alarm
                    mappings = session.query(AlarmMapping).filter_by(alarm_id=alarm.id).all()
                    for mapping in mappings:
                        mapping.active = False
                    
                    # Create new mapping
                    mapping = AlarmMapping(
                        alarm_id=alarm.id,
                        value=1 if "Low" in new_mapping else 2,  # 1 for low, 2 for high
                        threshold=float(new_mapping[0].split(": ")[1]),
                        message=new_mapping[1],
                        active=True
                    )
                    session.add(mapping)
                    session.commit()
                    
                    # Reload alarms
                    self.load_alarms()

    def remove_alarm(self):
        """Remove selected alarm"""
        try:
            selected = self.form.tableWidget.currentItem()
            if not selected:
                QtWidgets.QMessageBox.warning(self, "Error", "Please select an alarm to remove")
                return
                
            # Get the row of the selected item
            row = self.form.tableWidget.currentRow()
            channel = self.form.tableWidget.item(row, 0).text()
            
            with Session(self.db.engine) as session:
                # Find the alarm for this channel
                alarm = session.query(Alarm).filter_by(channel=channel).first()
                if alarm:
                    # Deactivate all mappings for this alarm
                    mappings = session.query(AlarmMapping).filter_by(alarm_id=alarm.id).all()
                    for mapping in mappings:
                        mapping.active = False
                    session.commit()
                    
                    # Reload alarms
                    self.load_alarms()
                    
        except Exception as e:
            logger.error(f"Error removing alarm: {e}")
            QtWidgets.QMessageBox.critical(self, "Error", f"Failed to remove alarm: {str(e)}")