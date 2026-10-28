from linter.rules import (
    check_select_star,
    check_update_without_where,
    check_delete_without_where,
    check_non_sargable_filter,
    check_select_without_where,
    check_leading_wildcard_like,
    check_not_in_subquery,
    check_large_offset,
    check_limit_without_order,
    check_join_without_condition,
    check_insert_without_columns,
    check_or_across_columns,
    check_random_order,
    check_scalar_subquery_in_select,
    check_null_comparison,
)


def run_linter(
    tree,
    dialect="generic"
):

    findings = []

    rules = [
        check_select_star,
        check_update_without_where,
        check_delete_without_where,
        check_non_sargable_filter,
        check_select_without_where,
        check_leading_wildcard_like,
        check_not_in_subquery,
        check_large_offset,
        check_limit_without_order,
        check_join_without_condition,
        check_insert_without_columns,
        check_or_across_columns,
        check_random_order,
        check_scalar_subquery_in_select,
        check_null_comparison,
    ]

    for rule in rules:

        try:

            result = rule(
                tree,
                dialect=dialect
            )

        except TypeError:

            # Keeps compatibility with your original
            # SQL001–SQL005 functions.

            result = rule(
                tree
            )

        if result:
            findings.append(
                result
            )

    return findings