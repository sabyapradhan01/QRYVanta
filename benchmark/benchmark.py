import re

from database.db import get_connection


QUERY = """
SELECT
    order_id,
    customer_id,
    total_amount
FROM orders
ORDER BY total_amount DESC;
"""

TABLE_NAME = "orders"
TABLE_ALIAS = "orders"
INDEX_NAME = "idx_orders_total_amount"
INDEX_COLUMN = "total_amount"

NUMBER_OF_RUNS = 5


def execute_explain_analyze(query):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("EXPLAIN ANALYZE " + query)

    result = cursor.fetchone()

    cursor.close()
    connection.close()

    return result[0]


def extract_cost(explain_text):
    match = re.search(
        r"cost=([0-9]+(?:\.[0-9]+)?)",
        explain_text
    )

    if match:
        return float(match.group(1))

    return None


def extract_actual_time(explain_text):
    matches = re.findall(
        r"actual time=([0-9]+(?:\.[0-9]+)?)\.\.([0-9]+(?:\.[0-9]+)?)",
        explain_text
    )

    if not matches:
        return None

    # Root node is the last node in the plan.
    _, final_time = matches[0]

    return float(final_time)


def extract_actual_rows(explain_text):
    matches = re.findall(
        r"actual time=[0-9]+(?:\.[0-9]+)?\.\.[0-9]+(?:\.[0-9]+)? "
        r"rows=([0-9]+)",
        explain_text
    )

    if matches:
        return int(matches[0])

    return None


def extract_access_method(explain_text, table_alias):
    """
    Detect the access method used for the specific
    table alias being benchmarked.
    """

    table_scan_pattern = f"Table scan on {table_alias}"

    index_lookup_pattern = f"Index lookup on {table_alias}"

    primary_lookup_pattern = (
        f"Single-row covering index lookup on {table_alias}"
    )

    if table_scan_pattern in explain_text:
        return "Table Scan"

    if index_lookup_pattern in explain_text:
        return "Index Lookup"

    if primary_lookup_pattern in explain_text:
        return "Primary Key / Covering Index Lookup"

    return "Other"


def drop_test_index():
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)

    cursor.execute(f"SHOW INDEX FROM {TABLE_NAME}")

    indexes = cursor.fetchall()

    index_exists = any(
        index["Key_name"] == INDEX_NAME
        for index in indexes
    )

    if index_exists:
        cursor.execute(
            f"DROP INDEX {INDEX_NAME} ON {TABLE_NAME}"
        )

        connection.commit()

        print("Test index removed.")
    else:
        print("Test index was not present.")

    cursor.close()
    connection.close()


def create_test_index():
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        f"""
        CREATE INDEX {INDEX_NAME}
        ON {TABLE_NAME}({INDEX_COLUMN})
            """
    )

    connection.commit()

    cursor.close()
    connection.close()

    print("Test index created.")


def benchmark_state(state_name):

    print(f"\nRunning {state_name}...")

    times = []
    costs = []
    rows = []
    methods = []

    for run in range(1, NUMBER_OF_RUNS + 1):

        plan = execute_explain_analyze(QUERY)

        execution_time = extract_actual_time(plan)
        cost = extract_cost(plan)
        actual_rows = extract_actual_rows(plan)
        access_method = extract_access_method(
        plan,
        TABLE_ALIAS
        )

        if execution_time is not None:
            times.append(execution_time)

        if cost is not None:
            costs.append(cost)

        if actual_rows is not None:
            rows.append(actual_rows)

        methods.append(access_method)

        print(
            f"Run {run}: "
            f"{execution_time} ms | "
            f"Cost: {cost} | "
            f"Rows: {actual_rows} | "
            f"Method: {access_method}"
        )

    average_time = sum(times) / len(times)
    average_cost = sum(costs) / len(costs)

    return {
        "times": times,
        "average_time": average_time,
        "average_cost": average_cost,
        "rows": rows[-1] if rows else None,
        "access_method": methods[-1]
    }


def run_benchmark():

    print("\n==========================================")
    print("SQL PERFORMANCE BENCHMARK")
    print("==========================================")

    # -----------------------------
    # BEFORE INDEX
    # -----------------------------

    drop_test_index()

    before = benchmark_state("BEFORE INDEX")

    # -----------------------------
    # AFTER INDEX
    # -----------------------------

    create_test_index()

    after = benchmark_state("AFTER INDEX")

    # -----------------------------
    # RESULTS
    # -----------------------------

    print("\n------------------------------------------")
    print("BEFORE INDEX")
    print("------------------------------------------")

    print(
        "Access Method:",
        before["access_method"]
    )

    print(
        "Average Cost:",
        round(before["average_cost"], 3)
    )

    print(
        "Average MySQL Execution Time:",
        round(before["average_time"], 3),
        "ms"
    )

    print(
        "Actual Rows:",
        before["rows"]
    )

    print(
        "Execution Times:",
        [round(t, 3) for t in before["times"]]
    )

    print("\n------------------------------------------")
    print("AFTER INDEX")
    print("------------------------------------------")

    print(
        "Access Method:",
        after["access_method"]
    )

    print(
        "Average Cost:",
        round(after["average_cost"], 3)
    )

    print(
        "Average MySQL Execution Time:",
        round(after["average_time"], 3),
        "ms"
    )

    print(
        "Actual Rows:",
        after["rows"]
    )

    print(
        "Execution Times:",
        [round(t, 3) for t in after["times"]]
    )

    # -----------------------------
    # COST COMPARISON
    # -----------------------------

    print("\n------------------------------------------")
    print("COMPARISON")
    print("------------------------------------------")

    cost_reduction = (
        (before["average_cost"] - after["average_cost"])
        / before["average_cost"]
    ) * 100

    print(
        "Estimated Cost Reduction:",
        round(cost_reduction, 2),
        "%"
    )

    # -----------------------------
    # EXECUTION TIME COMPARISON
    # -----------------------------

    time_change = (
        (before["average_time"] - after["average_time"])
        / before["average_time"]
    ) * 100

    print(
        "Execution Time Change:",
        round(time_change, 2),
        "%"
    )

    if time_change > 0:
        print("Observed Runtime Improvement: YES")
    else:
        print("Observed Runtime Improvement: NO")

    # -----------------------------
    # PLAN COMPARISON
    # -----------------------------

    plan_changed = (
        before["access_method"]
        != after["access_method"]
    )

    print(
        "Execution Plan Changed:",
        plan_changed
    )


if __name__ == "__main__":
    run_benchmark()