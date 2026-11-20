# Contributing to Claude Cook

Thanks for helping Claude cook better. The most useful contributions, in order:

1. **Recipe reports.** Cook something it gave you and tell us what happened: a time that was off, a sauce that broke, a cup weight that was wrong. Use the *Recipe report* issue template. Real-kitchen feedback is how the skill improves.
2. **Ingredient fixes.** If `nutrition.py analyze` matched an ingredient to the wrong USDA food, add or fix a line in `skills/cook/data/aliases.tsv` (tab-separated: name, FDC id, unit weights like `tbsp=19;each=50`, description). Find ids with `python3 skills/cook/scripts/nutrition.py search "<name>"`.
3. **Culinary knowledge.** Regional cuisine grammars, substitutions and technique notes in `skills/cook/references/`. Keep them dense and specific: numbers, temperatures and mechanisms, not general advice Claude already knows. Cite a source for anything quantitative.
4. **Engine features** in `skills/cook/scripts/` (standard library only, Python 3.8+).

## Ground rules

- Run `python3 -m unittest discover tests` before opening a PR.
- Keep `skills/cook/SKILL.md` lean: it loads every time the skill fires. Detail belongs in `references/`.
- Don't keyword-stuff skill descriptions; they decide when Claude uses the skill and must stay accurate.
- Nutrition data must come from USDA FoodData Central or a cited label. To regenerate the tables, see `skills/cook/data/SOURCE.md`.

## Measuring a change

The `evals/` folder holds graded test cases. With Claude Code you can compare the skill against a no-skill baseline (real, billed runs):

```bash
claude plugin eval . --allow-tools Write,Bash
```
