That's a good start, but there may be many more. Search for additional critical plan issues, as there may be more.

<user_intent>
{USER_INTENT}
</user_intent>

<file_later_work_command>
{FILE_LATER_WORK_COMMAND}
</file_later_work_command>

Use the same task input, current plan, critical issue standard, workspace, and report contract.
Treat `<user_intent>` as the current scope and constraint record. Use the transcript only as audit context. If they conflict, later entries in `<user_intent>` supersede earlier entries, and recorded user intent supersedes unsupported assistant interpretation.

Your priority is to realize the user's requests. Be creative, skeptical, and ambitious inside that boundary: rethink architecture, refactor, question assumptions, and identify materially better approaches when they help satisfy the request.

Current work is anything needed to realize the user vision well, including materially better plans, cleaner architecture, stronger tests, or refactors that make the requested outcome correct and durable. You should only be looking for that. If you happen to discover other todos, those are "Later work".

Plan-scope pruning is part of this review. If the current implementation plan contains work that is not strictly necessary to accomplish the user's current request, the current-work finding is that the plan should remove that work and file it as later work. File the future todo with `<file_later_work_command>`, but report only the plan removal needed to keep current work scoped to the request.

If you find later work, file it with the command in `<file_later_work_command>`, and then ignore it. Remember, your priority is work that is directly connected to realizing the user's requests. Do not include filed later work in `## Findings memo`, review output, blocker lists, plan edits, or implementation targets.

Your job is still issue discovery only. Do not edit files, do not commit, and do not propose a replacement plan.

Find as many new critical plan issues as you can in this turn. If you find one additional issue, assume there may be more and keep searching. A short report with only the next obvious issue is a failure if more important issues were discoverable.

Keep the findings/evidence memo simple and checkable:

## Issue 1
Finding: ...
Evidence:
- ...
- ...

If you find additional critical plan issues, return the same markdown sections in the same order with `## Plan verdict` set to `ISSUES`, listing only the additional issues from this pass in `## Findings memo`.

If you find no additional critical plan issues, return the report with `## Plan verdict` set to `READY`. Here, `READY` means only that you found no additional critical plan issues in this deepening pass; earlier findings still stand and will be sent to synthesis. In `## Findings memo`, write only `None`; do not include any `## Issue` entries.
