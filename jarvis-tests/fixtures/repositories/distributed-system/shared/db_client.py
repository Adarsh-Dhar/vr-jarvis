"""
Database Client - Simulated Database
In production this would connect to PostgreSQL.
"""

from typing import Dict, Any, Optional
from collections import defaultdict


class DatabaseClient:
    """Simulated database client"""

    def __init__(self):
        self.tables = defaultdict(dict)
        self.primary_keys = {
            'orders': 'order_id',
            'customers': 'customer_id',
            'payments': 'payment_id'
        }

    def insert(self, table_name: str, record: Dict[str, Any]) -> bool:
        """Insert a record into a table"""
        pk = self.primary_keys.get(table_name, 'id')
        if pk not in record:
            raise ValueError(f"Primary key {pk} not in record")

        self.tables[table_name][record[pk]] = record
        return True

    def get(self, table_name: str, pk_value: Any) -> Optional[Dict[str, Any]]:
        """Get a record by primary key"""
        return self.tables[table_name].get(pk_value)

    def update(self, table_name: str, pk_value: Any, updates: Dict[str, Any]) -> bool:
        """Update a record"""
        if pk_value in self.tables[table_name]:
            self.tables[table_name][pk_value].update(updates)
            return True
        return False

    def query(self, table_name: str, filters: Dict[str, Any]) -> list:
        """Query records with filters"""
        results = []
        for record in self.tables[table_name].values():
            if all(record.get(k) == v for k, v in filters.items()):
                results.append(record)
        return results

    def get_all(self, table_name: str) -> list:
        """Get all records from a table"""
        return list(self.tables[table_name].values())
