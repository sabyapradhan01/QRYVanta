import sqlglot

from core.plan_model import PlanModel
from core.query_context import QueryContext
from core.schema_model import SchemaModel


DIALECTS = {
    "oracle": "oracle",
    "mysql": "mysql",
    "postgres": "postgres",
    "postgresql": "postgres",
    "sqlite": "sqlite",
    "sqlserver": "tsql",
    "mssql": "tsql",
}


def build_query_context(query, adapter):
    dialect = getattr(adapter, "dialect", "") or DIALECTS.get(adapter.name.lower(), "")
    tree = sqlglot.parse_one(query, read=dialect) if dialect else sqlglot.parse_one(query)

    try:
        schema = adapter.get_schema()
    except Exception:
        schema = SchemaModel()

    try:
        plan = adapter.explain(query)
    except Exception:
        plan = PlanModel()

    return QueryContext(
        query=query,
        tree=tree,
        database=adapter.name,
        schema=schema,
        plan=plan,
    )
