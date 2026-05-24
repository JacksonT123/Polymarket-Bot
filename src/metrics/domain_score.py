def compute_domain_score(category_volume_breakdown: dict[str, float]) -> tuple[str, float]:
    """
    Returns (primary_category, domain_score).
    Rewards 60%+ concentration in a single category with score 1.0.
    """
    if not category_volume_breakdown:
        return "_default", 0.0
    primary_cat = max(category_volume_breakdown, key=lambda k: category_volume_breakdown[k])
    primary_pct = category_volume_breakdown[primary_cat]
    score = max(0.0, (primary_pct - 0.33) / (0.60 - 0.33))
    return primary_cat, min(1.0, score)
