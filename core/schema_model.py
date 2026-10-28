from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ColumnInfo:
    table: str
    name: str
    data_type: str
    nullable: Optional[bool] = None
    collation: Optional[str] = None

    def as_dict(self):
        return {
            "table": self.table,
            "name": self.name,
            "data_type": self.data_type,
            "nullable": self.nullable,
            "collation": self.collation,
        }


@dataclass
class IndexInfo:
    table: str
    name: str
    columns: list[str] = field(default_factory=list)
    unique: bool = False
    primary: bool = False
    cardinalities: list[Optional[float]] = field(default_factory=list)

    @property
    def cardinality(self):
        return self.cardinalities[0] if self.cardinalities else None

    def as_dict(self):
        return {
            "table": self.table,
            "name": self.name,
            "columns": list(self.columns),
            "unique": self.unique,
            "primary": self.primary,
            "cardinalities": list(self.cardinalities),
        }


@dataclass
class TableInfo:
    name: str
    row_count: Optional[float] = None
    columns: dict[str, ColumnInfo] = field(default_factory=dict)
    indexes: dict[str, IndexInfo] = field(default_factory=dict)


class SchemaModel:
    def __init__(self):
        self.tables: dict[str, TableInfo] = {}

    def add_table(self, table: TableInfo):
        self.tables[table.name.upper()] = table

    def get_table(self, name):
        if not name:
            return None
        return self.tables.get(name.upper())

    def has_table(self, name):
        return self.get_table(name) is not None

    def add_column(self, column: ColumnInfo):
        table = self.get_table(column.table)
        if table:
            table.columns[column.name.upper()] = column

    def get_column(self, table, column):
        table_info = self.get_table(table)
        if not table_info:
            return None
        return table_info.columns.get(column.upper())

    def column_info(self, table, column):
        item = self.get_column(table, column)
        if item is None:
            return None
        return item

    def has_column(self, table, column):
        return self.get_column(table, column) is not None

    def columns(self, table):
        table_info = self.get_table(table)
        return list(table_info.columns.values()) if table_info else []

    def add_index(self, index: IndexInfo):
        table = self.get_table(index.table)
        if table:
            table.indexes[index.name] = index

    def get_indexes(self, table):
        table_info = self.get_table(table)
        return list(table_info.indexes.values()) if table_info else []

    def index_definitions(self, table):
        return {index.name: index.as_dict() for index in self.get_indexes(table)}

    def indexed_columns(self, table):
        values = set()
        for index in self.get_indexes(table):
            values.update(index.columns)
        return values

    def indexes_leading_with(self, table, column):
        wanted = column.upper()
        result = []
        for index in self.get_indexes(table):
            if index.columns and index.columns[0].upper() == wanted:
                result.append(index.name)
        return result

    def has_index_on_column(self, table, column):
        return bool(self.indexes_leading_with(table, column))

    def row_count(self, table):
        table_info = self.get_table(table)
        return table_info.row_count if table_info else None
