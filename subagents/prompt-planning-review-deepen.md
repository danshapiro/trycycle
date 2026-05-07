That's a good start, but there may be many more. Search for additional critical plan issues, as there may be more.

<user_intent>
{USER_INTENT}
</user_intent>

Use the same task input, current plan, critical issue standard, workspace, and report contract.
Treat `<user_intent>` as the current scope and constraint record. Use the transcript only as audit context. If they conflict, later entries in `<user_intent>` supersede earlier entries, and recorded user intent supersedes unsupported assistant interpretation.

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
