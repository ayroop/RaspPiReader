import pyqtgraph as pg
import pyqtgraph.exporters
from PyQt5.QtWidgets import QApplication, QLabel, QCheckBox
from RaspPiReader import pool

DATA_SKIP_FACTOR = 10

class InitiatePlotWidget:
    def __init__(self, active_channels, parent_layout, legend_layout=None, headers=None):
        self.parent_layout = parent_layout
        self.headers = headers
        self.legend_layout = legend_layout
        self.active_channels = active_channels  # For example: ["CH1", "CH2", ...]
        self.create_plot()

    def create_plot(self):
        # Create left plot widget
        self.left_plot = pg.PlotWidget(background="white", title="")
        self.parent_layout.addWidget(self.left_plot)
        self.left_plot.showAxis('right')
        # Create a right plot viewbox linked to the left plot
        self.right_plot = pg.ViewBox()
        self.left_plot.scene().addItem(self.right_plot)
        self.left_plot.getAxis('right').linkToView(self.right_plot)
        self.right_plot.setXLink(self.left_plot)
        self.left_plot.getViewBox().sigResized.connect(self.update_views)

        self.right_plot.setDefaultPadding(0.0)
        self.left_plot.setDefaultPadding(0.0)

        # Set axis labels from headers if provided, else use fallback values
        if self.headers and len(self.headers) >= 3:
            self.left_plot.setLabel('bottom', self.headers[0], **{'font-size': '10pt'})
            self.left_plot.setLabel('left', self.headers[1], **{'font-size': '10pt'})
            self.left_plot.setLabel('right', self.headers[2], **{'font-size': '10pt'})
        else:
            self.left_plot.setLabel('bottom', "Time", **{'font-size': '10pt'})
            self.left_plot.setLabel('left', "Value", **{'font-size': '10pt'})
            self.left_plot.setLabel('right', "", **{'font-size': '10pt'})

        # Create legend: use built-in legend if no separate layout is provided.
        if self.legend_layout is not None:
            self.create_dynamic_legend()
        else:
            self.legend = self.left_plot.addLegend(colCount=2, brush='#f5f5f5', labelTextColor='#242323')

        self.last_data_index = 0
        self.data = pool.get('data_stack')

        # Determine which channels plot on left axis and on right axis.
        # Here we check configuration using each channel string.
        self.left_lines = [ch for ch in self.active_channels if pool.config('axis_direction' + str(ch)) == 'L']
        self.right_lines = [ch for ch in self.active_channels if ch not in self.left_lines]

        # Create curves using enumeration so that index arithmetic works properly.
        for idx, ch in enumerate(self.active_channels):
            args = {
                'pen': {'color': pool.config("color" + str(ch)), 'width': 2},
                'autoDownsample': True
            }
            if self.legend_layout is None and self.headers and len(self.headers) > idx + 2:
                args.update(name=self.headers[idx + 2])
            if ch in self.left_lines:
                curve = self.left_plot.plot([], [], **args)
            else:
                curve = pg.PlotCurveItem([], [], **args)
                self.right_plot.addItem(curve)
                if self.legend_layout is None and hasattr(curve, "name"):
                    self.legend.addItem(curve, curve.name())
            setattr(self, "line_" + str(ch), curve)

    def update_plot(self):
    # Ensure self.data is defined and has at least one row (time values)
        self.data = pool.get('data_stack') or []
        if not self.data or len(self.data) == 0 or len(self.data[0]) == 0:
            return  # No data to display

        n_data = len(self.data[0])
        if n_data > self.last_data_index:
            acc_time = pool.config('accuarate_data_time', float, 0.0) or 0.0
            if acc_time > 0:
                acc_index = 0
                for i in range(n_data, 0, -1):
                    if (self.data[0][-1] - self.data[0][i - 1]) > acc_time:
                        acc_index = i
                        break
                for ch in self.active_channels:
                    curve = getattr(self, "line_" + str(ch))
                    x_data = self.data[0][0:acc_index:DATA_SKIP_FACTOR] + self.data[0][acc_index:]
                    y_index = self.active_channels.index(ch) + 1
                    y_data = self.data[y_index][0:acc_index:DATA_SKIP_FACTOR] + self.data[y_index][acc_index:]
                    curve.setData(x_data, y_data)
            else:
                for ch in self.active_channels:
                    idx = self.active_channels.index(ch)
                    getattr(self, "line_" + str(ch)).setData(self.data[0], self.data[idx+1])
            self.left_plot.setXRange(0, self.data[0][-1])
            self.last_data_index = len(self.data[0]) - 1
            QApplication.processEvents()

    def update_views(self):
        # Ensure the right viewbox is always aligned to the left plot view.
        self.right_plot.setGeometry(self.left_plot.getViewBox().sceneBoundingRect())
        self.right_plot.linkedViewChanged(self.left_plot.getViewBox(), self.right_plot.XAxis)

    def create_dynamic_legend(self):
        # Create legend items with checkboxes for each channel.
        func = lambda idx: (lambda state: self.show_hide_plot(idx, state))
        for idx, ch in enumerate(self.active_channels):
            header_index = idx + 2 if self.headers and len(self.headers) > idx + 2 else None
            header_text = self.headers[header_index] if header_index is not None else f"Channel {ch}"
            check_box, label = self.create_legend_item(header_text, pool.config('color' + str(ch)))
            self.legend_layout.addRow(check_box, label)
            check_box.stateChanged.connect(func(idx))

    def create_legend_item(self, text, color):
        if color is None:
            color = "#000000"
        if text is None:
            text = "Undefined"
        check_box = QCheckBox()
        check_box.setChecked(True)
        legend_string = (
            '<font color="' + color + '"> &#8212;&#8212;&nbsp;&nbsp; </font>'
            + '<font color="black">' + text + '</font>'
        )
        label = QLabel()
        label.setText(legend_string)
        return check_box, label

    def show_hide_plot(self, idx, state):
        ch = self.active_channels[idx]
        if state:
            getattr(self, "line_" + str(ch)).show()
        else:
            getattr(self, "line_" + str(ch)).hide()

    def export_plot(self, full_export_path):
        exporter = pg.exporters.ImageExporter(self.left_plot.scene())
        exporter.parameters()['width'] = 2500
        exporter.export(full_export_path)

    def cleanup(self):
        self.left_plot.clear()
        self.right_plot.clear()