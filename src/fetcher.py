"""Simple fetcher for FDA food enforcement API and stubs for RSS.
"""
from typing import List, Dict
import requests

FDA_ENFORCEMENT = "https://api.fda.gov/food/enforcement.json"


def fetch_fda_recalls(limit: int = 10, sort_field: str = "recall_initiation_date") -> List[Dict]:
    """Fetch recent recalls from FDA enforcement API.

    By default the FDA API may not return items sorted by newest first. Use
    `sort_field` with `:desc` to request the latest recalls (e.g.
    `recall_initiation_date:desc`). Returns a list of dicts.
    """
    # The FDA API supports a `sort` parameter like 'field:desc' or 'field:asc'.
    # Request newest-first ordering for the provided sort_field to get latest recalls.
    params = {"limit": limit, "sort": f"{sort_field}:desc"}
    resp = requests.get(FDA_ENFORCEMENT, params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    # FDA returns results under 'results'
    return data.get("results", [])


if __name__ == "__main__":
    items = fetch_fda_recalls(5)
    for it in items:
        print(it.get("recall_number"), it.get("product_description"))
