# Data sources

| File | Contents | Source |
|---|---|---|
| `foods.tsv` | 6,781 foods, 42 nutrients per 100 g edible portion | USDA FoodData Central, SR Legacy (April 2018 release), CSV download |
| `portions.tsv` | 12,771 household measures with gram weights (cup, tbsp, medium, clove...) | same release, `food_portion.csv` |
| `extras.tsv` | Staples SR Legacy lacks (gochujang, mirin, MSG, nutritional yeast, oat milk...) | USDA FoodData Central Branded and Foundation records; the `fdc_id` column is the FDC record |
| `retention.tsv` | % of 17 minerals and vitamins and alcohol kept, for 270 food-group and cooking-method combinations | USDA Table of Nutrient Retention Factors, Release 6 (2007), `retn06.txt`; two cells the text file omits are taken from the published `retn06.pdf` table |
| `yields.tsv` | Cooking weight change and fat kept per food class and method | Derived from USDA SR Legacy raw/cooked pairs (protein mass or dry matter conserved); only classes with 4+ pairs |
| `aliases.tsv` | ~650 everyday ingredient names mapped to a USDA record, with unit weights where USDA has none and edible fractions for bone-in cuts | hand-curated for this project |

USDA FoodData Central data is public domain under CC0 1.0. Citation: U.S. Department of Agriculture, Agricultural Research Service. FoodData Central, 2019. fdc.nal.usda.gov.

Gaps: when USDA has no value for a nutrient, `foods.tsv` fills it from the median of the three most similar foods in the same USDA category (animal-only nutrients such as B12 and vitamin D are set to zero for plants). The `imputed` column lists every filled nutrient, and labels report how much of a recipe relied on filled values.

Excluded SR Legacy categories: baby foods, fast foods, restaurant foods, meals and entrées, American Indian/Alaska Native foods, branded and QC records. Values are rounded to 3 significant figures; blank cells mean USDA has no analyzed value.

Rebuild everything with `python3 tools/build_data.py <unzipped SR Legacy CSV folder> --retention retn06.txt`. To correct or add an alias, edit `aliases.tsv` (tab-separated: alias, fdc_id, options, description) and run the tests.
