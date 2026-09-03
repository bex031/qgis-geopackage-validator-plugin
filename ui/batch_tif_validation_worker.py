# -*- coding: utf-8 -*-
"""
Batch TIF Validation Worker - processes multiple TIF files in a folder
"""

from pathlib import Path
from datetime import datetime
from qgis.PyQt.QtCore import QObject, pyqtSignal

from ..tif_validator_engine import TifValidatorEngine


class BatchTifValidationWorker(QObject):
    """Worker for batch TIF validation in a separate thread."""
    
    # Signals
    progress = pyqtSignal(int)  # Progress percentage
    file_started = pyqtSignal(str)  # Filename
    file_completed = pyqtSignal(str, list)  # Filename, results
    finished = pyqtSignal(dict)  # Summary dictionary
    error = pyqtSignal(str)  # Error message

    def __init__(self, folder_path):
        """Initialize the worker.
        
        :param folder_path: Path to folder containing TIF files
        """
        super().__init__()
        self.folder_path = folder_path
        self.engine = TifValidatorEngine()
        self.should_stop = False

    def run(self):
        """Run the batch validation."""
        try:
            start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Find all TIF files in folder
            tif_files = list(Path(self.folder_path).glob('*.tif')) + \
                       list(Path(self.folder_path).glob('*.TIF'))
            
            if not tif_files:
                self.error.emit("No TIF files found in the selected folder")
                return
            
            total_files = len(tif_files)
            results = {}
            
            for idx, tif_path in enumerate(tif_files):
                if self.should_stop:
                    break
                
                # Emit file started signal
                filename = tif_path.name
                self.file_started.emit(filename)
                
                # Validate file
                try:
                    validation_result = self.engine.validate(str(tif_path))
                    results[str(tif_path)] = validation_result
                    self.file_completed.emit(filename, validation_result)
                except Exception as e:
                    results[str(tif_path)] = {
                        'filename': filename,
                        'status': 'ERROR',
                        'checks': [],
                        'error': str(e)
                    }
                    self.file_completed.emit(filename, None)
                
                # Update progress
                progress = int((idx + 1) / total_files * 100)
                self.progress.emit(progress)
            
            # Generate summary
            end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            summary = {
                'start_time': start_time,
                'end_time': end_time,
                'total_files': total_files,
                'results': results
            }
            
            self.finished.emit(summary)
        
        except Exception as e:
            self.error.emit(str(e))

    def stop(self):
        """Stop the validation process."""
        self.should_stop = True
