# -*- coding: utf-8 -*-
"""
Worker thread for validation to prevent UI freezing
"""

from qgis.PyQt.QtCore import QObject, pyqtSignal


class ValidatorWorker(QObject):
    """Worker thread for running validation in background."""
    
    progress = pyqtSignal(int)
    finished = pyqtSignal(list)
    error = pyqtSignal(str)
    
    def __init__(self, engine, gpkg_path, rule_path):
        """Initialize the worker.
        
        :param engine: Validator engine
        :param gpkg_path: Path to GeoPackage file
        :param rule_path: Path to rule file
        """
        super().__init__()
        self.engine = engine
        self.gpkg_path = gpkg_path
        self.rule_path = rule_path

    def run(self):
        """Run the validation process."""
        try:
            self.progress.emit(10)
            
            # Load GeoPackage
            self.engine.load_gpkg(self.gpkg_path)
            self.progress.emit(30)
            
            # Load rules
            self.engine.load_rules(self.rule_path)
            self.progress.emit(50)
            
            # Execute checks
            results = self.engine.execute_checks()
            self.progress.emit(90)
            
            self.progress.emit(100)
            self.finished.emit(results)
            
            # Close connection
            self.engine.close()
            
        except Exception as e:
            self.error.emit(str(e))
