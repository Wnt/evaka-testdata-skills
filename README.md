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
- `scripts/evaka_source.py`: fetches only the needed eVaka backend files of the deployed commit
  (sparse, depth 1, ~3 s, cached). No eVaka clone is needed.
- `scripts/row_types.py`: compact row shapes, enums and payload checking (catches misspelled
  fields, which the server silently ignores)
- `scripts/scenario.py`: high-level builders for the common case (unit, groups, staff, families,
  placements, reservations, absences, attendance, staff shifts). A typical request needs a
  ~30-60 line script.
- `scripts/evaka_testdata.py`: a stdlib Python library (time zones, workdays and holidays,
  test SSNs, names, absence categories, lint, upload)
- `references/`: pitfalls verified against staging, domain model, realism, compatibility
- `examples/`: `quick_unit.py` (3 groups, 15 children, staff, two weeks of attendance),
  `minimal_family.py`, and `full_unit_scenario.py` (a large reference scenario)

## Requirements

1. **The eVaka MCP server is connected** to your agent: `https://<environment>/api/mcp`
   (e.g. `https://staging.espoonvarhaiskasvatus.fi/api/mcp`). Authentication is OAuth: the
   agent opens an eVaka login, which you approve as an employee (dynamic client
   registration, so no keys need to be configured).
2. `python3` (3.9+), `git`, `curl` and network access to github.com. The scripts fetch the
   eVaka source they need themselves. No eVaka clone is needed.

## Installation

### Claude Code on the web / claude.ai (recommended for cloud sessions)

Upload the skill once in **claude.ai → Settings → Capabilities → Skills** as a zip of the
`evaka-test-data` directory. It is then available in every cloud session, with no tokens spent
and nothing committed to any project. An organization admin can enable it for the whole
organization. Build the zip:

```sh
git clone --depth 1 https://github.com/Wnt/evaka-testdata-skills
(cd evaka-testdata-skills/skills && zip -r ../../evaka-test-data.zip evaka-test-data)
```

Don't "install" it by attaching the zip in a chat. The agent then spends a turn and tokens
reviewing and copying it, and usually commits it into the project repository.

To get updates automatically instead, add this to the cloud environment's **setup script**
(environment settings → Setup script). It runs when a session starts:

```sh
rm -rf ~/.claude/skills/evaka-test-data && mkdir -p ~/.claude/skills && \
  git clone -q --depth 1 https://github.com/Wnt/evaka-testdata-skills /tmp/evaka-testdata-skills && \
  cp -r /tmp/evaka-testdata-skills/skills/evaka-test-data ~/.claude/skills/
```

### Local tools

Copy (or symlink) the `skills/evaka-test-data` directory to a location your tool scans:

| Tool | Personal (all projects) | Project-specific |
|---|---|---|
| Claude Code | `~/.claude/skills/evaka-test-data/` | `.claude/skills/evaka-test-data/` |
| OpenAI Codex | `~/.codex/skills/evaka-test-data/` (or `$CODEX_HOME/skills`) | `.agents/skills/evaka-test-data/` |
| GitHub Copilot (VS Code, CLI, cloud agent) | `~/.copilot/skills/evaka-test-data/` or `~/.agents/skills/` | `.github/skills/evaka-test-data/` or `.agents/skills/` |

The simplest cross-tool option is one clone plus symlinks. Tool paths change: check your
tool's documentation.

```sh
git clone https://github.com/Wnt/evaka-testdata-skills ~/evaka-testdata-skills
for d in ~/.claude/skills ~/.codex/skills ~/.copilot/skills; do
  mkdir -p "$d" && ln -sfn ~/evaka-testdata-skills/skills/evaka-test-data "$d/evaka-test-data"
done
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
