# Staying compatible as eVaka changes

New eVaka versions are deployed to test environments daily. Changes to the test fixtures are
rare and small, but they do happen: a field gets added, renamed or removed, an enum value is
added, or a new row type appears. This skill doesn't hard-code shapes. It reads them from the
deployed commit, so most changes need no action. When something does break, do this:

1. **Know what runs:** `appCommit` (C) from `get_environment_info`. The scripts fetch its
   backend source into a sparse depth-1 cache: `R=$(python3 -B scripts/evaka_source.py C)`.
2. **Re-read the shapes** of the failing type at that commit:
   `python3 -B scripts/row_types.py --commit C <type> --depth 2` (add `--full` for the Kotlin
   source) and re-run `--check` on your payload. That usually shows the fix directly (a new
   required field, a renamed field).
3. **See what changed** if the reason is still unclear. Compare with the commit your example,
   script or memory was based on (examples state theirs in the header). The cache has no
   history, but diffing two fetched commits works:
   ```
   git -C $R fetch -q --depth 1 --filter=blob:none origin <old-full-sha>
   git -C $R diff --stat <old> C -- service/src/main/kotlin/evaka/core/shared/dev/ \
       service/src/main/kotlin/evaka/core/mcp/
   git -C $R diff <old> C -- service/src/main/kotlin/evaka/core/shared/dev/DevApi.kt
   ```
   Look at the class of the failing row type, its `Database.Transaction.insert(...)` function
   (the SQL shows which fields are actually stored), and at `docs/db/schema.sql` for new NOT
   NULL columns and constraints. For commit messages and migrations, browse
   `https://github.com/espoon-voltti/evaka/commits/<C>` or use a full clone if one exists.
4. **Constraint names** in errors: `grep -n -B2 -A2 "<constraint>" $R/docs/db/schema.sql`.
5. **MCP tool behaviour** (allowed row types, safety checks, workflow steps, error texts):
   read `service/src/main/kotlin/evaka/core/mcp/` at the commit. `McpToolsRows.kt` maps row
   types to classes. `McpToolsApplications.kt` has `advance_application` and `send_message`.
6. Adapt the generator, validate with the rollback sentinel, insert.
7. If a script of this skill broke (e.g. the Kotlin file layout moved), patch it minimally,
   finish the task, and tell the user what you changed so it can be committed to the skill
   repository. If a statement in `pitfalls.md` turned out wrong, say so too.

The environment may lag behind or run ahead of the repo's main branch. Always use
`appCommit`, never a branch head, when reading shapes for a specific environment.
