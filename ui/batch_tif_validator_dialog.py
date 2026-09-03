# -*- coding: utf-8 -*-
"""
Batch TIF Validator Dialog
"""

import os
from pathlib import Path
from datetime import datetime
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QFileDialog, QTreeView, QProgressBar, QMessageBox, QWidget,
    QHeaderView
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
        
        self.setWindowTitle("Batch TIF Validator")
        self.setGeometry(100, 100, 900, 700)
        
        self.setup_ui()
        self.current_folder = None

    def setup_ui(self):
        """Set up the user interface."""
        main_layout = QVBoxLayout()
        
        # Folder selection section
        folder_layout = QHBoxLayout()
        folder_label = QLabel("Validation Folder:")
        self.folder_path_label = QLabel("No folder selected")
        self.folder_path_label.setStyleSheet("color: gray; font-style: italic;")
        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self.select_folder)
        
        folder_layout.addWidget(folder_label)
        folder_layout.addWidget(self.folder_path_label)
        folder_layout.addStretch()
        folder_layout.addWidget(browse_btn)
        main_layout.addLayout(folder_layout)
        
        # Progress section
        progress_layout = QHBoxLayout()
        progress_label = QLabel("Progress:")
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        progress_layout.addWidget(progress_label)
        progress_layout.addWidget(self.progress_bar)
        main_layout.addLayout(progress_layout)
        
        # Result tree view
        tree_label = QLabel("Validation Results:")
        main_layout.addWidget(tree_label)
        
        self.tree_model = TifResultTreeModel()
        self.tree_view = QTreeView()
        self.tree_view.setModel(self.tree_model)
        self.tree_view.header().setSectionResizeMode(0, 1)
        main_layout.addWidget(self.tree_view)
        
        # Control buttons
        button_layout = QHBoxLayout()
        
        self.validate_btn = QPushButton("Run Batch Validation")
        self.validate_btn.clicked.connect(self.run_validation)
        self.validate_btn.setEnabled(False)
        
        self.export_btn = QPushButton("Export Results (XML)")
        self.export_btn.clicked.connect(self.export_results)
        self.export_btn.setEnabled(False)
        
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.clicked.connect(self.stop_validation)
        self.stop_btn.setEnabled(False)
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close_dialog)
        
        button_layout.addWidget(self.validate_btn)
        button_layout.addWidget(self.export_btn)
        button_layout.addWidget(self.stop_btn)
        button_layout.addStretch()
        button_layout.addWidget(close_btn)
        main_layout.addLayout(button_layout)
        
        self.setLayout(main_layout)

    def select_folder(self):
        """Open folder selection dialog."""
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Folder with TIF Files",
            ""
        )
        
        if folder:
            self.current_folder = folder
            self.folder_path_label.setText(folder)
            self.folder_path_label.setStyleSheet("color: black; font-style: normal;")
            self.validate_btn.setEnabled(True)
            self.tree_model.removeRows(0, self.tree_model.rowCount())
            self.progress_bar.setValue(0)
            self.export_btn.setEnabled(False)

    def run_validation(self):
        """Run the batch validation."""
        if not self.current_folder:
            QMessageBox.warning(self, "Warning", "Please select a folder first.")
            return
        
        # Clear previous results
        self.tree_model.removeRows(0, self.tree_model.rowCount())
        self.progress_bar.setValue(0)
        self.validate_btn.setEnabled(False)
        self.export_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        
        # Create worker thread
        self.worker_thread = QThread()
        self.worker = BatchTifValidationWorker(self.current_folder)
        self.worker.moveToThread(self.worker_thread)
        
        # Connect signals
        self.worker_thread.started.connect(self.worker.run)
        self.worker.progress.connect(self.on_progress)
        self.worker.file_started.connect(self.on_file_started)
        self.worker.file_completed.connect(self.on_file_completed)
        self.worker.finished.connect(self.on_validation_finished)
        self.worker.error.connect(self.on_validation_error)
        
        # Start thread
        self.worker_thread.start()

    def on_progress(self, value):
        """Update progress bar.
        
        :param value: Progress percentage (0-100)
        """
        self.progress_bar.setValue(value)

    def on_file_started(self, filename):
        """Called when validation of a file starts.
        
        :param filename: Name of the file
        """
        pass  # Can be used to update status

    def on_file_completed(self, filename, results):
        """Called when validation of a file completes.
        
        :param filename: Name of the file
        :param results: Validation results
        """
        if results is None:
            return
        
        # Get or create root item for this validation run
        if self.tree_model.rowCount() == 0:
            start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            root_item = self.tree_model.add_validation_run(start_time, "In Progress")
        else:
            root_item = self.tree_model.item(0)
        
        # Add file item
        tif_path = results.get('tif_path', '')
        status = results.get('status', 'UNKNOWN')
        
        # Count passed/failed/error checks
        passed = 0
        failed = 0
        errors = 0
        
        checks = results.get('checks', [])
        for check in checks:
            check_status = check.get('status', 'UNKNOWN')
            if check_status == 'PASS':
                passed += 1
            elif check_status == 'FAIL':
                failed += 1
            elif check_status == 'ERROR':
                errors += 1
        
        file_item = self.tree_model.add_file(root_item, filename, tif_path, passed, failed, errors)
        
        # Add check items
        for check in checks:
            check_id = check.get('checkID', 'Unknown')
            check_status = check.get('status', 'UNKNOWN')
            description = check.get('description', '')
            issues = check.get('issues', [])
            issue_count = check.get('issue_count', 0)
            
            check_item = self.tree_model.add_check(file_item, check_id, check_status, description)
            
            # Add issues group if there are issues
            if issue_count > 0 and issues:
                # Format issues for display
                issue_details = ", ".join([str(issue) for issue in issues])
                self.tree_model.add_issues_group(check_item, issue_count, issue_details)
        
        # Handle file-level errors
        error_msg = results.get('error')
        if error_msg:
            self.tree_model.add_error(file_item, error_msg)
        
        # Expand tree
        self.tree_view.expandAll()

    def on_validation_finished(self, summary):
        """Called when validation is finished.
        
        :param summary: Summary dictionary with results
        """
        self.stop_btn.setEnabled(False)
        self.validate_btn.setEnabled(True)
        self.export_btn.setEnabled(True)
        
        # Update root item with end time
        if self.tree_model.rowCount() > 0:
            root_item = self.tree_model.item(0)
            end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            root_item.setText(f"Validation : {end_time.split()[0]} - {end_time}")
        
        # Show summary message
        total = summary.get('total_files', 0)
        results = summary.get('results', {})
        
        passed_files = sum(1 for r in results.values() if r.get('status') == 'SUCCESS')
        failed_files = sum(1 for r in results.values() if r.get('status') == 'FAIL')
        error_files = sum(1 for r in results.values() if r.get('status') == 'ERROR')
        
        summary_text = f"Validation completed!\n\n" \
                      f"Total files: {total}\n" \
                      f"Passed: {passed_files}\n" \
                      f"Failed: {failed_files}\n" \
                      f"Errors: {error_files}"
        
        QMessageBox.information(self, "Validation Complete", summary_text)
        
        # Store summary for export
        self.validation_summary = summary

    def on_validation_error(self, error_msg):
        """Called when an error occurs during validation.
        
        :param error_msg: Error message
        """
        self.stop_btn.setEnabled(False)
        self.validate_btn.setEnabled(True)
        QMessageBox.critical(self, "Validation Error", error_msg)

    def stop_validation(self):
        """Stop the validation process."""
        if self.worker:
            self.worker.stop()
        if self.worker_thread:
            self.worker_thread.quit()
            self.worker_thread.wait()
        self.stop_btn.setEnabled(False)
        self.validate_btn.setEnabled(True)

    def export_results(self):
        """Export validation results to XML."""
        if not hasattr(self, 'validation_summary'):
            QMessageBox.warning(self, "Warning", "No validation results to export.")
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Validation Results",
            "",
            "XML Files (*.xml)"
        )
        
        if not file_path:
            return
        
        try:
            self._generate_xml(file_path, self.validation_summary)
            QMessageBox.information(self, "Success", f"Results exported to:\n{file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", str(e))

    def _generate_xml(self, file_path, summary):
        """Generate XML file from validation results.
        
        :param file_path: Path to save XML file
        :param summary: Validation summary dictionary
        """
        # This is a simple XML generation. Can be enhanced with proper XML library
        xml_lines = ['<?xml version="1.0" encoding="UTF-8"?>']
        xml_lines.append('<TifValidationResults>')
        xml_lines.append(f'  <StartTime>{summary.get("start_time", "")}</StartTime>')
        xml_lines.append(f'  <EndTime>{summary.get("end_time", "")}</EndTime>')
        xml_lines.append(f'  <TotalFiles>{summary.get("total_files", 0)}</TotalFiles>')
        xml_lines.append('  <Files>')
        
        results = summary.get('results', {})
        for file_path_key, result in results.items():
            xml_lines.append('    <File>')
            xml_lines.append(f'      <Filename>{result.get("filename", "")}</Filename>')
            xml_lines.append(f'      <Status>{result.get("status", "UNKNOWN")}</Status>')
            
            if result.get('error'):
                xml_lines.append(f'      <Error>{result.get("error", "")}</Error>')
            
            xml_lines.append('      <Checks>')
            for check in result.get('checks', []):
                xml_lines.append('        <Check>')
                xml_lines.append(f'          <CheckID>{check.get("checkID", "")}</CheckID>')
                xml_lines.append(f'          <Status>{check.get("status", "")}</Status>')
                xml_lines.append(f'          <Description>{check.get("description", "")}</Description>')
                xml_lines.append(f'          <IssueCount>{check.get("issue_count", 0)}</IssueCount>')
                xml_lines.append('        </Check>')
            xml_lines.append('      </Checks>')
            xml_lines.append('    </File>')
        
        xml_lines.append('  </Files>')
        xml_lines.append('</TifValidationResults>')
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(xml_lines))

    def closeEvent(self, event):
        """Handle dialog close event."""
        if self.worker_thread and self.worker_thread.isRunning():
            self.stop_validation()
        self.closed.emit()
        super().closeEvent(event)

    def close_dialog(self):
        """Close the dialog."""
        self.close()
