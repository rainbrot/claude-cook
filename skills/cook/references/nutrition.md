# Nutritionist mode

Food-first nutrition that people will actually stick to because it tastes good. Sections: Principles · Energy · Protein · Carbohydrate and fiber · Fat · Limits · Micronutrients · Bioavailability and cooking · Satiety and weight · Blood sugar · Goal playbooks · Safety boundaries · How the label is computed.

## Principles

- **Adherence is the outcome that matters**, and people stick with food they enjoy. Hit targets with the near-zero-calorie flavor levers (`flavor.md`): salt to target, acid, umami, aroma, browning, heat, texture, temperature. Put small amounts of fat and sugar where they are tasted first (a finishing drizzle, a crisp topping, a glaze) rather than dissolved through the dish.
- Add before you subtract: more vegetables, legumes, protein and fiber usually beats removing things.
- No moralizing and no "clean" or "guilt-free" language. Respect cultural foods; adapt them rather than replacing them.
- Numbers serve the person. Lead with the food, then show how it meets their targets.

## Energy

- `nutrition.py targets` uses Mifflin-St Jeor: men 10 × kg + 6.25 × cm − 5 × age + 5; women the same with − 161. Multiply by activity: 1.2 sedentary, 1.375 light, 1.55 moderate, 1.725 very active, 1.9 athlete.
- Fat loss: about 15-25% below maintenance (roughly 0.5-1% of body weight per week). Floors of about 1,200 kcal (women) and 1,500 kcal (men) without medical supervision.
- Muscle gain: about 5-10% above maintenance with resistance training.
- These are estimates with ±10% error; adjust from real-world trend over 2-3 weeks.

## Protein

- RDA 0.8 g/kg is a minimum. Active adults, people losing weight and adults over 65: 1.2-1.6 g/kg. Muscle gain or aggressive fat loss: 1.6-2.2 g/kg. For BMI 30 and over, base it on a reference weight (the engine uses BMI 25 at their height).
- Per meal: about 0.3-0.4 g/kg (25-40 g for most adults), with about 2.5-3 g leucine to maximize muscle protein synthesis. Spread across 3-4 meals rather than one big dinner.
- Quality: animal proteins and soy are complete and leucine-rich. Plant proteins are lower in leucine and lysine (grains) or methionine (legumes); combine legumes and grains across the day and eat about 10-20% more total protein on a fully plant-based diet.
- Protein-dense, cheap and versatile: eggs, Greek yogurt, cottage cheese, chicken thighs and breasts, canned tuna and salmon, sardines, lentils, chickpeas, tofu, tempeh, edamame, lean ground meats, whey or soy powder.
- Raising protein without changing a dish's character: Greek yogurt in sauces and dressings, cottage cheese blended into pasta sauces and eggs, lentils or beans folded into meat sauces, an extra egg white in scrambles, edamame in grain bowls.

## Carbohydrate and fiber

- AMDR 45-65% of calories, but the range is wide; carbohydrate should scale with activity.
- Fiber: 14 g per 1,000 kcal (about 25 g women, 38 g men under 51). Most people eat about half that. Best sources: beans and lentils (7-8 g per half cup cooked), raspberries and blackberries, chia and flax, oats, barley, whole-grain bread and pasta, pears and apples with skin, artichokes, broccoli, Brussels sprouts, avocado.
- Swap half, not all: 50/50 white and whole-wheat pasta, white and brown rice, or white rice with lentils keeps texture people like.
- Resistant starch increases when cooked starches (rice, potatoes, pasta) are cooled and reheated; it modestly blunts the glucose response.

## Fat

- AMDR 20-35% of calories. Prefer unsaturated: olive oil, canola, nuts, seeds, avocado, fatty fish.
- Saturated fat under 10% of calories; replace it with unsaturated fat rather than with refined starch and sugar.
- Omega-3: two servings of fatty fish a week (salmon, sardines, mackerel, trout, herring), about 250-500 mg EPA + DHA a day. Plant ALA (flax, chia, walnuts, canola) converts poorly to EPA and DHA; the AI for ALA is 1.1 g (women) and 1.6 g (men).
- Avoid artificial trans fat (largely gone from the US food supply).

## Limits

- Sodium under 2,300 mg a day (FDA DV); 1,500 mg is the AHA ideal for many people with hypertension. Most sodium comes from processed and restaurant food, not the salt shaker.
- Added sugar under 10% of calories (under 50 g on 2,000 kcal). The AHA suggests 25 g (women) and 36 g (men).
- Alcohol: none is healthiest; if drinking, no more than 1 drink a day (women) or 2 (men).

## Micronutrients

Common shortfalls and the best food sources. Adult DRIs; `targets` gives the exact numbers by age and sex.

| Nutrient | Who falls short | Best sources |
|---|---|---|
| Vitamin D (15-20 mcg) | most people | fatty fish, UV-exposed mushrooms, fortified milk and plant milks, egg yolks; supplements are often needed |
| Calcium (1,000-1,200 mg) | dairy-free eaters, older women | dairy, calcium-set tofu, sardines and canned salmon with bones, fortified plant milks, kale, bok choy, broccoli, almonds (spinach calcium is poorly absorbed) |
| Iron (8 mg men, 18 mg women 19-50, 27 mg in pregnancy) | menstruating women, vegetarians, endurance athletes | red meat, dark poultry, clams and mussels, lentils, beans, tofu, pumpkin seeds, fortified cereals, spinach |
| Potassium (2,600 mg women, 3,400 mg men) | almost everyone | beans, potatoes, sweet potatoes, tomatoes, leafy greens, bananas, yogurt, salmon, avocado |
| Magnesium (310-420 mg) | many | pumpkin seeds, almonds, cashews, spinach, black beans, whole grains, dark chocolate |
| Fiber | almost everyone | see above |
| Vitamin B12 (2.4 mcg) | vegans, adults over 50, metformin users | animal foods, fortified nutritional yeast and plant milks; vegans need a supplement |
| Folate (400 mcg DFE, 600 in pregnancy) | people planning pregnancy | leafy greens, legumes, asparagus, avocado, fortified grains; folic acid supplement before and during pregnancy |
| Iodine (150 mcg) | people avoiding dairy, seafood and iodized salt (sea salt and kosher salt are usually not iodized) | iodized salt, dairy, seafood, eggs, seaweed |
| Choline (425-550 mg) | most people | eggs (about 150 mg each), liver, beef, chicken, fish, soy |
| Zinc (8-11 mg) | vegetarians | oysters, beef, crab, pumpkin seeds, chickpeas, cashews |
| Vitamin A (700-900 mcg RAE) | low vegetable eaters | sweet potato, carrots, spinach, kale, butternut squash (eat with fat) |
| Omega-3 | low fish eaters | see Fat |
| Selenium (55 mcg) | rare | 1-2 Brazil nuts a day is plenty; more risks excess |

## Bioavailability and cooking

- **Vitamin C with plant iron**: lemon on lentils, peppers with beans, tomatoes with spinach. It can multiply non-heme iron absorption several-fold.
- **Tea, coffee and calcium supplements reduce iron absorption**: have them an hour apart from iron-rich meals.
- **Fat with fat-soluble nutrients**: carotenoids and vitamins A, D, E and K need fat. Olive oil on salads, carrots cooked in oil; lycopene from cooked tomato with oil is far more available than from raw.
- **Phytates** in grains and legumes bind iron and zinc. Soaking, sprouting, fermenting (sourdough) and cooking reduce them.
- **Brassicas** (broccoli, cabbage, kale): chop and wait 30-40 minutes before cooking, or add raw mustard powder, radish or arugula afterward, to form sulforaphane.
- **Garlic**: crush and rest 10 minutes before heating to form allicin.
- **Water-soluble vitamins** (C, folate, B vitamins) leach into cooking water: steam, microwave, roast, or keep the liquid (soups, braises). Eat some raw produce daily for vitamin C and folate.
- **Turmeric**: black pepper (piperine) and fat greatly increase curcumin absorption.
- Frozen vegetables are picked ripe and blanched; they are often as nutritious as fresh.

## Satiety and weight

- Protein and fiber are the most satiating nutrients. Aim for 25-40 g protein and 8-10 g fiber per main meal.
- **Energy density** (kcal per gram) drives how much people eat. Under 0.6 is very low, 0.6-1.5 low, 1.5-4 medium, over 4 high. Add water-rich vegetables, broth and fruit to lower it; the engine reports it.
- In a controlled trial (Hall et al., 2019), people ate about 500 kcal a day more on an ultra-processed diet than on a minimally processed one matched for available nutrients. Home cooking from whole ingredients is the lever.
- Hyper-palatable combinations (fat + sodium, fat + sugar, carbohydrate + sodium; see `flavor.md`) drive overeating. Plan them as deliberate treats rather than eliminating them.
- Eating speed matters: chewy, crunchy, and hot foods slow people down.
- Liquid calories (juice, sweetened drinks, alcohol) barely register as fullness.

## Blood sugar

For diabetes, prediabetes, or steadier energy:
- **Plate method**: half non-starchy vegetables, a quarter protein, a quarter starch.
- Pair carbohydrate with protein, fat and fiber. Eat vegetables and protein before starch in the meal.
- Vinegar or lemon with a meal modestly lowers the glucose rise.
- Prefer intact whole grains, legumes, and cooled-then-reheated starches; keep portions of rice, pasta and bread moderate rather than eliminating them.
- People on insulin or sulfonylureas must not change carbohydrate intake sharply without their clinician (hypoglycemia risk).

## Goal playbooks

| Goal | Design rules |
|---|---|
| Fat loss | target deficit; 1.6-2.2 g/kg protein; fiber 30 g+; energy density under 1.5 for mains; big vegetable volume; flavor levers maxed; one planned treat |
| Muscle gain | small surplus; 1.6-2.2 g/kg protein over 4 meals with 25-40 g each; carbs around training; calorie-dense additions (olive oil, nuts, whole milk, rice) |
| Heart health (DASH, Mediterranean) | sodium under 2,300 (1,500 ideal); potassium-rich produce and beans; olive oil as main fat; fish twice weekly; nuts daily; whole grains; limit processed meat |
| Blood sugar | see above |
| Plant-based | B12 supplement; iron with vitamin C; zinc from seeds and legumes; iodized salt; omega-3 from flax, chia, walnuts or algae oil; calcium-set tofu and fortified milks; legumes daily |
| Pregnancy | about +340 kcal in the second and +450 in the third trimester; folate, iron, choline, iodine, DHA; strict food safety (`science.md`) |
| Older adults | 1.2 g/kg protein or more, spread out; vitamin D, calcium, B12; soft but flavorful textures; strong seasoning (taste declines with age) |
| Endurance athletes | carbohydrate 5-10 g/kg by training load; sodium in long sessions; iron |
| Kids | familiar plus repeated exposure; no forced clean plates; iron and calcium; whole milk under 2 |
| Kidney disease | protein, potassium, phosphorus and sodium limits are individual: defer to their renal dietitian; no potassium salt substitutes |

## Safety boundaries

- You are not a substitute for a registered dietitian or physician. Suggest one for: eating disorders, kidney or liver disease, pregnancy complications, type 1 diabetes dosing, children with growth concerns, extreme restriction, rapid unexplained weight change.
- Eating disorder signals (fear of foods, compensating behaviors, very low targets, distress about numbers): don't provide calorie counts or deficits; focus on regular, adequate, enjoyable meals and gently suggest professional support.
- Supplements: mention only well-established cases (B12 for vegans, vitamin D when intake or sun is low, folic acid before and during pregnancy, iron when deficient under medical guidance). Don't prescribe doses beyond standard labels.
- Don't promise disease outcomes from specific foods.

## How the label is computed

The engine follows USDA's own recipe-calculation method:
1. Ingredient weights × USDA FoodData Central values per 100 g (SR Legacy; Foundation and Branded records online).
2. Cooking: each `~method` tag selects a USDA Nutrient Retention Factor profile (Release 6) for the food's group, so boiled broccoli loses the vitamin C USDA measured it losing and simmered wine keeps only the alcohol USDA measured. Yields (weight change) come from USDA raw/cooked pairs; `+drain` removes the share of fat USDA pairs show rendering out.
3. Missing USDA values are filled from the closest related USDA foods (animal-only nutrients are zero in plants), and the label notes which nutrients were filled and for what share of the recipe.
4. Added sugars follow the FDA definition: sugars from sweeteners, syrups, honey and the sweetened part of prepared ingredients, not the lactose or fruit sugar an ingredient carries.
5. FDA rounding rules and 2016 Daily Values for the label.

Use `@` for frying oil, marinades and brines (only part is eaten), `yield:` when liquid reduces a lot, and `=online` or `{...}` label values when the person names a specific brand.
