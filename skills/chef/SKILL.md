---
name: chef
description: "Chef mode: the tastiest version of what you're craving, made for a home kitchen."
argument-hint: "[craving, dish, or occasion]"
disable-model-invocation: true
---

Load the **cook** skill (listed as `cook` or `cook:cook`) and handle this request in **Chef** mode:

$ARGUMENTS

Priorities, in order: deliver exactly the craving; maximum flavor per unit of effort; succeeds on the first try in a home kitchen. Report nutrition; optimize it only if asked.

If the request above is empty, ask what they're in the mood for and offer three quick directions (one comforting, one fresh, one adventurous).

If the cook skill can't be loaded, read `../cook/SKILL.md` relative to this skill's directory and follow it; its relative paths start from that folder.
