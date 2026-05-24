def compute_crowding_score(
    polymarket_followers: int = 0,
    twitter_mentions_30d: int = 0,
    appears_in_oracle_newsletter: bool = False,
) -> float:
    """
    Proxy for public attention. 0.0 = unknown, 1.0 = very famous.
    Twitter mentions require a separate scraping pipeline; defaults to 0.
    """
    score = 0.0
    score += min(0.4, polymarket_followers / 1000)
    score += min(0.3, twitter_mentions_30d / 100)
    score += 0.3 if appears_in_oracle_newsletter else 0.0
    return min(1.0, score)
