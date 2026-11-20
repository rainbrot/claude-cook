---
name: meal-plan
description: "Multi-day meal plan with prep schedule, grocery list and nutrition totals."
argument-hint: "[days, people, goals, budget]"
disable-model-invocation: true
---

Load the **cook** skill (listed as `cook` or `cook:cook`) and handle this request in **Meal plan** mode:

$ARGUMENTS

Follow the meal-plan workflow: intake defaults, component-based plan, prep game plan, `day` verification against targets, `shop` grocery list.

If the request above is empty, ask in one line for days, people, goals and any dietary needs, and offer to assume a 5-dinner weeknight plan for 2.

If the cook skill can't be loaded, read `../cook/SKILL.md` relative to this skill's directory and follow it; its relative paths start from that folder.
