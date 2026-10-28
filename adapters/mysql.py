import re

from adapters.base import DatabaseAdapter, QueryResult
from core.plan_model import PlanModel, PlanNode
from core.schema_model import ColumnInfo, IndexInfo, SchemaModel, TableInfo
from database.db import get_connection


class MySQLAdapter(DatabaseAdapter):
    name = "MySQL"
    dialect = "mysql"

    def connect(self):
        return get_connection(profile=self.profile, password=self.password)

    def quote_identifier(self, name):
        return "`" + name.replace("`", "``") + "`"

    def sample_query(self, table, limit=500):
        return f"SELECT * FROM {self.quote_identifier(table)} LIMIT {int(limit)}"

    def get_schema(self):
        schema = SchemaModel()
        connection = self.connect()
        cursor = connection.cursor()
        db_name = self.profile.database
        try:
            cursor.execute("""
                SELECT table_name, table_rows
                FROM information_schema.tables
                WHERE table_schema = %s
                  AND table_type IN ('BASE TABLE', 'VIEW')
                ORDER BY table_name
            """, (db_name,))
            for table_name, row_count in cursor.fetchall():
                schema.add_table(TableInfo(name=table_name, row_count=float(row_count) if row_count is not None else None))

            cursor.execute("""
                SELECT table_name, column_name, data_type, is_nullable, collation_name
                FROM information_schema.columns
                WHERE table_schema = %s
                ORDER BY table_name, ordinal_position
            """, (db_name,))
            for table_name, column_name, data_type, nullable, collation in cursor.fetchall():
                if schema.get_table(table_name):
                    schema.add_column(ColumnInfo(
                        table=table_name,
                        name=column_name,
                        data_type=data_type,
                        nullable=(nullable == "YES"),
                        collation=collation,
                    ))

            cursor.execute("""
                SELECT table_name, index_name, non_unique, seq_in_index, column_name, cardinality
                FROM information_schema.statistics
                WHERE table_schema = %s
                ORDER BY table_name, index_name, seq_in_index
            """, (db_name,))
            for table_name, index_name, non_unique, seq_in_index, column_name, cardinality in cursor.fetchall():
                table = schema.get_table(table_name)
                if not table:
                    continue
                index = table.indexes.get(index_name)
                if index is None:
                    index = IndexInfo(
                        table=table_name,
                        name=index_name,
                        unique=(non_unique == 0),
                        primary=(index_name.upper() == "PRIMARY"),
                    )
                    table.indexes[index_name] = index
                index.columns.append(column_name)
                if seq_in_index == 1 and cardinality is not None:
                    try:
                        index.cardinalities.append(float(cardinality))
                    except (TypeError, ValueError):
                        pass
        finally:
            cursor.close()
            connection.close()
        return schema

    def explain(self, query):
        clean = query.strip().rstrip(";").strip()
        connection = self.connect()
        cursor = connection.cursor()
        try:
            cursor.execute("EXPLAIN " + clean)
            columns = [item[0] for item in cursor.description]
            rows = cursor.fetchall()
        finally:
            cursor.close()
            connection.close()

        result = PlanModel()
        positions = {name.lower(): idx for idx, name in enumerate(columns)}
        for raw in rows:
            row = dict(zip(columns, raw))
            table = row.get(columns[positions.get("table", -1)]) if "table" in positions else None
            access_type = str(row.get(columns[positions.get("type", -1)]) or "").lower() if "type" in positions else ""
            index_name = row.get(columns[positions.get("key", -1)]) if "key" in positions else None
            estimated_rows = row.get(columns[positions.get("rows", -1)]) if "rows" in positions else None
            extra = str(row.get(columns[positions.get("extra", -1)]) or "") if "extra" in positions else ""

            if access_type == "ALL":
                result.add(PlanNode("TABLE_SCAN", table=table, estimated_rows=_as_float(estimated_rows), details=extra))
            elif access_type in {"index", "index_merge"}:
                result.add(PlanNode("INDEX_SCAN", table=table, index=index_name, estimated_rows=_as_float(estimated_rows), details=extra))
            elif access_type in {"range", "ref", "eq_ref", "const", "system", "ref_or_null", "fulltext"}:
                result.add(PlanNode("INDEX_RANGE_SCAN", table=table, index=index_name, estimated_rows=_as_float(estimated_rows), details=extra))
            elif access_type:
                result.add(PlanNode("TABLE_SCAN", table=table, estimated_rows=_as_float(estimated_rows), details=extra))

            if "using filesort" in extra.lower():
                result.add(PlanNode("SORT_ORDER_BY", table=table, estimated_rows=_as_float(estimated_rows), details=extra))
            if "using temporary" in extra.lower():
                result.add(PlanNode("TEMPORARY", table=table, estimated_rows=_as_float(estimated_rows), details=extra))

        return result

    def execute(self, query):
        clean = query.strip().rstrip(";").strip()
        connection = self.connect()
        cursor = connection.cursor()
        try:
            cursor.execute(clean)
            columns = [item[0] for item in cursor.description] if cursor.description else []
            rows = cursor.fetchall() if cursor.description else []
            connection.commit()
            return QueryResult(columns=columns, rows=rows, rowcount=cursor.rowcount, message="Statement executed successfully.")
        finally:
            cursor.close()
            connection.close()


def _as_float(value):
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None
