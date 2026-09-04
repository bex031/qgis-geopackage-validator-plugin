# -*- coding: utf-8 -*-
"""
Batch TIF Validator Dialog
"""

import os
from pathlib import Path
from datetime import datetime
import xml.etree.ElementTree as ET
from xml.dom import minidom

from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QFileDialog, QTreeView, QProgressBar, QMessageBox, QGroupBox
)
from qgis.PyQt.QtCore import Qt, QThread, pyqtSignal

from ..ui.tif_result_tree_model import TifResultTreeModel
from ..ui.batch_tif_validation_worker import BatchTifValidationWorker


class BatchTifValidatorDialog(QDialog):
    """Dialog for batch TIF file validation."""
    
    closed = pyqtSignal()

    def __init__(self, iface, engine):
        """Initialize the dialog.
        
        :param iface: QGIS interface
        :param engine: TIF validator engine
        """
        super().__init__(iface.mainWindow())
        self.iface = iface
        self.engine = engine
        self.worker = None
        self.worker_thread = None
        
        self.setWindowTitle("MBT TIF 검사도구(폴더)")
        self.setGeometry(100, 100, 1200, 800)
        
        self.init_ui()
        self.current_folder = None
        self.summary = None

    def init_ui(self):
        """Set up the user interface."""
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
        self.tree_model = TifResultTreeModel()
        self.results_tree = QTreeView()
        self.results_tree.setModel(self.tree_model)
        self.results_tree.setColumnWidth(0, 800)
        results_layout.addWidget(self.results_tree)
        results_group.setLayout(results_layout)
        layout.addWidget(results_group)
        
        # Status bar
        status_layout = QHBoxLayout()
        self.status_label = QLabel("Ready")
        status_layout.addWidget(self.status_label)
        self.export_btn = QPushButton("Export Results (XML)")
        self.export_btn.clicked.connect(self.export_results)
        self.export_btn.setEnabled(False)
        status_layout.addWidget(self.export_btn)
        layout.addLayout(status_layout)
        
        self.setLayout(layout)

    def select_folder(self):
        """Select a folder."""
        folder_path = QFileDialog.getExistingDirectory(
            self,
            "Select Folder containing TIF Files"
        )
        
        if folder_path:
            self.current_folder = folder_path
            self.folder_label.setText(Path(folder_path).name)
            self.validate_btn.setEnabled(True)
            self.tree_model.removeRows(0, self.tree_model.rowCount())
            self.progress_bar.setValue(0)
            self.export_btn.setEnabled(False)

    def run_validation(self):
        """Run the batch validation process."""
        self.validate_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.status_label.setText("Scanning folder...")
        self.tree_model.removeRows(0, self.tree_model.rowCount())
        self.summary = None
        
        # Clean up previous worker thread if exists
        if self.worker_thread is not None:
            self.worker_thread.quit()
            self.worker_thread.wait()
        
        # Create and run worker thread
        self.worker = BatchTifValidationWorker(self.current_folder)
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
        :param results: Validation results dictionary
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
        
        # Store summary for export
        self.summary = summary
        
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
        self.tree_model.removeRows(0, self.tree_model.rowCount())
        
        # Add root validation run node
        start_time = summary['start_time']
        end_time = summary['end_time']
        root_item = self.tree_model.add_validation_run(start_time, end_time)
        
        # Process each file's results
        for tif_path, file_data in summary['results'].items():
            filename = file_data['filename']
            
            # Check if there was an error loading the file
            if 'error' in file_data and file_data['error']:
                file_item = self.tree_model.add_file(
                    root_item, filename, tif_path, 0, 0, 1
                )
                self.tree_model.add_error(file_item, file_data['error'])
                continue
            
            # Count results
            checks = file_data.get('checks', [])
            passed = sum(1 for c in checks if c['status'] == 'PASS')
            failed = sum(1 for c in checks if c['status'] == 'FAIL')
            errors = sum(1 for c in checks if c['status'] == 'ERROR')
            
            # Add file node (dataset)
            file_item = self.tree_model.add_file(
                root_item, filename, tif_path, passed, failed, errors
            )
            
            # Add checks with issues
            for check in checks:
                status = check['status']
                
                # Show all checks for TIF validation
                check_item = self.tree_model.add_check(
                    file_item,
                    check['checkID'],
                    status,
                    check['description']
                )
                
                # Add issues if FAIL
                if status == 'FAIL' and check.get('issues'):
                    issues_group = self.tree_model.add_issues_group(
                        check_item,
                        len(check['issues']),
                        ", ".join([str(issue) for issue in check['issues']])
                    )
                
                # Add error if ERROR
                elif status == 'ERROR' and check.get('error'):
                    self.tree_model.add_error(check_item, check['error'])
        
        # Expand root node
        root_index = self.tree_model.indexFromItem(root_item)
        self.results_tree.expand(root_index)

    def export_results(self):
        """Export validation results to XML file."""
        if self.summary is None or self.tree_model.rowCount() == 0:
            QMessageBox.warning(self, "No Results", "No results to export")
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Batch Results",
            "",
            "XML Files (*.xml)"
        )
        
        if file_path:
            try:
                self.write_xml_export(file_path, self.summary)
                
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

    def write_xml_export(self, file_path, summary):
        """Write validation results to XML file.
        
        :param file_path: Path to output XML file
        :param summary: Validation summary dictionary
        """
        # Create root element
        validation_elem = ET.Element('Validation')
        validation_elem.set('start', summary['start_time'])
        validation_elem.set('end', summary['end_time'])
        
        # Create Files element
        files_elem = ET.SubElement(validation_elem, 'Files')
        
        # Process each file
        for tif_path, file_data in summary['results'].items():
            filename = file_data['filename']
            
            # Check if there was an error
            if 'error' in file_data and file_data['error']:
                file_elem = ET.SubElement(files_elem, 'File')
                file_elem.set('Name', filename)
                
                # Add error
                error_elem = ET.SubElement(file_elem, 'Error')
                error_elem.text = file_data['error']
                ET.SubElement(file_elem, 'Total').text = '0'
                ET.SubElement(file_elem, 'Passed').text = '0'
                ET.SubElement(file_elem, 'Failed').text = '0'
                ET.SubElement(file_elem, 'Errors').text = '1'
            else:
                checks = file_data.get('checks', [])
                passed = sum(1 for c in checks if c['status'] == 'PASS')
                failed = sum(1 for c in checks if c['status'] == 'FAIL')
                errors = sum(1 for c in checks if c['status'] == 'ERROR')
                total = len(checks)
                
                file_elem = ET.SubElement(files_elem, 'File')
                file_elem.set('Name', filename)
                
                # Add Summary
                ET.SubElement(file_elem, 'Total').text = str(total)
                ET.SubElement(file_elem, 'Passed').text = str(passed)
                ET.SubElement(file_elem, 'Failed').text = str(failed)
                ET.SubElement(file_elem, 'Errors').text = str(errors)
                
                # Add Checks
                checks_elem = ET.SubElement(file_elem, 'Checks')
                
                for check in checks:
                    check_elem = ET.SubElement(checks_elem, 'Check')
                    check_elem.set('Id', check['checkID'])
                    check_elem.set('Description', check['description'])
                    check_elem.set('Status', check['status'])
                    check_elem.set('Level', check.get('level', ''))
                    
                    # Add issues if FAIL
                    if check['status'] == 'FAIL' and check.get('issues'):
                        issues_elem = ET.SubElement(check_elem, 'Issues')
                        issues_elem.set('Count', str(len(check['issues'])))
                        
                        for idx, issue in enumerate(check['issues']):
                            issue_elem = ET.SubElement(issues_elem, 'Issue')
                            issue_elem.set('Number', str(idx + 1))
                            issue_elem.text = str(issue)
                    
                    # Add error if ERROR
                    elif check['status'] == 'ERROR' and check.get('error'):
                        error_elem = ET.SubElement(check_elem, 'Error')
                        error_elem.text = check['error']
        
        # Pretty print XML
        xml_str = minidom.parseString(ET.tostring(validation_elem)).toprettyxml(indent="  ")
        
        # Remove XML declaration and extra blank lines
        xml_lines = xml_str.split('\n')[1:]  # Skip XML declaration
        xml_str = '\n'.join([line for line in xml_lines if line.strip()])
        
        # Write to file
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(xml_str)

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
