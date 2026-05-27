"""Simple anti-sybil: group wallets that trade the same markets too often."""
from __future__ import annotations

from collections import defaultdict

from bot.models import LeaderCandidate


def assign_clusters(candidates: list[LeaderCandidate], market_sets: dict[str, set[str]]) -> dict[str, str]:
    """Return proxy -> cluster_id. Wallets sharing >70% markets with another get same cluster."""
    cluster_map: dict[str, str] = {}
    clusters: dict[str, set[str]] = defaultdict(set)
    cid = 0

    for c in candidates:
        markets = market_sets.get(c.proxy, set())
        matched = None
        for existing_id, members in clusters.items():
            for m_proxy in members:
                other = market_sets.get(m_proxy, set())
                if not markets or not other:
                    continue
                overlap = len(markets & other) / max(len(markets | other), 1)
                if overlap > 0.7:
                    matched = existing_id
                    break
            if matched:
                break
        if matched:
            cluster_map[c.proxy] = matched
            clusters[matched].add(c.proxy)
        else:
            new_id = f"cluster_{cid}"
            cid += 1
            cluster_map[c.proxy] = new_id
            clusters[new_id].add(c.proxy)
    return cluster_map


def pick_one_per_cluster(ranked: list[LeaderCandidate], cluster_map: dict[str, str]) -> list[LeaderCandidate]:
    seen_clusters: set[str] = set()
    out: list[LeaderCandidate] = []
    for c in ranked:
        cid = cluster_map.get(c.proxy, c.proxy)
        if cid in seen_clusters:
            continue
        seen_clusters.add(cid)
        out.append(c)
    return out
