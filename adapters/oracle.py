from adapters.base import DatabaseAdapter, QueryResult
from core.plan_model import PlanModel, PlanNode
from core.schema_model import ColumnInfo, IndexInfo, SchemaModel, TableInfo
from database.db import get_connection


class OracleAdapter(DatabaseAdapter):
    name = "Oracle"
    dialect = "oracle"

    def connect(self):
        return get_connection(profile=self.profile, password=self.password)

    def quote_identifier(self, name):
        return '"' + name.replace('"', '""') + '"'

    def sample_query(self, table, limit=500):
        safe = self.quote_identifier(table)
        return f"SELECT * FROM {safe} WHERE ROWNUM <= {int(limit)}"

    def get_schema(self):
        schema = SchemaModel()
        connection = self.connect()
        cursor = connection.cursor()
        try:
            cursor.execute("""
                SELECT table_name, num_rows
                FROM user_tables
                ORDER BY table_name
            """)
            for table_name, num_rows in cursor.fetchall():
                schema.add_table(TableInfo(name=table_name, row_count=num_rows))

            cursor.execute("""
                SELECT table_name, column_name, data_type, nullable
                FROM user_tab_columns
                ORDER BY table_name, column_id
            """)
            for table_name, column_name, data_type, nullable in cursor.fetchall():
                if schema.get_table(table_name):
                    schema.add_column(ColumnInfo(
                        table=table_name,
                        name=column_name,
                        data_type=data_type,
                        nullable=(nullable == "Y"),
                    ))

            cursor.execute("""
                SELECT
                    ic.table_name,
                    ic.index_name,
                    ic.column_name,
                    ic.column_position,
                    ui.uniqueness,
                    ui.distinct_keys
                FROM user_ind_columns ic
                JOIN user_indexes ui
                  ON ui.index_name = ic.index_name
                ORDER BY ic.table_name, ic.index_name, ic.column_position
            """)
            for table_name, index_name, column_name, position, uniqueness, distinct_keys in cursor.fetchall():
                table = schema.get_table(table_name)
                if not table:
                    continue
                index = table.indexes.get(index_name)
                if index is None:
                    index = IndexInfo(
                        table=table_name,
                        name=index_name,
                        unique=(uniqueness == "UNIQUE"),
                    )
                    table.indexes[index_name] = index
                index.columns.append(column_name)
                if distinct_keys is not None and position == 1:
                    index.cardinalities.append(float(distinct_keys))

            cursor.execute("""
                SELECT uc.table_name, uic.index_name
                FROM user_constraints uc
                LEFT JOIN user_indexes uic
                  ON uc.index_name = uic.index_name
                WHERE uc.constraint_type = 'P'
            """)
            for table_name, index_name in cursor.fetchall():
                if index_name and schema.get_table(table_name):
                    index = schema.get_table(table_name).indexes.get(index_name)
                    if index:
                        index.primary = True
        finally:
            cursor.close()
            connection.close()
        return schema

    def explain(self, query):
        clean = query.strip().rstrip(";").strip()
        connection = self.connect()
        cursor = connection.cursor()
        try:
            cursor.execute("EXPLAIN PLAN FOR " + clean)
            cursor.execute("SELECT PLAN_TABLE_OUTPUT FROM TABLE(DBMS_XPLAN.DISPLAY())")
            rows = cursor.fetchall()
        finally:
            cursor.close()
            connection.close()
        return self.parse_plan(rows)

    def parse_plan(self, rows):
        plan = PlanModel()
        for row in rows:
            if not row:
                continue
            text = str(row[0]).strip()
            if not text or "|" not in text:
                continue
            parts = [part.strip() for part in text.strip("|").split("|")]
            if len(parts) < 3:
                continue
            id_text = parts[0].lstrip("*").strip()
            if not id_text.isdigit():
                continue
            operation = parts[1].strip()
            table = parts[2].strip() or None
            try:
                estimated_rows = float(parts[3].replace(",", "")) if len(parts) >= 4 else None
            except ValueError:
                estimated_rows = None
            try:
                cost = float(parts[5].split()[0].replace(",", "")) if len(parts) >= 6 else None
            except (ValueError, IndexError):
                cost = None

            upper = operation.upper()
            node = None
            if "TABLE ACCESS FULL" in upper:
                node = PlanNode("TABLE_SCAN", table=table, estimated_rows=estimated_rows, cost=cost, depth=int(id_text), details=text)
            elif "TABLE ACCESS BY INDEX ROWID" in upper:
                node = PlanNode("TABLE_ACCESS_BY_INDEX", table=table, estimated_rows=estimated_rows, cost=cost, depth=int(id_text), details=text)
            elif "INDEX RANGE SCAN" in upper:
                node = PlanNode("INDEX_RANGE_SCAN", index=table, estimated_rows=estimated_rows, cost=cost, depth=int(id_text), details=text)
            elif "INDEX UNIQUE SCAN" in upper:
                node = PlanNode("INDEX_LOOKUP", index=table, estimated_rows=estimated_rows, cost=cost, depth=int(id_text), details=text)
            elif "INDEX FULL SCAN" in upper:
                node = PlanNode("INDEX_SCAN", index=table, estimated_rows=estimated_rows, cost=cost, depth=int(id_text), details=text)
            elif "NESTED LOOPS" in upper:
                node = PlanNode("NESTED_LOOPS", estimated_rows=estimated_rows, cost=cost, depth=int(id_text), details=text)
            elif "HASH JOIN" in upper:
                node = PlanNode("HASH_JOIN", estimated_rows=estimated_rows, cost=cost, depth=int(id_text), details=text)
            elif "MERGE JOIN" in upper:
                node = PlanNode("MERGE_JOIN", estimated_rows=estimated_rows, cost=cost, depth=int(id_text), details=text)
            elif "SORT ORDER BY" in upper:
                node = PlanNode("SORT_ORDER_BY", estimated_rows=estimated_rows, cost=cost, depth=int(id_text), details=text)
            elif "SORT GROUP BY" in upper:
                node = PlanNode("SORT_GROUP_BY", estimated_rows=estimated_rows, cost=cost, depth=int(id_text), details=text)
            elif any(token in upper for token in ("TEMP TABLE", "TEMPORARY", "MATERIALIZE")):
                node = PlanNode("TEMPORARY", estimated_rows=estimated_rows, cost=cost, depth=int(id_text), details=text)
            if node:
                plan.add(node)
        return plan

    def execute(self, query):
        clean = query.strip().rstrip(";").strip()
        connection = self.connect()
        cursor = connection.cursor()
        try:
            cursor.execute(clean)
            columns = [item[0] for item in cursor.description] if cursor.description else []
            rows = cursor.fetchall() if cursor.description else []
            if cursor.description is None:
                connection.commit()
            return QueryResult(columns=columns, rows=rows, rowcount=cursor.rowcount, message="Statement executed successfully.")
        finally:
            cursor.close()
            connection.close()
