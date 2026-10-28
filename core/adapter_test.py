from adapters.oracle import OracleAdapter


adapter = OracleAdapter()

print(
    "Database:",
    adapter.name
)

schema = adapter.get_schema()

print(
    "Tables:"
)

for name in schema.tables:

    table = schema.tables[name]

    print(
        f"  {table.name} "
        f"({len(table.columns)} columns, "
        f"{len(table.indexes)} indexes)"
    )


plan = adapter.explain(
    "SELECT * FROM customer"
)

print()
print(
    "Normalized execution plan:"
)

for node in plan.nodes:

    print(
        f"  {node.operation}"
        f" | table={node.table}"
        f" | index={node.index}"
    )