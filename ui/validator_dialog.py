# -*- coding: utf-8 -*-
"""
Main dialog for GeoPackage Validator
"""

import os
from pathlib import Path
from datetime import datetime

from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
    QFileDialog, QTextEdit, QMessageBox, QProgressBar, QTableWidget,
    QTableWidgetItem, QHeaderView, QGroupBox, QComboBox
)
from qgis.PyQt.QtCore import Qt, QTimer, QThread, pyqtSignal
from qgis.PyQt.QtGui import QColor, QFont

from .validator_worker import ValidatorWorker


class ValidatorDialog(QDialog):
    """Main dialog for the GeoPackage Validator plugin."""
    
    # Signal emitted when dialog is closed
    closed = pyqtSignal()

    def __init__(self, iface, engine, parent=None):
        """Initialize the validator dialog.
        
        :param iface: QGIS interface
        :param engine: Validator engine
        :param parent: Parent widget
        """
        super().__init__(parent)
        self.iface = iface
        self.engine = engine
        
        self.gpkg_path = None
        self.rule_path = None
        self.worker_thread = None
        self.worker = None
        
        self.setWindowTitle("해양기본도 검사도구")
        self.setGeometry(100, 100, 1000, 700)
        
        self.init_ui()

    def init_ui(self):
        """Initialize the user interface."""
        layout = QVBoxLayout()
        
        # File selection section
        file_layout = QHBoxLayout()
        
        # GeoPackage file selection
        file_layout.addWidget(QLabel("GeoPackage File:"))
        self.gpkg_label = QLabel("(not selected)")
        file_layout.addWidget(self.gpkg_label)
        self.gpkg_btn = QPushButton("Browse...")
        self.gpkg_btn.clicked.connect(self.select_gpkg)
        file_layout.addWidget(self.gpkg_btn)
        
        layout.addLayout(file_layout)
        
        # Rule file selection
        rule_layout = QHBoxLayout()
        rule_layout.addWidget(QLabel("Rule File (YAML):"))
        self.rule_label = QLabel("(not selected)")
        rule_layout.addWidget(self.rule_label)
        self.rule_btn = QPushButton("Browse...")
        self.rule_btn.clicked.connect(self.select_rule)
        rule_layout.addWidget(self.rule_btn)
        
        layout.addLayout(rule_layout)
        
        # Validate button
        self.validate_btn = QPushButton("Run Validation")
        self.validate_btn.clicked.connect(self.run_validation)
        self.validate_btn.setEnabled(False)
        layout.addWidget(self.validate_btn)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        # Results table
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(4)
        self.results_table.setHorizontalHeaderLabels(
            ["Check ID", "Description", "Status", "Issues"]
        )
        self.results_table.horizontalHeader().setStretchLastSection(True)
        self.results_table.setColumnWidth(0, 150)
        self.results_table.setColumnWidth(1, 300)
        self.results_table.setColumnWidth(2, 100)
        layout.addWidget(self.results_table)
        
        # Log/Details text
        log_group = QGroupBox("Details (Double-click table row to view)")
        log_layout = QVBoxLayout()
        self.details_text = QTextEdit()
        self.details_text.setReadOnly(True)
        self.details_text.setMaximumHeight(200)
        log_layout.addWidget(self.details_text)
        log_group.setLayout(log_layout)
        layout.addWidget(log_group)
        
        # Status bar
        status_layout = QHBoxLayout()
        self.status_label = QLabel("Ready")
        status_layout.addWidget(self.status_label)
        self.export_btn = QPushButton("Export Results")
        self.export_btn.clicked.connect(self.export_results)
        self.export_btn.setEnabled(False)
        status_layout.addWidget(self.export_btn)
        layout.addLayout(status_layout)
        
        self.setLayout(layout)

    def select_gpkg(self):
        """Select a GeoPackage file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select GeoPackage File",
            "",
            "GeoPackage Files (*.gpkg);;All Files (*)"
        )
        
        if file_path:
            self.gpkg_path = file_path
            self.gpkg_label.setText(Path(file_path).name)
            self.update_validate_button()

    def select_rule(self):
        """Select a rule YAML file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Rule File",
            "",
            "YAML Files (*.yaml *.yml);;All Files (*)"
        )
        
        if file_path:
            self.rule_path = file_path
            self.rule_label.setText(Path(file_path).name)
            self.update_validate_button()

    def update_validate_button(self):
        """Update the validate button state."""
        self.validate_btn.setEnabled(
            self.gpkg_path is not None and self.rule_path is not None
        )

    def run_validation(self):
        """Run the validation process."""
        self.validate_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.status_label.setText("Running validation...")
        self.details_text.clear()
        self.results_table.setRowCount(0)
        
        # Clean up previous worker thread if exists
        if self.worker_thread is not None:
            self.worker_thread.quit()
            self.worker_thread.wait()
        
        # Create and run worker thread
        self.worker = ValidatorWorker(
            self.engine, self.gpkg_path, self.rule_path
        )
        self.worker_thread = QThread()
        self.worker.moveToThread(self.worker_thread)
        
        self.worker.progress.connect(self.on_progress)
        self.worker.finished.connect(self.on_validation_finished)
        self.worker.error.connect(self.on_validation_error)
        
        self.worker_thread.started.connect(self.worker.run)
        self.worker_thread.start()

    def on_progress(self, value):
        """Update progress bar.
        
        :param value: Progress value (0-100)
        """
        self.progress_bar.setValue(value)

    def on_validation_finished(self, results):
        """Handle validation completion.
        
        :param results: List of validation results
        """
        self.progress_bar.setVisible(False)
        self.progress_bar.setValue(100)
        self.validate_btn.setEnabled(True)
        self.export_btn.setEnabled(True)
        
        self.display_results(results)
        
        # Summary
        pass_count = sum(1 for r in results if r['status'] == 'PASS')
        fail_count = sum(1 for r in results if r['status'] == 'FAIL')
        error_count = sum(1 for r in results if r['status'] == 'ERROR')
        
        summary = f"Validation completed: {pass_count} passed, {fail_count} failed, {error_count} errors"
        self.status_label.setText(summary)
        self.details_text.append(f"\n{summary}")
        
        # Clean up worker thread
        if self.worker_thread is not None:
            self.worker_thread.quit()
            self.worker_thread.wait()
            self.worker_thread = None
            self.worker = None

    def on_validation_error(self, error_msg):
        """Handle validation error.
        
        :param error_msg: Error message
        """
        self.progress_bar.setVisible(False)
        self.validate_btn.setEnabled(True)
        self.status_label.setText("Validation failed")
        
        QMessageBox.critical(
            self,
            "Validation Error",
            f"An error occurred:\n\n{error_msg}"
        )
        
        # Clean up worker thread
        if self.worker_thread is not None:
            self.worker_thread.quit()
            self.worker_thread.wait()
            self.worker_thread = None
            self.worker = None

    def display_results(self, results):
        """Display validation results in the table.
        
        :param results: List of validation results
        """
        self.results_table.setRowCount(len(results))
        
        for row, result in enumerate(results):
            # Check ID
            check_id_item = QTableWidgetItem(result['checkID'])
            self.results_table.setItem(row, 0, check_id_item)
            
            # Description
            desc_item = QTableWidgetItem(result['description'])
            self.results_table.setItem(row, 1, desc_item)
            
            # Status
            status_item = QTableWidgetItem(result['status'])
            if result['status'] == 'PASS':
                status_item.setBackground(QColor(0, 200, 0))
            elif result['status'] == 'FAIL':
                status_item.setBackground(QColor(255, 100, 0))
            else:  # ERROR
                status_item.setBackground(QColor(255, 0, 0))
            status_item.setForeground(QColor(255, 255, 255))
            self.results_table.setItem(row, 2, status_item)
            
            # Issues count
            if result['status'] == 'FAIL':
                issues_count = len(result['issues'])
                issues_item = QTableWidgetItem(f"{issues_count} issue(s)")
                issues_item.setBackground(QColor(255, 200, 100))
            else:
                issues_item = QTableWidgetItem("-")
            self.results_table.setItem(row, 3, issues_item)
            
            # Add details to text area on double-click
            self.results_table.itemDoubleClicked.connect(
                lambda item: self.show_issue_details(item)
            )

    def show_issue_details(self, item):
        """Show detailed information about an issue.
        
        :param item: Table widget item
        """
        row = self.results_table.row(item)
        results = self.engine.get_results()
        
        if row < len(results):
            result = results[row]
            details = f"{'='*80}\n"
            details += f"Check ID: {result['checkID']}\n"
            details += f"Description: {result['description']}\n"
            details += f"Status: {result['status']}\n"
            details += f"{'='*80}\n"
            
            # Add Details from YAML if available
            if result.get('details'):
                details += f"\nRule Details (from YAML):\n"
                details += f"{result['details']}\n"
                details += f"\n{'-'*80}\n"
            
            if result['error']:
                details += f"\nError: {result['error']}\n"
            
            if result['issues']:
                details += f"\nIssues found: {len(result['issues'])}\n"
                details += f"{'-'*80}\n"
                for idx, issue in enumerate(result['issues'], 1):
                    details += f"Issue #{idx}: {issue}\n"
            else:
                details += f"\nNo issues found.\n"
            
            self.details_text.setText(details)

    def export_results(self):
        """Export validation results to a file."""
        if not self.engine.get_results():
            QMessageBox.warning(self, "No Results", "No results to export")
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Results",
            "",
            "CSV Files (*.csv);;Text Files (*.txt)"
        )
        
        if file_path:
            try:
                results = self.engine.get_results()
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(f"Validation Report - {datetime.now()}\n")
                    f.write(f"GeoPackage: {self.gpkg_path}\n")
                    f.write(f"Rules: {self.rule_path}\n")
                    f.write("=" * 80 + "\n\n")
                    
                    for result in results:
                        f.write(f"Check ID: {result['checkID']}\n")
                        f.write(f"Description: {result['description']}\n")
                        f.write(f"Status: {result['status']}\n")
                        
                        # Add Details from YAML if available
                        if result.get('details'):
                            f.write(f"\nRule Details (from YAML):\n")
                            f.write(f"{result['details']}\n")
                        
                        if result['error']:
                            f.write(f"Error: {result['error']}\n")
                        
                        if result['issues']:
                            f.write(f"\nIssues: {len(result['issues'])}\n")
                            for idx, issue in enumerate(result['issues'], 1):
                                f.write(f"  #{idx}: {issue}\n")
                        
                        f.write("-" * 80 + "\n\n")
                
                QMessageBox.information(
                    self,
                    "Export Successful",
                    f"Results exported to:\n{file_path}"
                )
                
            except Exception as e:
                QMessageBox.critical(
                    self,
                    "Export Error",
                    f"Failed to export results:\n{str(e)}"
                )

    def closeEvent(self, event):
        """Handle dialog close event.
        
        :param event: Close event
        """
        # Clean up worker thread if still running
        if self.worker_thread is not None:
            self.worker_thread.quit()
            self.worker_thread.wait()
            self.worker_thread = None
            self.worker = None
        
        # Emit closed signal
        self.closed.emit()
        
        # Accept the close event
        event.accept()
