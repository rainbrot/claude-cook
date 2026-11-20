#!/usr/bin/env python3
"""Rebuild the USDA tables in skills/cook/data/.

Usage:
    python3 tools/build_data.py <SR Legacy CSV folder> [--retention retn06.txt]

Inputs (public domain, U.S. Department of Agriculture):
- SR Legacy CSV release: https://fdc.nal.usda.gov/download-datasets (FoodData_Central_sr_legacy_food_csv_2018-04)
- Table of Nutrient Retention Factors, Release 6 (2007):
  https://www.ars.usda.gov/ARSUserFiles/80400525/Data/retn/retn06.txt

Outputs:
- foods.tsv      foods x 42 nutrients per 100 g; gaps filled from the closest related foods, and the filled
                 nutrients listed in the `imputed` column
- portions.tsv   household measures with gram weights
- retention.tsv  % of each nutrient kept, per USDA cooking-method code
- yields.tsv     cooking weight change and fat kept, per food class and method, from USDA raw/cooked pairs
"""
import argparse
import csv
import os
import re
import statistics
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "skills", "cook", "data")
sys.path.insert(0, os.path.join(ROOT, "skills", "cook", "scripts"))
import cooking  # noqa: E402

# Output column -> USDA nutrient ids (first one present wins).
NUTRIENTS = [
    ("kcal", ["1008"]), ("protein", ["1003"]), ("fat", ["1004"]), ("carb", ["1005"]), ("fiber", ["1079"]),
    ("sugar", ["2000", "1063"]), ("satfat", ["1258"]), ("mufa", ["1292"]), ("pufa", ["1293"]),
    ("transfat", ["1257"]), ("chol", ["1253"]), ("sodium", ["1093"]), ("potassium", ["1092"]),
    ("calcium", ["1087"]), ("iron", ["1089"]), ("magnesium", ["1090"]), ("phosphorus", ["1091"]),
    ("zinc", ["1095"]), ("copper", ["1098"]), ("manganese", ["1101"]), ("selenium", ["1103"]),
    ("vita", ["1106"]), ("vitc", ["1162"]), ("vitd", ["1114"]), ("vite", ["1109"]), ("vitk", ["1185"]),
    ("thiamin", ["1165"]), ("riboflavin", ["1166"]), ("niacin", ["1167"]), ("b6", ["1175"]),
    ("folate", ["1190", "1177"]), ("b12", ["1178"]), ("choline", ["1180"]), ("pantothenic", ["1170"]),
    ("ala", ["1404", "1270"]), ("epa", ["1278"]), ("dha", ["1272"]), ("dpa", ["1280"]), ("leucine", ["1213"]),
    ("water", ["1051"]), ("alcohol", ["1018"]), ("caffeine", ["1057"]),
]
KEYS = [k for k, _ in NUTRIENTS]
# Never imputed: always analyzed, or meaningless to borrow.
NOT_IMPUTED = {"kcal", "protein", "fat", "carb", "water", "alcohol", "caffeine"}
PLANT_CATS = {"veg", "fruit", "legume", "grain", "cereal", "nut", "spice"}
ANIMAL_ONLY = {"vitd", "b12", "chol", "epa", "dha", "dpa"}

# Retention file nutrient numbers -> output keys.
RETN = {"301": "calcium", "303": "iron", "304": "magnesium", "305": "phosphorus", "306": "potassium",
        "307": "sodium", "309": "zinc", "312": "copper", "392": "vita", "401": "vitc", "404": "thiamin",
        "405": "riboflavin", "406": "niacin", "415": "b6", "417": "folate", "418": "b12", "421": "choline",
        "221": "alcohol"}

EXCLUDE_CATEGORIES = {"3", "21", "22", "24", "25", "26", "27"}
CATEGORY_CODES = {
    "1": "dairy", "2": "spice", "4": "fat", "5": "poultry", "6": "sauce", "7": "sausage", "8": "cereal",
    "9": "fruit", "10": "pork", "11": "veg", "12": "nut", "13": "beef", "14": "drink", "15": "seafood",
    "16": "legume", "17": "lamb", "18": "baked", "19": "sweet", "20": "grain", "23": "snack", "28": "alcohol",
}
SR_METHODS = [("pan-browned", "brown"), ("pan-fried", "panfry"), ("pan-broiled", "broil"), ("stir-fried", "stirfry"),
              ("roasted", "roast"), ("baked", "bake"), ("broiled", "broil"), ("grilled", "grill"),
              ("braised", "braise"), ("stewed", "stew"), ("simmered", "simmer"), ("boiled", "boil"),
              ("steamed", "steam"), ("microwaved", "microwave"), ("fried", "fry"), ("dry heat", "bake"),
              ("moist heat", "poach"), ("poached", "poach")]
PAIR_NOISE = {"raw", "unprepared", "cooked", "drained", "with", "without", "salt", "dry", "heat", "moist", "and",
              "crumbles", "patty", "patties", "loaf"}


def fmt(x):
    if x == 0:
        return "0"
    s = "%.3g" % x
    if "e" in s:
        s = "%.4f" % x
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s


def words(text):
    return [w for w in re.findall(r"[a-z0-9%/]+", text.lower())]


def rows(src, name):
    with open(os.path.join(src, name), newline="", encoding="utf-8") as f:
        yield from csv.DictReader(f)


def load_foods(src):
    foods = {}
    for r in rows(src, "food.csv"):
        cat = r["food_category_id"]
        if cat in EXCLUDE_CATEGORIES or cat not in CATEGORY_CODES:
            continue
        foods[r["fdc_id"]] = {"cat": CATEGORY_CODES[cat], "desc": r["description"].strip(), "aka": [], "v": {}}
    for r in rows(src, "food_attribute.csv"):
        if r["food_attribute_type_id"] == "1000" and r["fdc_id"] in foods:
            v = r["value"].strip()
            if v and v.lower() not in foods[r["fdc_id"]]["desc"].lower():
                foods[r["fdc_id"]]["aka"].append(v)
    wanted = {nid for _, ids in NUTRIENTS for nid in ids}
    raw = {}
    for r in rows(src, "food_nutrient.csv"):
        if r["fdc_id"] in foods and r["nutrient_id"] in wanted and r["amount"] != "":
            raw.setdefault(r["fdc_id"], {})[r["nutrient_id"]] = float(r["amount"])
    for fid, food in foods.items():
        got = raw.get(fid, {})
        for key, ids in NUTRIENTS:
            val = next((got[i] for i in ids if i in got), None)
            if val is not None:
                food["v"][key] = val
    return foods


def impute(foods):
    """Fill missing nutrients: animal-only nutrients are zero in plants; everything else comes from the
    median of the three most similar foods (same category, most shared description words) that have it."""
    toks = {fid: set(words(f["desc"])) for fid, f in foods.items()}
    first = {fid: f["desc"].split(",")[0].lower() for fid, f in foods.items()}
    by_cat = {}
    for fid, f in foods.items():
        by_cat.setdefault(f["cat"], []).append(fid)
    filled = 0
    for fid, f in foods.items():
        f["imputed"] = []
        missing = [k for k in KEYS if k not in f["v"] and k not in NOT_IMPUTED]
        if not missing:
            continue
        plant = f["cat"] in PLANT_CATS or (f["cat"] == "fat" and "oil" in f["desc"].lower()
                                           and not any(w in f["desc"].lower() for w in ("fish", "cod liver")))
        neighbors = None
        for key in missing:
            if plant and key in ANIMAL_ONLY and not (key == "vitd" and f["desc"].lower().startswith("mushroom")):
                f["v"][key] = 0.0
                f["imputed"].append(key)
                filled += 1
                continue
            if neighbors is None:
                scored = []
                for other in by_cat[f["cat"]]:
                    if other == fid:
                        continue
                    a, b = toks[fid], toks[other]
                    sim = len(a & b) / float(len(a | b) or 1) + (0.5 if first[other] == first[fid] else 0)
                    if sim >= 0.35:
                        scored.append((sim, other))
                scored.sort(reverse=True)
                neighbors = [o for _, o in scored[:40]]
            vals = [foods[o]["v"][key] for o in neighbors if key in foods[o]["v"]][:3]
            if vals:
                f["v"][key] = statistics.median(vals)
                f["imputed"].append(key)
                filled += 1
    return filled


def write_foods(foods):
    with open(os.path.join(OUT, "foods.tsv"), "w", encoding="utf-8", newline="") as f:
        f.write("\t".join(["fdc_id", "cat", "description", "aka"] + KEYS + ["imputed"]) + "\n")
        for fid in sorted(foods, key=int):
            food = foods[fid]
            cells = [fmt(food["v"][k]) if k in food["v"] else "" for k in KEYS]
            aka = "; ".join(food["aka"]).replace("\t", " ")
            f.write("\t".join([fid, food["cat"], food["desc"], aka] + cells + [",".join(food["imputed"])]) + "\n")


def write_portions(src, foods):
    n = 0
    with open(os.path.join(OUT, "portions.tsv"), "w", encoding="utf-8", newline="") as f:
        f.write("fdc_id\tamount\tmeasure\tgrams\n")
        for r in rows(src, "food_portion.csv"):
            if r["fdc_id"] not in foods or not r["gram_weight"]:
                continue
            measure = " ".join((r["modifier"] or r["portion_description"]).split())
            if not measure:
                continue
            amount = float(r["amount"] or 1) or 1
            f.write("%s\t%s\t%s\t%s\n" % (r["fdc_id"], fmt(amount), measure, fmt(float(r["gram_weight"]))))
            n += 1
    return n


def write_retention(path):
    codes = {}
    with open(path, encoding="latin-1") as f:
        for line in f:
            parts = [x.strip("~") for x in line.rstrip("\r\n").split("^")]
            if len(parts) < 6 or parts[3] not in RETN:
                continue
            code, _, desc, nbr, _, val = parts[:6]
            codes.setdefault(code, [desc, {}])[1][RETN[nbr]] = val
    # retn06.txt omits a few cells that the published retn06.pdf table lists: alcohol for 2.5 h of
    # simmering (5%), and the unchanged (100%) minerals and vitamins on the alcohol-method rows.
    keys = sorted(set(RETN.values()))
    codes["5009"][1].setdefault("alcohol", "5")
    for code, (desc, vals) in codes.items():
        if desc.startswith("ALC BEV"):
            for k in keys:
                if not vals.get(k):
                    vals[k] = "100"
    with open(os.path.join(OUT, "retention.tsv"), "w", encoding="utf-8", newline="") as f:
        f.write("\t".join(["code", "description"] + keys) + "\n")
        for code in sorted(codes):
            desc, vals = codes[code]
            f.write("\t".join([code, desc] + [vals.get(k, "") for k in keys]) + "\n")
    return len(codes)


def write_yields(foods):
    """Weight yield = protein(raw)/protein(cooked) for protein foods, dry matter ratio otherwise.
    Fat kept = fat(cooked) x yield / fat(raw)."""
    def key(desc):
        d = desc.lower()
        for phrase, _ in SR_METHODS:
            d = d.replace(phrase, " ")
        return tuple(w for w in words(d) if w not in PAIR_NOISE)

    raw = {}
    for fid, f in foods.items():
        d = f["desc"].lower()
        if re.search(r"(^|, )(raw|unprepared)(,|$)", d):
            raw.setdefault(key(f["desc"]), fid)
    samples = {}
    for fid, f in foods.items():
        d = f["desc"].lower()
        if "raw" in d or "unprepared" in d or "with salt" in d:
            continue
        method = next((m for phrase, m in SR_METHODS if phrase in d), None)
        if not method:
            continue
        rid = raw.get(key(f["desc"]))
        if not rid:
            continue
        r, c = foods[rid]["v"], f["v"]
        cls = cooking.cook_class(foods[rid]["cat"], foods[rid]["desc"], r.get("fat", 0))
        if cls is None:
            continue
        if r.get("protein", 0) >= 8 and c.get("protein"):
            y = r["protein"] / c["protein"]
        elif r.get("water") is not None and c.get("water") is not None and c["water"] < 100:
            y = (100 - r["water"]) / (100 - c["water"])
        else:
            continue
        if not 0.2 <= y <= 4:
            continue
        kept = None
        if r.get("fat", 0) >= 5 and c.get("fat") is not None:
            kept = min(c["fat"] * y / r["fat"], 1.0)
        samples.setdefault((cls, method), []).append((y, kept))
    n = 0
    with open(os.path.join(OUT, "yields.tsv"), "w", encoding="utf-8", newline="") as f:
        f.write("class\tmethod\tyield\tfat_kept\tpairs\n")
        for (cls, method), vals in sorted(samples.items()):
            if len(vals) < 4:  # too few USDA pairs to trust; cooking.py defaults apply
                continue
            ys = [v[0] for v in vals]
            ks = [v[1] for v in vals if v[1] is not None]
            f.write("%s\t%s\t%.3f\t%s\t%d\n" % (cls, method, statistics.median(ys),
                                                 "%.3f" % statistics.median(ks) if ks else "", len(vals)))
            n += 1
    return n


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("sr_dir")
    ap.add_argument("--retention", help="path to retn06.txt")
    args = ap.parse_args()
    foods = load_foods(args.sr_dir)
    print("yields: %d class/method pairs" % write_yields(foods))  # before imputation: real values only
    print("imputed values: %d" % impute(foods))
    write_foods(foods)
    print("foods: %d, portions: %d" % (len(foods), write_portions(args.sr_dir, foods)))
    if args.retention:
        print("retention codes: %d" % write_retention(args.retention))


if __name__ == "__main__":
    main()
