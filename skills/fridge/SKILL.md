---
name: fridge
description: "The best dish you can make from what's already in your kitchen."
argument-hint: "[ingredients on hand]"
disable-model-invocation: true
---

Load the **cook** skill (listed as `cook` or `cook:cook`) and handle this request in **Fridge** mode:

$ARGUMENTS

Lead with a recipe that needs nothing beyond what they listed plus salt, pepper and oil; then optional upgrades. Use the most perishable items first.

If the request above is empty, ask them to list what's in the fridge and pantry.

If the cook skill can't be loaded, read `../cook/SKILL.md` relative to this skill's directory and follow it; its relative paths start from that folder.
