# -*- coding: utf-8 -*-
"""
Batch validation worker for processing multiple GeoPackage files
"""

import os
from pathlib import Path
from datetime import datetime
from qgis.PyQt.QtCore import QObject, pyqtSignal


class BatchValidationWorker(QObject):
    """Worker for batch validation of multiple GeoPackage files."""
    
    progress = pyqtSignal(int)  # Overall progress 0-100
    file_started = pyqtSignal(str)  # Emitted when starting validation of a file
    file_completed = pyqtSignal(str, list)  # Emitted when file validation completes (filename, results)
    finished = pyqtSignal(dict)  # Emitted when all validations complete
    error = pyqtSignal(str)  # Emitted on error

    def __init__(self, engine, folder_path, rule_path):
        """Initialize the batch validation worker.
        
        :param engine: Validator engine
        :param folder_path: Path to folder to scan
        :param rule_path: Path to rule file
        """
        super().__init__()
        self.engine = engine
        self.folder_path = folder_path
        self.rule_path = rule_path
        self.gpkg_files = []
        self.all_results = {}
        self.start_time = None
        self.end_time = None

    def find_gpkg_files(self):
        """Find all GPKG files in folder and subfolders.
        
        :return: List of GPKG file paths
        """
        gpkg_files = []
        
        try:
            for root, dirs, files in os.walk(self.folder_path):
                for file in files:
                    if file.lower().endswith('.gpkg'):
                        full_path = os.path.join(root, file)
                        gpkg_files.append(full_path)
        except Exception as e:
            raise Exception(f"Failed to scan folder: {str(e)}")
        
        return sorted(gpkg_files)

    def run(self):
        """Run batch validation."""
        try:
            self.start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.progress.emit(0)
            
            # Find all GPKG files
            self.gpkg_files = self.find_gpkg_files()
            
            if len(self.gpkg_files) == 0:
                self.error.emit("No GeoPackage files found in the specified folder.")
                return
            
            # Process each GPKG file
            for idx, gpkg_path in enumerate(self.gpkg_files):
                filename = os.path.basename(gpkg_path)
                self.file_started.emit(filename)
                
                try:
                    # Load and validate
                    self.engine.load_gpkg(gpkg_path)
                    self.engine.load_rules(self.rule_path)
                    results = self.engine.execute_checks()
                    
                    # Store results
                    self.all_results[gpkg_path] = {
                        'filename': filename,
                        'results': results
                    }
                    
                    # Emit file completed signal
                    self.file_completed.emit(filename, results)
                    
                except Exception as e:
                    # Store error result
                    self.all_results[gpkg_path] = {
                        'filename': filename,
                        'error': str(e),
                        'results': []
                    }
                    self.file_completed.emit(filename, [])
                
                finally:
                    # Close database connection
                    self.engine.close()
                
                # Update progress
                progress_value = int((idx + 1) / len(self.gpkg_files) * 100)
                self.progress.emit(progress_value)
            
            self.end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Emit finished signal with all results
            summary = {
                'start_time': self.start_time,
                'end_time': self.end_time,
                'total_files': len(self.gpkg_files),
                'results': self.all_results
            }
            self.finished.emit(summary)
            
        except Exception as e:
            self.error.emit(str(e))
