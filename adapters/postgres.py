import json

from adapters.base import DatabaseAdapter, QueryResult
from core.plan_model import PlanModel, PlanNode
from core.schema_model import ColumnInfo, IndexInfo, SchemaModel, TableInfo
from database.db import get_connection


class PostgreSQLAdapter(DatabaseAdapter):
    name = "PostgreSQL"
    dialect = "postgres"

    def connect(self):
        return get_connection(profile=self.profile, password=self.password)

    def quote_identifier(self, name):
        return '"' + name.replace('"', '""') + '"'

    def sample_query(self, table, limit=500):
        """Build a sample query using PostgreSQL's actual table name.

        Schema metadata may normalize table labels for display (for example,
        ``customer`` to ``CUSTOMER``). PostgreSQL treats quoted identifiers as
        case-sensitive, so quoting that display label can point to a different
        relation. Resolve the real catalog name first, preferring an exact
        match and then a case-insensitive match.
        """
        requested = str(table)
        connection = self.connect()
        cursor = connection.cursor()
        actual_name = None
        try:
            cursor.execute(
                """
                SELECT c.relname
                FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = current_schema()
                  AND c.relkind IN ('r', 'p', 'v', 'm')
                  AND lower(c.relname) = lower(%s)
                ORDER BY CASE WHEN c.relname = %s THEN 0 ELSE 1 END
                LIMIT 1
                """,
                (requested, requested),
            )
            row = cursor.fetchone()
            if row:
                actual_name = row[0]
        finally:
            cursor.close()
            connection.close()

        if actual_name is None:
            raise ValueError(
                f"Table '{requested}' was not found in PostgreSQL schema "
                f"'{self.profile.schema or 'public'}'."
            )

        return f"SELECT * FROM {self.quote_identifier(actual_name)} LIMIT {int(limit)}"

    def get_schema(self):
        schema = SchemaModel()
        connection = self.connect()
        cursor = connection.cursor()
        try:
            cursor.execute("""
                SELECT c.relname, c.reltuples::bigint
                FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = current_schema()
                  AND c.relkind IN ('r', 'p', 'v', 'm')
                ORDER BY c.relname
            """)
            for table_name, row_count in cursor.fetchall():
                schema.add_table(TableInfo(
                    name=table_name,
                    row_count=float(row_count) if row_count is not None and row_count >= 0 else None,
                ))

            cursor.execute("""
                SELECT table_name, column_name, data_type, is_nullable, collation_name
                FROM information_schema.columns
                WHERE table_schema = current_schema()
                ORDER BY table_name, ordinal_position
            """)
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
                SELECT
                    t.relname AS table_name,
                    i.relname AS index_name,
                    ix.indisunique,
                    ix.indisprimary,
                    pg_get_indexdef(ix.indexrelid)
                FROM pg_index ix
                JOIN pg_class t ON t.oid = ix.indrelid
                JOIN pg_class i ON i.oid = ix.indexrelid
                JOIN pg_namespace n ON n.oid = t.relnamespace
                WHERE n.nspname = current_schema()
                ORDER BY t.relname, i.relname
            """)
            for table_name, index_name, unique, primary, indexdef in cursor.fetchall():
                table = schema.get_table(table_name)
                if not table:
                    continue
                index = IndexInfo(
                    table=table_name,
                    name=index_name,
                    unique=bool(unique),
                    primary=bool(primary),
                )
                index.columns = _parse_index_columns(indexdef)
                table.indexes[index_name] = index
        finally:
            cursor.close()
            connection.close()
        return schema

    def explain(self, query):
        clean = query.strip().rstrip(";").strip()
        connection = self.connect()
        cursor = connection.cursor()
        try:
            cursor.execute("EXPLAIN (FORMAT JSON) " + clean)
            row = cursor.fetchone()
        finally:
            cursor.close()
            connection.close()

        if not row:
            return PlanModel()

        payload = row[0]
        if isinstance(payload, str):
            payload = json.loads(payload)
        if isinstance(payload, list):
            payload = payload[0] if payload else {}
        root = payload.get("Plan", {}) if isinstance(payload, dict) else {}
        return _parse_plan(root)

    def execute(self, query):
        clean = query.strip().rstrip(";").strip()
        connection = self.connect()
        cursor = connection.cursor()
        try:
            cursor.execute(clean)
            columns = [item.name for item in cursor.description] if cursor.description else []
            rows = cursor.fetchall() if cursor.description else []
            connection.commit()
            return QueryResult(columns=columns, rows=rows, rowcount=cursor.rowcount, message="Statement executed successfully.")
        finally:
            cursor.close()
            connection.close()


def _parse_index_columns(indexdef):
    if not indexdef:
        return []
    try:
        body = indexdef.split("(", 1)[1].rsplit(")", 1)[0]
    except IndexError:
        return []
    columns = []
    for raw in body.split(","):
        token = raw.strip()
        token = token.split()[0]
        token = token.strip('"')
        if token:
            columns.append(token)
    return columns


def _parse_plan(node, model=None):
    model = model or PlanModel()
    if not node:
        return model

    kind = str(node.get("Node Type", ""))
    relation = node.get("Relation Name")
    index = node.get("Index Name")
    rows = _as_float(node.get("Plan Rows"))
    cost = _as_float(node.get("Total Cost"))

    mapping = {
        "Seq Scan": "TABLE_SCAN",
        "Index Scan": "INDEX_LOOKUP",
        "Index Only Scan": "INDEX_LOOKUP",
        "Bitmap Heap Scan": "TABLE_ACCESS_BY_INDEX",
        "Bitmap Index Scan": "INDEX_RANGE_SCAN",
        "Nested Loop": "NESTED_LOOPS",
        "Hash Join": "HASH_JOIN",
        "Merge Join": "MERGE_JOIN",
        "Sort": "SORT_ORDER_BY",
        "Materialize": "TEMPORARY",
    }
    operation = mapping.get(kind)
    if operation:
        model.add(PlanNode(
            operation=operation,
            table=relation,
            index=index,
            estimated_rows=rows,
            cost=cost,
            details=kind,
        ))

    for child in node.get("Plans", []) or []:
        _parse_plan(child, model)
    return model


def _as_float(value):
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None
