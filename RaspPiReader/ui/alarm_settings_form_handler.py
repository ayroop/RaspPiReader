import logging
from PyQt5 import QtWidgets
from RaspPiReader.libs.database import Database
from RaspPiReader.libs.models import Alarm
from RaspPiReader.ui.alarm_settings_form import AlarmSettingsForm

logger = logging.getLogger(__name__)

class AlarmSettingsFormHandler(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super(AlarmSettingsFormHandler, self).__init__(parent)
        self.setWindowTitle("Alarm Settings")
        
        # Initialize database
        self.db = Database("sqlite:///local_database.db")
        
        # Setup UI first
        self.setup_ui()
        
        # Then load alarms
        self.load_alarms()
        
        # Set a reasonable size for the dialog
        self.resize(500, 400)
        
        # Create form
        self.form = AlarmSettingsForm()
        
        # Create layout and add form to it
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self.form)
        self.setLayout(layout)
        
        # Connect buttons to their actions
        self.form.addButton.clicked.connect(self.add_alarm)
        self.form.editButton.clicked.connect(self.edit_alarm)
        self.form.removeButton.clicked.connect(self.remove_alarm)
    
    def load_alarms(self):
        alarms = self.db.session.query(Alarm).all()
        table = self.form.tableWidget
        table.setRowCount(len(alarms))
        for row, alarm in enumerate(alarms):
            # Display the channel (e.g., "CH1") instead of a numeric address
            table.setItem(row, 0, QtWidgets.QTableWidgetItem(str(alarm.channel)))
            # Expect alarm.alarm_text to contain multi-line mapping for values 1 to 8 (one per line)
            table.setItem(row, 1, QtWidgets.QTableWidgetItem(alarm.alarm_text))
        table.resizeColumnsToContents()

    def add_alarm(self):
        # Use a drop-down (item selection) for the alarm channel.
        channels = [f"CH{i}" for i in range(1, 15)]
        channel, ok = QtWidgets.QInputDialog.getItem(self, "Add Alarm", 
                                                      "Select Alarm Channel:", channels, 0, False)
        if ok and channel:
            # Use multi-line text input for alarm mapping.
            # Expect one line per alarm level (levels 1 to 8)
            mapping, ok2 = QtWidgets.QInputDialog.getMultiLineText(
                self, "Add Alarm Mapping",
                "Enter alarm mapping (one line per level 1 to 8):",
                "Level 1 Message\nLevel 2 Message\nLevel 3 Message\nLevel 4 Message\nLevel 5 Message\nLevel 6 Message\nLevel 7 Message\nLevel 8 Message"
            )
            if ok2 and mapping:
                new_alarm = Alarm(channel=channel, alarm_text=mapping)
                self.db.session.add(new_alarm)
                self.db.session.commit()
                self.load_alarms()

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
            alarm = self.db.session.query(Alarm).filter_by(channel=current_channel).first()
            if alarm:
                alarm.alarm_text = new_mapping
                self.db.session.commit()
                self.load_alarms()

    def remove_alarm(self):
        table = self.form.tableWidget
        row = table.currentRow()
        if row < 0:
            QtWidgets.QMessageBox.warning(self, "Remove Alarm", "Please select an alarm to remove.")
            return
        channel = table.item(row, 0).text()
        confirm = QtWidgets.QMessageBox.question(self, "Confirm Removal",
                                                 f"Remove alarm for channel {channel}?",
                                                 QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        if confirm == QtWidgets.QMessageBox.Yes:
            alarm = self.db.session.query(Alarm).filter_by(channel=channel).first()
            if alarm:
                self.db.session.delete(alarm)
                self.db.session.commit()
                self.load_alarms()

    def setup_ui(self):
        """Setup the alarm settings UI"""
        try:
            # Create main layout
            layout = QtWidgets.QVBoxLayout()
            
            # Add header
            header = QtWidgets.QLabel("Alarm Settings")
            header.setStyleSheet("font-size: 16px; font-weight: bold;")
            layout.addWidget(header)
            
            # Add explanation
            explanation = QtWidgets.QLabel("Set up alarms by selecting a channel, threshold value, and alarm message.")
            explanation.setWordWrap(True)
            layout.addWidget(explanation)
            
            # Create form layout for alarm settings
            form_layout = QtWidgets.QFormLayout()
            
            # Channel selection
            self.channel_combo = QtWidgets.QComboBox()
            for i in range(1, 15):  # CH1 to CH14
                self.channel_combo.addItem(f"CH{i}")
            form_layout.addRow("Channel:", self.channel_combo)
            
            # Threshold value
            self.threshold_edit = QtWidgets.QDoubleSpinBox()
            self.threshold_edit.setRange(-999999, 999999)
            self.threshold_edit.setDecimals(2)
            form_layout.addRow("Threshold Value:", self.threshold_edit)
            
            # Alarm message
            self.message_edit = QtWidgets.QLineEdit()
            self.message_edit.setPlaceholderText("Enter alarm message")
            form_layout.addRow("Alarm Message:", self.message_edit)
            
            layout.addLayout(form_layout)
            
            # Add buttons
            button_layout = QtWidgets.QHBoxLayout()
            
            add_button = QtWidgets.QPushButton("Add Alarm")
            add_button.clicked.connect(self.add_alarm)
            button_layout.addWidget(add_button)
            
            remove_button = QtWidgets.QPushButton("Remove Selected")
            remove_button.clicked.connect(self.remove_alarm)
            button_layout.addWidget(remove_button)
            
            layout.addLayout(button_layout)
            
            # Add alarm list
            self.alarm_list = QtWidgets.QListWidget()
            self.alarm_list.setSelectionMode(QtWidgets.QListWidget.SingleSelection)
            layout.addWidget(self.alarm_list)
            
            # Add close button
            close_button = QtWidgets.QPushButton("Close")
            close_button.clicked.connect(self.close)
            layout.addWidget(close_button)
            
            self.setLayout(layout)
            
            # Load existing alarms
            self.load_alarms()
            
        except Exception as e:
            logger.error(f"Error setting up alarm settings UI: {e}")
            raise

    def add_alarm(self):
        """Add a new alarm"""
        try:
            channel = self.channel_combo.currentText()
            threshold = self.threshold_edit.value()
            message = self.message_edit.text().strip()
            
            if not message:
                QtWidgets.QMessageBox.warning(self, "Error", "Please enter an alarm message")
                return
                
            # Create alarm record
            alarm = Alarm(
                channel=channel,
                threshold=threshold,
                alarm_text=message
            )
            
            # Save to database
            self.db.session.add(alarm)
            self.db.session.commit()
            
            # Add to list
            self.alarm_list.addItem(f"{channel} - Threshold: {threshold:.2f} - {message}")
            
            # Clear inputs
            self.message_edit.clear()
            
        except Exception as e:
            logger.error(f"Error adding alarm: {e}")
            QtWidgets.QMessageBox.critical(self, "Error", f"Failed to add alarm: {str(e)}")

    def remove_alarm(self):
        """Remove selected alarm"""
        try:
            selected = self.alarm_list.currentItem()
            if not selected:
                QtWidgets.QMessageBox.warning(self, "Error", "Please select an alarm to remove")
                return
                
            # Get alarm details from selected item
            text = selected.text()
            channel = text.split(" - ")[0]
            
            # Find and remove from database
            alarm = self.db.session.query(Alarm).filter_by(channel=channel).first()
            if alarm:
                self.db.session.delete(alarm)
                self.db.session.commit()
                
            # Remove from list
            self.alarm_list.takeItem(self.alarm_list.row(selected))
            
        except Exception as e:
            logger.error(f"Error removing alarm: {e}")
            QtWidgets.QMessageBox.critical(self, "Error", f"Failed to remove alarm: {str(e)}")

    def load_alarms(self):
        """Load existing alarms from database"""
        try:
            self.alarm_list.clear()
            alarms = self.db.session.query(Alarm).all()
            for alarm in alarms:
                self.alarm_list.addItem(f"{alarm.channel} - Threshold: {alarm.threshold:.2f} - {alarm.alarm_text}")
        except Exception as e:
            logger.error(f"Error loading alarms: {e}")
            raise