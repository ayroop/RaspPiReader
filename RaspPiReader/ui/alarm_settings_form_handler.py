from PyQt5 import QtWidgets
from RaspPiReader.libs.database import Database
from RaspPiReader.libs.models import Alarm
from RaspPiReader.ui.alarm_settings_form import AlarmSettingsForm

class AlarmSettingsFormHandler(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super(AlarmSettingsFormHandler, self).__init__(parent)
        self.setWindowTitle("Alarm Settings")
        
        # Create form
        self.form = AlarmSettingsForm()
        
        # Create layout and add form to it
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self.form)
        self.setLayout(layout)
        
        # Initialize database and load data
        self.db = Database("sqlite:///local_database.db")
        self.load_alarms()
        
        # Connect buttons to their actions
        self.form.addButton.clicked.connect(self.add_alarm)
        self.form.editButton.clicked.connect(self.edit_alarm)
        self.form.removeButton.clicked.connect(self.remove_alarm)
        
        # Set a reasonable size for the dialog
        self.resize(500, 400)
    
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