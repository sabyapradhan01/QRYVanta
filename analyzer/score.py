def calculate_query_score(findings):
    """
    Calculate a query health score based on
    the severity of detected findings.

    Score starts at 100 and decreases
    according to finding severity.
    """

    score = 100

    severity_points = {
        "High": 20,
        "Medium": 10,
        "Low": 5
    }

    for finding in findings:

        severity = finding.get(
            "severity",
            "Low"
        )

        deduction = severity_points.get(
            severity,
            0
        )

        score -= deduction

    # Keep score between 0 and 100
    score = max(
        0,
        min(100, score)
    )

    return score