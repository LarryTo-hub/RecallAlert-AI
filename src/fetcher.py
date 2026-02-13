"""Simple fetcher for FDA food enforcement API and stubs for RSS.
"""
from typing import List, Dict
import requests

FDA_ENFORCEMENT = "https://api.fda.gov/food/enforcement.json"


def fetch_fda_recalls(limit: int = 10) -> List[Dict]:
    """Fetch recent recalls from FDA enforcement API. Returns a list of dicts."""
    params = {"limit": limit}
    resp = requests.get(FDA_ENFORCEMENT, params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    # FDA returns results under 'results'
    return data.get("results", [])


if __name__ == "__main__":
    items = fetch_fda_recalls(5)
    for it in items:
        print(it.get("recall_number"), it.get("product_description"))
