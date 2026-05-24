import math


def compute_entropy_score(category_volume_breakdown: dict[str, float]) -> float:
    """
    Shannon entropy of category distribution — higher = more spread.
    Normalized to [0, 1].
    """
    if not category_volume_breakdown:
        return 0.0
    total = sum(category_volume_breakdown.values())
    if total == 0:
        return 0.0
    probs = [v / total for v in category_volume_breakdown.values() if v > 0]
    raw_entropy = -sum(p * math.log2(p) for p in probs)
    max_entropy = math.log2(len(probs)) if len(probs) > 1 else 1.0
    return raw_entropy / max_entropy if max_entropy > 0 else 0.0
