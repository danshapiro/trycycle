Good finds. Search for additional issues, as there may be more.

<user_intent>
{USER_INTENT}
</user_intent>

<file_later_work_command>
{FILE_LATER_WORK_COMMAND}
</file_later_work_command>

Use the same review target, severity standard, evidence requirements, and JSON schema from your current instructions. Return exactly one `<review_observations_json>...</review_observations_json>` block and no prose. Report only additional observations not already reported in this thread. If you find additional issues, set `status` to `"issues_found"` and include them in `observations`. If you find no additional issues, set `status` to `"no_issues"` with an empty `observations` array.
Use `<user_intent>` as the current scope boundary for intended behavior. Findings are blocking only when they are necessary to satisfy this user intent, the finalized plans, or regressions introduced by this work.

Your priority is to realize the user's vision as well as possible. Be creative, skeptical, and ambitious inside that boundary: rethink architecture, refactor, question assumptions, and identify materially better approaches when they help satisfy the request.

Current work is anything needed to realize the user vision well, including materially better plans, cleaner architecture, stronger tests, or refactors that make the requested outcome correct and durable.

Later work is valuable work you discover that is outside the current user vision. Later work may be severe, architectural, user-visible, or high-value. Filing it means "this deserves attention later," not "this is unimportant."

Output only current-work observations in `<review_observations_json>`. Do not include later work in this JSON, regardless of severity. File later work with `<file_later_work_command>` and then omit it from your response. If a finding lacks a clear causal chain to the current user vision, file it as later work instead.
