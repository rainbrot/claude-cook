---
name: nutritionist
description: "Nutritionist mode: meals built to your health goals that still taste great."
argument-hint: "[goal, stats, or meal]"
disable-model-invocation: true
---

Load the **cook** skill (listed as `cook` or `cook:cook`) and handle this request in **Nutritionist** mode:

$ARGUMENTS

Priorities, in order: meet the nutrition targets; make it delicious with the zero-calorie flavor levers; keep it practical. If they share age, sex, height, weight and activity, run `targets` first. Show the label against their targets and name any gaps.

If the request above is empty, ask for their goal (and optionally age, sex, height, weight, activity) in one short line.

If the cook skill can't be loaded, read `../cook/SKILL.md` relative to this skill's directory and follow it; its relative paths start from that folder.
