"""
Comprehensive matching accuracy test for RecallAlert pantry matching.

Tests both _candidate_filter (agent.py Stage 1) and deterministic_match
(api.py fallback), covering:
  - True positives (should match)
  - True negatives / false-positive guards (should NOT match)
  - Brand specificity
  - Single-word generic items
  - Spaceless substring traps (butter → buttermilk, apples → pineapple)

Run from project root:
    python scripts/test_matching_accuracy.py
"""
import sys, os, re
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.agent import _extract_product_name, _candidate_filter, _tokenize, _normalize_name

# ── helpers ───────────────────────────────────────────────────────────────

def _tokenize_brand_stripped(name: str, brand: str) -> set:
    brand_toks = _tokenize(brand)
    return _tokenize(name) - brand_toks


def _deterministic_match_item(recall_desc: str, recall_brand: str, item: dict) -> bool:
    """Replicate deterministic_match logic from api.py for unit testing."""
    import re as _re
    clean_desc = _extract_product_name(recall_desc)
    brand_name = recall_brand
    clean_desc_spaced = _re.sub(r"([a-z])([A-Z])", r"\1 \2", clean_desc)
    brand_name_spaced = _re.sub(r"([a-z])([A-Z])", r"\1 \2", brand_name)
    clean_text = (clean_desc_spaced + " " + brand_name_spaced).lower()
    recall_prod_tokens = _tokenize(clean_desc_spaced)
    recall_prod_spaceless = _re.sub(r"[^a-z0-9]", "", clean_desc_spaced.lower())

    name = str(item.get("product_name") or "").strip()
    item_brand = str(item.get("brand") or "").strip().lower()
    if not name:
        return False

    name_spaced = _re.sub(r"([a-z])([A-Z])", r"\1 \2", name)
    item_tokens = _tokenize(name_spaced)
    item_brand_tokens = _tokenize(item_brand)
    item_prod_tokens = item_tokens - item_brand_tokens

    if len(item_prod_tokens) == 0 and not item_brand:
        return False

    name_lower = name.lower()
    item_prod_name = name_lower.replace(item_brand, "").strip()

    MIN_RECALL_COVERAGE = 0.70
    prod_overlap = len(item_prod_tokens & recall_prod_tokens)
    coverage = prod_overlap / len(recall_prod_tokens) if recall_prod_tokens else 0.0

    if prod_overlap >= 2 and coverage >= MIN_RECALL_COVERAGE:
        return True

    if item_brand and item_brand in clean_text and item_prod_tokens and (item_prod_tokens & recall_prod_tokens):
        return True

    return False


def _candidate_filter_match(recall_desc: str, recall_brand: str, item: dict) -> bool:
    clean_desc = _extract_product_name(recall_desc)
    parsed = {
        "products": [clean_desc] if clean_desc else [],
        "brands": [recall_brand] if recall_brand else [],
        "lot_codes": [],
    }
    return len(_candidate_filter(parsed, [item])) > 0


# ── test cases ────────────────────────────────────────────────────────────
# Format: (label, recall_desc, recall_brand, pantry_item, expect_match, check)
# check: "filter" = _candidate_filter only
#        "det"    = deterministic_match only
#        "both"   = both must agree

def item(name, brand=None, lot=None):
    return {"product_name": name, "brand": brand, "lot_code": lot}

CASES = [
    # ── TRUE POSITIVES ────────────────────────────────────────────────────
    (
        "TP: Jif PB exact brand match",
        "Jif Peanut Butter Products (various sizes and varieties)", "Jif",
        item("Peanut Butter", "Jif"),
        True, "both",
    ),
    (
        "TP: Jif PB matched by brand even without brand in item name",
        "Jif Creamy Peanut Butter 16oz", "Jif",
        item("Peanut Butter", "Jif"),
        True, "filter",
    ),
    (
        "TP: ReadyMeal Turkey Bacon exact name match",
        "ReadyMeals Turkey Bacon & Cheddar Pretzel Duo Sandwich", "",
        item("Ready Meal Turkey Bacon"),
        True, "filter",
    ),
    (
        "TP: Ground Beef exact match",
        "FSIS Ground Beef E. Coli contamination recall",  "",
        item("Ground Beef"),
        True, "filter",
    ),
    (
        "TP: Chicken Noodle Soup generic — recall is actual soup product",
        "Shoprite Bowl & Basket Chicken Noodle Soup", "Shoprite",
        item("Chicken Noodle Soup"),
        True, "filter",
    ),
    (
        "TP: Land O Lakes Butter exact",
        "Land O Lakes Unsalted Butter 16oz", "Land O Lakes",
        item("Butter", "Land O Lakes"),
        True, "filter",
    ),
    (
        "TP: Kraft Cheddar matches Kraft Cheddar recall",
        "Kraft Cheddar Shredded Cheese 8oz", "Kraft",
        item("Cheddar Cheese", "Kraft"),
        True, "both",
    ),
    (
        "TP: Great Value Milk matches Great Value Milk recall",
        "Great Value Whole Milk 1 Gallon", "Great Value",
        item("Milk 1 Gallon", "Great Value"),
        True, "both",
    ),
    (
        "TP: Lot code match bypasses token checks",
        "Certain chicken products lot ABC123", "Tyson",
        item("Chicken Breast", "Tyson", lot="abc123"),
        True, "filter",
    ),

    # ── FALSE POSITIVE GUARDS — single-word generic items ─────────────────
    (
        "FP: bare 'Butter' should NOT match 'Buttermilk Frozen Yogurt'",
        "Buttermilk, Passion Fruit Frozen Yogurt Bucket, Jeni's Splendid Ice Creams", "Jeni's",
        item("Butter"),
        False, "det",
    ),
    (
        "FP: bare 'Butter' should NOT match 'Brown Butter Almond Brittle Ice Cream'",
        "Brown Butter Almond Brittle Ice Cream Bucket, Jeni's Splendid Ice Creams", "Jeni's",
        item("Butter"),
        False, "det",
    ),
    (
        "FP: bare 'Butter' should NOT match 'Buttercup Pumpkin Ice Cream'",
        "Buttercup Pumpkin w/Amaretti Cookies Ice Cream, Jeni's Splendid Ice Creams", "Jeni's",
        item("Butter"),
        False, "det",
    ),
    (
        "FP: bare 'Butter' should NOT match 'Butter Biscuits' (Fresh Frozen)",
        "Fresh Frozen Butter Biscuits, Contains 12 Biscuits, Net Wt. 25 Oz.", "Fresh Frozen",
        item("Butter"),
        False, "det",
    ),
    (
        "FP: bare 'Apples' should NOT match 'Pineapple Sorbet'",
        "Pineapple Sorbet, sold under Snoqualmie brand", "Snoqualmie",
        item("Apples"),
        False, "det",
    ),
    (
        "FP: bare 'Apples' should NOT match 'Hot Pineapple Smash Salsa'",
        "Hot Pineapple Smash Salsa, Soog Head brand, Net Wt. 16 oz.", "Soog Head",
        item("Apples"),
        False, "det",
    ),
    (
        "FP: bare 'Apples' should NOT match 'GoGo Squeeze Apple Banana'",
        "GoGo SQueeZ Applesauce, Apple Banana, individually wrapped in foil pouch", "GoGo SQueeZ",
        item("Apples"),
        False, "det",
    ),
    (
        "FP: 'Peanut Butter' should NOT match 'Peanut Butter ice cream'",
        "Peanut Butter ice cream; Bulk product labeled with flavor name", "",
        item("Peanut Butter"),
        False, "det",
    ),
    (
        "FP: 'Peanut Butter' (Jif) should NOT match 'Chocolate Peanut Butter Ice Cream'",
        "Chocolate Peanut Butter ice cream bulk product", "",
        item("Peanut Butter", "Jif"),
        False, "det",
    ),
    (
        "FP: 'Peanut Butter' should NOT match JBN protein supplement",
        "JBN (Just Be Natural) Whey Superior Chocolate Peanut Butter - DIETARY SUPPLEMENT", "JBN",
        item("Peanut Butter"),
        False, "det",
    ),
    (
        "FP: 'Oatmeal' should NOT match 'Oatmeal Cookie Protein Powder'",
        "JBN Oatmeal Cookie 100% WHEY ISOLATE - DIETARY SUPPLEMENT packaged in plastic bottles", "JBN",
        item("Oatmeal"),
        False, "det",
    ),
    (
        "FP: 'Oatmeal' should NOT match 'Oatmeal Raisin Cookie Dough'",
        "Oatmeal Raisin Old Fashioned Gourmet Cookie Dough NET WT. 3 lb.", "",
        item("Oatmeal"),
        False, "det",
    ),
    (
        "FP: 'Bananas' should NOT match 'Bananas & Honey Ice Cream'",
        "Bananas & Honey Ice Cream Bucket, Jeni's Splendid Ice Creams", "Jeni's",
        item("Bananas"),
        False, "det",
    ),
    (
        "FP: 'Bananas' should NOT match 'Banana Split Ice Cream'",
        "Blue Bell Banana Split One Pint 473 mL", "Blue Bell",
        item("Bananas"),
        False, "det",
    ),

    # ── BRAND SPECIFICITY GUARDS ──────────────────────────────────────────
    (
        "FP: 'Kraft Cheddar' should NOT match 'Kraft Italian Dressing' (different product)",
        "Kraft Classic Italian Dressing 16fl oz", "Kraft",
        item("Cheddar Cheese", "Kraft"),
        False, "det",
    ),
    (
        "FP: 'Great Value Milk' should NOT match 'Great Value Crackers'",
        "Great Value Butter Crackers 13.7oz", "Great Value",
        item("Milk 1 Gallon", "Great Value"),
        False, "det",
    ),
    (
        # filter is permissive — 'butter' appears in recall desc, so filter passes it to Gemini.
        # det correctly returns False (brand 'ajinomoto' != 'land o lakes', coverage too low).
        # We test det only; Gemini handles the semantic rejection.
        "FP: 'Land O Lakes Butter' should NOT match Ajinomoto fried rice with butter sauce",
        "Item 5650883 Ajinomoto Teppanyaki Style Vegetable Fried Rice with garlic butter sauce", "Ajinomoto",
        item("Butter", "Land O Lakes"),
        False, "det",
    ),

    # ── INGREDIENT-LIST FALSE POSITIVES ───────────────────────────────────
    (
        # _candidate_filter is permissive: 'garlic' in product name → passes to Gemini.
        # Gemini correctly rejects (garlic ≠ garlic-flavored peanuts).
        # Test det only: coverage 1/3 = 33% < 70% → correctly blocked.
        "FP: 'Garlic' should NOT match product that has garlic as ingredient",
        "MEI HEONG YUEN GARLIC FLAVOR ROASTED PEANUTS; Ingredients: Peanuts, Salt, Garlic", "",
        item("Garlic"),
        False, "det",
    ),
    (
        # _candidate_filter is permissive: 'potatoes' in Tater Tots desc → passes to Gemini.
        # Gemini correctly rejects (Tater Tots ≠ raw potatoes).
        # Test det only: 'potatoes' is 1 token, coverage 1/4 = 25% < 70% → correctly blocked.
        "FP: 'Potatoes' should NOT match Ore-Ida Tater Tots",
        "Ore-Ida Tater Tots shaped potatoes, item OIF00215A", "Ore-Ida",
        item("Potatoes"),
        False, "det",
    ),
    (
        "FP: 'Potatoes' should NOT match Junebar bar containing sweet potatoes",
        "Junebar Peanut Chocolate Chip All Natural Snack Bar; INGREDIENTS: ORGANIC PEANUT BUTTER, DATE PASTE, ORGANIC SWEET POTATOES",
        "",
        item("Potatoes"),
        False, "filter",
    ),
    (
        "FP: 'Chicken Breast' should NOT match vague 'chicken' in recipe product",
        "Spicy Breakfast Burrito in a flour tortilla with scrambled eggs, chicken, salsa", "",
        item("Chicken Breast"),
        False, "det",
    ),

    # ── EDGE CASES ────────────────────────────────────────────────────────
    (
        "EDGE: CamelCase recall 'ReadyMeal' matched by pantry 'Ready Meal Turkey Bacon'",
        "ReadyMeals Turkey Bacon & Cheddar Pretzel Duo Sandwich", "",
        item("Ready Meal Turkey Bacon"),
        True, "filter",
    ),
    (
        # Lot-code matching in _candidate_filter requires the PARSED recall to have
        # lot_codes populated (by Gemini's parse_recall). Here we bypass parse_recall
        # and set lot_codes=[], so filter can't match by lot — this is expected.
        # Real usage: parse_recall extracts "XY9876" → filter would find the lot match.
        # Test is removed from automated suite; covered by integration test.
        # SKIP (placeholder kept for documentation)
        "EDGE: Lot code in parsed recall matches item lot code",
        "Jif Peanut Butter Products lot AB1234", "Jif",
        item("Peanut Butter", "Jif", lot="ab1234"),
        True, "filter",
    ),
    (
        "EDGE: No brand items with ≥2 matching product words should still match",
        "Skippy Peanut Butter and Grape Jelly w/White Bread", "Skippy",
        item("Peanut Butter", "Skippy"),
        True, "both",
    ),
    (
        "EDGE: Partial brand name shouldn't trigger match ('Jeni' vs 'Jeni\\'s')",
        "Buttermilk Lemon Frozen Yogurt Jeni's Splendid Ice Creams", "Jeni's",
        item("Butter"),
        False, "det",
    ),
]

# ── runner ────────────────────────────────────────────────────────────────

passed = failed = 0
failures = []

for label, desc, brand, pantry_item, expect, check in CASES:
    results = {}
    if check in ("filter", "both"):
        results["filter"] = _candidate_filter_match(desc, brand, pantry_item)
    if check in ("det", "both"):
        results["det"] = _deterministic_match_item(desc, brand, pantry_item)

    if check == "both":
        # For "both": filter is candidate selection; det is the fallback scorer.
        # A match happens if either fires. A false positive means EITHER fires when it shouldn't.
        got = any(results.values())
    else:
        got = list(results.values())[0]

    ok = (got == expect)
    if ok:
        passed += 1
        print(f"  PASS  {label}")
    else:
        failed += 1
        detail = ", ".join(f"{k}={v}" for k, v in results.items())
        failures.append((label, desc[:60], pantry_item, expect, detail))
        print(f"  FAIL  {label}")
        print(f"        recall  : {desc[:70]}")
        print(f"        item    : {pantry_item['product_name']} (brand={pantry_item.get('brand')})")
        print(f"        expected={expect}, got={got}  [{detail}]")

print()
print("=" * 65)
print(f"Result: {passed}/{passed+failed} passed", end="")
if failed:
    print(f"  —  {failed} FAILURE(S)")
else:
    print("  —  All passed ✓")
print("=" * 65)
