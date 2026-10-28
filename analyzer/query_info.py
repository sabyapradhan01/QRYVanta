from sqlglot import expressions as exp


def get_query_info(tree):
    # ---------------------------------
    # Tables and aliases
    # ---------------------------------

    tables = []
    table_aliases = {}

    for table in tree.find_all(exp.Table):
        table_name = table.name
        alias = table.alias

        tables.append(table_name)

        if alias:
            table_aliases[alias] = table_name

    # ---------------------------------
    # Selected columns
    # ---------------------------------

    selected_columns = []

    select = tree.find(exp.Select)

    if select:
        for expression in select.expressions:

            if isinstance(expression, exp.Star):
                selected_columns.append("*")

            else:
                columns = list(
                    expression.find_all(exp.Column)
                )

                if columns:
                    for column in columns:
                        selected_columns.append(column.name)

                else:
                    selected_columns.append(
                        expression.sql()
                    )

    # ---------------------------------
    # WHERE filter columns
    # ---------------------------------

    filter_columns = []

    where = tree.find(exp.Where)

    if where:
        for column in where.this.find_all(exp.Column):

            table_alias = column.table

            # If the column has no table qualifier,
            # use the only table in the query.
            if not table_alias and len(tables) == 1:
                table_name = tables[0]

            else:
                table_name = table_aliases.get(
                    table_alias,
                    table_alias
                )

            filter_columns.append({
                "table_alias": table_alias,
                "table": table_name,
                "column": column.name
            })

    # ---------------------------------
    # JOIN columns
    # ---------------------------------

    join_columns = []

    for join in tree.find_all(exp.Join):

        on_condition = join.args.get("on")

        if on_condition:

            for column in on_condition.find_all(exp.Column):

                table_alias = column.table

                table_name = table_aliases.get(
                    table_alias,
                    table_alias
                )

                join_columns.append({
                    "table_alias": table_alias,
                    "table": table_name,
                    "column": column.name
                })

    # ---------------------------------
    # Query complexity information
    # ---------------------------------

    unique_tables = list(dict.fromkeys(tables))

    table_count = len(unique_tables)
    join_count = len(list(tree.find_all(exp.Join)))

    selected_column_count = len(selected_columns)
    filter_count = len(filter_columns)

    has_group_by = tree.find(exp.Group) is not None
    has_order_by = tree.find(exp.Order) is not None
    has_distinct = tree.find(exp.Distinct) is not None

    # ---------------------------------
    # Aggregate detection
    # ---------------------------------

    aggregate_functions = [
        exp.Count,
        exp.Sum,
        exp.Avg,
        exp.Min,
        exp.Max
    ]

    aggregate_count = 0

    for function_type in aggregate_functions:
        aggregate_count += len(
            list(tree.find_all(function_type))
        )

    # ---------------------------------
    # Return query information
    # ---------------------------------

    return {
        "tables": unique_tables,
        "table_aliases": table_aliases,
        "selected_columns": list(dict.fromkeys(selected_columns)),
        "filter_columns": filter_columns,
        "join_columns": join_columns,
        "where": str(where.this) if where else None,

        # ---------------------------------
        # Query complexity
        # ---------------------------------

        "table_count": table_count,
        "join_count": join_count,
        "selected_column_count": selected_column_count,
        "filter_count": filter_count,
        "has_group_by": has_group_by,
        "has_order_by": has_order_by,
        "has_distinct": has_distinct,
        "aggregate_count": aggregate_count
    }