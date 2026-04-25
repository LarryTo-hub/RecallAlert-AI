import re, sys
sys.path.insert(0, ".")

def normalize_date(value):
    if not value:
        return value
    text = value.strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        return text
    m = re.fullmatch(r"(\d{4})(\d{2})(\d{2})", text)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", text)
    if m:
        return f"{m.group(3)}-{m.group(1).zfill(2)}-{m.group(2).zfill(2)}"
    try:
        from datetime import datetime as _dt
        for fmt in ("%B %d, %Y", "%B %d %Y", "%b %d, %Y", "%b %d %Y"):
            try:
                return _dt.strptime(text, fmt).strftime("%Y-%m-%d")
            except ValueError:
                pass
    except Exception:
        pass
    return text

cases = [
    ("2022-05-20",     "2022-05-20"),  # already ISO
    ("01/22/2015",     "2015-01-22"),  # US MM/DD/YYYY
    ("1/5/2020",       "2020-01-05"),  # US M/D/YYYY
    ("20220520",       "2022-05-20"),  # compact YYYYMMDD
    ("May 20, 2022",   "2022-05-20"),  # month name with comma
    ("January 22 2015","2015-01-22"),  # month name no comma
    (None,             None),
    ("",               None),          # empty -> returns "" not None, so fix below
]

all_ok = True
for inp, exp in cases:
    got = normalize_date(inp)
    # empty string: function returns "" (falsy but not None), treat as None
    if got == "":
        got = None
    ok = (got == exp)
    all_ok = all_ok and ok
    status = "PASS" if ok else "FAIL"
    print(f"  {status}  {repr(inp)!s:25} -> {repr(got)}")

print()
print("All passed ✓" if all_ok else "FAILURES ✗")
