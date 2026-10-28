from analyzer.performance_rules import (
    check_composite_index_leading_column,
    check_covering_index_opportunity,
    check_expensive_sort,
    check_full_table_scan,
    check_group_by_index,
    check_heavy_column_without_limit,
    check_implicit_type_conversion,
    check_index_not_used,
    check_indexed_function_table_scan,
    check_join_type_mismatch,
    check_join_row_explosion,
    check_low_selectivity_index,
    check_missing_filter_index,
    check_non_sargable_filter,
    check_redundant_index,
    check_temporary_materialization,
    check_unindexed_join,
    check_unrestricted_large_scan,
    check_nested_loop_table_scan,
    check_update_index_rewrite,
    check_large_index_read,
    check_large_sort_without_limit,
)
from analyzer.recommendation import recommend_index
from analyzer.score import calculate_query_score
from core.context_builder import build_query_context
from core.database import create_adapter


def _compat_query_info(context):
    filters = context.bare_filters()
    joins = context.join_pairs()
    filter_columns = [
        {"table": item["table"], "column": item["column"]}
        for item in filters if item.get("table")
    ]
    join_columns = []
    for left_table, left_column, right_table, right_column in joins:
        join_columns.extend([
            {"table": left_table, "column": left_column},
            {"table": right_table, "column": right_column},
        ])
    select_columns = context.select_columns()
    return {
        "tables": list(context.tables),
        "table_count": len(context.tables),
        "join_count": context.join_count(),
        "selected_column_count": len(select_columns),
        "filter_count": len(filters),
        "filter_columns": filter_columns,
        "join_columns": join_columns,
        "has_group_by": context.has_group_by(),
        "has_order_by": context.has_order_by(),
        "has_distinct": context.has_distinct(),
        "aggregate_count": context.aggregate_count(),
        "where": context.where.sql() if context.where else None,
    }


def _plan_text(context):
    lines = []
    for node in context.plan.nodes:
        parts = [node.operation]
        if node.table:
            parts.append(f"table={node.table}")
        if node.index:
            parts.append(f"index={node.index}")
        if node.estimated_rows is not None:
            parts.append(f"rows={node.estimated_rows:g}")
        if node.cost is not None:
            parts.append(f"cost={node.cost:g}")
        if node.details:
            parts.append(node.details)
        lines.append(" | ".join(parts))
    return "\n".join(lines)


def _build_recommendations(context):
    recommendations = []
    seen = set()
    for predicate in context.bare_filters():
        table = predicate.get("table")
        column = predicate.get("column")
        if not table or not column:
            continue
        key = (table.upper(), column.upper())
        if key in seen or context.has_index(table, column):
            continue
        seen.add(key)
        recommendations.append(recommend_index(table, column))
    return recommendations


def analyze_query(query, tree=None, lint_findings=None, database_type="oracle", adapter=None):
    if adapter is None:
        adapter = create_adapter(database_type)

    context = build_query_context(query, adapter)
    rules = [
        lambda: check_full_table_scan(context),
        lambda: check_missing_filter_index(context),
        lambda: check_expensive_sort(context),
        lambda: check_unrestricted_large_scan(context),
        lambda: check_non_sargable_filter(context),
        lambda: check_unindexed_join(context),
        lambda: check_nested_loop_table_scan(context),
        lambda: check_implicit_type_conversion(context),
        lambda: check_redundant_index(context),
        lambda: check_composite_index_leading_column(context),
        lambda: check_covering_index_opportunity(context),
        lambda: check_group_by_index(context),
        lambda: check_heavy_column_without_limit(context),
        lambda: check_update_index_rewrite(context),
        lambda: check_join_type_mismatch(context),
        lambda: check_index_not_used(context),
        lambda: check_join_row_explosion(context),
        lambda: check_large_sort_without_limit(context),
        lambda: check_temporary_materialization(context),
        lambda: check_large_index_read(context),
        lambda: check_low_selectivity_index(context),
        lambda: check_indexed_function_table_scan(context),
    ]

    findings = []
    for rule in rules:
        try:
            result = rule()
        except Exception:
            result = None
        if result:
            findings.extend(result if isinstance(result, list) else [result])

    recommendations = _build_recommendations(context)
    return {
        "execution_plan": _plan_text(context),
        "query_info": _compat_query_info(context),
        "context": context,
        "findings": findings,
        "recommendations": recommendations,
        "query_score": calculate_query_score(findings),
    }
