# Edits Log — APPEND ONLY

This file is the permanent, immutable history of every change made in this project. Read it whenever you need full context on how the project got to its current state.

## Rules

1. **Never delete, overwrite, edit, or reformat existing entries.** Past entries are immutable. If you change your mind or revert something, add a NEW entry that references the old one — don't touch the original.
2. **Append-only.** New entries go at the bottom.
3. **Log every meaningful action**, including: file create/modify/delete, commands that change state, architectural decisions, dependencies added, bugs found, bugs fixed, refactors, dead-ends you backed out of. When in doubt, log it.
4. **Do not log:** trivial reads, navigation, file inspection, or your own thinking. Only log changes and decisions.

## Entry format (use exactly this)

---
## [YYYY-MM-DD HH:MM TZ] — <short title>
**What:** <1–2 sentences on what was done>
**Why:** <the user request or reason that triggered it>
**Files touched:** <path — created | modified | deleted>
**Commands run:** <shell commands, if any>
**Outcome:** <result, including errors, partial success, or surprises>
**Notes:** <gotchas, half-finished work, things future-you should know>
---

## On reverts and mistakes

If you undo something, write a new entry titled "Revert: <original title>" and reference the original timestamp. The original entry stays. The log tells the truth about what happened, including wrong turns.

## On compaction

If this file gets long, do not summarize or prune it yourself. Ask the user before doing anything destructive.

---

# Log

<!-- New entries below this line. Oldest at top, newest at bottom. -->
