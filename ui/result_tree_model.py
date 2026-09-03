# -*- coding: utf-8 -*-
"""
Tree model for displaying validation results in hierarchical structure
"""

from qgis.PyQt.QtGui import QStandardItemModel, QStandardItem
from qgis.PyQt.QtCore import Qt


class ResultTreeModel(QStandardItemModel):
    """Model for displaying validation results as a tree."""

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

    def add_dataset(self, parent_item, dataset_name, gpkg_path, passed, failed, errors):
        """Add a dataset item under validation run.
        
        :param parent_item: Parent item (validation run)
        :param dataset_name: Name of the dataset file
        :param gpkg_path: Full path to GeoPackage file
        :param passed: Number of passed checks
        :param failed: Number of failed checks
        :param errors: Number of error checks
        :return: Dataset item
        """
        summary = f"Validation Completed : {passed} passed, {failed} failed, {errors} errors"
        dataset_text = f"+ {dataset_name} : {summary}"
        dataset_item = QStandardItem(dataset_text)
        dataset_item.setEditable(False)
        dataset_item.setData(gpkg_path, Qt.UserRole)  # Store full path
        parent_item.appendRow(dataset_item)
        return dataset_item

    def add_check(self, parent_item, check_id, status, description, details=""):
        """Add a check item under dataset.
        
        :param parent_item: Parent item (dataset)
        :param check_id: Check ID
        :param status: PASS, FAIL, or ERROR
        :param description: Check description
        :param details: Check details from YAML
        :return: Check item
        """
        if details:
            check_text = f"+ {check_id} : [{status}] {description} / {details}"
        else:
            check_text = f"+ {check_id} : [{status}] {description}"
        
        check_item = QStandardItem(check_text)
        check_item.setEditable(False)
        check_item.setData(status, Qt.UserRole)  # Store status for easy access
        parent_item.appendRow(check_item)
        return check_item

    def add_issues_group(self, parent_item, issue_count, details=""):
        """Add an issues group item under check.
        
        :param parent_item: Parent item (check)
        :param issue_count: Number of issues found
        :param details: Additional details
        :return: Issues group item
        """
        if details:
            issues_text = f"+ ({issue_count}) Issues found : {details}"
        else:
            issues_text = f"+ ({issue_count}) Issues found"
        
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
        result_text = f"  {str(issue_data)}"
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
        error_text = f"+ ERROR : {error_message}"
        error_item = QStandardItem(error_text)
        error_item.setEditable(False)
        parent_item.appendRow(error_item)
        return error_item
