"""Fetch recent recalls from FDA and USDA."""
from typing import List, Dict
from urllib.parse import urljoin
import re
import requests
import feedparser
from bs4 import BeautifulSoup

FDA_ENFORCEMENT_ENDPOINTS = {
    "food": "https://api.fda.gov/food/enforcement.json",
    "drug": "https://api.fda.gov/drug/enforcement.json",
    "device": "https://api.fda.gov/device/enforcement.json",
}
FDA_RECALLS_PAGE = "https://www.fda.gov/safety/recalls-market-withdrawals-safety-alerts"
USDA_RECALLS_RSS = "https://www.fsis.usda.gov/recalls/rss"
USDA_RECALLS_MIRROR = "https://r.jina.ai/http://www.fsis.usda.gov/recalls"


def _extract_affected_area(text: str) -> str | None:
    """Extract a likely affected area token from card/body text."""
    if not text:
        return None

    # Common labels shown in recalls pages.
    region_patterns = [
        r"\bNATIONWIDE\b",
        r"\bMIDWEST\b",
        r"\bNORTHEAST\b",
        r"\bSOUTHEAST\b",
        r"\bSOUTHWEST\b",
        r"\bWEST\b",
        r"\bPUERTO\s+RICO\b",
    ]
    for pat in region_patterns:
        m = re.search(pat, text, flags=re.IGNORECASE)
        if m:
            return m.group(0).upper()

    return None


def _fetch_usda_recalls_from_page(limit: int = 5) -> List[Dict]:
    """Fetch latest USDA recalls directly from the USDA recalls webpage."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    try:
        resp = requests.get(
            "https://www.fsis.usda.gov/recalls",
            headers=headers,
            timeout=(5, 12),
        )
        resp.raise_for_status()
    except requests.RequestException:
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    candidates = soup.select(
        "article, .views-row, .usa-collection__item, .usa-card, .node--type-recall"
    )

    results: List[Dict] = []
    seen_titles = set()
    for node in candidates:
        link_tag = node.select_one("h2 a, h3 a, a")
        if not link_tag:
            continue

        title = link_tag.get_text(" ", strip=True)
        if not title or title in seen_titles:
            continue
        seen_titles.add(title)

        link = urljoin("https://www.fsis.usda.gov", link_tag.get("href") or "")
        summary_tag = node.select_one("p")
        summary = summary_tag.get_text(" ", strip=True) if summary_tag else None
        node_text = node.get_text(" ", strip=True)

        status_match = re.search(r"\b(ACTIVE|CLOSED|TERMINATED)\b", node_text, flags=re.IGNORECASE)
        status = status_match.group(1).upper() if status_match else None
        affected_area = _extract_affected_area(node_text)

        company_name = None
        company_candidate = node.select_one(".field--name-field-establishment a, .field--name-field-company a")
        if company_candidate:
            company_name = company_candidate.get_text(" ", strip=True)

        date_tag = node.select_one("time")
        report_date = date_tag.get_text(" ", strip=True) if date_tag else None
        if not report_date:
            # Fallback: extract first MM/DD/YYYY-like date in card text.
            m = re.search(r"\b\d{1,2}/\d{1,2}/\d{4}\b", node.get_text(" ", strip=True))
            report_date = m.group(0) if m else None

        results.append(
            {
                "source": "USDA-web",
                "recall_number": None,
                "brand_name": None,
                "product_description": title,
                "product_type": "Food",
                "reason_for_recall": summary,
                "company_name": company_name,
                "status": status,
                "affected_area": affected_area,
                "report_date": report_date,
                "recall_initiation_date": report_date,
                "url": link,
                "raw": {
                    "title": title,
                    "summary": summary,
                    "link": link,
                    "report_date": report_date,
                    "status": status,
                    "affected_area": affected_area,
                },
            }
        )

        if len(results) >= limit:
            break

    return results


def _fetch_usda_recalls_from_mirror(limit: int = 5) -> List[Dict]:
    """Fetch USDA recalls from a text mirror when direct FSIS access is blocked."""
    try:
        resp = requests.get(
            USDA_RECALLS_MIRROR,
            headers={"User-Agent": "Mozilla/5.0 (RecallAI)"},
            timeout=(5, 20),
        )
        resp.raise_for_status()
    except requests.RequestException:
        return []

    lines = resp.text.splitlines()
    results: List[Dict] = []

    i = 0
    while i < len(lines) and len(results) < limit:
        line = lines[i].strip()

        # Recall entry title line format:
        # ### [Title](http://www.fsis.usda.gov/recalls-alerts/...)
        m_title = re.match(r"^### \[(.+?)\]\((http[^)]+/recalls-alerts/[^)]+)\)", line)
        if not m_title:
            i += 1
            continue

        title = m_title.group(1).strip()
        link = m_title.group(2).strip()

        company_name = None
        status = None
        report_date = None
        affected_area = None
        reason = None

        # Parse a small window after title to extract metadata.
        j = i + 1
        window_end = min(i + 25, len(lines))
        while j < window_end:
            s = lines[j].strip()
            if not s:
                j += 1
                continue

            if company_name is None:
                m_company = re.match(r"^\[(.+?)\]\(http[^)]+/inspection/[^)]+\)", s)
                if m_company:
                    company_name = m_company.group(1).strip()
                    j += 1
                    continue

            if status is None and re.fullmatch(r"(?i)(active|closed|terminated)", s):
                status = s.upper()
                j += 1
                continue

            if report_date is None:
                m_date = re.search(r"\b(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun),\s*\d{2}/\d{2}/\d{4}\b", s)
                if m_date:
                    report_date = m_date.group(0)
                    j += 1
                    continue

            if affected_area is None and re.fullmatch(r"(?i)(nationwide|midwest|northeast|southeast|southwest|west|puerto rico|current)\b.*", s):
                affected_area = s.upper()
                j += 1
                continue

            if reason is None and ("WASHINGTON," in s or "U.S. Department of Agriculture" in s):
                reason = s

            # Stop at next recall title.
            if s.startswith("### ["):
                break

            j += 1

        results.append(
            {
                "source": "USDA-mirror",
                "recall_number": None,
                "brand_name": None,
                "product_description": title,
                "product_type": "Food",
                "reason_for_recall": reason,
                "company_name": company_name,
                "status": status,
                "affected_area": affected_area,
                "report_date": report_date,
                "recall_initiation_date": report_date,
                "url": link,
                "raw": {
                    "title": title,
                    "link": link,
                    "company_name": company_name,
                    "status": status,
                    "report_date": report_date,
                    "affected_area": affected_area,
                    "reason_for_recall": reason,
                },
            }
        )

        i = j + 1

    return results


def _fetch_fda_recalls_from_page(limit: int = 5) -> List[Dict]:
    """Fetch latest recalls directly from the FDA recalls webpage table."""
    try:
        resp = requests.get(
            FDA_RECALLS_PAGE,
            headers={"User-Agent": "Mozilla/5.0 (RecallAI)"},
            timeout=(5, 12),
        )
        resp.raise_for_status()
    except requests.RequestException:
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    rows = soup.select("table tbody tr")

    results: List[Dict] = []
    for row in rows[:limit]:
        cols = row.select("td")
        if len(cols) < 6:
            continue

        # Expected FDA table columns:
        # Date | Brand Name(s) | Product Description | Product Type |
        # Recall Reason Description | Company Name | ...
        date_text = cols[0].get_text(" ", strip=True)
        brand_names = cols[1].get_text(" ", strip=True)
        product_description = cols[2].get_text(" ", strip=True)
        product_type = cols[3].get_text(" ", strip=True)
        reason = cols[4].get_text(" ", strip=True)
        company = cols[5].get_text(" ", strip=True)

        results.append(
            {
                "source": "FDA-web",
                "recall_number": None,
                "brand_name": brand_names,
                "brand_names": brand_names,
                "product_description": product_description,
                "product_type": product_type,
                "reason_for_recall": reason,
                "company_name": company,
                "status": "ACTIVE" if not cols[6].get_text(" ", strip=True) else "TERMINATED",
                "affected_area": None,
                "report_date": date_text,
                "recall_initiation_date": date_text,
                "url": FDA_RECALLS_PAGE,
                "raw": {
                    "date": date_text,
                    "brand_names": brand_names,
                    "product_description": product_description,
                    "product_type": product_type,
                    "reason_for_recall": reason,
                    "company_name": company,
                    "status": "ACTIVE" if not cols[6].get_text(" ", strip=True) else "TERMINATED",
                },
            }
        )

    return results


def _fetch_fda_recalls_from_enforcement(limit: int = 5, sort_field: str = "report_date") -> List[Dict]:
    """Fetch latest FDA recalls across food, drug, and device enforcement APIs."""
    params = {"limit": limit, "sort": f"{sort_field}:desc"}
    combined: List[Dict] = []

    for category, endpoint in FDA_ENFORCEMENT_ENDPOINTS.items():
        try:
            resp = requests.get(endpoint, params=params, timeout=(5, 12))
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException:
            continue

        for item in data.get("results", []):
            openfda = item.get("openfda") or {}
            brand_names = openfda.get("brand_name") or []
            combined.append(
                {
                    "source": f"FDA-{category}",
                    "recall_number": item.get("recall_number"),
                    "brand_name": ", ".join(brand_names) if isinstance(brand_names, list) else str(brand_names or ""),
                    "product_description": item.get("product_description"),
                    "product_type": item.get("product_type") or category.title(),
                    "reason_for_recall": item.get("reason_for_recall"),
                    "company_name": item.get("company_name") or item.get("recalling_firm"),
                    "status": item.get("status") or item.get("recall_status"),
                    "affected_area": item.get("distribution_pattern"),
                    "report_date": item.get("report_date"),
                    "recall_initiation_date": item.get("recall_initiation_date"),
                    "url": None,
                    "raw": item,
                }
            )

    combined.sort(key=lambda x: (x.get(sort_field) or ""), reverse=True)
    return combined[:limit]


def fetch_fda_recalls(limit: int = 5, sort_field: str = "report_date") -> List[Dict]:
    """Fetch latest FDA recalls.

    Uses FDA recalls webpage table first (matches what users see on FDA site),
    then falls back to openFDA enforcement APIs if webpage fetch fails.
    """
    page_results = _fetch_fda_recalls_from_page(limit=limit)
    if page_results:
        return page_results
    return _fetch_fda_recalls_from_enforcement(limit=limit, sort_field=sort_field)


def fetch_usda_recalls(limit: int = 5) -> List[Dict]:
    # Prefer the USDA recalls webpage so we use the same extraction approach as FDA.
    page_results = _fetch_usda_recalls_from_page(limit=limit)
    if page_results:
        return page_results

    # Fallback: FSIS can block direct bot-like requests in some environments.
    mirror_results = _fetch_usda_recalls_from_mirror(limit=limit)
    if mirror_results:
        return mirror_results

    # Fallback to USDA RSS if page fetch is blocked/unavailable.
    try:
        resp = requests.get(
            USDA_RECALLS_RSS,
            headers={"User-Agent": "RecallAI/1.0"},
            timeout=(5, 12),
        )
        resp.raise_for_status()
        feed = feedparser.parse(resp.content)
    except requests.RequestException:
        return []
    except Exception:
        return []

    results = []
    for entry in feed.entries[:limit]:
        results.append(
            {
                "source": "USDA",
                "recall_number": getattr(entry, "id", None),
                "brand_name": None,
                "product_description": getattr(entry, "title", None),
                "product_type": "Food",
                "reason_for_recall": getattr(entry, "summary", None),
                "company_name": None,
                "status": None,
                "affected_area": None,
                "report_date": getattr(entry, "published", None),
                "recall_initiation_date": getattr(entry, "published", None),
                "url": getattr(entry, "link", None),
                "raw": {
                    "title": getattr(entry, "title", None),
                    "summary": getattr(entry, "summary", None),
                    "link": getattr(entry, "link", None),
                    "published": getattr(entry, "published", None),
                },
            }
        )
    return results


def fetch_all_recalls(fda_limit: int = 5, usda_limit: int = 5) -> List[Dict]:
    return fetch_fda_recalls(limit=fda_limit, sort_field="report_date") + fetch_usda_recalls(limit=usda_limit)