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
    QGroupBox
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
        self.validation_summary = None

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
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        # Results tree
        results_group = QGroupBox("Validation Results")
        results_layout = QVBoxLayout()
        self.tree_model = TifResultTreeModel()
        self.tree_view = QTreeView()
        self.tree_view.setModel(self.tree_model)
        self.tree_view.setColumnWidth(0, 800)
        results_layout.addWidget(self.tree_view)
        results_group.setLayout(results_layout)
        layout.addWidget(results_group)
        
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
        
        self.status_label = QLabel("Ready")
        
        button_layout.addWidget(self.validate_btn)
        button_layout.addWidget(self.export_btn)
        button_layout.addWidget(self.stop_btn)
        button_layout.addWidget(self.status_label)
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        self.setLayout(layout)

    def select_folder(self):
        """Open folder selection dialog."""
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Folder with TIF Files",
            ""
        )
        
        if folder:
            self.current_folder = folder
            self.folder_label.setText(Path(folder).name)
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
        self.progress_bar.setVisible(True)
        self.validate_btn.setEnabled(False)
        self.export_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.status_label.setText("Scanning folder...")
        
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
        self.status_label.setText(f"Validating: {filename}")

    def on_file_completed(self, filename, results):
        """Called when validation of a file completes.
        
        :param filename: Name of the file
        :param results: Validation results dictionary
        """
        if results is None:
            return
        
        # Get or create root item for this validation run
        if self.tree_model.rowCount() == 0:
            start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            root_item = self.tree_model.add_validation_run(start_time, "In Progress")
        else:
            root_item = self.tree_model.item(0)
        
        # Add file item (dataset)
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
        
        # Add dataset node
        file_item = self.tree_model.add_file(root_item, filename, tif_path, passed, failed, errors)
        
        # Add check items
        for check in checks:
            check_id = check.get('checkID', 'Unknown')
            check_status = check.get('status', 'UNKNOWN')
            description = check.get('description', '')
            issues = check.get('issues', [])
            issue_count = check.get('issue_count', 0)
            
            check_item = self.tree_model.add_check(file_item, check_id, check_status, description)
            
            # Add issues/errors if there are any
            if issue_count > 0 and issues:
                # Format issues for display
                issue_details = []
                for issue in issues:
                    issue_details.append(str(issue))
                issue_text = ", ".join(issue_details)
                self.tree_model.add_issues_group(check_item, issue_count, issue_text)
        
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
        self.progress_bar.setVisible(False)
        self.stop_btn.setEnabled(False)
        self.validate_btn.setEnabled(True)
        self.export_btn.setEnabled(True)
        
        # Update root item with end time
        if self.tree_model.rowCount() > 0:
            root_item = self.tree_model.item(0)
            end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            root_item.setText(f"Validation : {end_time.split()[0]} - {end_time}")
        
        # Calculate statistics
        total = summary.get('total_files', 0)
        results = summary.get('results', {})
        
        passed_files = sum(1 for r in results.values() if r.get('status') == 'SUCCESS')
        failed_files = sum(1 for r in results.values() if r.get('status') == 'FAIL')
        error_files = sum(1 for r in results.values() if r.get('status') == 'ERROR')
        
        # Update status label
        self.status_label.setText(f"Batch validation completed: {total} files processed")
        
        # Store summary for export
        self.validation_summary = summary

    def on_validation_error(self, error_msg):
        """Called when an error occurs during validation.
        
        :param error_msg: Error message
        """
        self.progress_bar.setVisible(False)
        self.stop_btn.setEnabled(False)
        self.validate_btn.setEnabled(True)
        self.status_label.setText("Batch validation failed")
        QMessageBox.critical(self, "Validation Error", error_msg)
        
        # Clean up worker thread
        if self.worker_thread is not None:
            self.worker_thread.quit()
            self.worker_thread.wait()
            self.worker_thread = None
            self.worker = None

    def stop_validation(self):
        """Stop the validation process."""
        if self.worker:
            self.worker.stop()
        if self.worker_thread:
            self.worker_thread.quit()
            self.worker_thread.wait()
        self.stop_btn.setEnabled(False)
        self.validate_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.status_label.setText("Validation stopped")

    def export_results(self):
        """Export validation results to XML."""
        if not self.validation_summary:
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
                xml_lines.append(f'          <Level>{check.get("level", "")}</Level>')
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
