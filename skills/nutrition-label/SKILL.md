---
name: nutrition-label
description: "USDA nutrition label (macros, micros, %DV, allergens) for any recipe."
argument-hint: "[recipe text or file path]"
disable-model-invocation: true
---

Load the **cook** skill (listed as `cook` or `cook:cook`) and handle this request in **Label** mode:

$ARGUMENTS

Convert the recipe faithfully into the engine's format (don't change quantities), run `analyze`, fix any wrong matches, and report the label plus every assumption you made. If they gave a file path or URL, read it first.

If the request above is empty, ask them to paste the recipe with servings.

If the cook skill can't be loaded, read `../cook/SKILL.md` relative to this skill's directory and follow it; its relative paths start from that folder.
