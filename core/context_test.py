from adapters.oracle import OracleAdapter
from core.context_builder import build_query_context


adapter = OracleAdapter()

query = """
SELECT c.customer_id,
       c.customer_name
FROM customer c
WHERE c.status = 'ACTIVE'
ORDER BY c.customer_name;
"""


context = build_query_context(
    query,
    adapter
)


print()
print("DATABASE:")
print(context.database)

print()
print("TABLES:")
print(context.tables)

print()
print("WHERE PREDICATES:")
for predicate in context.where_predicates():
    print(predicate)

print()
print("SELECT COLUMNS:")
print(context.select_columns())

print()
print("JOIN PAIRS:")
print(context.join_pairs())

print()
print("ORDER BY:")
print(context.has_order_by())

print()
print("GROUP BY:")
print(context.has_group_by())

print()
print("CUSTOMER INDEXES:")
print(context.indexes("CUSTOMER"))

print()
print("NORMALIZED PLAN:")

for node in context.plan.nodes:

    print(
        f"{node.operation} "
        f"| table={node.table} "
        f"| index={node.index} "
        f"| rows={node.estimated_rows} "
        f"| cost={node.cost}"
    )