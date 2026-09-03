# -*- coding: utf-8 -*-
"""
TIF Result Tree Model - for displaying TIF validation results in hierarchical structure
"""

from qgis.PyQt.QtGui import QStandardItemModel, QStandardItem, QColor, QFont
from qgis.PyQt.QtCore import Qt, QModelIndex


class TifResultTreeModel(QStandardItemModel):
    """Model for displaying TIF validation results as a tree."""

    def __init__(self):
        """Initialize the tree model."""
        super().__init__()
        self.setHorizontalHeaderLabels(['Result'])

    def add_validation_run(self, start_time, end_time):
        """Add a validation run root item.
        
        :param start_time: Start time of validation
        :param end_time: End time of validation
        :return: Root item
        """
        root_text = f"Validation : {start_time} - {end_time}"
        root_item = QStandardItem(root_text)
        root_item.setEditable(False)
        self.appendRow(root_item)
        return root_item

    def add_file(self, parent_item, filename, tif_path, passed, failed, errors):
        """Add a TIF file item under validation run.
        
        :param parent_item: Parent item (validation run)
        :param filename: Name of the TIF file
        :param tif_path: Full path to TIF file
        :param passed: Number of passed checks
        :param failed: Number of failed checks
        :param errors: Number of error checks
        :return: File item
        """
        summary = f"Validation Completed : {passed} passed, {failed} failed, {errors} errors"
        file_text = f"{filename} : {summary}"
        file_item = QStandardItem(file_text)
        file_item.setEditable(False)
        # Store full path as custom data
        file_item.setData(tif_path, 32)  # Qt.UserRole = 32
        
        # Highlight file if there are failures or errors
        if failed > 0 or errors > 0:
            font = QFont()
            font.setBold(True)
            file_item.setFont(font)
            file_item.setForeground(QColor(255, 0, 0))  # Red text
            file_item.setBackground(QColor(255, 200, 200))  # Light red background
        
        parent_item.appendRow(file_item)
        return file_item

    def add_check(self, parent_item, check_id, status, description):
        """Add a check item under file.
        
        :param parent_item: Parent item (file)
        :param check_id: Check ID
        :param status: PASS, FAIL, or ERROR
        :param description: Check description
        :return: Check item
        """
        check_text = f"{check_id} : [{status}] {description}"
        
        check_item = QStandardItem(check_text)
        check_item.setEditable(False)
        # Store status as custom data (Qt.UserRole = 32)
        check_item.setData(status, 32)
        
        # Highlight FAIL and ERROR with red color
        if status in ['FAIL', 'ERROR']:
            font = QFont()
            font.setBold(True)
            check_item.setFont(font)
            check_item.setForeground(QColor(255, 0, 0))  # Red color
        
        parent_item.appendRow(check_item)
        return check_item

    def add_issues_group(self, parent_item, issue_count, issue_details=""):
        """Add an issues group item under check.
        
        :param parent_item: Parent item (check)
        :param issue_count: Number of issues found
        :param issue_details: Issue details (shown to avoid duplication with check description)
        :return: Issues group item
        """
        # Show issue count and details
        if issue_details:
            issues_text = f"({issue_count}) Issues found : {issue_details}"
        else:
            issues_text = f"({issue_count}) Issues found"
        
        issues_item = QStandardItem(issues_text)
        issues_item.setEditable(False)
        parent_item.appendRow(issues_item)
        return issues_item

    def add_issue_result(self, parent_item, issue_data):
        """Add an individual issue result under issues group.
        
        :param parent_item: Parent item (issues group)
        :param issue_data: Issue data (tuple or string)
        :return: Issue result item
        """
        result_text = f"{str(issue_data)}"
        result_item = QStandardItem(result_text)
        result_item.setEditable(False)
        parent_item.appendRow(result_item)
        return result_item

    def add_error(self, parent_item, error_message):
        """Add an error item.
        
        :param parent_item: Parent item
        :param error_message: Error message
        :return: Error item
        """
        error_text = f"ERROR : {error_message}"
        error_item = QStandardItem(error_text)
        error_item.setEditable(False)
        # Highlight errors in red
        font = QFont()
        font.setBold(True)
        error_item.setFont(font)
        error_item.setForeground(QColor(255, 0, 0))  # Red color
        parent_item.appendRow(error_item)
        return error_item
