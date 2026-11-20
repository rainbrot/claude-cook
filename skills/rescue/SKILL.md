---
name: rescue
description: "Fix a dish that's going wrong right now."
argument-hint: "[what went wrong]"
disable-model-invocation: true
---

Load the **cook** skill (listed as `cook` or `cook:cook`) and handle this request in **Rescue** mode:

$ARGUMENTS

They are mid-cook: the first line is the action to take now. Then one line of why, then how to prevent it next time. Keep it short.

If the request above is empty, ask what they're making and what went wrong.

If the cook skill can't be loaded, read `../cook/SKILL.md` relative to this skill's directory and follow it; its relative paths start from that folder.
