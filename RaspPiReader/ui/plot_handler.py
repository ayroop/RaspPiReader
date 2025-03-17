import pyqtgraph as pg
from PyQt5.QtWidgets import QSizePolicy
from datetime import datetime
from RaspPiReader import pool
from RaspPiReader.libs.configuration import config  # config.colors is a list of QColor objects

class InitiatePlotWidget:
    def __init__(self, active_channels, parent_layout, legend_layout=None, headers=None):
        """
        active_channels: list of channel identifiers, e.g., ["CH1", "CH2", ..., "CH14"]
        parent_layout: Layout widget in which this plot is embedded.
        legend_layout: Optional legend layout.
        headers: Optional header definitions.
        """
        self.parent_layout = parent_layout
        self.headers = headers
        self.legend_layout = legend_layout
        self.active_channels = active_channels  # list of channel names
        self.curves = {}  # Maps channel -> curve object
        # Store data as (elapsed_time, value) tuples per channel
        self.data_points = {ch: [] for ch in self.active_channels}
        self.start_time = datetime.now()
        self.create_plot()

    def create_plot(self):
        # Create main PlotWidget with white background.
        self.plot_widget = pg.PlotWidget(background="w")
        self.plot_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.plot_widget.showGrid(x=True, y=True)
        self.plot_widget.setLabel('left', 'Value')
        self.plot_widget.setLabel('bottom', 'Time', units='s')
        # Expose plot_widget as left_plot as well (so code referring to self.left_plot works)
        self.left_plot = self.plot_widget  
        if self.parent_layout is not None:
            self.parent_layout.addWidget(self.plot_widget)
        # Create legend inside plot widget.
        self.legend = self.plot_widget.addLegend(offset=(30, 30))
        # Create one curve per active channel using user‐selected colors.
        for ch in self.active_channels:
            try:
                idx = int(ch.replace("CH", "")) - 1
            except Exception:
                idx = 0
            # Check user-selected color from pool; key example "color_CH1"
            color_key = f"color_{ch}"
            color = pool.config(color_key, str, None)
            if not color:
                if hasattr(config, 'colors') and config.colors:
                    color = config.colors[idx % len(config.colors)].name()
                else:
                    color = "b"
            pen = pg.mkPen(color=color, width=2)
            curve = self.plot_widget.plot([], [], pen=pen, name=ch)
            self.curves[ch] = curve

    def add_data_point(self, channel, value):
        """
        Add a new data point (elapsed time, value) for the given channel.
        """
        if channel not in self.data_points:
            self.data_points[channel] = []
        elapsed = (datetime.now() - self.start_time).total_seconds()
        self.data_points[channel].append((elapsed, value))
        # Limit to last 1000 points for each channel.
        if len(self.data_points[channel]) > 1000:
            self.data_points[channel] = self.data_points[channel][-1000:]

    def update_plot(self):
        """
        Update each curve using the stored data points and auto-range.
        """
        for ch in self.active_channels:
            data = self.data_points.get(ch, [])
            if data:
                times, values = zip(*data)
                self.curves[ch].setData(times, values)
            else:
                self.curves[ch].setData([], [])
        self.update_views()

    def update_views(self):
        """
        Adjust the view to include all data (auto-range).
        """
        self.plot_widget.enableAutoRange()

    def create_dynamic_legend(self):
        """
        Clear and re-add items to the legend.
        """
        self.legend.clear()
        for ch in self.active_channels:
            self.legend.addItem(self.curves[ch], ch)

    def show_hide_plot(self, channel, state):
        """
        Show/hide the specified channel's curve.
        """
        if channel in self.curves:
            self.curves[channel].setVisible(state)

    def export_plot(self, full_export_path):
        """
        Export the current plot as an image file.
        """
        try:
            exporter = pg.exporters.ImageExporter(self.plot_widget.plotItem)
            exporter.export(full_export_path)
        except Exception as e:
            print(f"Error exporting plot: {e}")

    def cleanup(self):
        """
        Clear the plot widget and reset data.
        """
        self.plot_widget.clear()
        self.data_points.clear()
        self.curves.clear()