import os
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QMainWindow, QFileDialog, QMessageBox, QGridLayout
from RaspPiReader import pool
from .plotPreviewForm import PlotPreviewForm
import pyqtgraph as pg
import logging
import tempfile
from datetime import datetime

logger = logging.getLogger(__name__)

class PlotPreviewFormHandler(QMainWindow):
    def __init__(self) -> object:
        super(PlotPreviewFormHandler, self).__init__()
        
        # Setup the UI form
        self.form_obj = PlotPreviewForm()
        self.form_obj.setupUi(self)
        
        # Connect button signals to their respective slots
        self.set_connections()
        
        # Get the PlotGridLayout directly from self (the QMainWindow), not from form_obj
        # The PlotGridLayout is created and attached to the parent (self) by setupUi
        self.plot_layout = self.PlotGridLayout if hasattr(self, 'PlotGridLayout') else None
        
        # If the layout wasn't found, create a new one
        if self.plot_layout is None:
            logger.warning("PlotGridLayout not found, creating a new QGridLayout")
            self.plot_layout = QGridLayout()
            if hasattr(self, 'frame'):
                self.frame.setLayout(self.plot_layout)
            else:
                logger.error("No frame widget found to set the new layout")
                # Try to find the frame using findChild as a fallback
                frame = self.findChild(QGridLayout, "frame")
                if frame:
                    frame.setLayout(self.plot_layout)
        
        self.plot = None
        self.showMaximized()
        logger.info("PlotPreviewFormHandler initialized")

    def set_connections(self):
        # Connect buttons to their handlers
        # These buttons are attributes of self (QMainWindow), not form_obj
        if hasattr(self, 'savePushButton'):
            self.savePushButton.clicked.connect(self.save_and_close)
        if hasattr(self, 'saveAsPushButton'):
            self.saveAsPushButton.clicked.connect(self.save_as_and_close)
        if hasattr(self, 'cancelPushButton'):
            self.cancelPushButton.clicked.connect(self.close)
        
        logger.info("PlotPreviewFormHandler connections set")

    def close(self):
        super().close()

    def save_and_close(self, file_full_path=None):
        try:
            if not file_full_path:
                # Get cycle form from pool - handle the case when it's None
                cycle_form = pool.get('cycle_start_form')
                if cycle_form is None or not hasattr(cycle_form, 'folder_path'):
                    # Use fallback path if cycle_form is None or missing attributes
                    reports_dir = os.path.join(os.getcwd(), "reports")
                    os.makedirs(reports_dir, exist_ok=True)
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    file_full_path = os.path.join(reports_dir, f"plot_{timestamp}.png")
                else:
                    file_full_path = os.path.join(cycle_form.folder_path, cycle_form.file_name + '.png')
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(file_full_path), exist_ok=True)
            
            # Save the plot
            if self.plot is None:
                logger.error("No plot to save")
                QMessageBox.warning(self, "Save Error", "No plot to save")
                return
                
            if hasattr(self.plot, 'export_plot'):
                success = self.plot.export_plot(file_full_path)
            else:
                # Fallback if export_plot doesn't exist
                if hasattr(self.plot, 'left_plot'):
                    exporter = pg.exporters.ImageExporter(self.plot.left_plot.plotItem)
                    exporter.export(file_full_path)
                    success = True
                elif hasattr(self.plot, 'plot_widget'):
                    exporter = pg.exporters.ImageExporter(self.plot.plot_widget.plotItem)
                    exporter.export(file_full_path)
                    success = True
                else:
                    logger.error("Plot has no left_plot or plot_widget attribute")
                    QMessageBox.warning(self, "Save Error", "Plot object structure not as expected")
                    return
            
            if success:
                logger.info(f"Plot saved to {file_full_path}")
                # Generate report only if main_form exists and has the generate_html_report method
                main_form = pool.get("main_form")
                if main_form and hasattr(main_form, 'generate_html_report'):
                    main_form.generate_html_report(image_path=file_full_path)
                    
                    # Trigger sync only if the action exists
                    if hasattr(main_form, 'actionSync_GDrive') and hasattr(main_form.actionSync_GDrive, 'triggered'):
                        main_form.actionSync_GDrive.triggered.emit()
            else:
                QMessageBox.warning(self, "Save Error", "Failed to save the plot image.")
                
        except Exception as e:
            logger.error(f"Error saving plot: {e}")
            QMessageBox.critical(self, "Error", f"Failed to save plot: {str(e)}")
        
        self.close()

    def save_as_and_close(self):
        try:
            # Determine initial file path
            cycle_form = pool.get('cycle_start_form')
            if cycle_form and hasattr(cycle_form, 'folder_path') and hasattr(cycle_form, 'file_name'):
                file_full_path = os.path.join(cycle_form.folder_path, cycle_form.file_name + '.png')
            else:
                # Use fallback path if cycle_form is None or missing attributes
                reports_dir = os.path.join(os.getcwd(), "reports")
                os.makedirs(reports_dir, exist_ok=True)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                file_full_path = os.path.join(reports_dir, f"plot_{timestamp}.png")
            
            # Show save dialog
            new_file_name, _ = QFileDialog.getSaveFileName(
                self, "Save Plot Image", file_full_path, "Images (*.png)"
            )
            
            if new_file_name:
                self.save_and_close(file_full_path=new_file_name)
            else:
                # User canceled the dialog
                pass
                
        except Exception as e:
            logger.error(f"Error in save_as_and_close: {e}")
            QMessageBox.critical(self, "Error", f"Failed to save plot: {str(e)}")

    def show(self):
        super().show()

    def initiate_plot(self, headers):
        try:
            # Ensure we have a valid plot_layout
            if self.plot_layout is None:
                logger.error("No valid plot_layout found")
                QMessageBox.critical(self, "Plot Error", "No layout available for the plot")
                return
                
            mf = pool.get('main_form')
            if mf and hasattr(mf, 'create_plot'):
                logger.info("Getting plot from main form's create_plot method")
                self.plot = mf.create_plot(plot_layout=self.plot_layout)
                
                # Set fonts for axes - check if left_plot exists
                if self.plot and hasattr(self.plot, 'left_plot') and self.plot.left_plot:
                    logger.info("Setting font and labels for plot")
                    font = QFont()
                    font.setPixelSize(20)
                    font.setBold(True)
                    self.plot.left_plot.getAxis("bottom").setTickFont(font)
                    self.plot.left_plot.getAxis("left").setTickFont(font)
                    self.plot.left_plot.getAxis("right").setTickFont(font)
                    
                    # Set axis labels from headers list
                    if headers and len(headers) >= 3:
                        self.plot.left_plot.setLabel('bottom', headers[0], **{'font-size': '15pt'})
                        self.plot.left_plot.setLabel('left', headers[1], **{'font-size': '15pt'})
                        self.plot.left_plot.setLabel('right', headers[2], **{'font-size': '15pt'})
                    
                    # Update legend label style if legend exists
                    if hasattr(self.plot, 'legend') and self.plot.legend:
                        legendLabelStyle = {'size': '12pt', 'bold': True}
                        for item in self.plot.legend.items:
                            for single_item in item:
                                if isinstance(single_item, pg.graphicsItems.LabelItem.LabelItem):
                                    single_item.setText(single_item.text, **legendLabelStyle)
                
                # Update the plot
                if self.plot and hasattr(self.plot, 'update_plot'):
                    logger.info("Updating plot")
                    self.plot.update_plot()
                else:
                    logger.warning("Plot doesn't have update_plot method or plot is None")
            else:
                logger.error("Main form not found or doesn't have create_plot method")
                QMessageBox.warning(self, "Plot Error", "Could not initialize plot. Main form not found.")
                
        except Exception as e:
            logger.error(f"Error initializing plot: {e}")
            QMessageBox.critical(self, "Plot Error", f"Failed to initialize plot: {str(e)}")