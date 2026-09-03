# -*- coding: utf-8 -*-
"""
Main plugin class for GeoPackage Validator
"""

import os
import sqlite3
import yaml
import re
from datetime import datetime
from pathlib import Path

from qgis.PyQt.QtWidgets import (
    QAction, QMainWindow, QDockWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFileDialog, QTextEdit, QMessageBox,
    QWidget, QProgressBar, QComboBox, QTableWidget, QTableWidgetItem
)
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtCore import Qt, QTimer, pyqtSignal, QObject
from qgis.core import QgsMessageLog, Qgis

from .validator_engine import ValidatorEngine
from .ui.validator_dialog import ValidatorDialog
from .ui.batch_validator_dialog import BatchValidatorDialog


class GeoPackageValidator:
    """QGIS plugin for validating GeoPackage files."""

    def __init__(self, iface):
        """Constructor.
        
        :param iface: A QGIS interface instance.
        :type iface: QgsInterface
        """
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        self.actions = []
        self.menu = '해양기본도 관련도구'
        self.toolbar = self.iface.addToolBar('해양기본도 관련도구')
        self.toolbar.setObjectName('GeoPackageValidator')
        
        self.dialog = None
        self.batch_dialog = None
        self.engine = ValidatorEngine()

    def add_action(self, icon_path, text, callback, enabled_flag=True,
                   add_to_menu=True, add_to_toolbar=True,
                   status_tip=None, whats_this=None, parent=None):
        """Add a toolbar icon to the toolbar.

        :param icon_path: Path to the icon for this action. Can be a resource
            path (e.g. ':/plugins/foo/bar.png') or a normal file system path.
        :type icon_path: str

        :param text: Text that should be shown in menu items for this action.
        :type text: str

        :param callback: Function to be called when the action is triggered.
        :type callback: function

        :param enabled_flag: A flag indicating if the action should be enabled
            by default. Defaults to True.
        :type enabled_flag: bool

        :param add_to_menu: Flag indicating whether the action should also
            be added to the menu. Defaults to True.
        :type add_to_menu: bool

        :param add_to_toolbar: Flag indicating whether the action should also
            be added to the toolbar. Defaults to True.
        :type add_to_toolbar: bool

        :param status_tip: Optional text to show in a status bar when the
            mouse pointer hovers over the action.
        :type status_tip: str

        :param whats_this: Optional text to show in the QGIS "What's This?"
            help system when the user clicks on the action.
        :type whats_this: str

        :param parent: Parent widget for the new action. Defaults to None.
        :type parent: QWidget

        :returns: The action created in raising the exception.
        :rtype: QAction
        """

        if icon_path:
            icon = QIcon(icon_path)
        else:
            icon = QIcon()

        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            self.toolbar.addAction(action)

        if add_to_menu:
            self.iface.addPluginToMenu(
                self.menu,
                action)

        self.actions.append(action)

        return action

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""

        icon_path = os.path.join(self.plugin_dir, 'icon.png')
        
        # Single file validation action
        self.add_action(
            icon_path,
            text='해양기본도 검사도구',
            callback=self.run,
            status_tip='단일 파일 검사',
            parent=self.iface.mainWindow())
        
        # Batch validation action
        self.add_action(
            icon_path,
            text='해양기본도 검사도구(폴더)',
            callback=self.run_batch,
            status_tip='폴더 내 모든 파일 검사',
            parent=self.iface.mainWindow())

    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        # Close dialogs if open
        if self.dialog is not None:
            self.dialog.close()
            self.dialog = None
        
        if self.batch_dialog is not None:
            self.batch_dialog.close()
            self.batch_dialog = None
        
        # Close database connection
        if self.engine:
            self.engine.close()
        
        for action in self.actions:
            self.iface.removePluginMenu(
                '&GeoPackage Validator',
                action)
            self.iface.removeToolBarIcon(action)

        del self.toolbar

    def on_dialog_closed(self):
        """Called when the single file dialog is closed."""
        self.dialog = None

    def on_batch_dialog_closed(self):
        """Called when the batch dialog is closed."""
        self.batch_dialog = None

    def run(self):
        """Run single file validator."""
        if self.dialog is None:
            self.dialog = ValidatorDialog(self.iface, self.engine)
            # Connect close signal to reset dialog reference
            self.dialog.closed.connect(self.on_dialog_closed)
            self.dialog.show()
        else:
            self.dialog.raise_()
            self.dialog.activateWindow()

    def run_batch(self):
        """Run batch validator."""
        # Always create a new instance to avoid reopening issues
        self.batch_dialog = BatchValidatorDialog(self.iface, self.engine)
        # Connect close signal to reset dialog reference
        self.batch_dialog.closed.connect(self.on_batch_dialog_closed)
        self.batch_dialog.show()
