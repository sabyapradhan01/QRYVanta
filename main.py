import sqlglot

from linter.linter import run_linter
from analyzer.analyzer import analyze_query


def analyze_sql(query):

    try:
        # ---------------------------------
        # Parse SQL
        # ---------------------------------

        tree = sqlglot.parse_one(query)

        print("\nSQL parsed successfully!")

        # ---------------------------------
        # Lint Analysis
        # ---------------------------------

        findings = run_linter(tree)

        print("\nLint Results:")

        if not findings:
            print("No issues found.")

        for finding in findings:

            print("\nRule ID:", finding["rule_id"])
            print("Severity:", finding["severity"])
            print("Problem:", finding["message"])
            print("Explanation:", finding["explanation"])
            print("Recommendation:", finding["recommendation"])

        # ---------------------------------
        # Performance Analysis
        # ---------------------------------

        analysis = analyze_query(
            query,
            tree,
            findings
        )

        # ---------------------------------
        # Query Complexity
        # ---------------------------------

        query_info = analysis["query_info"]

        print("\nQuery Complexity:")

        print(
            "Number of Tables:",
            query_info["table_count"]
        )

        print(
            "Number of JOINs:",
            query_info["join_count"]
        )

        print(
            "Selected Columns:",
            query_info["selected_column_count"]
        )

        print(
            "Filter Conditions:",
            query_info["filter_count"]
        )

        print(
            "Uses GROUP BY:",
            query_info["has_group_by"]
        )

        print(
            "Uses ORDER BY:",
            query_info["has_order_by"]
        )

        print(
            "Uses DISTINCT:",
            query_info["has_distinct"]
        )

        print(
            "Aggregate Functions:",
            query_info["aggregate_count"]
        )

        # ---------------------------------
        # Query Health Score
        # ---------------------------------

        print("\nQuery Health Score:")
        print(
            "Score:",
            analysis["query_score"],
            "/ 100"
        )

        # ---------------------------------
        # Performance Findings
        # ---------------------------------

        print("\nPerformance Analysis:")

        performance_findings = analysis["findings"]

        if not performance_findings:
            print("No performance issues found.")

        for finding in performance_findings:

            print("\nRule ID:", finding["rule_id"])
            print("Severity:", finding["severity"])
            print("Problem:", finding["message"])
            print("Explanation:", finding["explanation"])
            print("Recommendation:", finding["recommendation"])

        # ---------------------------------
        # Recommendations
        # ---------------------------------

        recommendations = analysis["recommendations"]

        print("\nRecommendations:")

        if not recommendations:
            print("No additional recommendations.")

        for recommendation in recommendations:

            print("\nType:", recommendation["type"])
            print("Message:", recommendation["message"])
            print("SQL:", recommendation["sql"])

    except Exception as e:

        print("\nSQL analysis failed.")
        print("Error:", e)


query = input("Enter your SQL query:\n")

analyze_sql(query)