def recommend_index(table_name, column_name):
    index_name = f"idx_{table_name}_{column_name}"

    return {
        "type": "INDEX",
        "message": f"Consider adding an index on {table_name}.{column_name}.",
        "sql": (
            f"CREATE INDEX {index_name} "
            f"ON {table_name}({column_name});"
        )
    }