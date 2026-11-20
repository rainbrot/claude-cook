# Meal planning

Plans people finish, not plans that rot in the fridge. Sections: Intake · Architecture · Components · Freshness and storage · Variety · Verify the nutrition · Output format · Budget.

## Intake

Use what they told you and default the rest (state defaults in one line):
- Who eats (how many, ages, appetites), which meals and days the plan covers (default: 5 weekday dinners, or breakfast-lunch-dinner for a "full" plan).
- Goal and targets: run `nutrition.py targets` when they give age, sex, height, weight and activity; otherwise use their stated goals or general guidelines.
- Time: a prep session (when, how long) and nightly cooking time. Default: one 2-hour session on Sunday plus 20 minutes on weeknights.
- Budget, equipment, likes, dislikes, allergies, cuisines they enjoy, tolerance for leftovers.

## Architecture

Choose one shape:
- **Prep-day plan**: cook components in one session and assemble quickly all week. Best for lunches and busy weeknights.
- **Cook-fresh plan**: short nightly recipes that share ingredients. Best for people who like cooking and dislike leftovers.
- **Hybrid** (default): a Sunday session that makes 2-3 components, plus 2-3 fast fresh dinners midweek to cover days 4-7 safely.

Plan rules:
- **Cross-use perishables.** Every fresh herb, half cabbage and bunch of greens appears in at least two meals. No ingredient bought for a single use unless it keeps (spices, condiments).
- **Leftovers that improve** (stews, curries, chili, braises, beans, soups, marinated proteins, grain salads with dressing on the side) go early in the week or in the freezer. **Leftovers that decline** (anything fried or crisp, dressed greens, avocado, reheated fish, pasta sitting in sauce) are cooked fresh or stored as separate components.
- **Cook once, eat twice**: plan intentional leftovers (roast chicken Monday → chicken salad wraps Wednesday; pot of beans → tacos, then soup).
- Respect real time: if weeknights are 20 minutes, every weeknight recipe fits 20 minutes including prep.

## Components

The flexible core of a good plan: make components, then remix them so each meal feels different.

| Component | Examples |
|---|---|
| Protein (1-2) | sheet-pan chicken thighs, seasoned ground turkey, baked tofu, a pot of beans or lentils, jammy eggs, slow-cooked pork shoulder |
| Grain or starch (1-2) | rice, quinoa, farro, roasted potatoes, soba, tortillas, good bread |
| Vegetables (2-3) | one roasted tray (broccoli, peppers, squash), one raw crunchy (cabbage slaw, cucumbers), one leafy |
| Sauces (2-3) | green herb sauce (chimichurri, salsa verde), creamy (tahini-lemon, yogurt-garlic, peanut-lime), punchy (chili crisp, salsa, gochujang-honey) |
| Pickles (1) | quick-pickled red onions, cucumber, carrots and daikon |
| Crunch (1) | toasted seeds or nuts, crispy chickpeas, fried shallots |

Remix formats: grain bowl, salad, wrap or taco, fried rice, noodle bowl, soup (add stock), stuffed sweet potato, frittata. Changing sauce + format makes the same components feel like different cuisines (tahini + bowl = Levantine; peanut-lime + noodles = Thai-ish; salsa + taco = Mexican).

## Freshness and storage

- Cooked food: 3-4 days in the fridge. For days 5-7, freeze portions on prep day or cook fresh.
- Cool quickly in shallow containers before refrigerating (within 2 hours).
- Store sauces, dressings, crunchy toppings and greens separately; combine at serving.
- Freeze well: soups, stews, chili, curries, cooked beans and grains, meatballs, burritos, marinated raw proteins, cookie dough. Freeze poorly: cream sauces (may split), cooked pasta in sauce (soft), raw salad vegetables, potatoes in soups (grainy), fried food.
- Reheat to 74°C (165°F). Rice: reheat until steaming throughout, only once.
- Label containers with contents and date.

## Variety

- Rotate protein, cuisine, color and texture across the week. Vary at least one of sauce, format or cuisine each day.
- Breakfasts can repeat; most people prefer routine in the morning. Dinners shouldn't repeat back-to-back.
- Include one "fun" meal (pizza night, tacos, burgers done well) so the plan feels like food, not a regimen.

## Verify the nutrition

`<skill-dir>` is the cook skill folder (the same path used in SKILL.md). Write each day as a file of `## Meal` sections under a `# Day N` header with `servings:` (how many the batch makes) and `eat:` (servings eaten that day), then run:

```bash
python3 <skill-dir>/scripts/nutrition.py targets --sex f --age 34 --height 168cm --weight 68kg --activity moderate --goal lose --out targets.json
python3 <skill-dir>/scripts/nutrition.py day plan.txt --targets targets.json
python3 <skill-dir>/scripts/nutrition.py shop plan.txt
```

Check per day: kcal within ±10% of target, protein at or above target and split across meals (25-40 g each), fiber at goal, sodium under the limit, and micronutrients the engine flags under 70%. Fix gaps with swaps rather than supplements: beans or lentils (fiber, potassium, folate, iron), sardines or salmon (vitamin D, omega-3, calcium with bones), yogurt or tofu (calcium), leafy greens (folate, vitamin K, magnesium), pumpkin seeds (magnesium, zinc, iron), sweet potato or carrots (vitamin A), citrus or peppers (vitamin C). The `shop` list sums every recipe as written: if a component is made once and eaten over several days, list it once.

## Output format

1. **The week at a glance**: a table, days × meals, each cell a dish name (short).
2. **Prep session**: a timed game plan (what goes in the oven first, what simmers while you chop), ending with storage instructions.
3. **Recipes**: components first, then each meal's assembly in 2-4 lines. Full recipe format only for dishes cooked from scratch on the day.
4. **Grocery list**: from `shop`, grouped by store section, with a pantry check line.
5. **Nutrition**: the per-day table from `day` (or a representative day and the weekly average for long plans) against targets, with any gaps and how the plan covers them.
6. **Notes**: what to freeze, what to cook fresh, and easy swaps.

## Budget

- Build around cheap proteins (eggs, beans, lentils, chicken thighs, canned fish, tofu, pork shoulder) and cheap produce (cabbage, carrots, onions, potatoes, bananas, frozen vegetables).
- One bunch of herbs, one bag of greens and one head of cabbage should each serve the whole week.
- Prices vary by place and season; don't quote prices unless asked, and then give rough ranges and say so.
