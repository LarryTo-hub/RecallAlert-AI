"""Validate Stage 1 filter against all 16 false-positive cases from the screenshot."""
import sys
sys.path.insert(0, ".")

from src.agent import _extract_product_name, _candidate_filter

GARLIC = {"product_name": "GARLIC", "brand": None, "lot_code": None}
POTATOES = {"product_name": "POTATOES", "brand": None, "lot_code": None}
SOY = {"product_name": "SOY SAUCE", "brand": None, "lot_code": None}
SESAME = {"product_name": "SESAME SEED", "brand": None, "lot_code": None}

# (raw_product_description, pantry_item, expect_match, label)
cases = [
    ("Junebar Peanut Chocolate Chip All Natural Snack Bar; INGREDIENTS: ORGANIC PEANUT BUTTER, DATE PASTE, ORGANIC BLACK BEANS, ORGANIC SWEET POTATOES, GLUTEN FREE ROLLED OATS", POTATOES, False, "Junebar bar POTATOES"),
    ("Junebar Chocolate Cherry All Natural Snack Bar; INGREDIENTS: ORGANIC ALMOND BUTTER, DATE PASTE, ORGANIC BLACK BEANS, ORGANIC SWEET POTATOES", POTATOES, False, "Junebar Cherry POTATOES"),
    ("Ore-Ida Tater Tots shaped potatoes, item number OIF00215A. Frozen potato product. Net Wt. 30 lbs", POTATOES, False, "Ore-Ida Tater Tots POTATOES"),
    ("Spicy Breakfast Burrito in a flour tortilla. Net Weight 10 oz Scrambled eggs, Salsa, Potatoes, Jalapenos.", POTATOES, False, "Breakfast Burrito POTATOES"),
    ("MEI HEONG YUEN GARLIC FLAVOR ROASTED PEANUTS; 9.17 oz; Ingredients: Peanuts, Salt, Garlic; Shelf Life: 18 Months", GARLIC, False, "Garlic Peanuts GARLIC"),
    ("Item 5650883 Ajinomoto Teppanyaki Style Vegetable Fried Rice - Japanese-style fried rice made with colorful vegetables in an aromatic garlic butter sauce.", GARLIC, False, "Teppanyaki Fried Rice GARLIC"),
    ("SAVANNAH BEE COMPANY HONEY BBQ SAUCE MUSTARD NET 16 FL OZ. INGREDIENTS: MUSTARD, HONEY, WATER, GARLIC", GARLIC, False, "Honey BBQ Sauce GARLIC"),
    ("SAVANNAH BEE COMPANY HONEY BBQ SAUCE MUSTARD NET 16 FL OZ. INGREDIENTS: MUSTARD, HONEY, WATER", SOY, False, "Honey BBQ Sauce SOY SAUCE"),
    ("GREENWAY FARMS of Georgia GARLIC DILL PICKLES CHIPS Net Wt 16 fl oz", GARLIC, False, "Garlic Dill Pickles GARLIC"),
    ("Dreamland's Zaatar Chickpea Salad is packaged in poly bags with a generic label which declares chickpeas, cumin, zataar, turmeric, dill, onion, garlic, parsley.", GARLIC, False, "Chickpea Salad GARLIC"),
    ("Made Fresh Salads brand Garlic & Herb Cream Cheese; 5 lb white plastic tub", GARLIC, False, "Garlic Herb Cream Cheese GARLIC"),
    ("Carrot Top Kitchens Lemon & Garlic Hummus; contains chickpeas, tahini, lemon juice & zest, garlic, salt; 8 oz.", GARLIC, False, "Lemon Garlic Hummus GARLIC"),
    ("Carrot Top Kitchens Cherry Pepper Hummus; contains chickpeas, tahini, pickled cherry peppers, vinegar, garlic, salt; 8 oz.", GARLIC, False, "Cherry Pepper Hummus GARLIC"),
    ("GLUTEN FREE 14 SEASONED VEGAN PIZZA CRUST; INGREDIENTS: WATER, RICE FLOUR, POTATO STARCH, GARLIC POWDER; MANUFACTURED BY VENCE BAKERY; Net Case Wt: 14 LB 6 OZ", GARLIC, False, "Pizza Crust GARLIC"),
    ("spicely ORGANIC garlic salt NO ARTIFICIAL COLORING NO GLUTEN - NO MSG Net wt: 3.4oz Ingredients: Salt, Garlic", GARLIC, False, "Spicely Garlic Salt GARLIC"),
    ("Sunflour Bakery Hamburger Bun, 18oz plastic bag containing 6 buns. UPC- 832971001522", SESAME, False, "Hamburger Bun SESAME SEED"),
    ("Item 81097 Ajinomoto Ling Ling Restaurant Style Fried Rice Savory Vegetable - A Chinese Style Fried Rice with Edamame, Carrots, Fire Roasted Corn & Red Bell Peppers Prepared with Sweet Soy Sauce Infused Rice. Net wt. 17oz.", SOY, False, "Ling Ling Fried Rice SOY SAUCE"),
    # True positives — should still match
    ("Ajinomoto Chicken Fried Rice", {"product_name": "Ajinomoto Chicken Fried Rice", "brand": "Ajinomoto", "lot_code": None}, True, "TRUE POSITIVE: exact name match"),
    ("Ritz Peanut Butter Sandwich Crackers all sizes", {"product_name": "Ritz Peanut Butter Crackers", "brand": "Ritz", "lot_code": None}, True, "TRUE POSITIVE: Ritz crackers brand match"),
]

passed = failed = 0
for desc, item, expect_match, label in cases:
    parsed = {"products": [_extract_product_name(desc)], "brands": [], "lot_codes": []}
    cands = _candidate_filter(parsed, [item])
    got_match = len(cands) > 0
    ok = got_match == expect_match
    if ok:
        passed += 1
    else:
        failed += 1
    status = "PASS" if ok else "FAIL <<<<<"
    extracted = _extract_product_name(desc)
    print(f"[{status}] {label}")
    if not ok:
        print(f"         extracted name : {extracted}")
        print(f"         item           : {item['product_name']}")
        print(f"         got_match={got_match}, expected={expect_match}")

print(f"\n{'='*50}")
print(f"Result: {passed}/{passed+failed} passed  ({'OK' if failed == 0 else str(failed) + ' FAILURES'})")
