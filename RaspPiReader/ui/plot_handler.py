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
        self.active_channels = active_channels
        self.create_plot()

    def create_plot(self):
        self.left_plot = pg.PlotWidget(background="white", title="")
        self.parent_layout.addWidget(self.left_plot)
        self.left_plot.showAxis('right')
        self.right_plot = pg.ViewBox()
        self.left_plot.scene().addItem(self.right_plot)
        self.left_plot.getAxis('right').linkToView(self.right_plot)
        self.right_plot.setXLink(self.left_plot)
        self.left_plot.getViewBox().sigResized.connect(self.update_views)

        self.right_plot.setDefaultPadding(padding=0.0)
        self.left_plot.setDefaultPadding(padding=0.0)

        # Ensure headers exist and contain at least 3 entries for proper labeling.
        if self.headers and len(self.headers) >= 3:
            self.left_plot.setLabel('bottom', self.headers[0], **{'font-size': '10pt'})
            self.left_plot.setLabel('left', self.headers[1], **{'font-size': '10pt'})
            self.left_plot.setLabel('right', self.headers[2], **{'font-size': '10pt'})
        else:
            # Fallback labels if headers not provided.
            self.left_plot.setLabel('bottom', "Time", **{'font-size': '10pt'})
            self.left_plot.setLabel('left', "Value", **{'font-size': '10pt'})
            self.left_plot.setLabel('right', "", **{'font-size': '10pt'})

        if self.legend_layout is not None:
            self.create_dynamic_legend()
        else:
            self.legend = self.left_plot.addLegend(colCount=2, brush='#f5f5f5', labelTextColor='#242323')

        self.last_data_index = 0
        self.data = pool.get('data_stack')

        self.left_lines = [i for i in self.active_channels if pool.config('axis_direction' + str(i)) == 'L']
        self.right_lines = [i for i in self.active_channels if i not in self.left_lines]

        for i in self.active_channels:
            args = {
                'pen': {'color': pool.config("color" + str(i)), 'width': 2},
                'autoDownsample': True
            }
            # If headers list is provided, use header names for legend
            if self.legend_layout is None and self.headers and len(self.headers) > i + 2:
                args.update(name=self.headers[i + 2])
            if i in self.left_lines:
                curve = self.left_plot.plot([], [], **args)
            else:
                curve = pg.PlotCurveItem([], [], **args)
                self.right_plot.addItem(curve)
                if self.legend_layout is None and hasattr(curve, "name"):
                    self.legend.addItem(curve, curve.name())

            setattr(self, "line" + str(i), curve)

    def update_plot(self):
        n_data = len(self.data[0])
        if n_data > self.last_data_index:
            # Use a default value (0.0) for acc_time if configuration returns None
            acc_time = pool.config('accuarate_data_time', float, 0.0)
            # Check and update plot based on acc_time threshold
            if acc_time > 0:
                acc_index = 0
                # Find the index where the time difference exceeds acc_time
                for i in range(n_data, 0, -1):
                    if (self.data[0][-1] - self.data[0][i - 1]) > acc_time:
                        acc_index = i
                        break
                # Update plot data in two segments with a skip factor for performance
                for i in self.active_channels:
                    curve = getattr(self, "line" + str(i))
                    x_data = self.data[0][0: acc_index: DATA_SKIP_FACTOR] + self.data[0][acc_index:]
                    y_data = self.data[i][0: acc_index: DATA_SKIP_FACTOR] + self.data[i][acc_index:]
                    curve.setData(x_data, y_data)
            else:
                # If acc_time is less than or equal to zero, plot all data
                for i in self.active_channels:
                    getattr(self, "line" + str(i)).setData(self.data[0], self.data[i])

            self.left_plot.setXRange(0, self.data[0][-1])
            self.last_data_index = len(self.data[0]) - 1
            QApplication.processEvents()

    def update_views(self):
        self.right_plot.setGeometry(self.left_plot.getViewBox().sceneBoundingRect())
        self.right_plot.linkedViewChanged(self.left_plot.getViewBox(), self.right_plot.XAxis)

    def create_dynamic_legend(self):
        # Create dynamic legend items linked to check boxes to toggle plot visibility
        func = lambda i: (lambda state: self.show_hide_plot(i, state))
        for i in self.active_channels:
            header_index = i + 2 if self.headers and len(self.headers) > i + 2 else None
            header_text = self.headers[header_index] if header_index is not None else f"Channel {i}"
            check_box, label = self.create_legend_item(header_text, pool.config('color' + str(i)))
            self.legend_layout.addRow(check_box, label)
            check_box.stateChanged.connect(func(i))

    def create_legend_item(self, text, color):
        # Set default color if not provided
        if color is None:
            color = "#000000"  # Default to black
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

    def show_hide_plot(self, index, state):
        if state:
            getattr(self, 'line' + str(index)).show()
        else:
            getattr(self, 'line' + str(index)).hide()

    def export_plot(self, full_export_path):
        exporter = pg.exporters.ImageExporter(self.left_plot.scene())
        exporter.parameters()['width'] = 2500
        exporter.export(full_export_path)
    
    def cleanup(self):
        # Implement the logic to clean up the plot
        self.left_plot.clear()
        self.right_plot.clear()