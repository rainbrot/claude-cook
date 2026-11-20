"""Tests for the Claude Cook nutrition engine. Run: python3 -m unittest discover tests"""
import glob
import io
import json
import os
import re
import sys
import unittest
from contextlib import redirect_stdout

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "skills", "cook", "scripts"))
os.environ["COOK_OFFLINE"] = "1"  # tests never touch the network

import cooking  # noqa: E402
import nutrition as n  # noqa: E402

DB = n.DB()


def grams(line):
    ln = n.parse_line(line)
    food, err = n.resolve(DB, ln)
    assert food is not None, "%s: %s" % (line, err)
    g, note = n.grams_for(ln, food)
    assert g is not None, "%s: %s" % (line, note)
    return g, food


class ParseTests(unittest.TestCase):
    def test_quantities(self):
        cases = {
            "1 1/2 cups flour": (1.5, "cup"), "1½ cups sugar": (1.5, "cup"), "2-3 tbsp soy sauce": (2.5, "tbsp"),
            "400g spaghetti": (400, "g"), "a pinch of salt": (1, "pinch"), "3 large eggs": (3, "large"),
            "2 fl oz cream": (2, "floz"), ".5 lb beef": (0.5, "lb"), "1-1/2 tsp cumin": (1.5, "tsp"),
        }
        for line, (qty, unit) in cases.items():
            ln = n.parse_line(line)
            self.assertAlmostEqual(ln.qty, qty, msg=line)
            self.assertEqual(ln.unit, unit, line)

    def test_options(self):
        ln = n.parse_line("1000 g canola oil @8%  # for frying")
        self.assertAlmostEqual(ln.consumed, 0.08)
        self.assertEqual(ln.name, "canola oil")
        ln = n.parse_line("20 g gochujang {kcal=210 sodium=2450} ")
        self.assertEqual(ln.custom["kcal"], 210)
        ln = n.parse_line("1/2 cup cilantro =fdc:169997")
        self.assertEqual(ln.pin, "169997")

    def test_parenthetical_sizes(self):
        g, _ = grams("1 (400 g) can crushed tomatoes")
        self.assertAlmostEqual(g, 400)
        g, _ = grams("2 (15-oz) cans black beans, drained")
        self.assertAlmostEqual(g, 510)  # drained weight from the alias, not the can's net weight

    def test_juice_of(self):
        g, food = grams("juice of 2 limes")
        self.assertIn("Lime juice", food.desc)
        self.assertAlmostEqual(g, 88)

    def test_sections(self):
        text = "# Day 1\n## Oats\nservings: 1\n50 g rolled oats\n## Bowl\nservings: 4\neat: 2\n600 g chicken thighs\n"
        recipes = n.parse_recipes(text)
        self.assertEqual([r.title for r in recipes], ["Oats", "Bowl"])
        self.assertEqual(recipes[1].eat, 2)
        self.assertEqual(recipes[0].day, "Day 1")


class MatchingTests(unittest.TestCase):
    EXPECT = {
        "boneless skinless chicken thighs": "thigh, meat only, raw",
        "unsalted butter": "Butter, without salt",
        "extra-virgin olive oil": "Oil, olive",
        "all-purpose flour": "all-purpose",
        "kosher salt": "Salt, table",
        "large eggs": "Egg, whole, raw",
        "baby spinach": "Spinach, raw",
        "grated parmesan": "parmesan",
        "fish sauce": "Sauce, fish",
        "gochujang": "Gochujang",
        "scallions": "scallions",
        "canned chickpeas": "Chickpeas",
        "heavy cream": "heavy whipping",
        "jalapeño": "jalapeno",
    }

    def test_aliases_point_at_real_foods(self):
        with open(os.path.join(DB.data_dir, "aliases.tsv"), encoding="utf-8") as f:
            for line in f:
                if line.startswith("#") or not line.strip():
                    continue
                alias, fid = line.split("\t")[:2]
                self.assertIn(fid, DB.rows, "alias %r -> missing fdc %s" % (alias, fid))

    def test_common_names(self):
        for name, fragment in self.EXPECT.items():
            hits = DB.search(name, 1)
            self.assertTrue(hits, name)
            self.assertIn(fragment.lower(), DB.rows[hits[0][1]][2].lower(), name)


class ConversionTests(unittest.TestCase):
    def test_usda_portions(self):
        for line, expected in [("1 cup all-purpose flour", 125), ("1 stick butter", 113), ("1 medium onion", 110),
                               ("1 cup heavy cream", 238), ("2 tbsp soy sauce", 32), ("3 garlic cloves", 9),
                               ("1 medium sweet potato", 130)]:
            g, _ = grams(line)
            self.assertAlmostEqual(g, expected, delta=1, msg=line)

    def test_salt_by_brand(self):
        self.assertAlmostEqual(grams("1 tsp Diamond Crystal kosher salt")[0], 2.8)
        self.assertAlmostEqual(grams("1 tsp Morton kosher salt")[0], 4.8)
        self.assertAlmostEqual(grams("1 tsp table salt")[0], 6.0)

    def test_mass_units(self):
        self.assertAlmostEqual(grams("1 lb ground beef")[0], 453.6, delta=0.1)
        self.assertAlmostEqual(grams("6 oz salmon")[0], 170.1, delta=0.1)


class AnalysisTests(unittest.TestCase):
    def run_recipe(self, text):
        return n.analyze_recipe(DB, n.parse_recipes(text)[0])

    def test_butter_energy(self):
        a = self.run_recipe("servings: 1\n100 g unsalted butter\n")
        self.assertAlmostEqual(a.per["kcal"], 717, delta=2)

    def test_salt_percent(self):
        a = self.run_recipe("servings: 1\ntype: soup\n990 g water\n10 g salt\n")
        pct = a.totals["sodium"] / 1000 * n.NA_TO_SALT / a.weight * 100
        self.assertAlmostEqual(pct, 0.985, delta=0.02)
        self.assertTrue(any("soup target" in c and "OK" in c for c in n.checks(a)))
        b = self.run_recipe("servings: 1\ntype: soup\n985 g water\n15 g salt\n")
        self.assertTrue(any("HIGH" in c for c in n.checks(b)))

    def test_consumed_fraction(self):
        a = self.run_recipe("servings: 1\n500 g potatoes\n1000 g canola oil @6%\n")
        self.assertAlmostEqual(a.totals["fat"], 60, delta=1)

    def test_added_sugar_flag(self):
        a = self.run_recipe("servings: 1\n50 g sugar\n200 g milk\n")
        self.assertAlmostEqual(a.totals["added_sugar"], 50, delta=0.5)  # lactose is not added sugar
        b = self.run_recipe("servings: 1\n100 g ketchup\n")
        self.assertAlmostEqual(b.totals["added_sugar"], 0.75 * b.totals["sugar"], delta=0.1)

    def test_allergens(self):
        a = self.run_recipe("servings: 2\n200 g pasta\n50 g parmesan\n2 large eggs\n1 tbsp soy sauce\n20 g pine nuts\n")
        for allergen in ("milk", "egg", "wheat/gluten", "soy", "tree nuts"):
            self.assertIn(allergen, a.allergens)
        b = self.run_recipe("servings: 2\n600 g chicken thighs\n200 g rice\n")
        self.assertEqual(b.allergens, [])

    def test_hidden_allergens(self):
        a = self.run_recipe("servings: 2\n2 tbsp hoisin sauce\n2 tbsp gochujang\n")
        self.assertIn("soy", a.allergens)
        self.assertIn("wheat/gluten", a.allergens)
        self.assertIn("sesame", a.likely_allergens)

    def test_fda_rounding(self):
        self.assertEqual(n.fda_round("kcal", 47), 45)
        self.assertEqual(n.fda_round("kcal", 643), 640)
        self.assertEqual(n.fda_round("fat", 3.3), "3.5")
        self.assertEqual(n.fda_round("sodium", 1214), "1,210")
        self.assertEqual(n.fda_round("protein", 0.7), "<1")

    def test_cli_label(self):
        buf = io.StringIO()
        path = os.path.join(ROOT, "tests", "fixtures", "tinga.txt")
        with redirect_stdout(buf):
            n.main(["analyze", path])
        out = buf.getvalue()
        self.assertIn("NUTRITION FACTS", out)
        flagged = [l for l in out.split("```")[0].splitlines() if "!!" in l]
        self.assertEqual(len(flagged), 1)  # only "salt to taste"
        self.assertIn("no quantity", flagged[0])

    def test_targets(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            n.main(["targets", "--sex", "m", "--age", "30", "--height", "180cm", "--weight", "80kg",
                    "--activity", "moderate", "--goal", "maintain"])
        bmr = 10 * 80 + 6.25 * 180 - 5 * 30 + 5
        self.assertIn("BMR %d" % bmr, buf.getvalue())


class CookingTests(unittest.TestCase):
    def run_recipe(self, text):
        return n.analyze_recipe(DB, n.parse_recipes(text)[0])

    def test_parse_tag(self):
        self.assertEqual(cooking.parse_tag("450 g ground beef ~brown+drain")[:3], ("brown", None, True))
        self.assertEqual(cooking.parse_tag("1 cup wine ~simmer:45")[:3], ("simmer", 45, False))
        self.assertEqual(cooking.parse_tag("2 tbsp oil")[0], None)
        ln = n.parse_line("2 cups broccoli florets ~steam")
        self.assertEqual((ln.method, ln.name), ("steam", "broccoli florets"))

    def test_classes_and_codes(self):
        f = DB.food(DB.search("broccoli", 1)[0][1])
        self.assertEqual(cooking.cook_class(f.cat, f.desc), "veg")
        self.assertEqual(cooking.retention_code("veg", "boil"), "3775")
        self.assertEqual(cooking.retention_code("beef_ground", "brown", drain=True), "0751")
        self.assertEqual(cooking.retention_code("alcohol", "simmer", 60), "5006")
        self.assertEqual(cooking.retention_code("alcohol", "flame"), "5003")

    def test_boiling_loses_vitamin_c(self):
        raw = self.run_recipe("servings: 1\n100 g broccoli\n")
        boiled = self.run_recipe("servings: 1\n100 g broccoli ~boil\n")
        factor = cooking.CookingData().retention["3775"][1]["vitc"]
        self.assertLess(factor, 1)
        self.assertAlmostEqual(boiled.totals["vitc"], raw.totals["vitc"] * factor, delta=0.01)
        self.assertAlmostEqual(boiled.totals["kcal"], raw.totals["kcal"], delta=0.01)  # energy kept

    def test_draining_fat(self):
        raw = self.run_recipe("servings: 1\n450 g ground beef\n")
        drained = self.run_recipe("servings: 1\n450 g ground beef ~brown+drain\n")
        kept = drained.totals["fat"] / raw.totals["fat"]
        self.assertTrue(0.5 < kept < 0.85, kept)
        self.assertAlmostEqual(raw.totals["kcal"] - drained.totals["kcal"], 9 * (raw.totals["fat"] - drained.totals["fat"]),
                               delta=1)
        self.assertAlmostEqual(drained.totals["protein"], raw.totals["protein"], delta=0.01)

    def test_alcohol_cooks_off(self):
        a = self.run_recipe("servings: 1\n240 g dry red wine ~braise:150\n")
        b = self.run_recipe("servings: 1\n240 g dry red wine\n")
        self.assertAlmostEqual(a.totals["alcohol"], 0.05 * b.totals["alcohol"], delta=0.05)
        self.assertLess(a.totals["kcal"], b.totals["kcal"])

    def test_cooked_weight(self):
        a = self.run_recipe("servings: 1\n1000 g chicken thighs ~roast\n")
        self.assertEqual(a.weight_basis, "est. cooked")
        self.assertTrue(600 < a.weight < 850, a.weight)
        b = self.run_recipe("servings: 1\nyield: 900 g\n1000 g chicken thighs ~roast\n")
        self.assertEqual(b.weight, 900)

    def test_imputed_values_flagged(self):
        fid = DB.search("cotija", 1)[0][1]
        food = DB.food(fid)
        self.assertTrue(food.imputed)
        for key in food.imputed:
            self.assertIn(key, food.values)
        plant = DB.food(DB.search("ground cumin", 1)[0][1])
        self.assertEqual(plant.values.get("b12"), 0)


class SkillPackageTests(unittest.TestCase):
    def test_frontmatter(self):
        for path in glob.glob(os.path.join(ROOT, "skills", "*", "SKILL.md")):
            with open(path, encoding="utf-8") as f:
                text = f.read()
            m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
            self.assertTrue(m, path)
            fm = m.group(1)
            name = re.search(r"^name: (.+)$", fm, re.M).group(1).strip()
            self.assertEqual(name, os.path.basename(os.path.dirname(path)))
            self.assertRegex(name, r"^[a-z0-9]+(-[a-z0-9]+)*$")
            desc = re.search(r"^description: (.+?)(?=^\w[\w-]*:|\Z)", fm, re.M | re.S).group(1)
            self.assertLessEqual(len(" ".join(desc.split())), 1024, path)
            self.assertLess(len(text.splitlines()), 500, path)

    def test_manifests(self):
        with open(os.path.join(ROOT, ".claude-plugin", "plugin.json")) as f:
            plugin = json.load(f)
        with open(os.path.join(ROOT, ".claude-plugin", "marketplace.json")) as f:
            market = json.load(f)
        self.assertEqual(plugin["name"], market["plugins"][0]["name"])
        self.assertEqual(plugin["version"], market["plugins"][0]["version"])


if __name__ == "__main__":
    unittest.main()
