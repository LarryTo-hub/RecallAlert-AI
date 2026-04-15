"""Validates that the deterministic_match and parse_recall fixes work correctly."""
import sys
sys.path.insert(0, '.')

from src.agent import _extract_product_name, _tokenize, _candidate_filter

def deterministic_match_test(recall_desc, brand, pantry_items):
    """Mirror of the fixed deterministic_match logic in api.py."""
    clean_desc = _extract_product_name(str(recall_desc or ''))
    brand_name = str(brand or '')
    clean_text = (clean_desc + ' ' + brand_name).lower()
    MIN_RECALL_COVERAGE = 0.40
    matched = []
    for item in pantry_items:
        name = str(item.get('product_name') or '').strip()
        item_brand = str(item.get('brand') or '').strip().lower()
        if not name:
            continue
        item_tokens = _tokenize(name)
        # Skip single-word generic items (no brand) — LLM handles these
        if len(item_tokens) <= 1 and not item_brand:
            print(f'  SKIP (single-word, no brand): {name}')
            continue
        name_lower = name.lower()
        recall_tokens = _tokenize(clean_text)
        overlap = len(item_tokens & recall_tokens)
        coverage = overlap / len(recall_tokens) if recall_tokens else 0.0
        if name_lower in clean_text and coverage >= MIN_RECALL_COVERAGE:
            matched.append(item)
            continue
        if overlap >= 2 and coverage >= MIN_RECALL_COVERAGE:
            matched.append(item)
            continue
        if item_brand and item_brand in clean_text:
            matched.append(item)
    return matched

print("=" * 60)
print("TEST 1: _extract_product_name strips ingredient lists")
print("=" * 60)
junebar_raw = ('Junebar Peanut Chocolate Chip All Natural Snack Bar; '
               'INGREDIENTS: ORGANIC PEANUT BUTTER, DATE PASTE, ORGANIC BLACK BEANS, '
               'ORGANIC SWEET POTATOES, GLUTEN FREE ROLLED OATS')
clean = _extract_product_name(junebar_raw)
print(f'Raw:   {junebar_raw[:80]}...')
print(f'Clean: {clean}')
assert 'SWEET POTATOES' not in clean.upper(), 'FAIL: SWEET POTATOES still in clean desc'
assert 'POTATOES' not in clean.upper(), 'FAIL: POTATOES still in clean'
print('PASS\n')

print("=" * 60)
print("TEST 2: 'potatoes' tokens NOT in clean Junebar desc")
print("=" * 60)
tokens = _tokenize(clean)
print(f'Tokens: {tokens}')
assert 'potatoes' not in tokens, 'FAIL: potatoes in clean tokens'
print('PASS\n')

print("=" * 60)
print("TEST 3: deterministic_match on known false-positive recalls")
print("=" * 60)
pantry = [
    {'product_name': 'POTATOES', 'brand': None},
    {'product_name': 'GARLIC', 'brand': None},
    {'product_name': 'SOY SAUCE', 'brand': None},
    {'product_name': 'SESAME SEED', 'brand': None},
]

cases = [
    (junebar_raw, 'Junebar', [], "Junebar + POTATOES"),
    ('GREENWAY FARMS of Georgia GARLIC DILL PICKLES CHIPS', 'Greenway Farms', [], "Garlic pickles + GARLIC"),
    ('Item 81097 Ajinomoto Ling Ling Restaurant Style Fried Rice; INGREDIENTS: soy sauce, sesame oil', 'Ajinomoto', [], "Fried rice + SOY SAUCE/SESAME SEED"),
    ('Sunflour Bakery Sesame Seed Hamburger Bun', 'Sunflour Bakery', [], "Sesame Seed Bun product name + SESAME SEED (coverage too low)"),
]

all_pass = True
for desc, brand, expected_names, label in cases:
    print(f'\n  Case: {label}')
    matched = deterministic_match_test(desc, brand, pantry)
    names = [x['product_name'] for x in matched]
    if names == expected_names:
        print(f'  PASS: matched={names}')
    else:
        print(f'  FAIL: expected={expected_names}, got={names}')
        all_pass = False

print()
print("=" * 60)
print("TEST 4: Valid multi-word product STILL matches (no false negatives)")
print("=" * 60)
pantry_valid = [
    {'product_name': 'Ritz Peanut Butter Crackers', 'brand': 'Ritz'},
    {'product_name': 'Ajinomoto Fried Rice', 'brand': 'Ajinomoto'},
]
valid_cases = [
    ('Ritz Peanut Butter Sandwich Crackers', 'Ritz', ['Ritz Peanut Butter Crackers'], "Ritz crackers"),
    ('Item 81097 Ajinomoto Ling Ling Restaurant Style Fried Rice', 'Ajinomoto', ['Ajinomoto Fried Rice'], "Ajinomoto fried rice"),
]
for desc, brand, expected_names, label in valid_cases:
    matched = deterministic_match_test(desc, brand, pantry_valid)
    names = [x['product_name'] for x in matched]
    if set(names) == set(expected_names):
        print(f'PASS ({label}): matched={names}')
    else:
        print(f'FAIL ({label}): expected={expected_names}, got={names}')
        all_pass = False

print()
print("=" * 60)
if all_pass:
    print("ALL TESTS PASSED")
else:
    print("SOME TESTS FAILED - review output above")
print("=" * 60)
