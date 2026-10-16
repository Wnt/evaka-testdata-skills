# eVaka test data skills

Agent Skills for creating realistic test data in eVaka test environments (e.g. Espoo
staging) through eVaka's MCP server. Skills follow the open
[Agent Skills](https://agentskills.io/specification) format, so the same skill works in
Claude (Claude Code, claude.ai), OpenAI Codex and GitHub Copilot (VS Code, CLI, cloud agent).

| Skill | Purpose |
|---|---|
| [`evaka-test-data`](skills/evaka-test-data/SKILL.md) | Any kind of test data: units, staff and their attendance, families, applications and decisions, placements, reservations, absences, attendance, VASU/LEOPS documents, assistance, finance, messages ... |

## How it works (and why it needs no maintenance)

The MCP server belongs to the eVaka repository and inserts rows with eVaka's Kotlin test
fixture classes. The skill does not store row shapes. `scripts/row_types.py` reads them from
the eVaka repo **at the commit running in the environment** (`appCommit`), and the workflow
tells the agent how to check compatibility from the repo history if the server reports an
error. When eVaka changes, the skill adapts.

The skill provides:
- `SKILL.md`: the workflow (plan → shapes → generator script → local check → server
  validation without saving → insert → workflows → verify → report)
- `scripts/row_types.py`: row shapes, enums and payload checking (catches misspelled fields,
  which the server silently ignores)
- `scripts/evaka_testdata.py`: a stdlib Python library (time zones, workdays and holidays,
  test SSNs, names, absence categories, lint, upload)
- `references/`: pitfalls verified against staging, domain model, realism, compatibility
- `examples/`: a minimal template and a full unit scenario

## Requirements

1. **The eVaka MCP server is connected** to your agent: `https://<environment>/api/mcp`
   (e.g. `https://staging.espoonvarhaiskasvatus.fi/api/mcp`). Authentication is OAuth: the
   agent opens an eVaka login, which you approve as an employee (dynamic client
   registration, so no keys need to be configured).
2. **A clone of the eVaka repo** in the agent's environment (`git clone
   https://github.com/espoon-voltti/evaka`), plus `python3` (3.9+), `git` and `curl`.

## Installation

Copy (or symlink) the `skills/evaka-test-data` directory to a location your tool scans:

| Tool | Personal (all projects) | Project-specific |
|---|---|---|
| Claude Code | `~/.claude/skills/evaka-test-data/` | `.claude/skills/evaka-test-data/` |
| claude.ai / Claude Code on the web | Settings → Capabilities → Skills → upload a zip of the `evaka-test-data` directory (an organization admin can share it with the whole org) | – |
| OpenAI Codex | `~/.codex/skills/evaka-test-data/` (or `$CODEX_HOME/skills`) | `.agents/skills/evaka-test-data/` |
| GitHub Copilot (VS Code, CLI, cloud agent) | `~/.copilot/skills/evaka-test-data/` or `~/.agents/skills/` | `.github/skills/evaka-test-data/` or `.agents/skills/` |

The simplest cross-tool option is `~/.agents/skills/` plus a symlink at the path your tool
expects. Tool paths change: check them in your tool's documentation.

```sh
git clone https://github.com/Wnt/evaka-testdata-skills ~/evaka-testdata-skills
mkdir -p ~/.claude/skills ~/.codex/skills ~/.copilot/skills
for d in ~/.claude/skills ~/.codex/skills ~/.copilot/skills; do
  ln -sfn ~/evaka-testdata-skills/skills/evaka-test-data "$d/evaka-test-data"
done
# zip for claude.ai:
(cd ~/evaka-testdata-skills/skills && zip -r ~/evaka-test-data.zip evaka-test-data)
```

Tools without skill support (e.g. Microsoft 365 Copilot chat): give `SKILL.md` and the
`references/` files to the agent as instructions. The scripts need an environment that can
run commands.

## Usage

Just ask in plain language, e.g.:

> Create test data in Espoo staging: a new daycare, 10 families with placements,
> applications, reservations and attendance for the last 2 weeks, VASU documents and
> preschool absence applications. Also add staff with their attendance.

> Add a family with three children to unit X, one of them with a pending preschool
> application, and push it through to the decision.

The agent puts all data in one named *batch*. You can list it (`list_test_data`) and delete
it (`delete_test_data`, `dryRun` first).

## Development

- Keep `SKILL.md` short (under 500 lines). Put details in `references/`.
- Don't hard-code row shapes: read them from the repo with `row_types.py`.
- Mark new findings in `references/pitfalls.md` with ✔ when verified against an environment.
- Check the format: `npx skills-ref validate skills/evaka-test-data` (agentskills.io reference
  tool), if available.
