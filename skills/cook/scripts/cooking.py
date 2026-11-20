"""Cooking model for the Claude Cook nutrition engine.

Turns raw-ingredient nutrition into as-cooked nutrition the way USDA calculates recipes:
- nutrient retention factors from the USDA Table of Nutrient Retention Factors, Release 6 (2007),
  chosen by food group and cooking method;
- cooking yields (weight change) derived from USDA SR Legacy raw/cooked pairs;
- fat lost to rendered drippings for fatty meats that are drained, from the same pairs.

A recipe line opts in with a tag: `~roast`, `~boil`, `~simmer:45` (minutes), `~brown+drain`.
"""
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.normpath(os.path.join(HERE, "..", "data"))

METHODS = {
    "raw": "raw", "bake": "bake", "baked": "bake", "airfry": "bake", "air-fry": "bake", "air-fried": "bake",
    "roast": "roast", "roasted": "roast", "smoke": "roast", "smoked": "roast",
    "broil": "broil", "broiled": "broil", "grill": "grill", "grilled": "grill", "char": "grill",
    "saute": "saute", "sauteed": "saute", "sweat": "saute", "stirfry": "stirfry", "stir-fry": "stirfry",
    "stir-fried": "stirfry", "panfry": "panfry", "pan-fry": "panfry", "pan-fried": "panfry", "sear": "sear",
    "seared": "sear", "fry": "fry", "fried": "fry", "deepfry": "fry", "deep-fry": "fry", "deep-fried": "fry",
    "fry-coated": "fry-coated", "breaded": "fry-coated", "battered": "fry-coated",
    "boil": "boil", "boiled": "boil", "blanch": "blanch", "blanched": "blanch",
    "simmer": "simmer", "simmered": "simmer", "pressure": "simmer", "stew": "stew", "stewed": "stew",
    "braise": "braise", "braised": "braise", "slow-cook": "braise", "slowcook": "braise",
    "steam": "steam", "steamed": "steam", "sous-vide": "steam", "sousvide": "steam",
    "microwave": "microwave", "microwaved": "microwave", "poach": "poach", "poached": "poach",
    "reheat": "reheat", "reheated": "reheat", "toast": "toast", "toasted": "toast",
    "brown": "brown", "browned": "brown", "mash": "mash", "mashed": "mash",
    "flame": "flame", "flambe": "flame", "deglaze": "deglaze",
}
TAG_RE = re.compile(r"~\s*([a-zA-Z-]+)(?::(\d+))?(\+drain(?:ed)?)?")

DRY = ("bake", "roast", "broil", "grill", "toast")
PAN = ("saute", "stirfry", "panfry", "sear", "brown")
WET = ("simmer", "stew", "braise")
SHORT_WET = ("boil", "blanch", "steam", "microwave", "poach")

GREENS = ("spinach", "kale", "chard", "collard", "mustard greens", "turnip greens", "beet greens", "lettuce",
          "arugula", "cabbage", "watercress", "endive", "dandelion", "escarole", "amaranth leaves", "cress",
          "broccoli raab", "pak-choi", "pe-tsai")
ROOTS = ("carrot", "beets", "beet,", "turnips", "parsnip", "radish", "rutabaga", "celeriac", "yambean",
         "yam", "taro", "cassava", "salsify", "burdock", "jerusalem")
CITRUS = ("orange", "lemon", "lime", "grapefruit", "tangerine", "mandarin", "clementine", "pummelo", "kumquat")
SHELLFISH = ("crustaceans", "mollusks", "shrimp", "crab", "lobster", "clam", "mussel", "oyster", "scallop",
             "squid", "octopus", "crayfish")


def parse_tag(text):
    """Return (method, minutes, drain, text_without_tag) for '~simmer:45' style tags."""
    m = TAG_RE.search(text)
    if not m:
        return None, None, False, text
    method = METHODS.get(m.group(1).lower())
    if method is None:
        return None, None, False, text
    minutes = int(m.group(2)) if m.group(2) else None
    return method, minutes, bool(m.group(3)), (text[:m.start()] + text[m.end():]).strip()


def cook_class(cat, desc, fat=0.0):
    """Map a food to the USDA retention-factor group it belongs to (None = no adjustment)."""
    d = desc.lower()
    first = d.split(",")[0]
    if cat == "alcohol" or d.startswith("alcoholic beverage") or first in ("wine", "beer", "sake"):
        return "alcohol"
    if cat == "dairy":
        if d.startswith("cheese"):
            return "cheese"
        if d.startswith("egg"):
            return "egg"
        if d.startswith(("butter", "ghee")):
            return None
        return "milk"
    if cat == "poultry":
        return "turkey" if d.startswith("turkey") else "chicken"
    if cat in ("pork", "sausage"):
        if "bacon" in d:
            return "bacon"
        if "ham" in first or "cured" in d:
            return "pork_cured"
        if cat == "sausage" or "sausage" in d or "chorizo" in d:
            return "sausage"
        return "pork_ground" if "ground" in d else "pork"
    if cat == "beef":
        if "liver" in d:
            return "liver"
        return "beef_ground" if "ground" in d else "beef"
    if cat == "lamb":
        if "liver" in d:
            return "liver"
        if d.startswith("veal"):
            return "veal"
        return "lamb_ground" if "ground" in d else "lamb"
    if cat == "seafood":
        if any(w in d for w in SHELLFISH):
            return "shellfish"
        return "fish_fatty" if fat >= 5 else "fish_lean"
    if cat == "veg":
        if first.startswith("potato"):
            return "potato"
        if first.startswith("sweet potato") or first.startswith("sweetpotato"):
            return "sweetpotato"
        if first.startswith("tomato"):
            return "tomato"
        if any(w in d for w in GREENS):
            return "greens"
        if any(first.startswith(w.rstrip(",")) for w in ROOTS):
            return "roots"
        return "veg"
    if cat == "fruit":
        if "dried" in d or first in ("raisins", "dates", "prunes", "plums, dried"):
            return "fruit_dried"
        if any(first.startswith(w) for w in CITRUS):
            return "fruit_citrus"
        return "fruit"
    if cat == "legume":
        if any(w in d for w in ("soy sauce", "miso", "peanut", "hummus", "soymilk", "natto")):
            return None
        if "canned" in d or "cooked" in d or d.startswith(("tofu", "tempeh", "refried")):
            return "legume_cooked"
        if first.startswith(("lentil", "peas, green, split", "peas, split")) or "split" in d:
            return "legume_quick"
        return "legume"
    if cat == "grain":
        if any(w in first for w in ("pasta", "noodle", "macaroni", "spaghetti", "couscous")):
            return "pasta"
        if any(w in first for w in ("rice", "quinoa", "bulgur", "barley", "millet", "buckwheat", "farro",
                                    "wheat, durum", "amaranth", "sorghum", "wild rice")):
            return "rice"
        return "flour"
    if cat == "cereal":
        return "cereal"
    if cat == "baked":
        return "flour"
    if cat == "nut":
        return "nut" if "butter" not in d and "milk" not in d else None
    return None


# (class, method) -> USDA retention code. Methods not listed fall back by family.
CODES = {
    "cheese": {"bake": "0001", "roast": "0001", "broil": "0003", "grill": "0003", "saute": "0003", "panfry": "0003",
               "fry": "0003", "toast": "0003", "_wet": "0005", "reheat": "0007"},
    "egg": {"bake": "0101", "roast": "0101", "_pan": "0103", "fry": "0103", "microwave": "0103", "boil": "0105",
            "steam": "0105", "poach": "0107", "_wet": "0107", "reheat": "0109"},
    "chicken": {"broil": "0801", "grill": "0801", "_pan": "0803", "fry": "0803", "fry-coated": "0804",
                "bake": "0805", "roast": "0805", "microwave": "0805", "toast": "0805", "brown": "0852",
                "_wet": "0856", "boil": "0855", "poach": "0855", "steam": "0855", "blanch": "0855", "reheat": "0864"},
    "turkey": {"_dry": "1805", "_pan": "1805", "fry": "1805", "fry-coated": "1805", "_wet": "1852", "boil": "1851",
               "poach": "1851", "steam": "1851", "reheat": "1860"},
    "pork": {"broil": "1251", "grill": "1251", "_pan": "1252", "fry": "1252", "fry-coated": "1253", "bake": "1254",
             "roast": "1254", "toast": "1254", "microwave": "1254", "brown": "1352", "_wet": "1302", "boil": "1301",
             "poach": "1301", "steam": "1301", "reheat": "1407"},
    "pork_ground": {"_dry": "1402", "_pan": "1402", "fry": "1402", "brown": "1402", "_wet": "1406", "boil": "1405",
                    "reheat": "1407", "_drain": "1401"},
    "pork_cured": {"bake": "1459", "roast": "1459", "broil": "1451", "grill": "1451", "_pan": "1451", "fry": "1451",
                   "_wet": "1522", "boil": "1521", "reheat": "1606"},
    "bacon": {"_any": "1456"},
    "sausage": {"broil": "1707", "grill": "1707", "bake": "1707", "roast": "1707", "_pan": "1709", "fry": "1709",
                "_wet": "1706", "boil": "1705", "poach": "1705", "reheat": "1712"},
    "beef": {"broil": "0602", "grill": "0602", "_pan": "0604", "fry": "0604", "fry-coated": "0605", "bake": "0601",
             "roast": "0601", "toast": "0601", "microwave": "0601", "brown": "0702", "braise": "0652",
             "stew": "0652", "simmer": "0654", "boil": "0653", "poach": "0653", "steam": "0653", "reheat": "0770"},
    "beef_ground": {"broil": "0603", "grill": "0603", "bake": "0750", "roast": "0750", "_pan": "0752",
                    "fry": "0752", "brown": "0752", "_wet": "0754", "boil": "0753", "reheat": "0770",
                    "_drain_dry": "0749", "_drain": "0751"},
    "lamb": {"broil": "1001", "grill": "1001", "_pan": "1001", "fry": "1001", "bake": "1004", "roast": "1004",
             "brown": "1052", "_wet": "1056", "boil": "1055", "poach": "1055", "reheat": "1074"},
    "lamb_ground": {"_any": "1003", "_wet": "1056", "reheat": "1074"},
    "veal": {"broil": "1951", "grill": "1951", "_pan": "1952", "fry": "1952", "fry-coated": "1953", "bake": "1954",
             "roast": "1954", "brown": "2052", "braise": "2002", "_wet": "2004", "reheat": "2064"},
    "liver": {"_pan": "1151", "fry": "1151", "_dry": "1151", "_wet": "1153", "boil": "1152", "reheat": "1154"},
    "fish_lean": {"bake": "2301", "roast": "2301", "broil": "2305", "grill": "2305", "_pan": "2309", "fry": "2309",
                  "fry-coated": "2310", "poach": "2401", "steam": "2401", "boil": "2401", "microwave": "2401",
                  "_wet": "2402", "reheat": "2554"},
    "fish_fatty": {"bake": "2451", "roast": "2451", "broil": "2455", "grill": "2455", "_pan": "2459", "fry": "2459",
                   "fry-coated": "2460", "poach": "2551", "steam": "2551", "boil": "2551", "microwave": "2551",
                   "_wet": "2552", "reheat": "2554"},
    "shellfish": {"bake": "2750", "roast": "2750", "broil": "2753", "grill": "2753", "_pan": "2755", "fry": "2755",
                  "fry-coated": "2756", "boil": "2761", "poach": "2761", "_wet": "2762", "steam": "2770",
                  "microwave": "2770", "reheat": "2771"},
    "potato": {"bake": "3301", "roast": "3301", "microwave": "3301", "boil": "3308", "_wet": "3309",
               "steam": "3307", "_pan": "3315", "fry": "3315", "fry-coated": "3315", "mash": "3316",
               "reheat": "3379", "broil": "3315", "grill": "3315"},
    "sweetpotato": {"bake": "3701", "roast": "3701", "microwave": "3701", "boil": "3708", "_wet": "3709",
                    "steam": "3707", "_pan": "3710", "fry": "3710", "mash": "3708", "reheat": "3711"},
    "tomato": {"_dry": "3751", "_wet": "3751", "boil": "3751", "_pan": "3752", "fry": "3752", "broil": "3752",
               "grill": "3752", "reheat": "3754"},
    "greens": {"_dry": "3001", "boil": "3005", "blanch": "3004", "steam": "3004", "microwave": "3004",
               "poach": "3004", "_wet": "3006", "_pan": "3015", "fry": "3015", "reheat": "3018"},
    "roots": {"_dry": "3451", "boil": "3455", "blanch": "3454", "microwave": "3454", "poach": "3454",
              "_wet": "3456", "_pan": "3460", "fry": "3460", "mash": "3455", "stirfry": "3465", "steam": "3464",
              "reheat": "3468"},
    "veg": {"_dry": "3771", "boil": "3775", "blanch": "3774", "microwave": "3774", "poach": "3774",
            "_wet": "3776", "_pan": "3780", "fry": "3780", "stirfry": "3785", "steam": "3784", "reheat": "3788"},
    "fruit_citrus": {"_any": "0270"},
    "fruit": {"bake": "0151", "roast": "0151", "toast": "0151", "broil": "0152", "grill": "0152", "_pan": "0153",
              "fry": "0153", "_wet": "0155", "boil": "0155", "poach": "0155", "steam": "0155", "reheat": "0157"},
    "fruit_dried": {"_dry": "0251", "_pan": "0253", "_wet": "0255", "boil": "0255", "poach": "0255",
                    "reheat": "0257"},
    "legume": {"boil": "0521", "_wet": "0522", "bake": "0524", "_pan": "0526", "fry": "0526", "reheat": "0550",
               "_long_boil": "0541", "_long_wet": "0542"},
    "legume_quick": {"boil": "0501", "_wet": "0502", "bake": "0504", "_pan": "0506", "fry": "0506",
                     "reheat": "0550"},
    "legume_cooked": {"_any": "0550"},
    "pasta": {"boil": "0381", "_wet": "0384", "bake": "0382", "reheat": "0385", "_pan": "0385"},
    "rice": {"boil": "0431", "_wet": "0432", "steam": "0432", "microwave": "0432", "_pan": "0433",
             "bake": "0432", "reheat": "0434"},
    "flour": {"bake": "0301", "roast": "0301", "_wet": "0302", "boil": "0302", "steam": "0302", "_pan": "0305",
              "fry": "0305", "toast": "0306", "reheat": "0304"},
    "cereal": {"_any": "0352"},
    "nut": {"roast": "2203", "bake": "2203", "toast": "2203", "_pan": "2203", "broil": "2202", "_wet": "2204",
            "boil": "2204"},
}
FAMILY = {m: "_dry" for m in DRY}
FAMILY.update({m: "_pan" for m in PAN})
FAMILY.update({m: "_wet" for m in WET})
FAMILY.update({"boil": "_wet", "blanch": "_wet", "steam": "_wet", "poach": "_wet", "microwave": "_dry",
               "mash": "_wet", "fry": "_pan", "fry-coated": "fry"})


def alcohol_code(method, minutes):
    if method == "flame":
        return "5003"
    if method in ("deglaze",) or (minutes is not None and minutes < 10):
        return "5002"
    if minutes is None:
        minutes = {"braise": 120, "stew": 90, "bake": 30, "roast": 60, "simmer": 30}.get(method, 15)
    for limit, code in ((15, "5004"), (30, "5005"), (60, "5006"), (90, "5007"), (120, "5008")):
        if minutes <= limit:
            return code
    return "5009"


def retention_code(cls, method, minutes=None, drain=False):
    if cls is None or method in (None, "raw"):
        return None
    if cls == "alcohol":
        return alcohol_code(method, minutes)
    if cls == "milk":
        if method == "reheat":
            return "2154"
        if minutes is None:
            minutes = 60 if method in ("braise", "stew") else 30 if method in WET + ("bake", "roast") else 10
        return "2151" if minutes <= 15 else "2152" if minutes <= 45 else "2153"
    table = CODES.get(cls, {})
    if drain:
        if method in DRY and "_drain_dry" in table:
            return table["_drain_dry"]
        if "_drain" in table:
            return table["_drain"]
    if cls == "legume" and minutes and minutes >= 100:
        key = "_long_boil" if method == "boil" else "_long_wet" if method in WET else None
        if key and key in table:
            return table[key]
    for key in (method, FAMILY.get(method), FAMILY.get(FAMILY.get(method)), "_any"):
        if key and key in table:
            return table[key]
    return None


# Fallback weight change when USDA has no raw/cooked pair for (class, method). The engine prefers
# the data-derived values in yields.tsv.
DEFAULT_YIELD = {
    "_meat": {"_dry": 0.72, "_pan": 0.72, "fry": 0.70, "fry-coated": 0.85, "_wet": 0.65, "boil": 0.65,
              "steam": 0.75, "poach": 0.75, "reheat": 0.97},
    "fish": {"_dry": 0.85, "_pan": 0.85, "fry": 0.83, "fry-coated": 0.95, "_wet": 0.88, "boil": 0.88,
             "steam": 0.88, "poach": 0.88},
    "shellfish": {"_any": 0.78},
    "potato": {"_dry": 0.75, "_pan": 0.65, "fry": 0.55, "boil": 1.0, "_wet": 1.0, "steam": 0.98, "mash": 1.0},
    "greens": {"_dry": 0.6, "_pan": 0.55, "boil": 0.9, "steam": 0.8, "blanch": 0.9, "_wet": 1.0},
    "_veg": {"_dry": 0.75, "_pan": 0.8, "fry": 0.7, "boil": 0.98, "steam": 0.95, "blanch": 0.97,
             "microwave": 0.93, "_wet": 1.0},
    "pasta": {"boil": 2.3, "_wet": 1.0, "bake": 1.0},
    "rice": {"boil": 2.9, "_wet": 1.0},
    "legume": {"boil": 2.5, "_wet": 1.0},
    "egg": {"_pan": 0.92, "boil": 1.0, "poach": 1.0, "bake": 0.9},
    "nut": {"_any": 0.98},
    "bacon": {"_any": 0.35},
}
GROUP = {"chicken": "_meat", "turkey": "_meat", "pork": "_meat", "pork_ground": "_meat", "pork_cured": "_meat",
         "bacon": "bacon", "sausage": "_meat", "beef": "_meat", "beef_ground": "_meat", "lamb": "_meat",
         "lamb_ground": "_meat", "veal": "_meat", "liver": "_meat", "fish_lean": "fish", "fish_fatty": "fish",
         "shellfish": "shellfish", "potato": "potato", "sweetpotato": "potato", "greens": "greens",
         "roots": "_veg", "veg": "_veg", "tomato": "_veg", "fruit": "_veg", "fruit_citrus": "_veg",
         "fruit_dried": "_veg", "pasta": "pasta", "rice": "rice", "legume": "legume", "legume_quick": "legume",
         "egg": "egg", "nut": "nut"}
# Share of fat kept when rendered fat is poured off, if USDA pairs don't give one.
DEFAULT_FAT_KEPT = {"bacon": 0.45, "beef_ground": 0.6, "pork_ground": 0.6, "lamb_ground": 0.6, "sausage": 0.7,
                    "chicken": 0.8, "pork": 0.85, "lamb": 0.8, "beef": 0.85}


class CookingData(object):
    def __init__(self, data_dir=DATA_DIR):
        self.retention = {}  # code -> (description, {nutrient: fraction})
        self.yields = {}  # (class, method) -> (yield, fat_kept, n)
        rpath = os.path.join(data_dir, "retention.tsv")
        if os.path.exists(rpath):
            with open(rpath, encoding="utf-8") as f:
                header = f.readline().rstrip("\n").split("\t")
                for line in f:
                    cells = line.rstrip("\n").split("\t")
                    factors = {k: float(v) / 100.0 for k, v in zip(header[2:], cells[2:]) if v != ""}
                    self.retention[cells[0]] = (cells[1], factors)
        ypath = os.path.join(data_dir, "yields.tsv")
        if os.path.exists(ypath):
            with open(ypath, encoding="utf-8") as f:
                f.readline()
                for line in f:
                    cls, method, y, fat_kept, n = line.rstrip("\n").split("\t")
                    self.yields[(cls, method)] = (float(y), float(fat_kept) if fat_kept else None, int(n))

    def weight_yield(self, cls, method):
        if cls is None or method in (None, "raw"):
            return 1.0
        hit = self.yields.get((cls, method)) or self.yields.get((cls, FAMILY.get(method)))
        if hit:
            return hit[0]
        table = DEFAULT_YIELD.get(GROUP.get(cls, ""), {})
        for key in (method, FAMILY.get(method), "_any"):
            if key in table:
                return table[key]
        return 1.0

    def fat_kept(self, cls, method):
        hit = self.yields.get((cls, method)) or self.yields.get((cls, FAMILY.get(method)))
        if hit and hit[1] is not None:
            return hit[1]
        return DEFAULT_FAT_KEPT.get(cls, 0.85)

    def apply(self, food_values, cls, method, minutes=None, drain=False):
        """Return (cooked values per 100 g raw, retention code, description, yield, fat_kept)."""
        if method in (None, "raw"):
            return dict(food_values), None, None, 1.0, 1.0
        values = dict(food_values)
        code = retention_code(cls, method, minutes, drain)
        desc = None
        if code and code in self.retention:
            desc, factors = self.retention[code]
            for key, frac in factors.items():
                if key in values:
                    if key == "alcohol":
                        lost = values["alcohol"] * (1 - frac)
                        values["kcal"] = max(values.get("kcal", 0) - 6.93 * lost, 0)
                    values[key] *= frac
        kept = 1.0
        if drain or cls == "bacon":
            kept = self.fat_kept(cls, method)
            lost = values.get("fat", 0) * (1 - kept)
            for key in ("fat", "satfat", "mufa", "pufa", "transfat", "ala", "epa", "dha", "dpa"):
                if key in values:
                    values[key] *= kept
            values["kcal"] = max(values.get("kcal", 0) - 9 * lost, 0)
        return values, code, desc, self.weight_yield(cls, method), kept
