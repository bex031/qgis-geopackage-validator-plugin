# -*- coding: utf-8 -*-
"""
This script initializes the plugin, making it known to QGIS.
"""


def classFactory(iface):
    """Load GeoPackageValidator class from file validator.
    
    :param iface: A QGIS interface instance.
    :type iface: QgsInterface
    """
    from .validator import GeoPackageValidator
    return GeoPackageValidator(iface)
