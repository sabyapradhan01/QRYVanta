from sqlglot import expressions as exp


MIN_LARGE_TABLE_ROWS = 1000
LARGE_ROWS = 10000
INDEX_FRACTION_THRESHOLD = 0.30
ROW_EXPLOSION_FACTOR = 2.0
LOW_CARDINALITY_MAX_DISTINCT = 10
COVERING_MIN_ROWS = 1000
COVERING_MAX_COLUMNS = 4
HEAVY_TYPES = {
    "text", "mediumtext", "longtext", "tinytext",
    "blob", "mediumblob", "longblob", "tinyblob",
    "json", "jsonb", "bytea", "xml", "clob", "nclob", "raw",
}
STRING_TYPES = {
    "char", "varchar", "varchar2", "nvarchar", "nvarchar2", "nchar",
    "text", "tinytext", "mediumtext", "longtext",
    "character varying", "character",
}


def _finding(rule_id, severity, message, explanation, recommendation):
    return {
        "rule_id": rule_id,
        "severity": severity,
        "message": message,
        "explanation": explanation,
        "recommendation": recommendation,
    }


def _numeric_literal(node):
    if isinstance(node, exp.Neg):
        node = node.this
    return isinstance(node, exp.Literal) and not node.is_string


# P001
def check_full_table_scan(context):
    scans = context.plan.table_scans()
    if not scans:
        return None
    tables = sorted({node.table.upper() for node in scans if node.table})
    target = ", ".join(tables)
    return _finding(
        "P001", "High",
        f"Full table scan detected{f' on {target}' if target else ''}.",
        "The execution plan contains a table-scan operation instead of an index access path.",
        "Check whether a selective filter or join column can be supported by an appropriate index, then validate the plan.",
    )


# P002
def check_missing_filter_index(context):
    if not context.has_where():
        return None
    for p in context.bare_filters():
        table, column = p["table"], p["column"]
        if not context.has_table_scan(table) or context.has_index(table, column):
            continue
        return _finding(
            "P002", "High",
            f"Filtered table '{table}' is scanned without an index on '{column}'.",
            f"The query filters {table}.{column}, but the plan scans the table and no leading index exists on that column.",
            f"Consider adding an index on {table}.{column}, then validate the execution plan and write overhead.",
        )
    return None


# P003
def check_expensive_sort(context):
    if not context.plan.sorts():
        return None
    return _finding(
        "P003", "Medium",
        "Explicit sort operation detected.",
        "The execution plan contains a sort operation, which requires additional CPU and memory work.",
        "Check whether an index aligned with ORDER BY or GROUP BY can provide rows in the required order.",
    )


# P004
def check_unrestricted_large_scan(context):
    if context.has_where():
        return None
    for node in context.plan.table_scans():
        rows = node.estimated_rows
        if rows is None and node.table:
            rows = context.table_row_count(node.table)
        if rows is not None and rows >= LARGE_ROWS:
            return _finding(
                "P004", "High",
                "Large unrestricted table scan detected.",
                f"The statement has no WHERE condition and the plan estimates about {int(rows)} rows for a table scan.",
                "Add a selective filter when the application does not need the entire table.",
            )
    return None


# P005
def check_non_sargable_filter(context):
    for p in context.where_predicates():
        if p.get("wrapped"):
            location = f"{p['table']}.{p['column']}" if p.get("table") else p["column"]
            return _finding(
                "P005", "Medium",
                "Non-SARGable filter detected.",
                f"A function or arithmetic expression is applied around {location} in WHERE, which may reduce normal index usability.",
                "Rewrite the predicate so the indexed column is not wrapped when possible; consider an expression/function-based index when necessary.",
            )
    return None


# P006
def check_unindexed_join(context):
    if not context.join_pairs() or not context.plan.joins():
        return None
    for lt, lc, rt, rc in context.join_pairs():
        for table, column, other in ((lt, lc, rt), (rt, rc, lt)):
            if not context.has_table_scan(table):
                continue
            if context.has_index(table, column):
                continue
            return _finding(
                "P006", "Medium",
                f"JOIN column '{table}.{column}' has no supporting index.",
                f"The query joins {lt}.{lc} with {rt}.{rc}, while the plan scans {table} and no leading index exists on {table}.{column}.",
                f"Consider an index on {table}.{column}; validate selectivity and write overhead before keeping it.",
            )
    return None


# P007
def check_nested_loop_table_scan(context):
    if not context.plan.joins() or not context.plan.table_scans():
        return None
    if any(node.operation in {"NESTED_LOOPS", "NESTED_LOOP_JOIN"} for node in context.plan.nodes):
        return _finding(
            "P007", "Medium",
            "Nested-loop JOIN with table scan detected.",
            "The plan combines a nested-loop join with a table scan; this can become expensive when the scanned side is large.",
            "Check whether an index can improve access to the scanned join input and validate row estimates.",
        )
    return None


# P008
def check_implicit_type_conversion(context):
    for p in context.bare_filters({"EQ", "NEQ", "GT", "GTE", "LT", "LTE"}):
        if not _numeric_literal(p.get("other")):
            continue
        info = context.column_info(p["table"], p["column"])
        if not info or str(info.data_type).lower() not in STRING_TYPES:
            continue
        return _finding(
            "P008", "Medium",
            f"Implicit type conversion on {p['table']}.{p['column']}.",
            f"The column is {info.data_type} but is compared to a numeric literal, forcing a type conversion at comparison time.",
            "Use a string literal for a string column, for example column = '123', unless the numeric conversion is intentional.",
        )
    return None


# P009
def check_redundant_index(context):
    for table in context.tables:
        defs = context.indexes(table)
        names = sorted(defs)
        for a in names:
            if defs[a]["primary"] or defs[a]["unique"]:
                continue
            ca = defs[a]["columns"]
            for b in names:
                if a == b:
                    continue
                cb = defs[b]["columns"]
                if len(ca) <= len(cb) and cb[:len(ca)] == ca:
                    return _finding(
                        "P009", "Low",
                        f"Potentially redundant index '{a}' on table '{table}'.",
                        f"Index {a} ({', '.join(ca)}) is a left-prefix of {b} ({', '.join(cb)}), so the longer index may already support the shorter access path.",
                        "Validate real workload, constraints, and write cost before removing the shorter index.",
                    )
    return None


# P010
def check_composite_index_leading_column(context):
    filtered = {}
    for p in context.bare_filters():
        filtered.setdefault(p["table"], set()).add(p["column"].upper())
    for table, columns in filtered.items():
        for name, definition in context.indexes(table).items():
            idx_cols = [str(c).upper() for c in definition["columns"]]
            if len(idx_cols) < 2:
                continue
            if idx_cols[0] not in columns and any(col in columns for col in idx_cols[1:]):
                return _finding(
                    "P010", "Medium",
                    f"Composite index '{name}' is being filtered without its leading column.",
                    f"The query filters a non-leading column of {name} ({', '.join(idx_cols)}), so the normal B-tree seek cannot start from that column.",
                    f"Add a predicate on {idx_cols[0]} when appropriate, or consider a separate/composite index whose leading column matches the workload.",
                )
    return None


# P011
def check_covering_index_opportunity(context):
    if not context.tables or context.select_star_tables():
        return None
    if context.table_row_count(context.tables[0]) is not None and context.table_row_count(context.tables[0]) < COVERING_MIN_ROWS:
        return None
    selected = context.select_columns()
    filters = context.bare_filters()
    if not selected or not filters:
        return None
    for table in {t for t, _ in selected}:
        needed = {column.upper() for t, column in selected if t == table}
        needed.update(p["column"].upper() for p in filters if p["table"] == table)
        if not needed or len(needed) > COVERING_MAX_COLUMNS:
            continue
        indexes = context.indexes(table)
        if any(needed.issubset({c.upper() for c in d["columns"]}) for d in indexes.values()):
            continue
        return _finding(
            "P011", "Low",
            f"Covering-index opportunity detected on '{table}'.",
            f"The query selects a small set of columns and filters the same table, but no existing index covers the referenced columns.",
            f"Consider a carefully chosen covering index for the filter plus projected columns, after validating size and write overhead.",
        )
    return None


# P012
def check_group_by_index(context):
    if not context.has_group_by():
        return None
    group_cols = []
    for group in context.group.expressions if hasattr(context.group, "expressions") else []:
        for col in group.find_all(exp.Column):
            table = context.resolve_table(col)
            if table:
                group_cols.append((table, col.name.upper()))
    if not group_cols:
        return None
    for table, column in group_cols:
        if context.indexes_leading_with(table, column):
            continue
        if context.plan.has_operation("SORT_GROUP_BY") or context.plan.sorts():
            return _finding(
                "P012", "Medium",
                f"GROUP BY lacks a supporting leading index on {table}.{column}.",
                "The query groups by a column without a matching leading index and the plan contains a sort/grouping operation.",
                f"Consider an index starting with {table}.{column} when grouping performance justifies its storage and write cost.",
            )
    return None


# P013
def check_heavy_column_without_limit(context):
    if context.has_limit() or not context.select:
        return None
    for table, column in context.select_columns():
        info = context.column_info(table, column)
        if info and str(info.data_type).lower() in HEAVY_TYPES:
            return _finding(
                "P013", "Medium",
                f"Heavy column '{table}.{column}' fetched without LIMIT.",
                f"The statement selects a {info.data_type} column without a result-size limit, which can create large I/O and transfer costs.",
                "Select the heavy column only when needed, paginate the result, or fetch it separately from the lightweight row metadata.",
            )
    return None


# P014
def check_update_index_rewrite(context):
    update = context.tree.find(exp.Update)
    if not update:
        return None
    table = update.this.name if isinstance(update.this, exp.Table) else None
    if not table:
        return None
    expressions = update.args.get("expressions") or []
    indexed = {c.upper() for c in context.indexed_columns(table)}
    changed = []
    for assignment in expressions:
        left = getattr(assignment, "this", None)
        if isinstance(left, exp.Column) and left.name.upper() in indexed:
            changed.append(left.name)
    if changed:
        return _finding(
            "P014", "Medium",
            f"UPDATE modifies indexed column(s): {', '.join(sorted(set(changed)))}.",
            "Changing indexed values requires the database to maintain the corresponding index entries, increasing write amplification.",
            "Only index columns that materially support reads; avoid unnecessary indexed updates in high-write workloads.",
        )
    return None


# P015
def check_join_type_mismatch(context):
    for lt, lc, rt, rc in context.join_pairs():
        left = context.column_info(lt, lc)
        right = context.column_info(rt, rc)
        if not left or not right:
            continue
        type_mismatch = str(left.data_type).lower() != str(right.data_type).lower()
        left_coll = (left.collation or "").lower()
        right_coll = (right.collation or "").lower()
        coll_mismatch = left_coll and right_coll and left_coll != right_coll
        if type_mismatch or coll_mismatch:
            evidence = []
            if type_mismatch:
                evidence.append(f"types {left.data_type} vs {right.data_type}")
            if coll_mismatch:
                evidence.append(f"collations {left.collation} vs {right.collation}")
            return _finding(
                "P015", "High",
                f"JOIN column mismatch: {lt}.{lc} ↔ {rt}.{rc}.",
                "Joined columns use different type or collation metadata, which may require conversions and reduce efficient index matching.",
                "Align the join-column definitions where semantically appropriate and validate the execution plan.",
            )
    return None


# P016
def check_index_not_used(context):
    for p in context.bare_filters():
        leading = context.indexes_leading_with(p["table"], p["column"])
        if leading and context.has_table_scan(p["table"]):
            return _finding(
                "P016", "Medium",
                f"Index exists but is not used for {p['table']}.{p['column']}.",
                f"Index '{leading[0]}' leads with the filtered column, yet the normalized plan still contains a table scan.",
                "Check selectivity, statistics, type/collation consistency, and planner choices before adding another index.",
            )
    return None


# P017
def check_join_row_explosion(context):
    if not context.plan.joins():
        return None
    child_rows = [n.estimated_rows for n in context.plan.nodes if n.estimated_rows is not None and n.table]
    if len(child_rows) < 2:
        return None
    max_child = max(child_rows)
    for join in context.plan.joins():
        if join.estimated_rows is not None and max_child > 0 and join.estimated_rows >= max(LARGE_ROWS, max_child * ROW_EXPLOSION_FACTOR):
            return _finding(
                "P017", "High",
                "JOIN row explosion detected in the execution plan.",
                f"The estimated join output ({int(join.estimated_rows)}) is much larger than the largest child estimate ({int(max_child)}), indicating a potentially multiplicative join result.",
                "Verify join predicates, relationship cardinalities, and filters; avoid accidental many-to-many joins when they are not required.",
            )
    return None


# P018
def check_large_sort_without_limit(context):
    if context.has_limit():
        return None
    for node in context.plan.sorts():
        if node.estimated_rows is not None and node.estimated_rows >= LARGE_ROWS:
            return _finding(
                "P018", "High",
                "Large sort detected without a result limit.",
                f"The plan sorts an estimated {int(node.estimated_rows)} rows and the statement has no LIMIT/FETCH restriction.",
                "Add a deterministic result limit when the application does not require all rows, or support the order with a suitable index.",
            )
    return None


# P019
def check_temporary_materialization(context):
    if context.plan.temporary_operations():
        return _finding(
            "P019", "Medium",
            "Temporary table/materialization operation detected.",
            "The execution plan contains an intermediate temporary/materialized result, which can add memory, I/O, and CPU overhead.",
            "Inspect GROUP BY, DISTINCT, ORDER BY, CTEs, and derived tables; simplify the query or add supporting indexes when appropriate.",
        )
    return None


# P020
def check_large_index_read(context):
    for node in context.plan.index_scans():
        if not node.table or node.estimated_rows is None:
            continue
        total = context.table_row_count(node.table)
        if not total or total <= 0:
            continue
        if node.estimated_rows / total >= 0.30:
            return _finding(
                "P020", "Medium",
                f"Index access is expected to read at least 30% of '{node.table}'.",
                f"The index operation estimates {int(node.estimated_rows)} rows from a table of about {int(total)} rows, reducing the benefit of random index access.",
                "Validate selectivity and consider whether a table scan or a more selective composite index is actually better.",
            )
    return None


# P021
def check_low_selectivity_index(context):
    if not context.has_where():
        return None
    for p in context.bare_filters({"EQ"}):
        total = context.table_row_count(p["table"])
        if not total or total < MIN_LARGE_TABLE_ROWS:
            continue
        for name, definition in context.indexes(p["table"]).items():
            if not definition["columns"] or definition["columns"][0].upper() != p["column"].upper():
                continue
            cardinality = definition["cardinalities"][0] if definition["cardinalities"] else None
            if cardinality is not None and cardinality <= LOW_CARDINALITY_MAX_DISTINCT:
                return _finding(
                    "P021", "Medium",
                    f"Low-selectivity index on {p['table']}.{p['column']}.",
                    f"Index '{name}' has only about {int(cardinality)} distinct leading values over roughly {int(total)} rows.",
                    "Do not rely on the low-cardinality index alone; consider a more selective composite index or allow a scan when it is cheaper.",
                )
    return None


# P022
def check_indexed_function_table_scan(context):
    for p in context.where_predicates():
        if not p.get("wrapped") or not context.has_index(p["table"], p["column"]):
            continue
        if context.has_table_scan(p["table"]):
            return _finding(
                "P022", "High",
                f"Function on indexed column '{p['table']}.{p['column']}' is associated with a table scan.",
                "The WHERE predicate wraps an indexed column in a function or expression and the plan contains a table scan, confirming the index is not providing the expected access path.",
                "Rewrite the predicate to leave the column bare where possible, or use the database's expression/function-based index feature when appropriate.",
            )
    return None
