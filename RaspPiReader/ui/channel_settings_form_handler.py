from PyQt5 import QtWidgets
from RaspPiReader.libs.database import Database
from RaspPiReader.libs.models import ChannelConfigSettings

class ChannelSettingsFormHandler(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super(ChannelSettingsFormHandler, self).__init__(parent)
        self.setWindowTitle("Channel Settings")
        self.resize(800, 600)
        self.db = Database("sqlite:///local_database.db")
        self._setup_ui()
        self.load_channels()

    def _setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        self.table = QtWidgets.QTableWidget(14, 12)
        headers = ["ID", "Address", "Label", "PV", "SV", "Set Point", "Low Limit", "High Limit", "Decimal", "Scale", "Axis", "Color"]
        self.table.setHorizontalHeaderLabels(headers)
        layout.addWidget(self.table)
        buttons_layout = QtWidgets.QHBoxLayout()
        save_btn = QtWidgets.QPushButton("Save")
        save_btn.clicked.connect(self._save_channels)
        close_btn = QtWidgets.QPushButton("Close")
        close_btn.clicked.connect(self.close)
        buttons_layout.addWidget(save_btn)
        buttons_layout.addWidget(close_btn)
        layout.addLayout(buttons_layout)

    def load_channels(self):
        session = self.db.session
        channels = session.query(ChannelConfigSettings).order_by(ChannelConfigSettings.id).all()
        for row, channel in enumerate(channels):
            self.table.setItem(row, 0, QtWidgets.QTableWidgetItem(str(channel.id)))
            self.table.setItem(row, 1, QtWidgets.QTableWidgetItem(str(channel.address)))
            self.table.setItem(row, 2, QtWidgets.QTableWidgetItem(channel.label))
            self.table.setItem(row, 3, QtWidgets.QTableWidgetItem(str(channel.pv)))
            self.table.setItem(row, 4, QtWidgets.QTableWidgetItem(str(channel.sv)))
            self.table.setItem(row, 5, QtWidgets.QTableWidgetItem(str(channel.set_point)))
            self.table.setItem(row, 6, QtWidgets.QTableWidgetItem(str(channel.limit_low)))
            self.table.setItem(row, 7, QtWidgets.QTableWidgetItem(str(channel.limit_high)))
            #self.table.setItem(row, 8, QtWidgets.QTableWidgetItem(str(channel.dec_point)))
            self.table.setItem(row, 8, QtWidgets.QTableWidgetItem(str(channel.decimal_point)))
            self.table.setItem(row, 9, QtWidgets.QTableWidgetItem(str(channel.scale)))
            self.table.setItem(row, 10, QtWidgets.QTableWidgetItem(channel.axis_direction))
            self.table.setItem(row, 11, QtWidgets.QTableWidgetItem(channel.color))

    def _save_channels(self):
        session = self.db.session
        for row in range(self.table.rowCount()):
            id_item = self.table.item(row, 0)
            if not id_item:
                continue
            channel_id = int(id_item.text())
            channel = session.query(ChannelConfigSettings).filter_by(id=channel_id).first()
            if channel:
                channel.address = int(self.table.item(row, 1).text())
                channel.label = self.table.item(row, 2).text()
                channel.pv = int(self.table.item(row, 3).text())
                channel.sv = int(self.table.item(row, 4).text())
                channel.set_point = int(self.table.item(row, 5).text())
                channel.limit_low = int(self.table.item(row, 6).text())
                channel.limit_high = int(self.table.item(row, 7).text())
                channel.dec_point = int(self.table.item(row, 8).text())
                channel.scale = self.table.item(row, 9).text().lower() == "true"
                channel.axis_direction = self.table.item(row, 10).text()
                channel.color = self.table.item(row, 11).text()
        session.commit()
        QtWidgets.QMessageBox.information(self, "Saved", "Channel settings have been saved.")