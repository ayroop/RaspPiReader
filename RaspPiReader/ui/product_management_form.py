import csv
import os
from PyQt5 import QtWidgets
from PyQt5.QtWidgets import QMessageBox, QFileDialog
from RaspPiReader.libs.database import Database
from RaspPiReader.libs.models import Product
from RaspPiReader import pool  # current user stored in pool (e.g. pool.config('current_user'))

class ProductManagementForm(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super(ProductManagementForm, self).__init__(parent)
        self.setWindowTitle("Product Management")
        self.resize(600, 400)
        self.db = Database("sqlite:///local_database.db")
        self.setupUI()
        self.load_products()

    def setupUI(self):
        layout = QtWidgets.QVBoxLayout(self)

        # Top layout: search and import buttons
        top_layout = QtWidgets.QHBoxLayout()
        self.searchLineEdit = QtWidgets.QLineEdit(self)
        self.searchLineEdit.setPlaceholderText("Search by name, serial number or user")
        self.searchLineEdit.textChanged.connect(self.filter_products)
        top_layout.addWidget(self.searchLineEdit)
        self.importButton = QtWidgets.QPushButton("Import CSV", self)
        self.importButton.clicked.connect(self.import_csv)
        top_layout.addWidget(self.importButton)
        layout.addLayout(top_layout)

        # Table to display products (4 columns now)
        self.table = QtWidgets.QTableWidget(self)
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["ID", "Name", "Serial Number", "Added By"])
        layout.addWidget(self.table)

        # Bottom layout: Add, Edit, Remove buttons
        button_layout = QtWidgets.QHBoxLayout()
        self.addButton = QtWidgets.QPushButton("Add Product", self)
        self.addButton.clicked.connect(self.add_product)
        button_layout.addWidget(self.addButton)
        self.editButton = QtWidgets.QPushButton("Edit Product", self)
        self.editButton.clicked.connect(self.edit_product)
        button_layout.addWidget(self.editButton)
        self.removeButton = QtWidgets.QPushButton("Remove Product", self)
        self.removeButton.clicked.connect(self.remove_product)
        button_layout.addWidget(self.removeButton)
        layout.addLayout(button_layout)

    def load_products(self):
        products = self.db.session.query(Product).all()
        self.all_products = products  # Store for filtering
        self.display_products(products)

    def display_products(self, products):
        self.table.setRowCount(len(products))
        for row, prod in enumerate(products):
            self.table.setItem(row, 0, QtWidgets.QTableWidgetItem(str(prod.id)))
            self.table.setItem(row, 1, QtWidgets.QTableWidgetItem(prod.name))
            self.table.setItem(row, 2, QtWidgets.QTableWidgetItem(prod.serial_number))
            self.table.setItem(row, 3, QtWidgets.QTableWidgetItem(prod.added_by))
        self.table.resizeColumnsToContents()

    def filter_products(self):
        filter_text = self.searchLineEdit.text().strip().lower()
        if filter_text:
            filtered = [p for p in self.all_products 
                        if filter_text in p.name.lower() 
                        or filter_text in p.serial_number.lower() 
                        or filter_text in p.added_by.lower()]
        else:
            filtered = self.all_products
        self.display_products(filtered)

    def add_product(self):
        dlg = ProductEditDialog(self)
        if dlg.exec_() == QtWidgets.QDialog.Accepted:
            data = dlg.get_data()
            if len(data['serial_number']) > 250:
                QMessageBox.warning(self, "Error", "Serial number cannot exceed 250 characters")
                return
            # Retrieve current user username from the pool (set at login)
            current_user = pool.get('current_user') or "Unknown"
            new_prod = Product(name=data['name'], serial_number=data['serial_number'], added_by=current_user)
            self.db.session.add(new_prod)
            self.db.session.commit()
            self.load_products()

    def edit_product(self):
        current = self.table.currentRow()
        if current < 0:
            QMessageBox.warning(self, "Warning", "Select a product to edit")
            return
        product_id = int(self.table.item(current, 0).text())
        prod = self.db.session.query(Product).get(product_id)
        dlg = ProductEditDialog(self, prod)
        if dlg.exec_() == QtWidgets.QDialog.Accepted:
            data = dlg.get_data()
            if len(data['serial_number']) > 250:
                QMessageBox.warning(self, "Error", "Serial number cannot exceed 250 characters")
                return
            prod.name = data['name']
            prod.serial_number = data['serial_number']
            self.db.session.commit()
            self.load_products()

    def remove_product(self):
        current = self.table.currentRow()
        if current < 0:
            QMessageBox.warning(self, "Warning", "Select a product to remove")
            return
        product_id = int(self.table.item(current, 0).text())
        prod = self.db.session.query(Product).get(product_id)
        reply = QMessageBox.question(self, "Confirm", f"Remove product {prod.name}?",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.db.session.delete(prod)
            self.db.session.commit()
            self.load_products()

    def import_csv(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Import CSV", "", "CSV Files (*.csv)")
        if file_path:
            try:
                with open(file_path, newline='', encoding='utf-8') as csvfile:
                    reader = csv.DictReader(csvfile)
                    for row in reader:
                        name = row.get('name')
                        serial = row.get('serial_number')
                        if name and serial:
                            if len(serial) > 250:
                                continue  # Skip if exceeding limit
                            # Optional: if CSV also includes "added_by", use it; otherwise use current user
                            added_by = row.get('added_by') or (pool.get('current_user') or "Unknown")
                            existing = self.db.session.query(Product).filter_by(serial_number=serial).first()
                            if not existing:
                                new_prod = Product(name=name, serial_number=serial, added_by=added_by)
                                self.db.session.add(new_prod)
                    self.db.session.commit()
                    self.load_products()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to import CSV: {e}")

class ProductEditDialog(QtWidgets.QDialog):
    def __init__(self, parent=None, product=None):
        super(ProductEditDialog, self).__init__(parent)
        self.setWindowTitle("Edit Product" if product else "Add Product")
        self.product = product
        self.setupUI()
        if self.product:
            self.load_data()

    def setupUI(self):
        layout = QtWidgets.QFormLayout(self)
        self.nameLineEdit = QtWidgets.QLineEdit(self)
        self.serialLineEdit = QtWidgets.QLineEdit(self)
        layout.addRow("Name:", self.nameLineEdit)
        layout.addRow("Serial Number:", self.serialLineEdit)
        buttonBox = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel, self)
        buttonBox.accepted.connect(self.accept)
        buttonBox.rejected.connect(self.reject)
        layout.addWidget(buttonBox)

    def load_data(self):
        self.nameLineEdit.setText(self.product.name)
        self.serialLineEdit.setText(self.product.serial_number)

    def get_data(self):
        return {
            'name': self.nameLineEdit.text().strip(),
            'serial_number': self.serialLineEdit.text().strip()
        }