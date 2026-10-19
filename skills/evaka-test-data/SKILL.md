---
name: evaka-test-data
description: Creates realistic test data of any shape in eVaka test environments (e.g. Espoo staging) through the eVaka MCP server - units, groups, staff and their attendance, families, applications and their decision workflow, placements, reservations, absences, attendance, VASU/LEOPS and other child documents, preschool absence applications, assistance, finance (fees, invoices, incomes), messages and calendar events. Use whenever someone asks to create, seed, populate, extend or clean up eVaka test/demo data or test data batches, in Finnish or English (e.g. "luo testidata stagingiin", "lisää päiväkotiin lapsia ja läsnäoloja").
compatibility: Needs the eVaka MCP server connected (https://<environment>/api/mcp), python3 (3.9+), git, curl and network access to github.com. Works with any agent that supports Agent Skills and MCP (Claude Code, Codex, GitHub Copilot, ...).
metadata:
  version: "1.1"
---

# eVaka test data

The eVaka MCP server (tools `get_environment_info`, `search_units`, `search_persons`,
`search_employees`, `insert_rows`, `create_upload_url`, `advance_application`, `send_message`,
`list_test_data`, `delete_test_data`) inserts rows with eVaka's Kotlin test fixture classes and
runs some real business workflows.

Core idea: **never guess row shapes**. The server deserializes each row into a Kotlin class at
the deployed commit. `scripts/row_types.py` reads those classes from that exact commit, so the
skill keeps working when eVaka changes.

Paths are relative to this skill's directory. Run Python with `python3 -B` (no `__pycache__`).

## Be fast and frugal

- **Source code:** the scripts fetch the needed backend files of `appCommit` themselves (sparse,
  depth 1, ~3 s, cached in `~/.cache/evaka-src`). Do NOT clone eVaka yourself. A full clone is
  slow, and a `--filter=blob:none` clone makes `git grep` download files one by one (minutes).
- **Common scenarios** (a unit with groups, staff, families, placements, reservations, absences,
  attendance, staff shifts): use `scripts/scenario.py` and copy `examples/quick_unit.py`. That
  keeps your script around 30-60 lines. Use `scripts/evaka_testdata.py` (`Rows`) directly only
  for row types the scenario helpers don't cover.
- **Read only what you need.** SKILL.md and `references/pitfalls.md` are always relevant. Read
  `domain-model.md` / `realism.md` only for unfamiliar entity types. Don't read
  `examples/full_unit_scenario.py` (52 kB) whole: grep it for realistic content (VASU texts,
  absence applications, calendar events).
- Look up shapes only for the row types you write by hand. The compact output is one line per
  field.
- Don't install or commit this skill into the project repository unless the user asks.

## Workflow

1. **Environment.** `get_environment_info` gives `today`, `appCommit` (C below), care areas and
   service need options (ids are environment specific). Get the local time: `TZ=Europe/Helsinki date`.
2. **Plan** from the request and fill gaps with realistic defaults instead of asking. Ask only
   about things that are both unclear and costly to redo (which environment, whether to use an
   existing unit). Choose one batch name (kebab-case). Look up existing entities you build on
   with `search_*`.
3. **Shapes** (only for hand-written rows):
   `python3 -B scripts/row_types.py --commit C` lists the row types and value formats.
   `python3 -B scripts/row_types.py --commit C absence_application child_document` shows fields:
   `[required]`, `= default`, and `(!)` for hard-coded test dates you must set. `--class X`
   describes any class or enum, including polymorphic ones (`type` discriminator).
4. **Generator script** in a scratch directory, with a fixed seed. Parents go before children
   (groups are inserted in order). Give explicit ids to rows that others reference.
5. **Check:** `python3 -B scripts/row_types.py --commit C --check payload.json`. It catches
   unknown/misspelled fields (the server SILENTLY IGNORES them), missing required fields, 2019
   test defaults and wrong polymorphic types. `Rows.write()` also prints lint findings
   (overlaps, time formats, known constraints). Fix everything.
6. **Validate on the server without saving:** write with `rollback=True` (appends a group of
   the unknown type `__rollback__`, so the transaction fails at the very end). Success is exactly
   `Unknown row type '__rollback__' in group N`. Any other error names the group, row and cause.
   Small payloads go directly via `insert_rows`. Big ones: `create_upload_url`, then
   `curl -sS -X POST -H 'Content-Type: application/json' --data-binary @file <url> | cut -c1-300`.
   Each URL works once, for 10 minutes.
7. **Insert for real**: the same payload without the sentinel, with a new upload URL. On a
   timeout, check `list_test_data` before retrying.
8. **Workflows** that need business logic come after the rows exist: `advance_application`,
   `send_message` (see pitfalls.md). Rows that depend on system-created entities (e.g. a group
   placement for a placement created by accepting a decision) go in a follow-up `insert_rows`
   to the same batch. Get their ids with `search_persons`.
9. **Verify** with one `search_units` / `search_persons` spot check.
10. **Report** briefly: batch name, what was created (counts and the story), employee UI links
    (`<employeeFrontendUrl>/units/<unitId>`, `/child-information/<childId>`,
    `/applications/<id>`), anything global you created, and how to delete
    (`delete_test_data`, `dryRun` first).

## When the server returns an error

- **Constraint/overlap/FK errors:** find the constraint with
  `grep -n "<name>" $(python3 -B scripts/evaka_source.py C)/docs/db/schema.sql`. Fix the data
  and re-validate.
- **Deserialization errors** (`Cannot deserialize`, missing parameter, unknown enum value) or
  an **unknown row type**: eVaka changed. Re-run `row_types.py` for the type (it reads the
  deployed commit) and adapt. If that doesn't explain it, follow `references/compatibility.md`.
  If a helper in this skill breaks because eVaka changed, patch it minimally in place, finish
  the task, and tell the user what you changed so it can go into the skill repository.
- **Forbidden/Conflict from workflow tools** are deliberate safety rules (test-only entities,
  no ADMIN employees, no deciding real applications). See pitfalls.md.

## Safety rules

- Environments are shared: ONE batch per scenario. Don't reference other batches' rows
  (that blocks their deletion).
- Avoid global data (care areas, preschool/club terms, holiday periods, service need
  options, published document templates) unless the scenario needs it, and report it if you
  create any.
- Fake people only: `test_ssn()` (individual numbers 900-999), `@example.com` emails.
- `delete_test_data`: `dryRun` first. Use `allowUntrackedRows` only with the user's OK, unless
  the untracked rows clearly came from your own workflow calls.
