"""Fetch recent recalls from FDA and USDA."""
from typing import List, Dict
from urllib.parse import urljoin
import re
import time
import requests
import feedparser
from bs4 import BeautifulSoup

FDA_ENFORCEMENT_ENDPOINTS = {
    "food": "https://api.fda.gov/food/enforcement.json",
    "drug": "https://api.fda.gov/drug/enforcement.json",
    "device": "https://api.fda.gov/device/enforcement.json",
}

# openFDA allows up to 1 000 results per request and skip up to 25 000.
_ENFORCEMENT_PAGE_SIZE = 100  # conservative page size to avoid timeouts
_ENFORCEMENT_MAX_SKIP = 25000  # hard cap imposed by openFDA
FDA_RECALLS_PAGE = "https://www.fda.gov/safety/recalls-market-withdrawals-safety-alerts"
USDA_RECALLS_RSS = "https://www.fsis.usda.gov/recalls/rss"
USDA_RECALLS_MIRROR = "https://r.jina.ai/http://www.fsis.usda.gov/recalls"
USDA_RECALLS_PAGE = "https://www.fsis.usda.gov/recalls"


def _normalize_date(val: str | None) -> str | None:
    """Convert YYYYMMDD → MM/DD/YYYY; leave all other formats unchanged."""
    if not val:
        return val
    m = re.fullmatch(r"(\d{4})(\d{2})(\d{2})", val.strip())
    return f"{m.group(2)}/{m.group(3)}/{m.group(1)}" if m else val


def _normalize_status(val: str | None) -> str | None:
    """Map FDA 'Ongoing' to canonical 'ACTIVE'; uppercase known statuses."""
    if not val:
        return val
    clean = val.strip().lower()
    if clean in ("ongoing", "on going", "on-going"):
        return "ACTIVE"
    upper = val.strip().upper()
    return upper if upper in ("ACTIVE", "CLOSED", "TERMINATED") else val.strip()


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


def _extract_usda_recall_number(*texts: str | None) -> str | None:
    """Extract USDA recall number, typically like '012-2026'."""
    pattern = r"\b\d{3}-\d{4}\b"
    for text in texts:
        if not text:
            continue
        m = re.search(pattern, text)
        if m:
            return m.group(0)
    return None


def _fetch_usda_recalls_from_page(limit: int | None = 5, max_pages: int = 130) -> List[Dict]:
    """Fetch USDA recalls directly from paginated USDA recalls pages."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    results: List[Dict] = []
    seen_links = set()

    for page in range(max_pages):
        try:
            resp = requests.get(
                USDA_RECALLS_PAGE,
                params={"page": page},
                headers=headers,
                timeout=(5, 15),
            )
            resp.raise_for_status()
        except requests.RequestException:
            # If first page fails, we have no results; otherwise stop pagination.
            if page == 0:
                return []
            break

        soup = BeautifulSoup(resp.text, "html.parser")
        candidates = soup.select(
            "article, .views-row, .usa-collection__item, .usa-card, .node--type-recall"
        )
        if not candidates:
            # End of pagination.
            break

        page_new = 0
        for node in candidates:
            link_tag = node.select_one("h2 a, h3 a, a")
            if not link_tag:
                continue

            title = link_tag.get_text(" ", strip=True)
            if not title:
                continue

            link = urljoin("https://www.fsis.usda.gov", link_tag.get("href") or "")
            if not link or link in seen_links:
                continue
            seen_links.add(link)

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
                m = re.search(r"\b\d{1,2}/\d{1,2}/\d{4}\b", node_text)
                report_date = m.group(0) if m else None

            recall_number = _extract_usda_recall_number(title, link, node_text)

            results.append(
                {
                    "source": "USDA-web",
                    "recall_number": recall_number,
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
            page_new += 1

            if limit is not None and len(results) >= limit:
                return results

        # If a page had no new links, stop to avoid spinning on repeated pages.
        if page_new == 0:
            break

    return results


# _fetch_usda_recalls_from_mirror is defined below
def _fetch_usda_recalls_from_mirror(
    limit: int | None = 5,
    max_pages: int = 150,
    start_page: int = 0,
    per_page_retries: int = 3,
) -> List[Dict]:
    """Fetch USDA recalls from text mirror, including pagination by page query.

    Covers all historical pages (USDA site currently has 120+ pages going back
    to 2014).  Stops only after 3 consecutive pages that yield no new entries,
    which guards against transient r.jina.ai failures without cutting off early.
    """
    results: List[Dict] = []
    seen_links = set()
    consecutive_empty = 0
    consecutive_failures = 0

    for page in range(start_page, start_page + max_pages):
        mirror_url = USDA_RECALLS_MIRROR if page == 0 else f"{USDA_RECALLS_MIRROR}?page={page}"
        resp = None
        for attempt in range(max(1, per_page_retries)):
            try:
                candidate = requests.get(
                    mirror_url,
                    headers={"User-Agent": "Mozilla/5.0 (RecallAI)"},
                    timeout=(6, 25),
                )
                candidate.raise_for_status()
                resp = candidate
                break
            except requests.RequestException:
                # Small backoff helps avoid transient throttling on deep crawls.
                time.sleep(0.35 * (attempt + 1))

        if resp is None:
            # r.jina.ai can intermittently fail for some pages; continue until
            # failures are sustained so we don't truncate historical coverage.
            consecutive_failures += 1
            if consecutive_failures >= 5:
                if page == 0:
                    return []
                break
            continue

        consecutive_failures = 0

        lines = resp.text.splitlines()
        page_new = 0

        i = 0
        while i < len(lines):
            line = lines[i].strip()

            # Recall entry title line format:
            # ### [Title](http://www.fsis.usda.gov/recalls-alerts/...)
            m_title = re.match(r"^### \[(.+?)\]\((http[^)]+/recalls-alerts/[^)]+)\)", line)
            if not m_title:
                i += 1
                continue

            title = m_title.group(1).strip()
            link = m_title.group(2).strip()
            if not link or link in seen_links:
                i += 1
                continue
            seen_links.add(link)

            recall_number = _extract_usda_recall_number(title, link)

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
                    "recall_number": recall_number,
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
            page_new += 1

            if limit is not None and len(results) >= limit:
                return results

            i = j + 1

        # Stop only after 3 consecutive pages with no new entries, to tolerate
        # transient r.jina.ai fetch failures on individual pages.
        if page_new == 0:
            consecutive_empty += 1
            if consecutive_empty >= 3:
                break
        else:
            consecutive_empty = 0

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


def _fetch_fda_recalls_from_enforcement(
    limit: int | None = None,
    sort_field: str = "report_date",
) -> List[Dict]:
    """Fetch FDA recalls from openFDA enforcement APIs with full pagination.

    Args:
        limit: Maximum total records to return across all categories.
               Pass None to fetch every available record (up to the openFDA
               skip cap of 25 000 per category).
        sort_field: Result ordering field (descending).
    """
    combined: List[Dict] = []

    for category, endpoint in FDA_ENFORCEMENT_ENDPOINTS.items():
        skip = 0
        while True:
            # How many more records do we still want from this call?
            if limit is not None:
                needed = limit - len(combined)
                if needed <= 0:
                    break
                page_size = min(_ENFORCEMENT_PAGE_SIZE, needed)
            else:
                page_size = _ENFORCEMENT_PAGE_SIZE

            params = {
                "limit": page_size,
                "skip": skip,
                "sort": f"{sort_field}:desc",
            }
            try:
                resp = requests.get(endpoint, params=params, timeout=(5, 20))
                resp.raise_for_status()
                data = resp.json()
            except requests.RequestException:
                break

            results = data.get("results", [])
            if not results:
                break

            for item in results:
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
                        "status": _normalize_status(item.get("status") or item.get("recall_status")),
                        "affected_area": item.get("distribution_pattern"),
                        "report_date": _normalize_date(item.get("report_date")),
                        "recall_initiation_date": _normalize_date(item.get("recall_initiation_date")),
                        "url": None,
                        "raw": item,
                    }
                )

            meta = data.get("meta", {}).get("results", {})
            total = meta.get("total", 0)
            skip += len(results)

            # Stop when the category is exhausted or we hit the openFDA hard cap.
            if skip >= total or skip >= _ENFORCEMENT_MAX_SKIP:
                break

    combined.sort(key=lambda x: (x.get(sort_field) or ""), reverse=True)
    if limit is not None:
        combined = combined[:limit]
    return combined


def iter_fda_recalls_pages(sort_field: str = "report_date"):
    """Generator that yields one page (list of dicts) of FDA enforcement records at a time.

    Allows callers to save records to the DB progressively page-by-page
    instead of waiting for all pages to be fetched first.
    """
    for category, endpoint in FDA_ENFORCEMENT_ENDPOINTS.items():
        skip = 0
        while True:
            params = {
                "limit": _ENFORCEMENT_PAGE_SIZE,
                "skip": skip,
                "sort": f"{sort_field}:desc",
            }
            try:
                resp = requests.get(endpoint, params=params, timeout=(5, 20))
                resp.raise_for_status()
                data = resp.json()
            except requests.RequestException:
                break

            results = data.get("results", [])
            if not results:
                break

            page_records = []
            for item in results:
                openfda = item.get("openfda") or {}
                brand_names = openfda.get("brand_name") or []
                page_records.append(
                    {
                        "source": f"FDA-{category}",
                        "recall_number": item.get("recall_number"),
                        "brand_name": ", ".join(brand_names) if isinstance(brand_names, list) else str(brand_names or ""),
                        "product_description": item.get("product_description"),
                        "product_type": item.get("product_type") or category.title(),
                        "reason_for_recall": item.get("reason_for_recall"),
                        "company_name": item.get("company_name") or item.get("recalling_firm"),
                        "status": _normalize_status(item.get("status") or item.get("recall_status")),
                        "affected_area": item.get("distribution_pattern"),
                        "report_date": _normalize_date(item.get("report_date")),
                        "recall_initiation_date": _normalize_date(item.get("recall_initiation_date")),
                        "url": None,
                        "raw": item,
                    }
                )

            yield page_records

            meta = data.get("meta", {}).get("results", {})
            total = meta.get("total", 0)
            skip += len(results)

            if skip >= total or skip >= _ENFORCEMENT_MAX_SKIP:
                break


def fetch_fda_recalls(limit: int | None = None, sort_field: str = "report_date") -> List[Dict]:
    """Fetch FDA recalls with optional full pagination.

    - limit=None (default): paginate exhaustively through all categories
      (food / drug / device) using the openFDA enforcement API.  This is
      the recommended mode for the initial database seed and for catching
      every recall across 50+ pages of the FDA site.
    - limit=N (small number, ≤ 50): tries the live FDA webpage table first
      so results match what users see on fda.gov, then falls back to the
      enforcement API.

    All results are deduplicated downstream by recall_number / SHA-1 hash,
    so safe to call repeatedly without creating duplicate records.
    """
    # For bulk / comprehensive fetches use the enforcement API directly —
    # the webpage is a single JS-rendered table and cannot be paginated.
    if limit is None or limit > 50:
        return _fetch_fda_recalls_from_enforcement(limit=limit, sort_field=sort_field)

    # For small on-demand fetches, prefer the live webpage table.
    page_results = _fetch_fda_recalls_from_page(limit=limit)
    if page_results:
        return page_results
    return _fetch_fda_recalls_from_enforcement(limit=limit, sort_field=sort_field)


def fetch_usda_recalls(limit: int | None = 5) -> List[Dict]:
    # Pull from both sources (web + mirror) and merge. Either source can be
    # incomplete on a given run due FSIS bot controls or transient mirror issues.
    # Unioning both gives the best historical coverage.
    page_results = _fetch_usda_recalls_from_page(limit=None if limit is None else max(limit, 50))
    mirror_results = _fetch_usda_recalls_from_mirror(limit=None if limit is None else max(limit, 50))

    # For full historical pulls, run an extra sweep over deep pages where the
    # long-running ACTIVE recalls (e.g., 2014-CURRENT) tend to appear.
    if limit is None:
        mirror_results += _fetch_usda_recalls_from_mirror(limit=None, max_pages=80, start_page=60)
        for anchor_page in (100, 110, 115, 118, 119, 120, 121):
            mirror_results += _fetch_usda_recalls_from_mirror(
                limit=None,
                max_pages=1,
                start_page=anchor_page,
                per_page_retries=8,
            )

    combined = page_results + mirror_results
    if combined:
        seen = set()
        deduped = []
        for r in combined:
            key = r.get("recall_number") or r.get("url") or r.get("product_description")
            if key in seen:
                continue
            seen.add(key)
            deduped.append(r)
            if limit is not None and len(deduped) >= limit:
                break
        return deduped

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
    for entry in (feed.entries if limit is None else feed.entries[:limit]):
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


def fetch_all_recalls(fda_limit: int | None = None, usda_limit: int | None = None) -> List[Dict]:
    """Fetch all recalls from all sources. Pass fda_limit=N to cap FDA records."""
    return fetch_fda_recalls(limit=fda_limit, sort_field="report_date") + fetch_usda_recalls(limit=usda_limit)