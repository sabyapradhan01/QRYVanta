from sqlglot import expressions as exp


# ============================================================
# HELPERS
# ============================================================

def _finding(
    rule_id,
    severity,
    message,
    explanation,
    recommendation
):
    return {
        "rule_id": rule_id,
        "severity": severity,
        "message": message,
        "explanation": explanation,
        "recommendation": recommendation,
    }


def _top_select(tree):
    if isinstance(tree, exp.Select):
        return tree

    return tree.find(exp.Select)


def _dialect_name(dialect):
    if not dialect:
        return "generic"

    dialect = dialect.lower().strip()

    aliases = {
        "postgres": "postgresql",
        "pg": "postgresql",
        "mssql": "sqlserver",
        "tsql": "sqlserver",
    }

    return aliases.get(dialect, dialect)


def _from_clause(select):
    if not select:
        return None

    return (
        select.args.get("from")
        or select.args.get("from_")
    )


# ============================================================
# SQL001 — SELECT *
# ============================================================

def check_select_star(tree):
    """
    Detect SELECT * but not COUNT(*), SUM(*), etc.
    """

    select = tree.find(exp.Select)

    if not select:
        return None

    for expression in select.expressions:
        if isinstance(expression, exp.Star):
            return {
                "rule_id": "SQL001",
                "severity": "Medium",
                "message": "SELECT * detected.",
                "explanation": (
                    "Selecting all columns may retrieve "
                    "unnecessary data."
                ),
                "recommendation": (
                    "Specify only the columns required by "
                    "the query."
                )
            }

    return None


# ============================================================
# SQL002 — UPDATE WITHOUT WHERE
# ============================================================

def check_update_without_where(tree):
    """
    Detect UPDATE statements without a WHERE clause.
    """

    if tree.find(exp.Update):

        if not tree.find(exp.Where):
            return {
                "rule_id": "SQL002",
                "severity": "High",
                "message": (
                    "UPDATE statement without WHERE detected."
                ),
                "explanation": (
                    "An UPDATE statement without a WHERE clause "
                    "can modify every row in the table."
                ),
                "recommendation": (
                    "Add an appropriate WHERE condition to "
                    "restrict the rows being updated."
                )
            }

    return None


# ============================================================
# SQL003 — DELETE WITHOUT WHERE
# ============================================================

def check_delete_without_where(tree):
    """
    Detect DELETE statements without a WHERE clause.
    """

    if tree.find(exp.Delete):

        if not tree.find(exp.Where):
            return {
                "rule_id": "SQL003",
                "severity": "High",
                "message": (
                    "DELETE statement without WHERE detected."
                ),
                "explanation": (
                    "A DELETE statement without a WHERE clause "
                    "can remove every row from the table."
                ),
                "recommendation": (
                    "Add an appropriate WHERE condition to "
                    "restrict the rows being deleted."
                )
            }

    return None


# ============================================================
# SQL004 — NON-SARGABLE FILTER
# ============================================================

def check_non_sargable_filter(tree):
    """
    Detect functions applied directly to columns
    in the WHERE clause.
    """

    where = tree.find(exp.Where)

    if not where:
        return None

    where_text = str(where.this).upper()

    non_sargable_functions = [
        "YEAR(",
        "MONTH(",
        "DAY(",
        "UPPER(",
        "LOWER(",
        "DATE(",
        "CAST(",
        "TRUNC(",
        "TO_CHAR(",
        "TO_DATE(",
        "TO_NUMBER(",
        "NVL("
    ]

    for function in non_sargable_functions:

        if function in where_text:
            return {
                "rule_id": "SQL004",
                "severity": "Medium",
                "message": (
                    "Non-SARGable filter detected."
                ),
                "explanation": (
                    "A function is applied directly to a column "
                    "in the WHERE clause, which may reduce the "
                    "effectiveness of indexing."
                ),
                "recommendation": (
                    "Rewrite the condition so the column is not "
                    "wrapped in a function, when possible."
                )
            }

    return None


# ============================================================
# SQL005 — SELECT WITHOUT WHERE
# ============================================================

def check_select_without_where(tree):
    """
    Detect broad SELECT statements without a WHERE clause.
    """

    select = tree.find(exp.Select)

    if not select:
        return None

    if tree.find(exp.Where):
        return None

    aggregate_functions = [
        exp.Count,
        exp.Sum,
        exp.Avg,
        exp.Min,
        exp.Max
    ]

    for function_type in aggregate_functions:
        if tree.find(function_type):
            return None

    if tree.find(exp.Group):
        return None

    return {
        "rule_id": "SQL005",
        "severity": "Low",
        "message": (
            "SELECT statement without WHERE detected."
        ),
        "explanation": (
            "The query does not contain a WHERE condition, "
            "so it may read a large number of rows."
        ),
        "recommendation": (
            "Add a WHERE condition when the application "
            "does not require all rows."
        )
    }


# ============================================================
# SQL006 — LEADING WILDCARD LIKE
# ============================================================

def check_leading_wildcard_like(
    tree,
    dialect="generic"
):
    """
    Detect LIKE patterns beginning with % or _.
    """

    for like in tree.find_all(exp.Like):

        pattern = like.expression

        if not (
            isinstance(pattern, exp.Literal)
            and pattern.is_string
        ):
            continue

        value = str(pattern.this)

        if (
            value.startswith("%")
            or value.startswith("_")
        ):
            return _finding(
                "SQL006",
                "Medium",
                "LIKE pattern starts with a wildcard.",
                (
                    "A leading wildcard prevents a normal "
                    "B-tree index from efficiently seeking "
                    "to the beginning of the search range."
                ),
                (
                    "Prefer prefix matching such as 'abc%' "
                    "when possible, or use an appropriate "
                    "full-text/search strategy."
                ),
            )

    return None


# ============================================================
# SQL007 — NOT IN SUBQUERY
# ============================================================

def check_not_in_subquery(
    tree,
    dialect="generic"
):
    """
    Detect NOT IN containing a subquery.
    """

    for node in tree.find_all(exp.Not):

        inner = node.this

        if not isinstance(inner, exp.In):
            continue

        if not inner.args.get("query"):
            continue

        return _finding(
            "SQL007",
            "High",
            "NOT IN with a subquery detected.",
            (
                "If the subquery can return NULL, SQL's "
                "three-valued logic can make NOT IN produce "
                "unexpected results."
            ),
            (
                "Consider NOT EXISTS or another equivalent "
                "anti-join and verify the execution plan."
            ),
        )

    return None


# ============================================================
# SQL008 — LARGE OFFSET
# ============================================================

def check_large_offset(
    tree,
    dialect="generic"
):
    """
    Detect excessively large pagination offsets.
    """

    select = _top_select(tree)

    if not select:
        return None

    offset = select.args.get("offset")

    if not offset:
        return None

    value = getattr(
        offset,
        "expression",
        None
    )

    if not (
        isinstance(value, exp.Literal)
        and value.is_int
    ):
        return None

    amount = int(value.this)

    if amount < 1000:
        return None

    return _finding(
        "SQL008",
        "Medium",
        f"Large OFFSET ({amount}) pagination detected.",
        (
            "Large offsets can force the database to process "
            "and discard many rows before returning the "
            "requested page."
        ),
        (
            "Consider keyset/seek pagination using a stable "
            "indexed sort key."
        ),
    )


# ============================================================
# SQL009 — LIMIT/FETCH WITHOUT ORDER BY
# ============================================================

def check_limit_without_order(
    tree,
    dialect="generic"
):
    """
    Detect limited result sets without deterministic ordering.
    """

    select = _top_select(tree)

    if not select:
        return None

    limit = select.args.get("limit")

    if not limit:
        return None

    if select.args.get("order"):
        return None

    value = getattr(
        limit,
        "expression",
        None
    )

    # LIMIT 1 is often intentionally used for existence/top-one
    # lookups, so don't flag it.
    if (
        isinstance(value, exp.Literal)
        and value.is_int
        and int(value.this) == 1
    ):
        return None

    return _finding(
        "SQL009",
        "Low",
        "Limited result without ORDER BY detected.",
        (
            "Without an explicit ordering, the database is "
            "free to return any qualifying rows."
        ),
        (
            "Add a deterministic ORDER BY when the application "
            "expects a stable subset of rows."
        ),
    )


# ============================================================
# SQL010 — JOIN WITHOUT CONDITION
# ============================================================

def check_join_without_condition(
    tree,
    dialect="generic"
):
    """
    Detect JOINs without ON/USING conditions and
    potentially accidental Cartesian products.
    """

    select = _top_select(tree)

    if not select:
        return None

    # --------------------------------------------------------
    # Explicit JOINs
    # --------------------------------------------------------

    for join in tree.find_all(exp.Join):

        on = join.args.get("on")
        using = join.args.get("using")

        if on is not None or using is not None:
            continue

        try:
            join_sql = join.sql().upper()
        except Exception:
            join_sql = ""

        if "CROSS JOIN" in join_sql:
            return _finding(
                "SQL010",
                "Medium",
                "CROSS JOIN detected.",
                (
                    "A CROSS JOIN intentionally creates a "
                    "Cartesian product."
                ),
                (
                    "Keep CROSS JOIN only when this Cartesian "
                    "result is intentional."
                ),
            )

        return _finding(
            "SQL010",
            "High",
            "JOIN without a join condition detected.",
            (
                "The joined tables are not connected by an "
                "ON or USING condition."
            ),
            (
                "Add an appropriate ON/USING condition, or "
                "use CROSS JOIN explicitly if intentional."
            ),
        )

    # --------------------------------------------------------
    # Comma-separated FROM tables
    # --------------------------------------------------------

    from_clause = _from_clause(select)

    if not from_clause:
        return None

    expressions = list(from_clause.expressions)

    if len(expressions) <= 1:
        return None

    where = tree.find(exp.Where)

    if where:

        for eq in where.find_all(exp.EQ):

            left = eq.left
            right = eq.right

            if (
                isinstance(left, exp.Column)
                and isinstance(right, exp.Column)
                and left.table
                and right.table
                and left.table != right.table
            ):
                return _finding(
                    "SQL010",
                    "Low",
                    "Implicit comma-join syntax detected.",
                    (
                        "Multiple tables are listed in FROM "
                        "with the relationship expressed in WHERE."
                    ),
                    (
                        "Prefer explicit JOIN ... ON syntax."
                    ),
                )

    return _finding(
        "SQL010",
        "High",
        "Multiple FROM tables without a join condition detected.",
        (
            "Multiple tables appear in FROM without a "
            "predicate connecting them."
        ),
        (
            "Add a join condition or use CROSS JOIN explicitly "
            "when the Cartesian product is intentional."
        ),
    )


# ============================================================
# SQL011 — INSERT WITHOUT COLUMN LIST
# ============================================================

def check_insert_without_columns(
    tree,
    dialect="generic"
):
    """
    Detect INSERT statements without an explicit column list.
    """

    for insert in tree.find_all(exp.Insert):

        target = insert.this

        if isinstance(target, exp.Schema):
            continue

        if isinstance(target, exp.Table):
            return _finding(
                "SQL011",
                "Medium",
                "INSERT without an explicit column list.",
                (
                    "Values are matched by positional order. "
                    "Schema changes can therefore break the "
                    "statement or cause incorrect mappings."
                ),
                (
                    "Use INSERT INTO table "
                    "(col1, col2, ...) VALUES (...)."
                ),
            )

    return None


# ============================================================
# SQL012 — OR ACROSS DIFFERENT COLUMNS
# ============================================================

def check_or_across_columns(
    tree,
    dialect="generic"
):
    """
    Detect OR predicates involving different columns.
    """

    where = tree.find(exp.Where)

    if not where:
        return None

    for or_node in where.find_all(exp.Or):

        left_columns = {
            column.name.upper()
            for column in or_node.left.find_all(exp.Column)
        }

        right_columns = {
            column.name.upper()
            for column in or_node.right.find_all(exp.Column)
        }

        if (
            left_columns
            and right_columns
            and left_columns != right_columns
        ):
            columns = ", ".join(
                sorted(
                    left_columns | right_columns
                )
            )

            return _finding(
                "SQL012",
                "Medium",
                "OR across different columns detected.",
                (
                    f"The condition combines {columns} with OR. "
                    "Different predicate branches may require "
                    "different access paths."
                ),
                (
                    "Consider whether equivalent UNION ALL branches "
                    "or another predicate structure would allow "
                    "more selective access. Verify with EXPLAIN."
                ),
            )

    return None


# ============================================================
# SQL013 — RANDOM ORDERING
# ============================================================

def check_random_order(
    tree,
    dialect="generic"
):
    """
    Detect database-specific random ordering functions.

    Handles:
        MySQL       -> RAND()
        PostgreSQL  -> RANDOM()
        Oracle      -> DBMS_RANDOM.VALUE
        SQLite      -> RANDOM()
        SQL Server  -> NEWID(), RAND()
    """

    order = tree.find(exp.Order)

    if not order:
        return None

    dialect_name = _dialect_name(dialect)

    random_names = {
        "mysql": {
            "RAND"
        },
        "postgresql": {
            "RANDOM"
        },
        "oracle": {
            "DBMS_RANDOM"
        },
        "sqlite": {
            "RANDOM"
        },
        "sqlserver": {
            "NEWID",
            "RAND"
        },
        "generic": {
            "RAND",
            "RANDOM",
            "DBMS_RANDOM",
            "NEWID"
        }
    }

    names = random_names.get(
        dialect_name,
        random_names["generic"]
    )

    # --------------------------------------------------------
    # Check every ORDER BY expression.
    #
    # We deliberately inspect:
    #   1. SQL generated by SQLGlot
    #   2. Python string form of the expression
    #
    # This makes Oracle DBMS_RANDOM.VALUE detection reliable.
    # --------------------------------------------------------

    for expression in order.expressions:

        texts = set()

        try:
            texts.add(
                expression.sql(
                    dialect=dialect_name
                ).upper()
            )
        except Exception:
            pass

        try:
            texts.add(
                expression.sql().upper()
            )
        except Exception:
            pass

        try:
            texts.add(
                str(expression).upper()
            )
        except Exception:
            pass

        for sql_text in texts:

            for name in names:

                if name in sql_text:
                    return _finding(
                        "SQL013",
                        "High",
                        "Random ordering detected.",
                        (
                            "Random ordering may require a random "
                            "value to be evaluated for many rows "
                            "followed by sorting."
                        ),
                        (
                            "Use an application-appropriate sampling "
                            "strategy when only a small number of rows "
                            "is required."
                        ),
                    )

    # --------------------------------------------------------
    # Extra AST-level check for Oracle DBMS_RANDOM
    #
    # SQLGlot may represent:
    #
    #     DBMS_RANDOM.VALUE
    #
    # as nested Dot expressions rather than a normal Function.
    # --------------------------------------------------------

    if dialect_name == "oracle":

        order_text = ""

        try:
            order_text = order.sql(
                dialect="oracle"
            ).upper()
        except Exception:
            pass

        if "DBMS_RANDOM" in order_text:
            return _finding(
                "SQL013",
                "High",
                "Random ordering detected.",
                (
                    "Random ordering may require a random "
                    "value to be evaluated for many rows "
                    "followed by sorting."
                ),
                (
                    "Use an application-appropriate sampling "
                    "strategy when only a small number of rows "
                    "is required."
                ),
            )

        for node in order.walk():

            try:
                node_sql = node.sql(
                    dialect="oracle"
                ).upper()
            except Exception:
                node_sql = ""

            if "DBMS_RANDOM" in node_sql:
                return _finding(
                    "SQL013",
                    "High",
                    "Random ordering detected.",
                    (
                        "Random ordering may require a random "
                        "value to be evaluated for many rows "
                        "followed by sorting."
                    ),
                    (
                        "Use an application-appropriate sampling "
                        "strategy when only a small number of rows "
                        "is required."
                    ),
                )

    return None


# ============================================================
# SQL014 — SUBQUERY IN SELECT LIST
# ============================================================

def check_scalar_subquery_in_select(
    tree,
    dialect="generic"
):
    """
    Detect scalar subqueries in the SELECT list.
    """

    select = _top_select(tree)

    if not select:
        return None

    for expression in select.expressions:

        subquery = expression.find(
            exp.Subquery
        )

        if subquery:
            return _finding(
                "SQL014",
                "Medium",
                "Subquery in SELECT list detected.",
                (
                    "A scalar subquery in the SELECT list may "
                    "require additional work for each outer "
                    "result row, especially if correlated."
                ),
                (
                    "Consider a JOIN, pre-aggregated derived table, "
                    "or equivalent window function."
                ),
            )

    return None


# ============================================================
# SQL015 — NULL COMPARISON
# ============================================================

def check_null_comparison(
    tree,
    dialect="generic"
):
    """
    Detect = NULL and <> NULL comparisons.
    """

    for node in tree.find_all(
        (
            exp.EQ,
            exp.NEQ,
        )
    ):

        if (
            isinstance(node.left, exp.Null)
            or isinstance(node.right, exp.Null)
        ):
            return _finding(
                "SQL015",
                "High",
                "Comparison with NULL using = or <> detected.",
                (
                    "NULL represents an unknown value. Equality "
                    "and inequality comparisons with NULL do not "
                    "evaluate to TRUE for matching rows."
                ),
                (
                    "Use IS NULL or IS NOT NULL instead."
                ),
            )

    return None