# -*- coding: utf-8 -*-
"""
TIF File Validator Engine - for validating MBT (Mobile Base Terrain) TIF files
"""

import re
import numpy as np
from pathlib import Path
from datetime import datetime
from collections import namedtuple
from osgeo import gdal, osr
from pyproj import Transformer


class TifValidatorEngine:
    """Engine for validating TIF/GeoTIFF files."""
    
    def __init__(self):
        """Initialize the TIF validator engine."""
        gdal.DontUseExceptions()
    
    def open_dataset(self, file_path):
        """Open a TIF file as GDAL dataset.
        
        :param file_path: Path to TIF file
        :return: GDAL dataset or None if error
        """
        try:
            dataset = gdal.Open(str(file_path), gdal.GA_ReadOnly)
            if dataset is None:
                raise Exception(f"Failed to open file: {file_path}")
            return dataset
        except Exception as e:
            raise Exception(f"Error opening {file_path}: {str(e)}")
    
    def close_dataset(self, dataset):
        """Close a GDAL dataset.
        
        :param dataset: GDAL dataset
        """
        if dataset is not None:
            dataset = None
    
    def get_crs(self, dataset):
        """Get CRS code from dataset.
        
        :param dataset: GDAL dataset
        :return: CRS code string [AuthorityName:Code]
        """
        try:
            crs = dataset.GetProjection()
            osr_crs = osr.SpatialReference(wkt=crs)
            
            if osr_crs.IsProjected:
                name = osr_crs.GetAuthorityName('PROJCS')
                code = osr_crs.GetAuthorityCode('PROJCS')
            else:
                name = osr_crs.GetAuthorityName('GEOGCS')
                code = osr_crs.GetAuthorityCode('GEOGCS')
            
            return f"{name}:{code}"
        except Exception:
            return "Unknown"
    
    def check_crs(self, dataset):
        """Check if CRS is EPSG:5186.
        
        :param dataset: GDAL dataset
        :return: List of tuples with issues (empty if valid)
        """
        Result = namedtuple("_resultSet", ['CRS'])
        result = []
        
        code = self.get_crs(dataset)
        if code != 'EPSG:5186':
            result.append(Result(code))
        
        return result
    
    def check_resolution(self, dataset):
        """Check if resolution is valid (1m, 5m, or 10m).
        
        :param dataset: GDAL dataset
        :return: List of tuples with issues (empty if valid)
        """
        Result = namedtuple("_resultSet", ["ResX", "ResY"])
        result = []
        
        ulx, xres, xskew, uly, yskew, yres = dataset.GetGeoTransform()
        
        valid_resolutions = [(1, -1), (5, -5), (10, -10)]
        is_valid = any(xres == vx and yres == vy for vx, vy in valid_resolutions)
        
        if not is_valid:
            result.append(Result(str(xres), str(abs(yres))))
        
        return result
    
    def get_extent_from_code(self, cell_code):
        """Calculate extent from cell code (WGS-84 basis).
        
        :param cell_code: Cell code (without 'H')
        :return: Dictionary with extent information
        """
        t4 = np.array([["1", "2"], ["3", "4"]])[::-1, :]
        
        t16 = np.array([
            ["01", "02", "03", "04"],
            ["05", "06", "07", "08"],
            ["09", "10", "11", "12"],
            ["13", "14", "15", "16"]
        ])[::-1, :]
        
        t100 = np.array([
            ["001", "002", "003", "004", "005", "006", "007", "008", "009", "010"],
            ["011", "012", "013", "014", "015", "016", "017", "018", "019", "020"],
            ["021", "022", "023", "024", "025", "026", "027", "028", "029", "030"],
            ["031", "032", "033", "034", "035", "036", "037", "038", "039", "040"],
            ["041", "042", "043", "044", "045", "046", "047", "048", "049", "050"],
            ["051", "052", "053", "054", "055", "056", "057", "058", "059", "060"],
            ["061", "062", "063", "064", "065", "066", "067", "068", "069", "070"],
            ["071", "072", "073", "074", "075", "076", "077", "078", "079", "080"],
            ["081", "082", "083", "084", "085", "086", "087", "088", "089", "090"],
            ["091", "092", "093", "094", "095", "096", "097", "098", "099", "100"]
        ])[::-1, :]
        
        extent = {
            "scale": 0,
            "xmin": -1.0,
            "xmax": -1.0,
            "ymin": -1.0,
            "ymax": -1.0
        }
        
        try:
            lat = float(cell_code[0:2])
            lon = float(cell_code[2:4]) + 100
            index = np.where(t16 == cell_code[4:6])
            lat += 0.25 * index[0][0]
            lon += 0.25 * index[1][0]
            
            if len(cell_code) == 9:
                index = np.where(t100 == cell_code[6:9])
                lat += 0.025 * index[0][0]
                lon += 0.025 * index[1][0]
                extent["xmin"] = lon
                extent["xmax"] = lon + 0.025
                extent['ymin'] = lat
                extent['ymax'] = lat + 0.025
            elif len(cell_code) == 7:
                index = np.where(t4 == cell_code[6:7])
                lat += 0.125 * index[0][0]
                lon += 0.125 * index[1][0]
                extent["xmin"] = lon
                extent["xmax"] = lon + 0.125
                extent['ymin'] = lat
                extent['ymax'] = lat + 0.125
                extent['scale'] = 25000
        except Exception:
            pass
        
        return extent
    
    def check_filename(self, dataset):
        """Check if filename follows correct format.
        
        :param dataset: GDAL dataset
        :return: List of tuples with issues (empty if valid)
        """
        Result = namedtuple("_resultSet", ["Filename"])
        result = []
        
        try:
            filename = Path(dataset.GetFileList()[0]).name
            
            # Check basic format
            if not (re.match(r'^MBT_[0-9]{4}_[0-9]{7}.tif$', filename) or 
                    re.match(r'^MBT_[0-9]{4}_[0-9]{9}.tif$', filename)):
                result.append(Result(filename))
                return result
            
            # Extract cell code and validate coordinates
            cell_code = filename.split('.')[0].split('_')[2]
            lat = int(cell_code[0:2])
            lon = int(cell_code[2:4]) + 100
            
            if not (30 <= lat <= 40 and 122 <= lon <= 134):
                result.append(Result(filename))
            
        except Exception:
            result.append(Result("Unknown filename"))
        
        return result
    
    def check_extent(self, dataset):
        """Check if extent matches cell code extent.
        
        :param dataset: GDAL dataset
        :return: List of tuples with issues (empty if valid)
        """
        Result = namedtuple("_resultSet", ["Expected"])
        result = []
        
        try:
            filename = Path(dataset.GetFileList()[0]).name
            cell_code = filename.split('.')[0].split('_')[2]
            extent = self.get_extent_from_code(cell_code)
            
            # Transform extent to EPSG:5186
            tf = Transformer.from_crs('EPSG:4326', 'EPSG:5186')
            bounds = np.array([
                [extent['xmin'], extent['ymin']],
                [extent['xmax'], extent['ymax']]
            ])
            bounds5186 = np.array(tf.transform(bounds[:, 1], bounds[:, 0])).T[:, ::-1]
            
            # Calculate raster extent
            ulx, xres, xskew, uly, yskew, yres = dataset.GetGeoTransform()
            r_min_x = ulx
            r_max_y = uly
            r_max_x = ulx + xres * dataset.RasterXSize
            r_min_y = uly + yres * dataset.RasterYSize
            
            # Check if raster extent contains cell code extent
            if not ((r_min_x < bounds5186[0][0] and r_min_y < bounds5186[0][1]) and
                    (r_max_x > bounds5186[1][0] and r_max_y > bounds5186[1][1])):
                expected = f"Extent From CellCode = [{np.floor(bounds5186[0])},{np.ceil(bounds5186[1])}] File Extent = [{np.floor([r_min_x,r_min_y])},{np.ceil([r_max_x, r_max_y])}]"
                result.append(Result(expected))
        
        except Exception:
            pass
        
        return result
    
    def validate(self, file_path):
        """Validate a TIF file.
        
        :param file_path: Path to TIF file
        :return: Dictionary with validation results
        """
        results = {
            'filename': Path(file_path).name,
            'status': 'SUCCESS',
            'checks': [],
            'error': None
        }
        
        try:
            dataset = self.open_dataset(file_path)
            
            checks = [
                {
                    'checkID': 'MBT-VAL-VA-03',
                    'function': self.check_crs,
                    'description': '파일의 좌표계가 EPSG:5186인지 확인한다.',
                    'level': 'Critical'
                },
                {
                    'checkID': 'MBT-VAL-VA-04',
                    'function': self.check_resolution,
                    'description': '해상도가 1m, 5m, 10m 중 하나인지 확인한다.',
                    'level': 'Critical'
                },
                {
                    'checkID': 'MBT-VAL-VA-05',
                    'function': self.check_filename,
                    'description': '파일의 이름이 적절한지 확인한다.',
                    'level': 'Critical'
                },
                {
                    'checkID': 'MBT-VAL-VA-06',
                    'function': self.check_extent,
                    'description': '파일의 범위가 적절한지 확인한다.',
                    'level': 'Critical'
                }
            ]
            
            has_issues = False
            
            for check in checks:
                check_result = check['function'](dataset)
                
                check_data = {
                    'checkID': check['checkID'],
                    'status': 'PASS' if len(check_result) == 0 else 'FAIL',
                    'description': check['description'],
                    'level': check['level'],
                    'issues': check_result,
                    'issue_count': len(check_result)
                }
                
                results['checks'].append(check_data)
                
                if len(check_result) > 0:
                    has_issues = True
            
            if has_issues:
                results['status'] = 'FAIL'
            
            self.close_dataset(dataset)
        
        except Exception as e:
            results['status'] = 'ERROR'
            results['error'] = str(e)
        
        return results
