from adapters.mysql import MySQLAdapter
from adapters.oracle import OracleAdapter
from adapters.postgres import PostgreSQLAdapter


def create_adapter(database_type, profile=None, password=None):
    normalized = database_type.strip().lower()
    if normalized == "postgresql":
        normalized = "postgres"

    mapping = {
        "oracle": OracleAdapter,
        "mysql": MySQLAdapter,
        "postgres": PostgreSQLAdapter,
    }

    adapter_cls = mapping.get(normalized)
    if adapter_cls is None:
        raise ValueError(f"Unsupported database: {database_type}")

    return adapter_cls(profile=profile, password=password)
