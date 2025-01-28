import os

from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QMainWindow, QFileDialog

from RaspPiReader import pool
from .plotPreviewForm import PlotPreviewForm
import pyqtgraph as pg

class PlotPreviewFormHandler(QMainWindow):
    def __init__(self) -> object:
        super(PlotPreviewFormHandler, self).__init__()
        self.form_obj = PlotPreviewForm()
        self.form_obj.setupUi(self)
        self.set_connections()
        self.plot_layout = self.PlotGridLayout
        self.plot = None
        # self.setWindowModality(Qt.ApplicationModal)
        self.showMaximized()

    def set_connections(self):
        self.savePushButton.clicked.connect(self.save_and_close)
        self.saveAsPushButton.clicked.connect(self.save_as_and_close)
        self.cancelPushButton.clicked.connect(self.close)

    def close(self):
        super().close()

    def save_and_close(self, file_full_path=None):
        try:
            if not file_full_path:
                cycle_form = pool.get('cycle_start_form')
                file_full_path = os.path.join(cycle_form.folder_path, cycle_form.file_name + '.png')
            self.plot.export_plot(file_full_path)
            pool.get("main_form").generate_html_report(image_path=file_full_path)
            pool.get("main_form").actionSync_GDrive.triggered.emit()
        except Exception as e:
            print(e)
        self.close()

    def save_as_and_close(self):
        cycle_form = pool.get('cycle_start_form')
        file_full_path = os.path.join(cycle_form.folder_path, cycle_form.file_name + '.png')
        new_file_name, _ = QFileDialog.getSaveFileName(self, "Save audio file", file_full_path, "Images (*.png)")
        self.save_and_close(path=new_file_name)


    def show(self):
        super().show()

    def initiate_plot(self, headers):
        mf = pool.get('main_form')
        self.plot = mf.create_plot(plot_layout=self.plot_layout)

        font = QFont()
        font.setPixelSize(20)
        font.setBold(True)
        self.plot.left_plot.getAxis("bottom").setTickFont(font)
        self.plot.left_plot.getAxis("left").setTickFont(font)
        self.plot.left_plot.getAxis("right").setTickFont(font)

        self.plot.left_plot.setLabel('bottom', headers[0], **{'font-size': '15pt'})
        self.plot.left_plot.setLabel('left', headers[1], **{'font-size': '15pt'})
        self.plot.left_plot.setLabel('right', headers[2], **{'font-size': '15pt'})

        legendLabelStyle = {'size': '12pt', 'bold': True}
        for item in self.plot.legend.items:
            for single_item in item:
                if isinstance(single_item, pg.graphicsItems.LabelItem.LabelItem):
                    single_item.setText(single_item.text, **legendLabelStyle)
        self.plot.update_plot()





