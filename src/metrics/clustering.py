from datetime import timedelta


def detect_cluster_size_diy(wallet_address: str, first_funding_tx: dict | None, candidate_pool: list[dict]) -> int:
    """
    DIY cluster detection via funding source correlation.
    Falls back to this when PolyTrack subscription is unavailable.
    """
    if not first_funding_tx:
        return 1

    funding_source = first_funding_tx.get("from_address", "")
    funding_amount = first_funding_tx.get("value_usd", 0)
    funding_ts = first_funding_tx.get("timestamp")

    related: list[str] = []
    for other in candidate_pool:
        if other.get("address") == wallet_address:
            continue
        other_tx = other.get("first_funding_tx", {})
        if not other_tx:
            continue
        same_funder = other_tx.get("from_address") == funding_source
        if not same_funder:
            continue
        other_amount = other_tx.get("value_usd", 0)
        other_ts = other_tx.get("timestamp")
        similar_amount = (
            abs(other_amount - funding_amount) / funding_amount < 0.1
            if funding_amount > 0
            else False
        )
        funded_close = False
        if funding_ts and other_ts:
            funded_close = abs((other_ts - funding_ts).days) < 7
        if similar_amount or funded_close:
            related.append(other["address"])

    return 1 + len(related)
