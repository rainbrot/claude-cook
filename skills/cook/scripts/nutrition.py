#!/usr/bin/env python3
"""Claude Cook nutrition engine. Standard library only, works offline.

Commands (add -h to any for details):
  analyze  FILE|-      nutrition label + kitchen checks for one or more recipes
  search   QUERY       find USDA foods; pin one in a recipe line with =fdc:ID
  portions QUERY|ID    USDA gram weights (cup, tbsp, medium, clove...) for a food
  day      FILE...     meal-plan totals: "# Day" headers, "## Meal" sections
  shop     FILE...     consolidated grocery list grouped by store section
  targets  ...         calorie, macro and micronutrient targets for a person

Recipe format (one ingredient per line, quantities as you would write them):
  # Chicken tinga                         <- title (optional)
  servings: 4
  yield: 1500 g                           <- finished cooked weight (optional)
  type: braise                            <- enables the salt-target check
  900 g boneless skinless chicken thighs
  1 medium onion, sliced
  1 (400 g) can crushed tomatoes
  1000 g canola oil @8%                   <- only 8% is eaten (deep frying)
  20 g gochujang {kcal=210 carb=45 sugar=21 protein=5 fat=1.5 sodium=2450}
  1/2 cup cilantro =fdc:169997            <- pin an exact USDA food
  680 g chicken thighs ~roast             <- cooking method: applies USDA retention factors and yields
  450 g ground beef ~brown+drain          <- rendered fat poured off
  2 tbsp Mother-in-Law's gochujang =online  <- fetch this exact product from USDA FoodData Central
Methods: bake roast broil grill saute stirfry panfry sear fry fry-coated boil blanch simmer stew braise
steam microwave poach toast brown mash reheat flame deglaze; add :minutes (~braise:150) and +drain.
Several recipes in one file: start each with "## Name".
"""
import argparse
import hashlib
import json
import math
import os
import re
import sys
import unicodedata
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import cooking  # noqa: E402

DATA_DIR = os.path.normpath(os.path.join(HERE, "..", "data"))
CACHE_DIR = os.path.join(os.path.expanduser("~"), ".cache", "claude-cook")

NA_TO_SALT = 2.542  # g NaCl per g sodium

# FDA Daily Values for adults and children 4+ (21 CFR 101.9).
DV = {
    "fat": 78, "satfat": 20, "chol": 300, "sodium": 2300, "carb": 275, "fiber": 28,
    "added_sugar": 50, "protein": 50, "vitd": 20, "calcium": 1300, "iron": 18,
    "potassium": 4700, "vita": 900, "vitc": 90, "vite": 15, "vitk": 120, "thiamin": 1.2,
    "riboflavin": 1.3, "niacin": 16, "b6": 1.7, "folate": 400, "b12": 2.4, "choline": 550,
    "pantothenic": 5, "phosphorus": 1250, "magnesium": 420, "zinc": 11, "selenium": 55,
    "copper": 0.9, "manganese": 2.3,
}

NAMES = {
    "kcal": ("Calories", "kcal"), "protein": ("Protein", "g"), "fat": ("Total Fat", "g"),
    "carb": ("Total Carbohydrate", "g"), "fiber": ("Dietary Fiber", "g"), "sugar": ("Total Sugars", "g"),
    "satfat": ("Saturated Fat", "g"), "transfat": ("Trans Fat", "g"), "chol": ("Cholesterol", "mg"),
    "sodium": ("Sodium", "mg"), "potassium": ("Potassium", "mg"), "calcium": ("Calcium", "mg"),
    "iron": ("Iron", "mg"), "magnesium": ("Magnesium", "mg"), "phosphorus": ("Phosphorus", "mg"),
    "zinc": ("Zinc", "mg"), "copper": ("Copper", "mg"), "manganese": ("Manganese", "mg"),
    "selenium": ("Selenium", "mcg"), "vita": ("Vitamin A", "mcg"), "vitc": ("Vitamin C", "mg"),
    "vitd": ("Vitamin D", "mcg"), "vite": ("Vitamin E", "mg"), "vitk": ("Vitamin K", "mcg"),
    "thiamin": ("Thiamin B1", "mg"), "riboflavin": ("Riboflavin B2", "mg"), "niacin": ("Niacin B3", "mg"),
    "b6": ("Vitamin B6", "mg"), "folate": ("Folate", "mcg DFE"), "b12": ("Vitamin B12", "mcg"),
    "choline": ("Choline", "mg"), "pantothenic": ("Pantothenic B5", "mg"), "ala": ("Omega-3 ALA", "g"),
    "epa": ("EPA", "g"), "dha": ("DHA", "g"), "leucine": ("Leucine", "g"), "added_sugar": ("Added Sugars", "g"),
    "alcohol": ("Alcohol", "g"), "caffeine": ("Caffeine", "mg"),
}
MICROS = ["vita", "vitc", "vite", "vitk", "thiamin", "riboflavin", "niacin", "b6", "folate", "b12",
          "choline", "magnesium", "phosphorus", "zinc", "selenium", "copper", "manganese"]

# Practical salt targets, % NaCl of finished weight (intrinsic + added). Taste still decides.
SALT_TARGETS = {
    "soup": (0.6, 1.0), "broth": (0.6, 1.0), "stew": (0.8, 1.3), "braise": (0.8, 1.3), "curry": (0.8, 1.3),
    "chili": (0.8, 1.3), "sauce": (1.0, 2.0), "pasta": (0.6, 1.2), "noodles": (0.8, 1.4),
    "stir-fry": (0.8, 1.4), "meat": (0.8, 1.4), "fish": (0.7, 1.2), "eggs": (0.6, 1.1),
    "vegetables": (0.6, 1.1), "side": (0.6, 1.1), "salad": (0.6, 1.2), "grain": (0.4, 0.9),
    "rice": (0.4, 0.9), "sandwich": (1.0, 1.6), "pizza": (1.0, 1.6), "bread": (1.0, 1.5),
    "dough": (1.0, 1.7), "baked": (0.3, 0.9), "cookies": (0.4, 1.0), "cake": (0.2, 0.6),
    "dessert": (0.05, 0.4), "dip": (0.9, 1.8), "dressing": (1.5, 4.0), "condiment": (1.5, 4.0),
    "snack": (1.0, 2.0), "marinade": (1.5, 4.0), "brine": (3.0, 6.0), "ferment": (2.0, 3.0),
    "breakfast": (0.5, 1.2), "bowl": (0.7, 1.2),
}

MASS = {"g": 1.0, "gram": 1.0, "kg": 1000.0, "kilogram": 1000.0, "mg": 0.001,
        "oz": 28.3495, "ounce": 28.3495, "lb": 453.592, "pound": 453.592}
VOLUME = {"ml": 1.0, "milliliter": 1.0, "millilitre": 1.0, "cc": 1.0, "cl": 10.0, "dl": 100.0,
          "l": 1000.0, "liter": 1000.0, "litre": 1000.0, "tsp": 4.92892, "tbsp": 14.7868,
          "cup": 236.588, "floz": 29.5735, "pint": 473.176, "quart": 946.353, "gallon": 3785.41,
          "pinch": 0.308, "dash": 0.616}
UNIT_ALIASES = {
    "grams": "g", "gr": "g", "kgs": "kg", "kilograms": "kg", "ounces": "oz", "lbs": "lb", "pounds": "lb",
    "teaspoon": "tsp", "teaspoons": "tsp", "tsps": "tsp", "tablespoon": "tbsp", "tablespoons": "tbsp",
    "tbsps": "tbsp", "tbs": "tbsp", "tbl": "tbsp", "tbls": "tbsp", "cups": "cup", "c": "cup",
    "milliliters": "ml", "millilitres": "ml", "mls": "ml", "liters": "l", "litres": "l", "lt": "l",
    "pints": "pint", "pt": "pint", "quarts": "quart", "qt": "quart", "gallons": "gallon", "gal": "gallon",
    "pinches": "pinch", "dashes": "dash", "cloves": "clove", "slices": "slice", "stalks": "stalk",
    "ribs": "rib", "sprigs": "sprig", "leaves": "leaf", "heads": "head", "bunches": "bunch",
    "ears": "ear", "cans": "can", "tins": "can", "tin": "can", "jars": "jar", "packages": "package",
    "pkg": "package", "pkgs": "package", "packets": "packet", "sticks": "stick", "pieces": "piece",
    "pcs": "piece", "pc": "piece", "fillets": "fillet", "filet": "fillet", "filets": "fillet",
    "breasts": "breast", "thighs": "thigh", "drumsticks": "drumstick", "wings": "wing", "links": "link",
    "strips": "strip", "ea": "each", "bulbs": "bulb", "containers": "container", "bottles": "bottle",
    "bags": "bag", "boxes": "box", "loaves": "loaf", "sheets": "sheet", "cubes": "cube", "inches": "inch",
    "in": "inch", "knobs": "knob", "handfuls": "handful", "bars": "bar", "squares": "square",
    "scoops": "scoop", "envelopes": "envelope", "pats": "pat", "fruits": "fruit", "steaks": "steak",
    "chops": "chop", "patties": "patty", "rings": "ring", "wedges": "wedge", "tortillas": "tortilla",
}
COUNT_UNITS = {"clove", "slice", "stalk", "rib", "sprig", "leaf", "head", "bunch", "ear", "can", "jar",
               "package", "packet", "stick", "piece", "fillet", "breast", "thigh", "drumstick", "wing",
               "link", "strip", "whole", "each", "bulb", "container", "bottle", "bag", "box", "loaf",
               "sheet", "cube", "inch", "knob", "handful", "bar", "square", "scoop", "envelope", "pat",
               "fruit", "steak", "chop", "patty", "ring", "wedge", "small", "medium", "large", "jumbo"}
SIZES = ("small", "medium", "large", "jumbo", "extra large")
WORD_NUMBERS = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
                "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
                "half": 0.5, "dozen": 12}
UNICODE_FRACTIONS = {"½": "1/2", "⅓": "1/3", "⅔": "2/3", "¼": "1/4", "¾": "3/4", "⅕": "1/5",
                     "⅖": "2/5", "⅗": "3/5", "⅘": "4/5", "⅙": "1/6", "⅚": "5/6", "⅛": "1/8",
                     "⅜": "3/8", "⅝": "5/8", "⅞": "7/8", "⁄": "/"}

# Words dropped from ingredient names before matching (prep and serving notes).
PREP_WORDS = {
    "chopped", "minced", "diced", "sliced", "finely", "roughly", "thinly", "coarsely", "julienned",
    "divided", "softened", "melted", "cubed", "trimmed", "rinsed", "patted", "halved", "quartered",
    "torn", "optional", "garnish", "serving", "taste", "temperature", "room", "freshly", "packed",
    "heaping", "scant", "level", "peeled", "deveined", "pitted", "seeded", "stemmed", "cored",
    "crumbled", "shredded", "cut", "into", "inch", "pieces", "piece", "bite", "sized", "size", "about",
    "approximately", "plus", "more", "extra", "needed", "as", "for", "the", "a", "an", "of", "to",
    "or", "and", "in", "on", "at", "your", "favorite", "good", "quality", "best", "smashed", "lightly",
    "well", "very", "small", "medium", "large", "jumbo", "chunk", "chunks", "wedges", "rounds", "thin",
    "thick", "ribbons", "matchsticks", "lengthwise", "crosswise", "squeezed", "juiced", "zested",
    "beaten", "whisked", "sifted", "spooned", "leveled", "cold", "warm", "chilled", "separated",
    "drained", "rinsed", "reserved", "liquid", "discarded",
}
STATE_WORDS = {"cooked", "boiled", "roasted", "baked", "fried", "braised", "stewed", "broiled", "grilled",
               "microwaved", "steamed", "simmered", "toasted", "heated", "prepared", "scrambled",
               "poached", "rotisserie", "pan", "smoked", "cured"}
SOFT_PENALTY = {"canned", "frozen", "dehydrated", "imitation", "industrial", "commercial", "lowfat",
                "nonfat", "reduced", "low", "free", "light", "lite", "fortified", "mix", "substitute",
                "diet", "instant", "condensed", "concentrate", "unprepared", "powder", "dried",
                "sweetened", "unsweetened", "salt", "babyfood", "vitamin", "added", "includes",
                "school", "lunch", "formulated", "glazed", "breaded", "batter", "stuffed", "drained",
                "solids", "liquids", "pack", "syrup", "juice", "with", "without", "made", "skin",
                "seeds", "mature", "regular", "enriched", "unenriched", "bleached", "unbleached"}
IRREGULAR = {"leaves": "leaf", "potatoes": "potato", "tomatoes": "tomato", "loaves": "loaf",
             "halves": "half", "knives": "knife", "molasses": "molasses", "asparagus": "asparagus",
             "couscous": "couscous", "hummus": "hummus", "swiss": "swiss", "citrus": "citrus",
             "brussels": "brussels", "grits": "grits", "oats": "oat", "anise": "anise",
             "cheeses": "cheese", "sauces": "sauce", "noodles": "noodle", "olives": "olive"}


def singular(w):
    if w in IRREGULAR:
        return IRREGULAR[w]
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 4 and w.endswith(("ches", "shes", "sses", "xes", "oes")):
        return w[:-2]
    if len(w) > 3 and w.endswith("s") and not w.endswith(("ss", "us", "is")):
        return w[:-1]
    return w


def tokens(text):
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = text.lower().replace("&", " and ")
    return [singular(w) for w in re.findall(r"[a-z0-9]+", text)]


def round_sig(x, sig=3):
    if x == 0 or not math.isfinite(x):
        return 0
    return round(x, sig - int(math.floor(math.log10(abs(x)))) - 1)


# --------------------------------------------------------------------------------------------
# Database


class Food(object):
    def __init__(self, fid, cat, desc, values, source="USDA SR Legacy", opts=None):
        self.id = fid
        self.cat = cat
        self.desc = desc
        self.values = values  # nutrient -> amount per 100 g (missing = unknown)
        self.source = source
        self.opts = opts or {}
        self.portions = []  # (amount, measure, grams)
        self.imputed = set()  # nutrients filled from related USDA foods
        self.ingredients = ""  # ingredient statement (branded foods fetched online)

    def unit_weights(self):
        """Alias-provided gram weights, e.g. tsp=2.8 for Diamond Crystal salt."""
        return {k: float(v) for k, v in self.opts.items() if k not in ("edible", "added_sugar")}


class DB(object):
    def __init__(self, data_dir=DATA_DIR):
        self.data_dir = data_dir
        self.rows = {}
        self.sources = {}
        self.imputed = {}
        self.columns = []
        self.index = {}
        self.doc_tokens = {}
        self.first_tokens = {}
        self.aliases = []  # (frozenset tokens, fdc_id, opts, alias text)
        self.alias_exact = {}
        self._portions = None
        self._load()

    def _load(self):
        # foods.tsv: USDA SR Legacy (4th column = common names).
        # extras.tsv: label/Foundation data for staples SR Legacy lacks (4th column = source).
        for name, is_extra in (("foods.tsv", False), ("extras.tsv", True)):
            path = os.path.join(self.data_dir, name)
            if not os.path.exists(path):
                continue
            with open(path, encoding="utf-8") as f:
                header = f.readline().rstrip("\n").split("\t")
                has_imputed = header[-1] == "imputed"
                self.columns = header[4:-1] if has_imputed else header[4:]
                for line in f:
                    cells = line.rstrip("\n").split("\t")
                    fid = cells[0]
                    if has_imputed:
                        if cells[-1]:
                            self.imputed[fid] = set(cells[-1].split(","))
                        cells = cells[:-1]
                    self.rows[fid] = cells
                    if is_extra:
                        self.sources[fid] = cells[3]
                    toks = set(tokens(cells[2] if is_extra else cells[2] + " " + cells[3]))
                    self.doc_tokens[fid] = toks
                    self.first_tokens[fid] = set(tokens(cells[2].split(",")[0]))
                    for t in toks:
                        self.index.setdefault(t, set()).add(fid)
        apath = os.path.join(self.data_dir, "aliases.tsv")
        if os.path.exists(apath):
            with open(apath, encoding="utf-8") as f:
                for line in f:
                    if not line.strip() or line.startswith("#"):
                        continue
                    cells = line.rstrip("\n").split("\t")
                    alias, fid = cells[0], cells[1]
                    opts = {}
                    if len(cells) > 2 and cells[2].strip():
                        for kv in cells[2].split(";"):
                            if "=" in kv:
                                k, v = kv.split("=", 1)
                                opts[k.strip()] = v.strip()
                    toks = frozenset(t for t in tokens(alias) if t not in PREP_WORDS)
                    self.aliases.append((toks, fid, opts, alias))
                    self.alias_exact.setdefault(toks, (fid, opts, alias))

    def portions_for(self, fid):
        if self._portions is None:
            self._portions = {}
            with open(os.path.join(self.data_dir, "portions.tsv"), encoding="utf-8") as f:
                f.readline()
                for line in f:
                    pid, amount, measure, grams = line.rstrip("\n").split("\t")
                    self._portions.setdefault(pid, []).append((float(amount), measure, float(grams)))
        return self._portions.get(fid, [])

    def food(self, fid, opts=None):
        cells = self.rows.get(str(fid))
        if cells is None:
            return None
        values = {}
        for col, v in zip(self.columns, cells[4:]):
            if v != "":
                values[col] = float(v)
        food = Food(cells[0], cells[1], cells[2], values, source=self.sources.get(cells[0], "USDA SR Legacy"),
                    opts=dict(opts or {}))
        food.imputed = self.imputed.get(cells[0], set())
        food.portions = self.portions_for(cells[0])
        return food

    def search(self, name, limit=8):
        """Rank foods for an ingredient name. Returns [(score, fdc_id, opts, via_alias)]."""
        q = [t for t in tokens(name) if t not in PREP_WORDS]
        qset = set(q)
        if not qset:
            return []
        exact = self.alias_exact.get(frozenset(qset))
        if exact:
            return [(100.0, exact[0], exact[1], exact[2])]
        q_states = qset & STATE_WORDS
        scored = {}
        # Alias candidates: canonical names that cover part of the query.
        for atoks, fid, opts, alias in self.aliases:
            if not atoks or not atoks & qset:
                continue
            hit = len(atoks & qset)
            missing_q = len(qset - atoks)
            missing_a = len(atoks - qset)
            s = 4.0 * hit - 2.5 * missing_q - 3.0 * missing_a + 2.5
            if s > scored.get(fid, (-99,))[0]:
                scored[fid] = (s, opts, alias)
        # Fuzzy candidates over USDA descriptions.
        cand = set()
        for t in qset:
            cand |= self.index.get(t, set())
            if len(t) >= 5:
                for key in self.index:
                    if len(key) >= 5 and (key.startswith(t) or t.startswith(key)) and key != t:
                        cand |= self.index[key]
        for fid in cand:
            d = self.doc_tokens[fid]
            first = self.first_tokens[fid]
            s = 0.0
            for t in qset:
                if t in d:
                    s += 3.0 + (1.0 if t in first else 0.0)
                elif len(t) >= 5 and any(len(x) >= 5 and (x.startswith(t) or t.startswith(x)) for x in d):
                    s += 1.2
                else:
                    s -= 2.0
            if first and first <= qset:
                s += 1.5
            extras = d - qset
            s -= 0.15 * len(extras)
            if not q_states:
                if extras & STATE_WORDS:
                    s -= 2.0
                if "raw" in d:
                    s += 1.5
            s -= 0.8 * len(extras & SOFT_PENALTY)
            desc = self.rows[fid][2]
            if re.search(r"\b[A-Z]{3,}\b", desc) or "Pillsbury" in desc:
                s -= 2.5
            prev = scored.get(fid)
            if prev is None:
                scored[fid] = (s, {}, None)
            elif s > prev[0]:
                scored[fid] = (s, prev[1], prev[2])
        ranked = sorted(((v[0], fid, v[1], v[2]) for fid, v in scored.items()),
                        key=lambda r: (-r[0], len(self.rows[r[1]][2])))
        return ranked[:limit]


# --------------------------------------------------------------------------------------------
# Online fallback (USDA FoodData Central API; free key at https://fdc.nal.usda.gov/api-key-signup)

API_NUTRIENTS = {
    "1008": "kcal", "1003": "protein", "1004": "fat", "1005": "carb", "1079": "fiber", "2000": "sugar",
    "1063": "sugar", "1258": "satfat", "1292": "mufa", "1293": "pufa", "1257": "transfat",
    "1253": "chol", "1093": "sodium", "1092": "potassium", "1087": "calcium", "1089": "iron",
    "1090": "magnesium", "1091": "phosphorus", "1095": "zinc", "1098": "copper", "1101": "manganese",
    "1103": "selenium", "1106": "vita", "1162": "vitc", "1114": "vitd", "1109": "vite", "1185": "vitk",
    "1165": "thiamin", "1166": "riboflavin", "1167": "niacin", "1175": "b6", "1190": "folate",
    "1178": "b12", "1180": "choline", "1170": "pantothenic", "1404": "ala", "1278": "epa", "1272": "dha",
    "1213": "leucine", "1051": "water", "1018": "alcohol", "1057": "caffeine", "1235": "added_sugar",
}


def fdc_api(path, params):
    key = os.environ.get("FDC_API_KEY") or os.environ.get("USDA_API_KEY") or "DEMO_KEY"
    params = dict(params, api_key=key)
    url = "https://api.nal.usda.gov/fdc/v1/%s?%s" % (path, urllib.parse.urlencode(params))
    with urllib.request.urlopen(url, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))


def fetch_online(fid):
    cache = os.path.join(CACHE_DIR, "fdc-%s.json" % fid)
    data = None
    if os.path.exists(cache):
        with open(cache, encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = fdc_api("food/%s" % fid, {})
        try:
            os.makedirs(CACHE_DIR, exist_ok=True)
            with open(cache, "w", encoding="utf-8") as f:
                json.dump(data, f)
        except OSError:
            pass
    values = {}
    for n in data.get("foodNutrients", []):
        nid = str((n.get("nutrient") or {}).get("id", n.get("nutrientId", "")))
        key = API_NUTRIENTS.get(nid)
        amount = n.get("amount", n.get("value"))
        if key and amount is not None and key not in values:
            values[key] = float(amount)
    if "kcal" not in values:
        for n in data.get("foodNutrients", []):
            nid = str((n.get("nutrient") or {}).get("id", ""))
            if nid in ("2047", "2048") and n.get("amount") is not None:
                values["kcal"] = float(n["amount"])
                break
    desc = data.get("description", "FDC %s" % fid)
    if data.get("brandOwner"):
        desc = "%s (%s)" % (desc, data["brandOwner"])
    food = Food(str(fid), "online", desc, values, source="USDA FDC %s" % data.get("dataType", ""))
    food.ingredients = (data.get("ingredients") or "").lower()
    for p in data.get("foodPortions", []):
        unit = (p.get("measureUnit") or {}).get("name", "")
        measure = p.get("modifier") or p.get("portionDescription") or unit
        if unit and unit not in ("undetermined", "RACC") and unit not in measure:
            measure = "%s %s" % (unit, measure)
        if p.get("gramWeight"):
            food.portions.append((float(p.get("amount") or 1), measure.strip(), float(p["gramWeight"])))
    if data.get("servingSize") and str(data.get("servingSizeUnit", "")).lower() in ("g", "grm", "ml", "mlt"):
        hh = data.get("householdServingFullText") or "serving"
        m = re.match(r"\s*([\d./]+)\s*(.*)", hh)
        amount = parse_number(m.group(1)) if m else None
        food.portions.append((amount or 1.0, (m.group(2) if m else hh) or "serving", float(data["servingSize"])))
    return food


def online_disabled():
    return os.environ.get("COOK_OFFLINE", "") not in ("", "0")


def search_online(query, limit=10):
    """FoodData Central search (Foundation, SR Legacy, Branded), cached on disk."""
    key = hashlib.sha1(("%s|%d" % (query.lower(), limit)).encode("utf-8")).hexdigest()[:16]
    cache = os.path.join(CACHE_DIR, "search-%s.json" % key)
    if os.path.exists(cache):
        with open(cache, encoding="utf-8") as f:
            return json.load(f)
    data = fdc_api("foods/search", {"query": query, "pageSize": limit,
                                     "dataType": "Foundation,SR Legacy,Branded"}).get("foods", [])
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(cache, "w", encoding="utf-8") as f:
            json.dump(data, f)
    except OSError:
        pass
    return data


def food_from_search_hit(hit):
    values = {}
    for n in hit.get("foodNutrients", []):
        k = API_NUTRIENTS.get(str(n.get("nutrientId", "")))
        if k and n.get("value") is not None and k not in values:
            values[k] = float(n["value"])
    if "kcal" not in values:
        e = next((n.get("value") for n in hit.get("foodNutrients", []) if n.get("nutrientId") in (2047, 2048)), None)
        values["kcal"] = float(e) if e is not None else (
            4 * values.get("protein", 0) + 4 * values.get("carb", 0) + 9 * values.get("fat", 0))
    desc = hit.get("description", "").strip()
    brand = hit.get("brandName") or hit.get("brandOwner")
    if brand:
        desc = "%s (%s)" % (desc.title() if desc.isupper() else desc, brand.title() if brand.isupper() else brand)
    cat = "online"
    food = Food(str(hit.get("fdcId")), cat, desc, values, source="USDA FDC %s" % hit.get("dataType", ""))
    food.ingredients = (hit.get("ingredients") or "").lower()
    size, unit = hit.get("servingSize"), str(hit.get("servingSizeUnit", "")).lower()
    if size and unit in ("g", "grm", "ml", "mlt"):
        hh = hit.get("householdServingFullText") or "serving"
        m = re.match(r"\s*([\d./]+)\s*(.*)", hh)
        amount = parse_number(m.group(1)) if m else None
        food.portions.append((amount or 1.0, (m.group(2) if m else hh) or "serving", float(size)))
    return food


def resolve_online(name):
    """Best FoodData Central match for a free-text ingredient (generic records preferred on ties)."""
    hits = search_online(name)
    q = set(t for t in tokens(name) if t not in PREP_WORDS)
    best, best_score = None, -1e9
    for i, h in enumerate(hits):
        d = set(tokens(h.get("description", "") + " " + (h.get("brandName") or h.get("brandOwner") or "")))
        score = 3 * len(q & d) - 2 * len(q - d) - 0.1 * len(d - q) - 0.05 * i
        if h.get("dataType") in ("Foundation", "SR Legacy"):
            score += 0.5
        if not any(n.get("nutrientId") in (1008, 2047, 2048, 1003) for n in h.get("foodNutrients", [])):
            continue
        if score > best_score:
            best, best_score = h, score
    if best is None or best_score < 1:
        return None
    return food_from_search_hit(best)


# --------------------------------------------------------------------------------------------
# Parsing


def parse_number(s):
    s = s.strip()
    try:
        if re.match(r"^\d+\s+\d+/\d+$", s) or re.match(r"^\d+-\d+/\d+$", s):
            whole, frac = re.split(r"[\s-]+", s)
            a, b = frac.split("/")
            return float(whole) + float(a) / float(b)
        if "/" in s:
            a, b = s.split("/")
            return float(a) / float(b)
        return float(s)
    except (ValueError, ZeroDivisionError):
        return None


QTY_RE = r"(?:\d+\s+\d+/\d+|\d+-\d+/\d+|\d+/\d+|\d*\.\d+|\d+)"
RANGE_RE = re.compile(r"^(%s)(?:\s*(?:-|–|to)\s*(%s))?" % (QTY_RE, QTY_RE))


class Line(object):
    def __init__(self, raw):
        self.raw = raw
        self.qty = None
        self.unit = None
        self.size_g = None  # per-item weight from "(400 g)"
        self.size_ml = None
        self.name = ""
        self.pin = None
        self.consumed = 1.0
        self.custom = None
        self.grams = None
        self.note = ""
        self.food = None
        self.warn = None
        self.method = None
        self.minutes = None
        self.drain = False
        self.online = False
        self.cook_note = ""


def norm_unit(word):
    w = word.lower().rstrip(".")
    w = UNIT_ALIASES.get(w, w)
    return w


def parse_line(raw):
    ln = Line(raw)
    s = raw.strip()
    s = re.sub(r"^\s*(?:[-*•]\s+|\d+[.)]\s+(?=\d))", "", s)
    for k, v in UNICODE_FRACTIONS.items():
        s = s.replace(k, " " + v if k != "⁄" else v)
    s = re.sub(r"(\d)\s+(\d/\d)", r"\1 \2", s).strip()
    m = re.search(r"\{([^}]*)\}", s)
    if m:
        ln.custom = {}
        for kv in re.split(r"[\s,;]+", m.group(1).strip()):
            if "=" in kv:
                k, v = kv.split("=", 1)
                try:
                    ln.custom[k.strip().lower()] = float(v)
                except ValueError:
                    pass
        s = s[:m.start()] + s[m.end():]
    m = re.search(r"=\s*fdc:(\d+)", s)
    if m:
        ln.pin = m.group(1)
        s = s[:m.start()] + s[m.end():]
    m = re.search(r"=\s*online\b", s)
    if m:
        ln.online = True
        s = s[:m.start()] + s[m.end():]
    ln.method, ln.minutes, ln.drain, s = cooking.parse_tag(s)
    m = re.search(r"@\s*(\d+(?:\.\d+)?)\s*(%?)", s)
    if m:
        val = float(m.group(1))
        ln.consumed = val / 100.0 if (m.group(2) or val > 1) else val
        s = s[:m.start()] + s[m.end():]
    s = re.sub(r"\s#\s.*$", "", s).strip()
    # "juice of 2 limes" -> "2 limes juice"; "1 lemon, juiced" -> "1 lemon juice"
    jm = re.match(r"^(?:the\s+)?(juice|zest)\s+(?:of|from)\s+(.+)$", s, re.I)
    if jm:
        s = "%s %s" % (jm.group(2), jm.group(1).lower())
    s = re.sub(r",?\s*(?:zested\s+and\s+)?juiced\b", " juice", s, flags=re.I)
    # quantity
    m = RANGE_RE.match(s)
    if m:
        a = parse_number(m.group(1))
        b = parse_number(m.group(2)) if m.group(2) else None
        ln.qty = (a + b) / 2.0 if b else a
        s = s[m.end():].strip()
    else:
        w = s.split(" ", 1)
        if w[0].lower() in WORD_NUMBERS and len(w) > 1:
            ln.qty = float(WORD_NUMBERS[w[0].lower()])
            s = w[1].strip()
            if s.lower().startswith("half "):
                ln.qty *= 0.5
                s = s[5:]
    # parenthetical size: (400 g), (14.5-oz), (about 1 lb)
    def take_paren(text):
        pm = re.match(r"^\(([^)]*)\)\s*", text)
        if not pm:
            return text
        inner = pm.group(1).lower().replace("-", " ")
        sm = re.search(r"(%s)\s*(fl\.?\s*oz|[a-z]+)" % QTY_RE, inner)
        if sm:
            val = parse_number(sm.group(1))
            u = norm_unit(sm.group(2).replace(" ", "").replace(".", ""))
            u = "floz" if u in ("floz",) else u
            if val and u in MASS:
                ln.size_g = val * MASS[u]
            elif val and u in VOLUME:
                ln.size_ml = val * VOLUME[u]
        return text[pm.end():]
    s = take_paren(s)
    # unit
    fm = re.match(r"^(fl\.?\s*oz\.?|fluid\s+ounces?)\b\.?\s*", s, re.I)
    if fm:
        ln.unit = "floz"
        s = s[fm.end():]
    else:
        m = re.match(r"^([a-zA-Z]+)\.?(?:\s+|$)", s)
        if m:
            u = norm_unit(m.group(1))
            if u in MASS or u in VOLUME or u in COUNT_UNITS:
                if u == "extra" and s.lower().startswith("extra large"):
                    u = "large"
                ln.unit = u
                s = s[m.end():]
        if ln.unit == "extra":
            ln.unit = None
    s = take_paren(s.strip())
    s = re.sub(r"^of\s+", "", s.strip(), flags=re.I)
    ln.name = s.strip(" ,;:-")
    return ln


META_RE = re.compile(r"^(servings|serves|yield|makes|type|eat|title)\s*[:=]\s*(.+)$", re.I)


class Recipe(object):
    def __init__(self, title=None):
        self.title = title
        self.servings = 1.0
        self.servings_set = False
        self.yield_g = None
        self.type = None
        self.eat = 1.0
        self.lines = []
        self.day = None


def parse_grams(text):
    m = re.match(r"\s*(%s)\s*([a-zA-Z]*)" % QTY_RE, text)
    if not m:
        return None
    val = parse_number(m.group(1))
    unit = norm_unit(m.group(2) or "g")
    if unit in MASS:
        return val * MASS[unit]
    if unit in VOLUME:
        return val * VOLUME[unit]
    return None


def parse_recipes(text):
    recipes = []
    day = None
    cur = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("## "):
            cur = Recipe(line[3:].strip())
            cur.day = day
            recipes.append(cur)
            continue
        if line.startswith("#"):
            heading = line.lstrip("#").strip()
            if cur is None or (not cur.lines and cur.title is None):
                if cur is None:
                    cur = Recipe(heading)
                    recipes.append(cur)
                else:
                    cur.title = heading
            day = heading
            continue
        if cur is None:
            cur = Recipe()
            recipes.append(cur)
        m = META_RE.match(line)
        if m:
            key, val = m.group(1).lower(), m.group(2).strip()
            if key in ("servings", "serves", "makes"):
                n = re.search(QTY_RE, val)
                if n:
                    cur.servings = parse_number(n.group(0)) or 1.0
                    cur.servings_set = True
            elif key == "yield":
                cur.yield_g = parse_grams(val)
            elif key == "type":
                cur.type = val.lower()
            elif key == "eat":
                cur.eat = parse_number(val.split()[0]) or 1.0
            elif key == "title":
                cur.title = val
            continue
        if line.endswith(":") and not re.search(r"\d", line):
            continue  # group label such as "For the sauce:"
        cur.lines.append(parse_line(line))
    # "# Day" headers produce empty placeholder recipes; drop them.
    return [r for r in recipes if r.lines]


# --------------------------------------------------------------------------------------------
# Unit conversion


def measure_unit(measure):
    m = measure.lower().strip()
    if m.startswith("fl oz") or m.startswith("fluid ounce"):
        return "floz"
    w = re.match(r"[a-z]+", m)
    return norm_unit(w.group(0)) if w else ""


def grams_for(ln, food):
    """Convert a parsed line to grams; returns (grams, note) or (None, error)."""
    qty = ln.qty if ln.qty is not None else 1.0
    unit = ln.unit
    weights = food.unit_weights()
    hints = set(tokens(ln.name))
    if unit in MASS:
        return qty * MASS[unit], ""
    if ln.size_g and (unit is None or unit in COUNT_UNITS):
        if re.search(r"\bdrain", ln.raw, re.I):
            if "can" in weights:
                return qty * weights["can"], "drained, 1 can = %g g (alias)" % weights["can"]
            return qty * ln.size_g * 0.6, "drained ~60%% of %g g" % round_sig(ln.size_g)
        return qty * ln.size_g, "%g x %g g" % (qty, round_sig(ln.size_g))
    if ln.size_ml and (unit is None or unit in COUNT_UNITS):
        unit, qty = "ml", qty * ln.size_ml
    if unit in VOLUME:
        if unit in weights:
            return qty * weights[unit], "1 %s = %g g (alias)" % (unit, weights[unit])
        vol = [(a, meas, g) for a, meas, g in food.portions if measure_unit(meas) in VOLUME]
        same = [p for p in vol if measure_unit(p[1]) == unit]
        pick = None
        for group in (same, vol):
            if group:
                pick = max(group, key=lambda p: len(hints & set(tokens(p[1]))))
                if not hints & set(tokens(pick[1])):
                    plain = [p for p in group if "whipped" not in re.sub(r"\(.*?\)", "", p[1].lower())]
                    pick = (plain or group)[0]
                break
        if pick:
            a, meas, g = pick
            g_per_ml = g / (a * VOLUME[measure_unit(meas)])
            grams = qty * VOLUME[unit] * g_per_ml
            return grams, "via USDA '%g %s' = %g g" % (a, meas, g)
        for vu in ("tbsp", "tsp", "cup"):
            if vu in weights:
                return qty * VOLUME[unit] * weights[vu] / VOLUME[vu], "via alias %s" % vu
        density = estimate_density(food)
        if density:
            return qty * VOLUME[unit] * density, "density estimate %.2f g/ml" % density
        return None, "no volume data; give grams"
    # counts, sizes, containers, or no unit
    if unit and unit in weights:
        return qty * weights[unit], "1 %s = %g g (alias)" % (unit, weights[unit])
    if unit is None and "each" in weights:
        return qty * weights["each"], "1 each = %g g (alias)" % weights["each"]
    counts = [(a, meas, g) for a, meas, g in food.portions
              if measure_unit(meas) not in VOLUME and measure_unit(meas) not in MASS
              and not re.match(r"(nlea )?serving|package|container|oz\b|lb\b", meas.lower())]
    pick = None
    if unit:
        if unit in SIZES:
            pick = next((p for p in counts if unit in p[1].lower() and "slice" not in p[1].lower()), None)
        if pick is None:
            pick = next((p for p in food.portions if measure_unit(p[1]) == unit), None)
    if pick is None:
        for h in hints:
            pick = next((p for p in counts if measure_unit(p[1]) == h), None)
            if pick:
                break
    if pick is None and (unit is None or unit in SIZES or unit in ("whole", "each", "piece", "fruit")):
        for pref in ("medium", "large", "fruit", "whole", "each", "piece", "item", "unit", "egg"):
            pick = next((p for p in counts if p[1].lower().startswith(pref)), None)
            if pick:
                break
        if pick is None and counts:
            pick = counts[0]
    if pick:
        a, meas, g = pick
        return qty * g / a, "1 %s = %g g" % (meas if a == 1 else "%s / %g" % (meas, a), round_sig(g / a))
    have = ", ".join("%g %s=%gg" % (a, meas, g) for a, meas, g in food.portions[:6]) or "none"
    return None, "can't convert '%s'; USDA portions: %s; write grams" % (unit or "count", have)


def estimate_density(food):
    d = food.desc.lower()
    if food.cat == "nut":
        return 0.6
    if food.cat == "spice":
        return 0.5
    if food.cat == "fat" and "oil" in d:
        return 0.92
    if any(w in d for w in ("honey", "syrup", "molasses")):
        return 1.4
    if food.cat in ("drink", "alcohol") or any(w in d for w in (
            "milk", "cream", "juice", "broth", "stock", "vinegar", "sauce", "wine", "water", "buttermilk")):
        return 1.03
    return None


# --------------------------------------------------------------------------------------------
# Analysis

# Share of an ingredient's sugars that count as "added" under the FDA definition (sugars from sweeteners,
# syrups, honey and concentrates; not the lactose or fruit/vegetable sugar the ingredient carries).
ADDED_SUGAR_SHARE = [
    ("unsweetened", 0.0), ("catsup", 0.75), ("ketchup", 0.75), ("barbecue", 0.85), ("hoisin", 0.85),
    ("teriyaki", 0.85), ("sweet and sour", 0.85), ("gochujang", 0.9), ("mirin", 1.0), ("jams", 0.9),
    ("jelly", 0.9), ("marmalade", 0.9), ("preserves", 0.9), ("condensed, sweetened", 0.78),
    ("sweetened condensed", 0.78), ("cranberries, dried", 0.85), ("candied", 0.9), ("frosting", 1.0),
    ("syrup", 1.0), ("honey", 1.0), ("molasses", 1.0), ("sugars,", 1.0), ("sugar,", 1.0), ("sweetener", 1.0),
    ("chocolate", 1.0), ("candies", 1.0), ("sweetened", 0.85), ("cookies", 0.95), ("cake", 0.95),
    ("granola", 0.8), ("yogurt, fruit", 0.6), ("ice cream", 0.75), ("pudding", 0.8),
]


def added_sugar_fraction(food):
    if "added_sugar" in food.opts:
        return float(food.opts["added_sugar"])
    if "added_sugar" in food.values:
        return None  # label data with declared added sugars
    d = food.desc.lower()
    for word, share in ADDED_SUGAR_SHARE:
        if word in d:
            return share
    if food.cat == "sweet" or d.startswith("sugar"):
        return 1.0
    return 0.0


def has(text, words):
    """True if any word/prefix occurs at a word boundary (avoids 'rye' in 'fryers')."""
    return any(re.search(r"\b" + re.escape(w), text) for w in words)


ROLE_RULES = [
    ("salt", lambda f, d: f.values.get("sodium", 0) >= 1000),
    ("acid", lambda f, d: has(d, (
        "vinegar", "lemon", "lime", "orange juice", "grapefruit", "tomato", "wine", "yogurt", "buttermilk",
        "sour cream", "tamarind", "pickle", "sauerkraut", "kimchi", "mustard", "sumac", "capers",
        "kefir", "pomegranate", "cranberr", "tomatillo", "rhubarb", "cream cheese", "goat cheese",
        "feta", "verjuice", "passion")) and "seed" not in d),
    ("umami", lambda f, d: has(d, (
        "tomato", "parmesan", "romano", "soy sauce", "tamari", "miso", "fish sauce", "anchov", "mushroom",
        "seaweed", "kombu", "kelp", "nori", "oyster sauce", "worcestershire", "bonito", "monosodium",
        "yeast extract", "nutritional yeast", "kimchi", "bacon", "ham", "prosciutto", "broth", "stock",
        "gochujang", "cheddar", "gruyere", "aged", "sauerkraut", "peas", "shiitake", "sardine"))),
    ("fat", lambda f, d: f.values.get("fat", 0) >= 30),
    ("sweet", lambda f, d: f.values.get("sugar", 0) >= 15 or f.cat == "sweet"),
    ("heat", lambda f, d: has(d, (
        "pepper, red or cayenne", "cayenne", "chili", "chile", "jalape", "serrano", "habanero",
        "sriracha", "hot sauce", "pepper or hot", "gochujang", "horseradish", "wasabi", "mustard",
        "ginger", "pepper, black", "chipotle", "harissa", "sambal"))),
    ("bitter", lambda f, d: has(d, (
        "coffee", "cocoa", "chocolate, dark", "baking chocolate", "radicchio", "endive", "arugula",
        "beer", "grapefruit", "mustard greens", "broccoli raab", "rapini", "dandelion", "tea,",
        "fenugreek", "kale", "walnut", "turmeric"))),
    ("aromatic", lambda f, d: (f.cat == "spice" and not d.startswith("salt")) or has(d, (
        "onion", "garlic", "shallot", "leek", "scallion", "ginger", "lemongrass", "lemon grass",
        "basil", "coriander", "cilantro", "parsley", "mint", "dill", "thyme", "rosemary", "oregano",
        "sage", "tarragon", "chive", "peel", "zest", "fennel", "celery", "vanilla"))),
    ("crunch", lambda f, d: f.cat == "nut" or f.cat != "spice" and has(d, (
        "cracker", "chips", "crumbs", "crouton", "seeds", "cucumber", "radish", "celery", "cabbage",
        "jicama", "apples, raw", "lettuce", "sprouts", "granola", "popcorn", "pork skins", "peas, edible",
        "carrots, raw", "fennel", "snack", "pretzel", "tortilla chip", "fried"))),
]
NUCLEOTIDE_CATS = {"poultry", "beef", "pork", "lamb", "seafood", "sausage"}

ALLERGEN_RULES = [
    ("milk", lambda f, d: (f.cat == "dairy" and not d.startswith("egg")) or has(d, (
        "butter", "cheese", "cream", "milk", "yogurt", "whey", "ghee", "casein")) and not has(
        d, ("coconut", "almond", "soymilk", "soy milk", "oat milk", "rice milk", "cream of tartar",
                         "cream style", "peanut butter", "nut butter", "cocoa butter", "apple butter", "cashew"))),
    ("egg", lambda f, d: d.startswith("egg") or "mayonnaise" in d or "egg noodle" in d or "noodles, egg" in d),
    ("fish", lambda f, d: (f.cat == "seafood" and not has(d, SHELLFISH)) or has(
        d, ("fish sauce", "worcestershire", "anchov", "bonito"))),
    ("shellfish", lambda f, d: has(d, SHELLFISH) or "oyster sauce" in d),
    ("tree nuts", lambda f, d: has(d, (
        "almond", "walnut", "pecan", "cashew", "pistachio", "hazelnut", "filbert", "macadamia",
        "brazilnut", "brazil nut", "pine nut", "pinyon"))),
    ("peanut", lambda f, d: "peanut" in d),
    ("wheat/gluten", lambda f, d: has(d, (
        "wheat", "bread", "pasta", "spaghetti", "macaroni", "couscous", "bulgur", "semolina", "barley",
        "rye", "soy sauce made from soy and wheat", "cracker", "crumbs", "tortillas, ready-to-bake or -fry, flour",
        "seitan", "beer", "malt", "noodles, egg", "cake", "cookie", "pie crust", "pita", "naan", "panko",
        "biscuit", "muffin", "pancake", "waffle", "croissant", "bagel", "pizza", "dumpling")) and not has(
        d, ("rice flour", "corn flour", "masa", "potato flour", "buckwheat", "gluten-free",
                         "rice noodles", "tamari", "cornstarch", "almond flour", "soy flour", "rice cake",
                         "buckwheat", "wheat-free"))),
    ("soy", lambda f, d: has(d, ("soy", "tofu", "tempeh", "edamame", "miso", "natto"))
        and "soybean oil" not in d and "oil, soybean" not in d),
    ("sesame", lambda f, d: "sesame" in d or "tahini" in d),
]
SHELLFISH = ("shrimp", "crab", "lobster", "crayfish", "prawn", "clam", "mussel", "oyster", "scallop",
             "squid", "octopus", "crustacean", "mollusk")
# Allergens hidden inside prepared ingredients. "likely" ones vary by brand: the cook should read the label.
HIDDEN_ALLERGENS = [
    ("gochujang", ("wheat/gluten", "soy"), False), ("hoisin", ("soy", "wheat/gluten"), False),
    ("hoisin", ("sesame",), True), ("teriyaki", ("soy", "wheat/gluten"), False),
    ("oyster sauce", ("wheat/gluten",), True), ("miso", ("wheat/gluten",), True),
    ("caesar", ("fish", "egg", "milk"), False), ("pesto", ("tree nuts", "milk"), False),
    ("curry paste", ("shellfish", "fish"), True), ("shrimp paste", ("shellfish",), False),
    ("xo sauce", ("shellfish",), False), ("dashi", ("fish",), False), ("furikake", ("sesame", "fish"), False),
    ("ranch", ("milk", "egg"), False), ("chocolate", ("milk", "soy"), True), ("candies", ("milk", "soy"), True),
    ("bouillon", ("wheat/gluten", "soy", "milk"), True), ("broth", ("wheat/gluten",), True),
    ("sausage", ("milk", "wheat/gluten", "soy"), True), ("noodles", ("wheat/gluten",), False),
    ("udon", ("wheat/gluten",), False), ("ramen", ("wheat/gluten",), False), ("soba", ("wheat/gluten",), True),
    ("za'atar", ("sesame",), False), ("zaatar", ("sesame",), False), ("dukkah", ("sesame", "tree nuts"), False),
    ("marzipan", ("tree nuts",), False), ("almond paste", ("tree nuts",), False), ("nutella", ("tree nuts", "milk"), False),
    ("margarine", ("milk", "soy"), True), ("mayonnaise", ("egg",), False), ("aioli", ("egg",), False),
    ("tartar sauce", ("egg",), False), ("hollandaise", ("egg", "milk"), False), ("custard", ("egg", "milk"), False),
    ("panko", ("wheat/gluten",), False), ("breadcrumb", ("wheat/gluten",), False), ("crumbs", ("wheat/gluten",), False),
    ("tortilla, flour", ("wheat/gluten",), False), ("seitan", ("wheat/gluten",), False),
    ("vital wheat gluten", ("wheat/gluten",), False), ("malt", ("wheat/gluten",), False),
    ("tahini", ("sesame",), False), ("halvah", ("sesame",), False), ("chili crisp", ("soy", "sesame"), True),
    ("worcestershire", ("fish",), False), ("fish sauce", ("fish",), False),
]
INGREDIENT_ALLERGENS = [  # words in a branded product's ingredient statement
    ("milk", ("milk", "whey", "casein", "butter", "cream", "cheese", "lactose")), ("egg", ("egg",)),
    ("fish", ("anchov", "fish", "bonito", "cod", "tuna")), ("shellfish", ("shrimp", "crab", "lobster", "oyster", "clam")),
    ("tree nuts", ("almond", "walnut", "pecan", "cashew", "pistachio", "hazelnut", "macadamia", "pine nut")),
    ("peanut", ("peanut",)), ("wheat/gluten", ("wheat", "barley", "rye", "malt")), ("soy", ("soy",)),
    ("sesame", ("sesame",)),
]


class Analysis(object):
    pass


def resolve(db, ln, online=False):
    if ln.custom is not None:
        vals = dict(ln.custom)
        for k in list(vals):
            if k in ("tsp", "tbsp", "cup", "each", "piece"):
                vals.pop(k)
        if "kcal" not in vals:
            vals["kcal"] = 4 * vals.get("protein", 0) + 4 * vals.get("carb", 0) + 9 * vals.get("fat", 0)
        opts = {k: v for k, v in ln.custom.items() if k in ("tsp", "tbsp", "cup", "each", "piece")}
        if "added_sugar" in ln.custom:
            opts["added_sugar"] = 1.0
        food = Food("custom", "custom", ln.name or "custom item", vals, source="label/custom", opts=opts)
        return food, None
    if ln.pin:
        food = db.food(ln.pin)
        if food is None:
            try:
                food = fetch_online(ln.pin)
            except Exception as e:  # network or key problems
                return None, "fdc:%s not in local data and online lookup failed (%s)" % (ln.pin, e)
        return food, None
    if not ln.name:
        return None, "no ingredient name"
    hits = [] if ln.online else db.search(ln.name, limit=3)
    if hits and hits[0][0] >= 2.0:
        score, fid, opts, alias = hits[0]
        return db.food(fid, opts), None
    if online and not online_disabled():
        try:
            food = resolve_online(ln.name)
        except Exception as e:  # offline, rate-limited, sandboxed
            food, err = None, str(e)
        else:
            err = "no FoodData Central match"
        if food is not None:
            return food, None
    else:
        err = "online lookup disabled"
    sug = "; ".join("%s=fdc:%s" % (db.rows[h[1]][2][:50], h[1]) for h in hits[:3])
    return None, "no confident match (%s)%s" % (err, " closest offline: %s" % sug if sug else "")


COOK = None


def cooking_data():
    global COOK
    if COOK is None:
        COOK = cooking.CookingData()
    return COOK


def analyze_recipe(db, recipe, online=True):
    a = Analysis()
    a.recipe = recipe
    a.items = []
    a.warnings = []
    totals = {}
    known_weight = {}  # nutrient -> grams of food with data
    raw_weight = 0.0
    cooked_weight = 0.0
    imputed_weight = {}
    added_sugar = 0.0
    measured_added = False
    roles = {}
    allergens = set()
    likely = {}
    has_glu = has_nuc = False
    any_cooked = False
    cook = cooking_data()
    for ln in recipe.lines:
        if ln.qty is None and ln.unit is None and ln.custom is None and not ln.size_g:
            ln.warn = "no quantity, skipped"
            a.items.append(ln)
            continue
        food, err = resolve(db, ln, online)
        if food is None:
            ln.warn = err
            a.items.append(ln)
            continue
        ln.food = food
        grams, note = grams_for(ln, food)
        if grams is None:
            ln.warn = note
            a.items.append(ln)
            continue
        edible = float(food.opts.get("edible", 1.0))
        ln.grams = grams
        ln.note = note
        eaten = grams * ln.consumed * edible
        if edible != 1.0:
            ln.note = (ln.note + "; " if ln.note else "") + "edible %d%%" % round(edible * 100)
        a.items.append(ln)
        raw_weight += eaten
        values = food.values
        weight_yield = 1.0
        if ln.method and ln.method != "raw":
            cls = cooking.cook_class(food.cat, food.desc, food.values.get("fat", 0))
            values, code, rdesc, weight_yield, kept = cook.apply(food.values, cls, ln.method, ln.minutes, ln.drain)
            any_cooked = True
            bits = ["~%s" % ln.method]
            bits.append("USDA retention '%s'" % rdesc.title() if rdesc else "no USDA retention data for this food")
            if weight_yield != 1.0:
                bits.append("yield x%.2f" % weight_yield)
            if kept < 1.0:
                bits.append("%d%% of fat kept" % round(kept * 100))
            ln.cook_note = ", ".join(bits)
        cooked_weight += eaten * weight_yield
        for k, v in values.items():
            totals[k] = totals.get(k, 0.0) + v * eaten / 100.0
            known_weight[k] = known_weight.get(k, 0.0) + eaten
        for k in food.imputed:
            imputed_weight[k] = imputed_weight.get(k, 0.0) + eaten
        frac = added_sugar_fraction(food)
        if frac is None:
            measured_added = True
            added_sugar += food.values.get("added_sugar", 0) * eaten / 100.0
        else:
            added_sugar += frac * values.get("sugar", 0) * eaten / 100.0
        d = (food.desc + " " + ln.name).lower()
        for word, found, maybe in HIDDEN_ALLERGENS:
            if has(d, (word,)):
                for allergen in found:
                    if maybe:
                        likely.setdefault(allergen, set()).add(short_name(ln, food))
                    else:
                        allergens.add(allergen)
        if food.ingredients:
            for allergen, words_ in INGREDIENT_ALLERGENS:
                if has(food.ingredients, words_):
                    allergens.add(allergen)
        for role, rule in ROLE_RULES:
            if eaten > 0 and rule(food, d):
                roles.setdefault(role, []).append(short_name(ln, food))
                if role == "umami" and food.cat not in NUCLEOTIDE_CATS:
                    has_glu = True
        for allergen, rule in ALLERGEN_RULES:
            if rule(food, d):
                allergens.add(allergen)
        if food.cat in NUCLEOTIDE_CATS or any(w in d for w in (
                "shiitake", "mushrooms, dried", "bonito", "anchov", "sardine", "broth", "stock", "dashi")):
            has_nuc = True
    totals["added_sugar"] = added_sugar
    a.totals = totals
    a.coverage = {k: known_weight.get(k, 0.0) / raw_weight if raw_weight else 0 for k in NAMES}
    a.imputed = {k: v / raw_weight for k, v in imputed_weight.items() if raw_weight}
    a.raw_weight = raw_weight
    a.cooked = any_cooked
    a.weight_basis = "finished" if recipe.yield_g else ("est. cooked" if any_cooked else "raw")
    a.weight = recipe.yield_g or (cooked_weight if any_cooked else raw_weight)
    a.likely_allergens = {k: sorted(v) for k, v in likely.items() if k not in allergens}
    a.servings = recipe.servings or 1.0
    a.per = {k: v / a.servings for k, v in totals.items()}
    a.roles = roles
    a.allergens = sorted(allergens)
    a.umami_synergy = has_glu and has_nuc
    a.measured_added = measured_added
    return a


def short_name(ln, food):
    n = ln.name.split(",")[0].strip() or food.desc.split(",")[0]
    return n[:28]


# --------------------------------------------------------------------------------------------
# Formatting


def fda_round(key, x):
    if key == "kcal":
        return 0 if x < 5 else (int(5 * round(x / 5.0)) if x <= 50 else int(10 * round(x / 10.0)))
    if key in ("fat", "satfat", "transfat"):
        if x < 0.5:
            return "0"
        return ("%g" % (0.5 * round(x / 0.5))) if x < 5 else "%d" % round(x)
    if key == "chol":
        return "0" if x < 2 else ("<5" if x < 5 else "%d" % (5 * round(x / 5.0)))
    if key in ("sodium", "potassium"):
        if x < 5:
            return "0"
        return "%d" % (5 * round(x / 5.0)) if x <= 140 else "{:,}".format(int(10 * round(x / 10.0)))
    if x < 0.5:
        return "0"
    return "<1" if x < 1 else "%d" % round(x)


def pct(key, x):
    return int(round(100.0 * x / DV[key])) if key in DV else None


def fmt_amount(x, unit):
    if x >= 100:
        s = "{:,}".format(int(round(x)))
    elif x >= 10:
        s = "%.0f" % x
    elif x >= 1:
        s = "%.1f" % x
    else:
        s = "%.2f" % x
    return "%s %s" % (s, unit)


def label_text(a, micros=True):
    p = a.per
    title = a.recipe.title or "Recipe"
    W = 46
    serving_g = a.weight / a.servings
    basis = {"finished": "finished weight", "est. cooked": "as cooked", "raw": "raw ingredients"}[a.weight_basis]
    out = []
    out.append("NUTRITION FACTS - %s" % title)
    out.append("%g serving%s | serving ~%d g (%s)" % (
        a.servings, "" if a.servings == 1 else "s", round(serving_g), basis))
    out.append("=" * W)
    out.append("Calories".ljust(W - 6) + str(fda_round("kcal", p.get("kcal", 0))).rjust(6))
    out.append("-" * W)
    out.append("% Daily Value*".rjust(W))

    def row(label, key, indent=0, show_pct=True, unit="g"):
        val = fda_round(key, p.get(key, 0))
        left = " " * indent + "%s %s%s" % (label, val, unit)
        right = ("%d%%" % pct(key, p.get(key, 0))) if show_pct and key in DV else ""
        out.append((left.ljust(W - len(right)) + right).rstrip())

    row("Total Fat", "fat")
    row("Saturated Fat", "satfat", 3)
    row("Trans Fat", "transfat", 3, False)
    row("Cholesterol", "chol", unit="mg")
    row("Sodium", "sodium", unit="mg")
    row("Total Carbohydrate", "carb")
    row("Dietary Fiber", "fiber", 3)
    row("Total Sugars", "sugar", 3, False)
    added = p.get("added_sugar", 0)
    left = "      Includes %sg Added Sugars" % fda_round("added_sugar", added)
    right = "%d%%" % pct("added_sugar", added)
    out.append(left.ljust(W - len(right)) + right)
    row("Protein", "protein")
    out.append("=" * W)

    def cell(key):
        name, unit = SHORT_NAMES.get(key, NAMES[key])
        return "%s %s %d%%" % (name, fmt_amount(p.get(key, 0), unit).replace(" ", ""), pct(key, p.get(key, 0)))

    def two_columns(keys):
        for i in range(0, len(keys), 2):
            left = cell(keys[i])
            right = cell(keys[i + 1]) if i + 1 < len(keys) else ""
            out.append((left.ljust(W // 2) + right).rstrip())

    two_columns(["vitd", "calcium", "iron", "potassium"])
    if micros:
        out.append("-" * W)
        two_columns(MICROS)
        o3 = p.get("ala", 0) + p.get("epa", 0) + p.get("dha", 0)
        line = "Omega-3 %.2fg" % o3
        if p.get("epa", 0) + p.get("dha", 0) >= 0.05:
            line += " (EPA+DHA %.2fg)" % (p.get("epa", 0) + p.get("dha", 0))
        if p.get("alcohol", 0) >= 0.5:
            line += " | Alcohol %.1fg%s" % (p["alcohol"], " after cooking" if a.cooked else "")
        if p.get("caffeine", 0) >= 1:
            line += " | Caffeine %dmg" % round(p["caffeine"])
        out.append(line)
    out.append("-" * W)
    out.append("* %DV = share of a 2,000-calorie daily diet.")
    return out


SHORT_NAMES = {"thiamin": ("Thiamin", "mg"), "riboflavin": ("Riboflavin", "mg"), "niacin": ("Niacin", "mg"),
               "folate": ("Folate", "mcg"), "b12": ("Vitamin B12", "mcg"), "b6": ("Vitamin B6", "mg")}


def checks(a):
    p, t = a.per, a.totals
    out = []
    kcal = p.get("kcal", 0)
    e = {"protein": 4 * p.get("protein", 0), "carb": 4 * p.get("carb", 0), "fat": 9 * p.get("fat", 0),
         "alcohol": 7 * p.get("alcohol", 0)}
    tot = sum(e.values()) or 1
    out.append("Energy split: protein %d%% | carbs %d%% | fat %d%%%s" % (
        round(100 * e["protein"] / tot), round(100 * e["carb"] / tot), round(100 * e["fat"] / tot),
        (" | alcohol %d%%" % round(100 * e["alcohol"] / tot)) if e["alcohol"] > 1 else ""))
    w = a.weight or 1
    ed = t.get("kcal", 0) / w
    band = "very low" if ed < 0.6 else "low" if ed < 1.5 else "medium" if ed < 4 else "high"
    out.append("Energy density: %.2f kcal/g (%s; %s weight %d g)" % (ed, band, a.weight_basis, round(w)))
    salt_pct = t.get("sodium", 0) / 1000.0 * NA_TO_SALT / w * 100
    line = "Salt: %.2f%% of %s weight (%.1f g salt-equivalent in the whole recipe)" % (
        salt_pct, a.weight_basis, t.get("sodium", 0) / 1000.0 * NA_TO_SALT)
    rt = a.recipe.type
    if rt:
        key = next((k for k in SALT_TARGETS if k == rt or k in rt.split() or k in rt), None)
        if key:
            lo, hi = SALT_TARGETS[key]
            verdict = "OK" if lo <= salt_pct <= hi else ("LOW" if salt_pct < lo else "HIGH")
            line += " -> %s target %.1f-%.1f%%: %s" % (key, lo, hi, verdict)
            if not a.recipe.yield_g and verdict != "OK":
                line += " (give yield: if liquid reduces or evaporates)"
        else:
            line += " (unknown type '%s'; known: %s)" % (rt, ", ".join(sorted(SALT_TARGETS)))
    out.append(line)
    out.append("Sugar: %.1f%% of weight | protein %.1f g per 100 kcal" % (
        100 * t.get("sugar", 0) / w, 100 * p.get("protein", 0) / kcal if kcal else 0))
    if kcal:
        fat_k = 100 * 9 * p.get("fat", 0) / kcal
        sug_k = 100 * 4 * p.get("sugar", 0) / kcal
        carb_k = 100 * 4 * (p.get("carb", 0) - p.get("fiber", 0)) / kcal
        na_w = 100 * t.get("sodium", 0) / 1000.0 / w
        flags = []
        if fat_k > 25 and na_w >= 0.30:
            flags.append("fat+sodium")
        if fat_k > 20 and sug_k > 20:
            flags.append("fat+sugar")
        if carb_k > 40 and na_w >= 0.20:
            flags.append("carb+sodium")
        out.append("Hyper-palatable combos (Fazzino 2019): %s" % (", ".join(flags) if flags else "none"))
    if a.roles:
        bits = []
        for role, _ in ROLE_RULES:
            names = a.roles.get(role)
            bits.append("%s: %s" % (role, ", ".join(dict.fromkeys(names)) if names else "NONE"))
        out.append("Flavor roles: " + " | ".join(bits))
        out.append("Umami synergy (glutamate + nucleotide sources): %s" % ("yes" if a.umami_synergy else "no"))
    line = "Allergens: %s" % (", ".join(a.allergens) or "none of the 9 major allergens")
    if a.likely_allergens:
        line += " | brand-dependent, check the label: %s" % "; ".join(
            "%s (%s)" % (k, ", ".join(v)) for k, v in sorted(a.likely_allergens.items()))
    out.append(line)
    filled = ["%s %d%%" % (NAMES[k][0], round(100 * v)) for k, v in sorted(a.imputed.items(), key=lambda kv: -kv[1])
              if k in NAMES and v >= 0.10 and k not in ("pantothenic", "leucine")]
    if filled:
        out.append("Filled from closest related USDA foods (share of recipe weight): %s" % ", ".join(filled))
    gaps = [NAMES[k][0] for k in ["vitd", "vitk", "choline", "vite", "selenium", "folate", "sugar", "fiber"]
            if a.coverage.get(k, 1) < 0.85]
    if gaps:
        out.append("No USDA value for >15%% of the weight: %s" % ", ".join(gaps))
    return out


def match_lines(a):
    out = []
    for ln in a.items:
        q = ln.raw.strip()[:44]
        if ln.warn:
            out.append("  !! %-44s %s" % (q, ln.warn))
            continue
        tag = ln.food.id if ln.food.id not in ("custom",) else "custom"
        extra = []
        if ln.consumed != 1.0:
            extra.append("%d%% eaten" % round(ln.consumed * 100))
        if ln.note:
            extra.append(ln.note)
        if ln.cook_note:
            extra.append(ln.cook_note)
        if ln.food.cat == "online":
            extra.append(ln.food.source)
        out.append("  %6.0f g  %-44s -> %s [%s]%s" % (
            ln.grams, q, ln.food.desc[:72], tag, (" (" + "; ".join(extra) + ")") if extra else ""))
    return out


def as_json(a):
    return {
        "title": a.recipe.title, "servings": a.servings, "total_weight_g": round(a.weight, 1),
        "per_serving": {k: round_sig(v, 4) for k, v in sorted(a.per.items())},
        "totals": {k: round_sig(v, 4) for k, v in sorted(a.totals.items())},
        "percent_dv": {k: pct(k, a.per.get(k, 0)) for k in DV},
        "salt_pct": round(a.totals.get("sodium", 0) / 1000.0 * NA_TO_SALT / (a.weight or 1) * 100, 3),
        "weight_basis": a.weight_basis, "allergens": a.allergens, "likely_allergens": a.likely_allergens,
        "imputed_share": {k: round(v, 3) for k, v in a.imputed.items()}, "roles": a.roles,
        "ingredients": [{"line": ln.raw, "grams": ln.grams, "fdc_id": ln.food.id if ln.food else None,
                         "food": ln.food.desc if ln.food else None, "cooking": ln.cook_note or None,
                         "warning": ln.warn} for ln in a.items],
    }


# --------------------------------------------------------------------------------------------
# Commands


def read_inputs(paths):
    texts = []
    for p in paths:
        if p == "-":
            texts.append(sys.stdin.read())
        else:
            with open(p, encoding="utf-8") as f:
                texts.append(f.read())
    return "\n".join(texts)


def cmd_analyze(args, db):
    recipes = parse_recipes(read_inputs(args.files))
    if not recipes:
        sys.exit("No ingredient lines found.")
    results = []
    for r in recipes:
        if args.servings:
            r.servings = args.servings
        if args.yield_g:
            r.yield_g = parse_grams(args.yield_g)
        if args.type:
            r.type = args.type
        results.append(analyze_recipe(db, r))
    if args.format == "json":
        print(json.dumps([as_json(a) for a in results], indent=1))
        return
    for a in results:
        print("Ingredient matches (fix a wrong one with =fdc:ID from `search`, or {custom per-100g values}):")
        print("\n".join(match_lines(a)))
        if not a.recipe.servings_set:
            print("  !! no 'servings:' line, assuming 1")
        print()
        print("Label (paste this block unchanged):")
        print("```")
        print("\n".join(label_text(a, micros=args.micros != "none")))
        print("```")
        print()
        print("Kitchen checks:")
        for c in checks(a):
            print("- " + c)
        print("Sources: USDA FoodData Central (SR Legacy%s); %s." % (
            ", Foundation/Branded online" if any(ln.food and ln.food.cat == "online" for ln in a.items) else "",
            "cooking losses from USDA Nutrient Retention Factors R6, yields from USDA raw/cooked pairs"
            if a.cooked else "raw ingredients (tag cooked items with ~method for as-cooked values)"))
        print()


def cmd_search(args, db):
    query = " ".join(args.query)
    if args.online:
        for f in search_online(query, args.limit):
            kcal = next((n.get("value") for n in f.get("foodNutrients", []) if n.get("nutrientId") == 1008), "?")
            brand = (" | " + f["brandOwner"]) if f.get("brandOwner") else ""
            print("fdc:%s  [%s] %s%s  (%s kcal/100g)" % (f["fdcId"], f.get("dataType"), f["description"], brand, kcal))
        return
    for score, fid, opts, alias in db.search(query, limit=args.limit):
        row = db.rows[fid]
        kcal = row[4]
        via = (" (alias '%s')" % alias) if alias else ""
        print("fdc:%s  %s  [%s, %s kcal/100g, score %.1f]%s" % (fid, row[2], row[1], kcal, score, via))


def cmd_portions(args, db):
    q = " ".join(args.query)
    fid = q.replace("fdc:", "") if re.match(r"^(fdc:)?\d+$", q) else None
    if fid is None:
        hits = db.search(q, limit=1)
        if not hits:
            sys.exit("No match for %r" % q)
        fid = hits[0][1]
    food = db.food(fid) or fetch_online(fid)
    print("%s [fdc:%s]" % (food.desc, food.id))
    for a, meas, g in food.portions:
        print("  %g %s = %g g" % (a, meas, g))
    if not food.portions:
        print("  (no USDA portions; weigh it or use grams)")


def nutrient_row(label, p):
    return "| %s | %d | %.0f g | %.0f g | %.0f g | %.0f g | {:,} mg |".format(int(round(p.get("sodium", 0)))) % (
        label, round(p.get("kcal", 0)), p.get("protein", 0), p.get("carb", 0), p.get("fat", 0), p.get("fiber", 0))


def cmd_day(args, db):
    recipes = parse_recipes(read_inputs(args.files))
    targets = {}
    if args.targets:
        with open(args.targets, encoding="utf-8") as f:
            targets = json.load(f)
    days = []
    for r in recipes:
        key = r.day or "Day"
        if not days or days[-1][0] != key:
            days.append((key, []))
        days[-1][1].append(r)
    day_totals = []
    for day, meals in days:
        print("### %s" % day)
        print("| Meal | kcal | Protein | Carbs | Fat | Fiber | Sodium |")
        print("|---|---|---|---|---|---|---|")
        total = {}
        warnings = []
        for r in meals:
            a = analyze_recipe(db, r)
            eaten = {k: v * r.eat for k, v in a.per.items()}
            for k, v in eaten.items():
                total[k] = total.get(k, 0.0) + v
            print(nutrient_row("%s (%g serving%s)" % (r.title or "meal", r.eat, "" if r.eat == 1 else "s"), eaten))
            warnings += ["%s: %s -> %s" % (r.title, ln.raw.strip(), ln.warn) for ln in a.items if ln.warn]
        print(nutrient_row("**Total**", total))
        if targets:
            print(nutrient_row("Target", {k: targets.get(k, 0) for k in ("kcal", "protein", "carb", "fat", "fiber", "sodium")}))
        print()
        print(day_summary(total, targets))
        for w in warnings:
            print("  !! " + w)
        print()
        day_totals.append(total)
    if len(day_totals) > 1:
        avg = {}
        for t in day_totals:
            for k, v in t.items():
                avg[k] = avg.get(k, 0.0) + v / len(day_totals)
        print("### Average of %d days" % len(day_totals))
        print("| | kcal | Protein | Carbs | Fat | Fiber | Sodium |")
        print("|---|---|---|---|---|---|---|")
        print(nutrient_row("Daily average", avg))
        print()
        print(day_summary(avg, targets))


def day_summary(t, targets):
    kcal = t.get("kcal", 0) or 1
    lines = []
    sat = 100 * 9 * t.get("satfat", 0) / kcal
    add = 100 * 4 * t.get("added_sugar", 0) / kcal
    fiber_goal = targets.get("fiber", 14 * kcal / 1000.0)
    lines.append("Sat fat %.0f g (%.0f%% kcal, aim <10%%) | added sugar ~%.0f g (%.0f%% kcal, aim <10%%) | "
                 "fiber %.0f g (goal %.0f g) | sodium {:,} mg (limit {:,})".format(
                     int(t.get("sodium", 0)), int(targets.get("sodium", 2300))) % (
                     t.get("satfat", 0), sat, t.get("added_sugar", 0), add, t.get("fiber", 0), fiber_goal))
    goals = targets.get("micros", {})
    parts, low = [], []
    for key in ["vitd", "calcium", "iron", "potassium"] + MICROS:
        goal = goals.get(key, DV.get(key))
        if not goal:
            continue
        val = 100 * t.get(key, 0) / goal
        parts.append("%s %d%%" % (NAMES[key][0], val))
        if val < 70:
            low.append(NAMES[key][0])
    o3 = t.get("epa", 0) + t.get("dha", 0)
    lines.append("Micros (%% of %s): %s | EPA+DHA %.2f g" % (
        "personal targets" if goals else "FDA DV", ", ".join(parts), o3))
    lines.append("Below 70%%: %s" % (", ".join(low) if low else "none"))
    return "\n".join(lines)


SECTIONS = [
    ("Produce", {"veg", "fruit"}), ("Meat & poultry", {"poultry", "beef", "pork", "lamb", "sausage"}),
    ("Seafood", {"seafood"}), ("Dairy, eggs & tofu", {"dairy"}), ("Grains, pasta & bread", {"grain", "baked", "cereal"}),
    ("Beans, nuts & seeds", {"legume", "nut"}), ("Oils, sauces & condiments", {"fat", "sauce"}),
    ("Spices & baking", {"spice", "sweet"}), ("Drinks", {"drink", "alcohol"}), ("Other", set()),
]


def cmd_shop(args, db):
    recipes = parse_recipes(read_inputs(args.files))
    items = {}
    problems = []
    for r in recipes:
        a = analyze_recipe(db, r)
        for ln in a.items:
            if ln.warn or ln.grams is None:
                problems.append("%s -> %s" % (ln.raw.strip(), ln.warn))
                continue
            key = ln.food.id if ln.food.id != "custom" else "custom:" + ln.name.lower()
            it = items.setdefault(key, {"food": ln.food, "grams": 0.0, "uses": set(), "name": ln.name})
            it["grams"] += ln.grams * args.scale
            it["uses"].add(r.title or "recipe")
    by_section = {}
    pantry = []
    for it in items.values():
        f = it["food"]
        d = f.desc.lower()
        if d.startswith("beverages, water") or d.startswith("water"):
            continue
        if f.cat in ("spice", "fat") or d.startswith("salt") or (f.cat == "sweet" and it["grams"] < 60):
            if it["grams"] < 120 or f.cat == "spice":
                pantry.append(it)
                continue
        sec = next((s for s, cats in SECTIONS if f.cat in cats), "Other")
        if "fresh" in d and f.cat == "spice":
            sec = "Produce"
        elif d.startswith(("soy sauce", "miso", "peanut butter", "hummus")):
            sec = "Oils, sauces & condiments"
        elif d.startswith(("tofu", "tempeh")):
            sec = "Dairy, eggs & tofu"
        by_section.setdefault(sec, []).append(it)
    print("## Grocery list (%d recipe%s%s)" % (len(recipes), "" if len(recipes) == 1 else "s",
                                               ", x%g" % args.scale if args.scale != 1 else ""))
    for sec, _ in SECTIONS:
        group = by_section.get(sec)
        if not group:
            continue
        print("\n**%s**" % sec)
        for it in sorted(group, key=lambda i: i["food"].desc):
            print("- %s - %s" % (shop_name(it), shop_qty(it)))
    if pantry:
        print("\n**Pantry check** (small amounts): " + ", ".join(
            "%s %s" % (shop_name(it), shop_amount(it["grams"])) for it in sorted(pantry, key=lambda i: i["food"].desc)))
    for p in problems:
        print("  !! " + p)


def shop_name(it):
    return it["name"].split(",")[0].strip() or it["food"].desc.split(",")[0]


def shop_amount(g):
    if g >= 1000:
        return "%.2g kg (%.1f lb)" % (g / 1000.0, g / 453.592)
    if g >= 200:
        return "%d g (%.1f lb)" % (round(g, -1), g / 453.592)
    return "%d g" % round(g)


def shop_qty(it):
    g = it["grams"]
    f = it["food"]
    juice = next((p for p in f.portions if p[1].lower().endswith(" yields")), None)
    if juice and f.cat == "fruit":
        n = math.ceil(g / (juice[2] / juice[0]) * 2) / 2.0
        return "%g %s%s, juiced (%d g juice)" % (n, juice[1].split()[0], "" if n <= 1 else "s", round(g))
    if f.cat in ("veg", "fruit", "dairy"):
        for pref in ("medium", "large", "fruit", "clove", "head", "bunch", "stalk", "each"):
            p = next((p for p in f.portions if p[1].lower().startswith(pref)), None)
            if p and p[2] / p[0] >= 3:
                n = g / (p[2] / p[0])
                if 0.5 <= n <= 60:
                    return "%s %s (%s)" % (("%g" % (math.ceil(n * 2) / 2.0)), p[1].split(" (")[0], shop_amount(g))
    return shop_amount(g)


ACTIVITY = {"sedentary": 1.2, "light": 1.375, "moderate": 1.55, "active": 1.725, "athlete": 1.9}


def dri(sex, age, preg=False, lact=False):
    m = sex == "m"
    old = age >= 51
    d = {
        "calcium": 1200 if (age > 70 or (not m and old)) else 1000,
        "iron": 27 if preg else 9 if lact else (8 if (m or old) else 18),
        "magnesium": (400 if age < 31 else 420) if m else (350 if preg else 310 if age < 31 else 320),
        "zinc": 11 if m else (11 if preg else 12 if lact else 8),
        "vitd": 20 if age > 70 else 15,
        "vitc": 90 if m else (85 if preg else 120 if lact else 75),
        "vita": 900 if m else (770 if preg else 1300 if lact else 700),
        "vite": 19 if lact else 15,
        "vitk": 120 if m else 90,
        "thiamin": 1.2 if m else (1.4 if preg or lact else 1.1),
        "riboflavin": 1.3 if m else (1.4 if preg else 1.6 if lact else 1.1),
        "niacin": 16 if m else (18 if preg else 17 if lact else 14),
        "b6": (1.7 if old else 1.3) if m else (1.9 if preg else 2.0 if lact else 1.5 if old else 1.3),
        "folate": 600 if preg else 500 if lact else 400,
        "b12": 2.6 if preg else 2.8 if lact else 2.4,
        "choline": 550 if m or lact else (450 if preg else 425),
        "potassium": 3400 if m else (2900 if preg else 2800 if lact else 2600),
        "phosphorus": 700,
        "selenium": 60 if preg else 70 if lact else 55,
        "copper": 0.9 if not (preg or lact) else (1.0 if preg else 1.3),
        "manganese": 2.3 if m else (2.0 if preg else 2.6 if lact else 1.8),
    }
    return d


def parse_length_cm(s):
    s = s.strip().lower()
    m = re.match(r"^(\d+)\s*'\s*(\d+(?:\.\d+)?)?\s*\"?$", s) or re.match(r"^(\d+)\s*ft\s*(\d+(?:\.\d+)?)?\s*(?:in)?$", s)
    if m:
        return (int(m.group(1)) * 12 + float(m.group(2) or 0)) * 2.54
    m = re.match(r"^(\d+(?:\.\d+)?)\s*(cm|m|in|inches)?$", s)
    if not m:
        sys.exit("Can't read height %r (try 170cm or 5'7\")" % s)
    v, u = float(m.group(1)), m.group(2) or ("cm" if float(m.group(1)) > 3 else "m")
    return v * {"cm": 1, "m": 100, "in": 2.54, "inches": 2.54}[u]


def parse_mass_kg(s):
    m = re.match(r"^\s*(\d+(?:\.\d+)?)\s*(kg|lb|lbs)?\s*$", s.lower())
    if not m:
        sys.exit("Can't read weight %r (try 70kg or 154lb)" % s)
    v = float(m.group(1))
    return v * 0.453592 if m.group(2) in ("lb", "lbs") else v


def cmd_targets(args, db=None):
    h = parse_length_cm(args.height)
    w = parse_mass_kg(args.weight)
    m = args.sex.lower().startswith("m")
    bmr = 10 * w + 6.25 * h - 5 * args.age + (5 if m else -161)
    tdee = bmr * ACTIVITY[args.activity]
    goal = args.goal
    floor = 1500 if m else 1200
    if goal == "lose":
        kcal = max(tdee - min(max(0.2 * tdee, 300), 750), floor)
    elif goal == "gain":
        kcal = tdee + max(0.1 * tdee, 250)
    else:
        kcal = tdee
    if args.pregnant:
        kcal += 340 if args.trimester == 2 else 450 if args.trimester == 3 else 0
    if args.lactating:
        kcal += 400
    bmi = w / (h / 100.0) ** 2
    ref_w = min(w, 25 * (h / 100.0) ** 2) if bmi >= 30 else w
    gkg = args.protein or {"lose": 1.8, "gain": 1.8, "recomp": 2.0}.get(goal, 1.4 if args.age < 65 else 1.2)
    if args.pregnant:
        gkg = max(gkg, 1.1)
    protein = gkg * ref_w
    fat = 0.30 * kcal / 9
    carb = max((kcal - protein * 4 - fat * 9) / 4, 130)
    t = {
        "kcal": round(kcal), "protein": round(protein), "fat": round(fat), "carb": round(carb),
        "fiber": round(14 * kcal / 1000), "sodium": 2300, "satfat_max_g": round(0.10 * kcal / 9),
        "added_sugar_max_g": round(0.10 * kcal / 4), "micros": dri("m" if m else "f", args.age, args.pregnant, args.lactating),
        "basis": {"bmr": round(bmr), "tdee": round(tdee), "bmi": round(bmi, 1), "protein_g_per_kg": gkg,
                  "protein_reference_kg": round(ref_w, 1), "equation": "Mifflin-St Jeor"},
    }
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(t, f, indent=1)
    print("BMR %d kcal | TDEE %d kcal (%s x%.3g) | BMI %.1f" % (bmr, tdee, args.activity, ACTIVITY[args.activity], bmi))
    print("Daily target: %d kcal | protein %d g (%.1f g/kg%s) | fat %d g (30%%) | carbs %d g | fiber %d g" % (
        t["kcal"], t["protein"], gkg, " of reference weight %.0f kg" % ref_w if ref_w != w else "", t["fat"],
        t["carb"], t["fiber"]))
    print("Limits: sodium <2,300 mg | sat fat <%d g | added sugar <%d g" % (t["satfat_max_g"], t["added_sugar_max_g"]))
    print("Per meal (3 meals): ~%d kcal, ~%d g protein" % (t["kcal"] / 3, t["protein"] / 3))
    print("Micronutrient targets (DRI): " + ", ".join(
        "%s %g %s" % (NAMES[k][0], v, NAMES[k][1]) for k, v in t["micros"].items()))
    if goal == "lose" and kcal == floor:
        print("Note: target hit the %d kcal floor; go slower or add activity rather than eating less." % floor)
    if args.out:
        print("Saved to %s (use with: day --targets %s)" % (args.out, args.out))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd")
    a = sub.add_parser("analyze", help="nutrition label + kitchen checks")
    a.add_argument("files", nargs="+", help="recipe file(s), or - for stdin")
    a.add_argument("--servings", type=float)
    a.add_argument("--yield", dest="yield_g", help="finished weight, e.g. 1400g")
    a.add_argument("--type", help="dish type for the salt check: " + ", ".join(sorted(SALT_TARGETS)))
    a.add_argument("--format", choices=["md", "json"], default="md")
    a.add_argument("--micros", choices=["all", "none"], default="all")
    s = sub.add_parser("search", help="find USDA foods")
    s.add_argument("query", nargs="+")
    s.add_argument("--limit", type=int, default=8)
    s.add_argument("--online", action="store_true", help="search FoodData Central online (branded foods too)")
    p = sub.add_parser("portions", help="USDA gram weights for a food")
    p.add_argument("query", nargs="+")
    d = sub.add_parser("day", help="meal-plan day totals")
    d.add_argument("files", nargs="+")
    d.add_argument("--targets", help="JSON from `targets --out`")
    sh = sub.add_parser("shop", help="consolidated grocery list")
    sh.add_argument("files", nargs="+")
    sh.add_argument("--scale", type=float, default=1.0)
    t = sub.add_parser("targets", help="calorie/macro/micro targets")
    t.add_argument("--sex", required=True, choices=["m", "f", "male", "female"])
    t.add_argument("--age", type=int, required=True)
    t.add_argument("--height", required=True, help="e.g. 170cm or 5'7\"")
    t.add_argument("--weight", required=True, help="e.g. 70kg or 154lb")
    t.add_argument("--activity", choices=sorted(ACTIVITY), default="light")
    t.add_argument("--goal", choices=["lose", "maintain", "gain", "recomp"], default="maintain")
    t.add_argument("--protein", type=float, help="override protein g/kg")
    t.add_argument("--pregnant", action="store_true")
    t.add_argument("--trimester", type=int, default=2)
    t.add_argument("--lactating", action="store_true")
    t.add_argument("--out", help="save targets JSON here")
    args = ap.parse_args(argv)
    if not args.cmd:
        ap.print_help()
        return
    if args.cmd == "targets":
        cmd_targets(args)
        return
    db = DB()
    {"analyze": cmd_analyze, "search": cmd_search, "portions": cmd_portions, "day": cmd_day,
     "shop": cmd_shop}[args.cmd](args, db)


if __name__ == "__main__":
    main()
