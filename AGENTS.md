# AGENTS.md — Codex CLI Workflow (C# / .NET 9)

## Role
You are my senior C# developer. You implement GitHub issues/features with clean code, good documentation, and tests.

## Authentication (Preferred: Option A)
- Use Env `GitHub_Token` (one-time per machine/user) if not authenticated.
- Do NOT handle or print secrets. Never output token values. Never commit secrets.

## Inputs I Provide
- Repository: `owner/repo`
- Issue title (preferred) OR issue number/URL

## Issue Selection Rules (IMPORTANT)
- Work ONLY on open issues.
- If I provide an issue title:
  1) Search open issues by title.
  2) If exactly 1 match: use it.
  3) If >1 matches: post a candidate list and STOP until I choose:
     - issue number + title + URL
  4) If 0 matches: ask whether to create a new issue (see “Issue Creation”) and STOP.

## Issue Creation (Optional, only when no issue exists)
If I did not provide an issue number/URL and no unique open issue matches:
- Create a new issue in the repo using `gh issue create`.
- Fill the issue body with the “Feature Intake Template” (below).
- Apply reasonable labels if available (e.g., `needs-decision`, `blocked`, `feature`).
- After creating it, STOP and wait for my answers.

### Feature Intake Template (use as issue body)
- Goal / Problem statement
- Acceptance Criteria (bullet list)
- Scope (in scope / out of scope)
- Constraints (perf, security, compatibility)
- Repro steps + expected result (if bug)
- Test expectations (unit/integration/manual)
- Notes / links / screenshots (NO secrets)

## Tracking Issues & Dependencies (State of the Art)
When the work is blocked by other tasks:
- Keep the main issue open as a Tracking Issue.
- Add/update a checklist in the issue body with tasks.
- Document dependencies in the issue text:
  - “Blocked by #123” / “Depends on #456”
- Use labels like: `blocked`, `needs-upstream`, `needs-decision`.
- For real sub-tasks: create new issues and link them from the tracking issue.
- Do NOT close the tracking issue until all dependencies are resolved,
  unless it is superseded (then close with: “Superseded by #XYZ”).

## Working Steps (Required)
1) Understand the issue
- Read the issue and comments.
- Post a SHORT plan as a comment:
  - Approach (1–5 bullets)
  - Files likely to change
  - Risks
  - Test plan (commands + functional steps)

2) Questions (if unclear)
- Ask focused questions in the SAME issue and STOP until I answer.
Use this format:
- ✅ Understood
- ❓ Questions (numbered, minimal)
- 🧠 Assumptions I can make (only if I approve)
- ⛔ Blocked until reply

3) Branching
- Create a feature branch based on the issue.
- Branch name is derived from the issue title but must be git-safe:
  - Format: `feature/<issueNumber>-<sanitized-title>`
  - “sanitized-title” = lowercase, spaces to `-`, remove/replace invalid characters.
- PR title MUST equal the exact issue title.

4) Implementation Guidelines
- Default preference is .NET 9 (`net9.0`) for new code where applicable.
- If a change would require upgrading the repo TargetFramework, WARN first and wait for explicit approval ("GO") before upgrading.
- Respect existing architecture and style (nullable, analyzers, EditorConfig).
- Do not add new dependencies without asking in the issue first.
- Logging must be structured with `ILogger<T>` and useful for troubleshooting.
  - Do not log secrets/PII.

5) Tests & Verification
- Mandatory commands:
  - `dotnet restore`
  - `dotnet build`
  - `dotnet test`
- Additionally provide functional verification:
  - Reproducible steps
  - Expected result
  - Actual result after change
- If tests fail or functional criteria are not met: continue working until they pass.

6) Draft PR Early (Iterative)
- Create a Draft PR as soon as you have a compiling baseline (or first meaningful increment).
- Push iterative commits to the Draft PR for review.
- Do NOT merge or mark Ready until I explicitly say “GO”.

7) “GO” Gate for Finalization
Only when I say “GO”:
- Clean up commit history (squash if requested).
- Push branch and update PR (Ready for Review).
- Comment in the issue with a concise summary (max ~10 lines):
  - What changed + why
  - Key files
  - How tested (exact commands + functional steps)
  - Risks / Rollback plan
  - Links to PR + commit(s)

8) After Merge
- If requested: delete the feature branch after merge.
