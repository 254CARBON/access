"""
Mock ClickHouse server providing analytical database functionality.
"""

import json
import time
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException, Query, Body
from pydantic import BaseModel
import sys
import os

# Add shared directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from shared.logging import get_logger


@dataclass
class MockTable:
    """Mock ClickHouse table."""
    name: str
    columns: Dict[str, str]  # column_name -> type
    data: List[Dict[str, Any]] = field(default_factory=list)


class MockClickHouseServer:
    """Mock ClickHouse server implementation."""
    
    def __init__(self, port: int = 8123):
        self.port = port
        self.logger = get_logger("mock.clickhouse")
        self.app = FastAPI(title="Mock ClickHouse", version="1.0.0")
        
        # In-memory storage
        self.tables: Dict[str, MockTable] = {}
        self.databases: Dict[str, List[str]] = {"default": []}
        
        # Create default tables with sample data
        self._create_default_tables()
        
        self._setup_routes()
    
    def _create_default_tables(self):
        """Create default tables with sample data."""
        # Instruments table
        instruments_table = MockTable(
            name="instruments",
            columns={
                "id": "String",
                "symbol": "String", 
                "name": "String",
                "type": "String",
                "commodity": "String",
                "exchange": "String",
                "currency": "String",
                "created_at": "DateTime",
                "updated_at": "DateTime"
            }
        )
        
        # Sample instruments data
        instruments_data = [
            {
                "id": "INST001",
                "symbol": "BRN",
                "name": "Brent Crude Oil",
                "type": "commodity",
                "commodity": "oil",
                "exchange": "ICE",
                "currency": "USD",
                "created_at": "2024-01-01 00:00:00",
                "updated_at": "2024-01-01 00:00:00"
            },
            {
                "id": "INST002", 
                "symbol": "WTI",
                "name": "West Texas Intermediate",
                "type": "commodity",
                "commodity": "oil",
                "exchange": "NYMEX",
                "currency": "USD",
                "created_at": "2024-01-01 00:00:00",
                "updated_at": "2024-01-01 00:00:00"
            },
            {
                "id": "INST003",
                "symbol": "NG",
                "name": "Natural Gas",
                "type": "commodity", 
                "commodity": "gas",
                "exchange": "NYMEX",
                "currency": "USD",
                "created_at": "2024-01-01 00:00:00",
                "updated_at": "2024-01-01 00:00:00"
            }
        ]
        
        instruments_table.data = instruments_data
        self.tables["instruments"] = instruments_table
        
        # Pricing data table
        pricing_table = MockTable(
            name="pricing_data",
            columns={
                "instrument_id": "String",
                "timestamp": "DateTime",
                "price": "Float64",
                "volume": "Float64",
                "bid": "Float64",
                "ask": "Float64",
                "tenant_id": "String"
            }
        )
        
        # Generate sample pricing data
        pricing_data = []
        base_time = datetime.now() - timedelta(days=30)
        
        for i in range(1000):
            timestamp = base_time + timedelta(minutes=i * 5)
            for instrument in ["INST001", "INST002", "INST003"]:
                base_price = 50.0 if instrument == "INST001" else 45.0 if instrument == "INST002" else 3.0
                price = base_price + (i * 0.01) + (hash(instrument) % 10) * 0.1
                
                pricing_data.append({
                    "instrument_id": instrument,
                    "timestamp": timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                    "price": round(price, 2),
                    "volume": round(1000 + (i % 100) * 10, 2),
                    "bid": round(price - 0.01, 2),
                    "ask": round(price + 0.01, 2),
                    "tenant_id": "tenant-1"
                })
        
        pricing_table.data = pricing_data
        self.tables["pricing_data"] = pricing_table
        
        # Curves table
        curves_table = MockTable(
            name="curves",
            columns={
                "id": "String",
                "name": "String",
                "commodity": "String",
                "tenor": "String",
                "price": "Float64",
                "timestamp": "DateTime",
                "tenant_id": "String"
            }
        )
        
        # Sample curves data
        curves_data = []
        tenors = ["1M", "3M", "6M", "1Y", "2Y", "5Y"]
        commodities = ["oil", "gas", "power"]
        
        for commodity in commodities:
            for i, tenor in enumerate(tenors):
                base_price = 50.0 if commodity == "oil" else 3.0 if commodity == "gas" else 30.0
                price = base_price + i * 2.0
                
                curves_data.append({
                    "id": f"CURVE_{commodity}_{tenor}",
                    "name": f"{commodity.title()} {tenor} Curve",
                    "commodity": commodity,
                    "tenor": tenor,
                    "price": round(price, 2),
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "tenant_id": "tenant-1"
                })
        
        curves_table.data = curves_data
        self.tables["curves"] = curves_table
        
        # Add tables to default database
        self.databases["default"] = list(self.tables.keys())
    
    def _setup_routes(self):
        """Set up mock ClickHouse routes."""
        
        @self.app.get("/")
        async def root():
            """Root endpoint."""
            return {
                "service": "mock-clickhouse",
                "message": "Mock ClickHouse server for 254Carbon Access Layer",
                "version": "1.0.0",
                "databases": list(self.databases.keys()),
                "tables": list(self.tables.keys())
            }
        
        @self.app.get("/databases")
        async def list_databases():
            """List databases."""
            return {
                "databases": [
                    {
                        "name": db_name,
                        "tables": tables
                    }
                    for db_name, tables in self.databases.items()
                ]
            }
        
        @self.app.get("/tables")
        async def list_tables(database: str = Query("default")):
            """List tables in database."""
            if database not in self.databases:
                raise HTTPException(status_code=404, detail="Database not found")
            
            tables_info = []
            for table_name in self.databases[database]:
                if table_name in self.tables:
                    table = self.tables[table_name]
                    tables_info.append({
                        "name": table.name,
                        "columns": table.columns,
                        "row_count": len(table.data)
                    })
            
            return {"tables": tables_info}
        
        @self.app.post("/query")
        async def execute_query(
            query: str = Body(..., embed=True),
            database: str = Query("default")
        ):
            """Execute SQL query."""
            if database not in self.databases:
                raise HTTPException(status_code=404, detail="Database not found")
            
            try:
                result = self._execute_query(query, database)
                return result
            except Exception as e:
                self.logger.error(f"Query execution error: {e}")
                raise HTTPException(status_code=400, detail=str(e))
        
        @self.app.get("/query")
        async def execute_query_get(
            query: str = Query(...),
            database: str = Query("default")
        ):
            """Execute SQL query via GET."""
            if database not in self.databases:
                raise HTTPException(status_code=404, detail="Database not found")
            
            try:
                result = self._execute_query(query, database)
                return result
            except Exception as e:
                self.logger.error(f"Query execution error: {e}")
                raise HTTPException(status_code=400, detail=str(e))
        
        @self.app.post("/tables/{table_name}/insert")
        async def insert_data(
            table_name: str,
            data: List[Dict[str, Any]] = Body(...),
            database: str = Query("default")
        ):
            """Insert data into table."""
            if database not in self.databases:
                raise HTTPException(status_code=404, detail="Database not found")
            
            if table_name not in self.tables:
                raise HTTPException(status_code=404, detail="Table not found")
            
            table = self.tables[table_name]
            
            # Validate data against table schema
            for row in data:
                for column in row.keys():
                    if column not in table.columns:
                        raise HTTPException(status_code=400, detail=f"Column '{column}' not found in table")
            
            # Insert data
            table.data.extend(data)
            
            return {
                "message": f"Inserted {len(data)} rows into table '{table_name}'",
                "total_rows": len(table.data)
            }
    
    def _execute_query(self, query: str, database: str) -> Dict[str, Any]:
        """Execute SQL query."""
        query = query.strip().upper()
        
        if query.startswith("SELECT"):
            return self._execute_select(query, database)
        elif query.startswith("SHOW TABLES"):
            return self._execute_show_tables(database)
        elif query.startswith("DESCRIBE") or query.startswith("DESC"):
            return self._execute_describe(query, database)
        elif query.startswith("CREATE TABLE"):
            return self._execute_create_table(query, database)
        else:
            raise ValueError(f"Unsupported query type: {query}")
    
    def _execute_select(self, query: str, database: str) -> Dict[str, Any]:
        """Execute SELECT query."""
        # Simple query parsing (very basic)
        if "FROM" not in query:
            raise ValueError("SELECT query must include FROM clause")
        
        # Extract table name
        parts = query.split()
        from_index = parts.index("FROM")
        if from_index + 1 >= len(parts):
            raise ValueError("FROM clause missing table name")
        
        table_name = parts[from_index + 1].strip(";")
        
        if table_name not in self.tables:
            raise ValueError(f"Table '{table_name}' not found")
        
        table = self.tables[table_name]
        
        # Simple WHERE clause parsing
        where_clause = None
        if "WHERE" in query:
            where_index = parts.index("WHERE")
            if where_index + 1 < len(parts):
                where_clause = " ".join(parts[where_index + 1:]).strip(";")
        
        # Simple LIMIT parsing
        limit = None
        if "LIMIT" in query:
            limit_index = parts.index("LIMIT")
            if limit_index + 1 < len(parts):
                limit = int(parts[limit_index + 1])
        
        # Filter data
        filtered_data = table.data.copy()
        
        if where_clause:
            # Simple WHERE clause handling
            if "tenant_id" in where_clause:
                # Extract tenant_id value
                if "=" in where_clause:
                    tenant_value = where_clause.split("=")[1].strip().strip("'\"")
                    filtered_data = [row for row in filtered_data if row.get("tenant_id") == tenant_value]
        
        # Apply limit
        if limit:
            filtered_data = filtered_data[:limit]
        
        return {
            "data": filtered_data,
            "rows": len(filtered_data),
            "columns": list(table.columns.keys())
        }
    
    def _execute_show_tables(self, database: str) -> Dict[str, Any]:
        """Execute SHOW TABLES query."""
        if database not in self.databases:
            raise ValueError(f"Database '{database}' not found")
        
        return {
            "data": [{"name": table_name} for table_name in self.databases[database]],
            "rows": len(self.databases[database]),
            "columns": ["name"]
        }
    
    def _execute_describe(self, query: str, database: str) -> Dict[str, Any]:
        """Execute DESCRIBE query."""
        parts = query.split()
        if len(parts) < 2:
            raise ValueError("DESCRIBE query missing table name")
        
        table_name = parts[1].strip(";")
        
        if table_name not in self.tables:
            raise ValueError(f"Table '{table_name}' not found")
        
        table = self.tables[table_name]
        
        return {
            "data": [
                {"name": col_name, "type": col_type}
                for col_name, col_type in table.columns.items()
            ],
            "rows": len(table.columns),
            "columns": ["name", "type"]
        }
    
    def _execute_create_table(self, query: str, database: str) -> Dict[str, Any]:
        """Execute CREATE TABLE query."""
        # Simple table creation (basic implementation)
        return {
            "message": "Table created successfully",
            "rows": 0,
            "columns": []
        }


def create_app():
    """Create mock ClickHouse application."""
    server = MockClickHouseServer()
    return server.app


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(create_app(), host="0.0.0.0", port=8123)
