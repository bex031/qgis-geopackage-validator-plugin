# -*- coding: utf-8 -*-
"""
Batch Validator Dialog - for validating multiple GeoPackage files in a folder
"""

import os
from pathlib import Path
from datetime import datetime

from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
    QFileDialog, QMessageBox, QProgressBar, QTreeView, QGroupBox
)
from qgis.PyQt.QtCore import Qt, QThread, pyqtSignal
from qgis.PyQt.QtGui import QColor, QFont

from .batch_validation_worker import BatchValidationWorker
from .result_tree_model import ResultTreeModel


class BatchValidatorDialog(QDialog):
    """Dialog for batch validation of multiple GeoPackage files."""
    
    # Signal emitted when dialog is closed
    closed = pyqtSignal()

    def __init__(self, iface, engine, parent=None):
        """Initialize the batch validator dialog.
        
        :param iface: QGIS interface
        :param engine: Validator engine
        :param parent: Parent widget
        """
        super().__init__(parent)
        self.iface = iface
        self.engine = engine
        
        self.folder_path = None
        self.rule_path = None
        self.worker_thread = None
        self.worker = None
        
        self.setWindowTitle("GeoPackage Batch Validator")
        self.setGeometry(100, 100, 1200, 800)
        
        self.init_ui()

    def init_ui(self):
        """Initialize the user interface."""
        layout = QVBoxLayout()
        
        # Folder selection section
        folder_layout = QHBoxLayout()
        folder_layout.addWidget(QLabel("Folder:"))
        self.folder_label = QLabel("(not selected)")
        folder_layout.addWidget(self.folder_label)
        self.folder_btn = QPushButton("Browse...")
        self.folder_btn.clicked.connect(self.select_folder)
        folder_layout.addWidget(self.folder_btn)
        layout.addLayout(folder_layout)
        
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
        self.validate_btn = QPushButton("Run Batch Validation")
        self.validate_btn.clicked.connect(self.run_validation)
        self.validate_btn.setEnabled(False)
        layout.addWidget(self.validate_btn)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        # Results tree
        results_group = QGroupBox("Validation Results")
        results_layout = QVBoxLayout()
        self.results_tree = QTreeView()
        self.tree_model = ResultTreeModel()
        self.results_tree.setModel(self.tree_model)
        self.results_tree.setColumnWidth(0, 800)
        results_layout.addWidget(self.results_tree)
        results_group.setLayout(results_layout)
        layout.addWidget(results_group)
        
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

    def select_folder(self):
        """Select a folder."""
        folder_path = QFileDialog.getExistingDirectory(
            self,
            "Select Folder containing GeoPackage Files"
        )
        
        if folder_path:
            self.folder_path = folder_path
            self.folder_label.setText(Path(folder_path).name)
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
            self.folder_path is not None and self.rule_path is not None
        )

    def run_validation(self):
        """Run the batch validation process."""
        self.validate_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.status_label.setText("Scanning folder...")
        self.tree_model.clear()
        
        # Clean up previous worker thread if exists
        if self.worker_thread is not None:
            self.worker_thread.quit()
            self.worker_thread.wait()
        
        # Create and run worker thread
        self.worker = BatchValidationWorker(
            self.engine, self.folder_path, self.rule_path
        )
        self.worker_thread = QThread()
        self.worker.moveToThread(self.worker_thread)
        
        self.worker.progress.connect(self.on_progress)
        self.worker.file_started.connect(self.on_file_started)
        self.worker.file_completed.connect(self.on_file_completed)
        self.worker.finished.connect(self.on_validation_finished)
        self.worker.error.connect(self.on_validation_error)
        
        self.worker_thread.started.connect(self.worker.run)
        self.worker_thread.start()

    def on_progress(self, value):
        """Update progress bar.
        
        :param value: Progress value (0-100)
        """
        self.progress_bar.setValue(value)

    def on_file_started(self, filename):
        """Handle file validation start.
        
        :param filename: Name of the file being validated
        """
        self.status_label.setText(f"Validating: {filename}")

    def on_file_completed(self, filename, results):
        """Handle file validation completion.
        
        :param filename: Name of the completed file
        :param results: List of validation results
        """
        pass  # Tree will be built in on_validation_finished

    def on_validation_finished(self, summary):
        """Handle batch validation completion.
        
        :param summary: Dictionary with validation summary
        """
        self.progress_bar.setVisible(False)
        self.progress_bar.setValue(100)
        self.validate_btn.setEnabled(True)
        self.export_btn.setEnabled(True)
        
        # Build results tree
        self.build_results_tree(summary)
        
        # Update status
        total_files = summary['total_files']
        self.status_label.setText(
            f"Batch validation completed: {total_files} files processed"
        )
        
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
        self.status_label.setText("Batch validation failed")
        
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

    def build_results_tree(self, summary):
        """Build the results tree from validation summary.
        
        :param summary: Dictionary with validation results
        """
        # Clear existing tree
        self.tree_model.clear()
        
        # Add root validation run node
        start_time = summary['start_time']
        end_time = summary['end_time']
        root_item = self.tree_model.add_validation_run(start_time, end_time)
        
        # Process each file's results
        for gpkg_path, file_data in summary['results'].items():
            filename = file_data['filename']
            
            # Check if there was an error loading the file
            if 'error' in file_data:
                dataset_item = self.tree_model.add_dataset(
                    root_item, filename, gpkg_path, 0, 0, 0
                )
                self.tree_model.add_error(dataset_item, file_data['error'])
                continue
            
            # Count results
            results = file_data['results']
            passed = sum(1 for r in results if r['status'] == 'PASS')
            failed = sum(1 for r in results if r['status'] == 'FAIL')
            errors = sum(1 for r in results if r['status'] == 'ERROR')
            
            # Only add dataset node if there are failures or errors
            if failed > 0 or errors > 0:
                dataset_item = self.tree_model.add_dataset(
                    root_item, filename, gpkg_path, passed, failed, errors
                )
                
                # Add checks with issues
                for result in results:
                    status = result['status']
                    
                    # Only show FAIL and ERROR
                    if status == 'FAIL' or status == 'ERROR':
                        check_item = self.tree_model.add_check(
                            dataset_item,
                            result['checkID'],
                            status,
                            result['description'],
                            result.get('details', '')
                        )
                        
                        # Add issues if FAIL
                        if status == 'FAIL' and result['issues']:
                            issues_group = self.tree_model.add_issues_group(
                                check_item,
                                len(result['issues']),
                                result.get('details', '')
                            )
                            
                            for issue in result['issues']:
                                self.tree_model.add_issue_result(issues_group, issue)
                        
                        # Add error if ERROR
                        elif status == 'ERROR' and result['error']:
                            self.tree_model.add_error(check_item, result['error'])
            else:
                # Add only dataset node for passed validations (no details)
                self.tree_model.add_dataset(
                    root_item, filename, gpkg_path, passed, failed, errors
                )
        
        # Expand root node
        root_index = self.tree_model.indexFromItem(root_item)
        self.results_tree.expand(root_index)

    def export_results(self):
        """Export validation results to a file."""
        if self.tree_model.rowCount() == 0:
            QMessageBox.warning(self, "No Results", "No results to export")
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Batch Results",
            "",
            "Text Files (*.txt);;CSV Files (*.csv)"
        )
        
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    self.write_tree_to_file(f, self.tree_model.invisibleRootItem(), "")
                
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

    def write_tree_to_file(self, file, item, indent):
        """Recursively write tree items to file.
        
        :param file: File object
        :param item: Tree item
        :param indent: Current indentation level
        """
        for row in range(item.rowCount()):
            child = item.child(row)
            file.write(f"{indent}{child.text()}\n")
            self.write_tree_to_file(file, child, indent + "  ")

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
