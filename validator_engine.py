# -*- coding: utf-8 -*-
"""
Validator Engine - Core logic for validation
"""

import sqlite3
import yaml
import re
from datetime import datetime


class ValidatorEngine:
    """Core validation engine for GeoPackage files."""

    def __init__(self):
        """Initialize the validator engine."""
        self.conn = None
        self.rule = None
        self.results = []

    def regexp_match(self, item, expr):
        """Check if item matches the regex pattern.
        
        :param item: String to match
        :param expr: Regex pattern
        :return: True if matches, False otherwise
        """
        if item is None:
            return False
        return re.match(expr, item) is not None

    def regexp_search(self, item, expr):
        """Search for regex pattern in item.
        
        :param item: String to search in
        :param expr: Regex pattern
        :return: True if found, False otherwise
        """
        if item is None:
            return False
        return re.search(expr, item) is not None

    def load_gpkg(self, gpkg_path):
        """Load a GeoPackage file.
        
        :param gpkg_path: Path to the GeoPackage file
        :return: True if successful, False otherwise
        """
        try:
            self.conn = sqlite3.connect(gpkg_path)
            self.conn.enable_load_extension(True)
            
            try:
                self.conn.execute('SELECT load_extension("mod_spatialite");')
                self.conn.execute('SELECT EnableGpkgMode();')
            except Exception as e:
                # Spatialite may not be available, but we can still work with basic SQLite
                print(f"Warning: Spatialite not available: {e}")
            
            # Register custom functions
            self.conn.create_function("REGEXP_MATCH", 2, self.regexp_match)
            self.conn.create_function("REGEXP_SEARCH", 2, self.regexp_search)
            
            return True
        except Exception as e:
            raise Exception(f"Failed to load GeoPackage: {str(e)}")

    def load_rules(self, rule_path):
        """Load validation rules from YAML file.
        
        :param rule_path: Path to the YAML rule file
        :return: True if successful, False otherwise
        """
        try:
            with open(rule_path, 'r', encoding='utf-8') as f:
                self.rule = yaml.load(f, Loader=yaml.FullLoader)
            return True
        except Exception as e:
            raise Exception(f"Failed to load rules: {str(e)}")

    def execute_checks(self):
        """Execute all checks from the loaded rules.
        
        :return: List of check results
        """
        if self.conn is None:
            raise Exception("GeoPackage not loaded")
        if self.rule is None:
            raise Exception("Rules not loaded")

        self.results = []

        for check in self.rule.get("Checks", []):
            result = {
                'checkID': check.get('CheckID', 'Unknown'),
                'description': check.get('Description', ''),
                'details': check.get('Details', ''),  # Add Details from YAML
                'level': check.get('Level', 'Unknown'),
                'category': check.get('Category', ''),
                'status': 'PASS',
                'issues': [],
                'error': None
            }

            try:
                query = check.get('Query', '').strip()
                if not query:
                    result['error'] = 'No query defined'
                    result['status'] = 'ERROR'
                else:
                    cur = self.conn.execute(query)
                    rows = cur.fetchall()
                    
                    if len(rows) == 0:
                        result['status'] = 'PASS'
                    else:
                        result['status'] = 'FAIL'
                        result['issues'] = rows

            except Exception as e:
                result['status'] = 'ERROR'
                result['error'] = str(e)

            self.results.append(result)

        return self.results

    def close(self):
        """Close the database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None

    def get_results(self):
        """Get the validation results.
        
        :return: List of check results
        """
        return self.results
