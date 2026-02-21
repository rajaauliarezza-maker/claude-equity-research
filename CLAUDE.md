# CLAUDE.md

This file provides guidance to AI assistants working in the `claude-equity-research` repository.

## Project Overview

**claude-equity-research** is a Claude Code plugin that delivers institutional-grade equity research reports via a single slash command (`/trading-ideas`). It has no traditional runtime dependencies — the entire plugin is a Markdown file with YAML frontmatter that Claude Code interprets natively. Analysis is performed at invocation time using Claude's built-in `WebSearch` and `WebFetch` tools.

**Owner**: quant-sentiment-ai
**License**: MIT
**Version**: 1.0.0
**Status**: Active

---

## Repository Structure

```
claude-equity-research/
├── CLAUDE.md                          # This file
├── README.md                          # User-facing project overview
├── PLUGIN.md                          # Claude Code plugin documentation
├── SECURITY.md                        # Vulnerability reporting policy
├── LICENSE                            # MIT License
├── .gitignore                         # Python/IDE/OS ignores
├── .claude-plugin/
│   └── marketplace.json               # Plugin marketplace metadata
├── commands/
│   ├── trading-ideas.md               # PRIMARY: The Claude Code command
│   └── README.md                      # Command-specific usage guide
├── config/
│   └── config.example.json            # Reference configuration template
├── docs/
│   ├── methodology.md                 # 8-section analysis framework details
│   ├── installation.md                # Setup instructions and troubleshooting
│   └── customization.md               # Sector-specific and advanced customization
└── examples/
    └── sample_reports/
        ├── AAPL_analysis.md            # Apple Inc. sample output
        └── HOOD_analysis.md            # Robinhood sample output
```

### Key File Roles

| File | Role |
|------|------|
| `commands/trading-ideas.md` | **The plugin itself** — defines the Claude Code command via YAML frontmatter and a Markdown prompt |
| `.claude-plugin/marketplace.json` | Registers the plugin with the Claude Code plugin marketplace |
| `config/config.example.json` | Reference for configuration options; users copy and customize this |
| `docs/methodology.md` | Authoritative spec for the 8-section report structure |

---

## How the Plugin Works

This is **not** a traditional application. There is no executable, no build step, and no server.

1. A user installs `commands/trading-ideas.md` into `~/.claude/commands/`.
2. When they run `/trading-ideas AAPL`, Claude Code reads the file.
3. The YAML frontmatter declares allowed tools (`WebSearch`, `WebFetch`) and usage hints.
4. The Markdown body is the system prompt that tells Claude how to conduct and format the research.
5. Claude executes live web searches and synthesizes the report in real time.

**No API keys, no external services, no runtime environment required.**

---

## Command Specification (`commands/trading-ideas.md`)

The frontmatter block must remain valid YAML:

```yaml
---
description: Professional equity research analysis with institutional-grade formatting
argument-hint: [TICKER] [--detailed]
allowed-tools: WebSearch, WebFetch
---
```

- `allowed-tools` controls which Claude Code tools the command may use. Currently only `WebSearch` and `WebFetch` are granted.
- `argument-hint` is displayed in Claude Code's `/help` output.
- The Markdown body below the frontmatter is the full prompt; formatting and section headers are load-bearing — they define the output structure.

### Report Sections (must be preserved in order)

1. **Executive Summary** — BUY/SELL/HOLD, price target, conviction level
2. **Fundamental Analysis** — revenue, margins, peer comparisons, forward guidance
3. **Catalyst Analysis** — near-term (0–6 months), medium-term (6–24 months), event-driven
4. **Valuation & Price Targets** — bull/base/bear scenarios with probability weighting
5. **Risk Assessment** — company-specific and macro risks, position sizing (1–5%)
6. **Technical Context & Options Intelligence** — support/resistance, put/call ratios, IV
7. **Market Positioning** — sector performance, rotation trends, relative strength
8. **Insider Signals** — Form 4 activity, buybacks, institutional ownership changes

Followed by a **Recommendation Summary** table and a mandatory **disclaimer**.

---

## Configuration (`config/config.example.json`)

The config file is a reference template — it is not loaded automatically by the plugin. Users who want to customize behavior copy it and reference it manually or integrate it into their own tooling.

Key configurable areas:

| Key | Purpose |
|-----|---------|
| `analysis_settings.default_timeframe` | Default horizon (`"12m"`) |
| `analysis_settings.risk_tolerance` | `"conservative"`, `"moderate"`, `"aggressive"` |
| `risk_parameters.*` | Position size, stop-loss, conviction score per risk profile |
| `sector_preferences.*` | Weight multipliers and key metrics per sector |
| `data_sources.web_search.max_results` | Number of search results to fetch |
| `compliance_settings.prohibited_terms` | Terms that must never appear in output |
| `customization.analyst_name` | Branding for report footer |

**Do not add secrets, API keys, or personal data to `config.example.json`.**

---

## Marketplace Metadata (`.claude-plugin/marketplace.json`)

This file registers the plugin for discovery via `/plugin marketplace add quant-sentiment-ai/claude-equity-research`. Fields:

- `metadata.pluginRoot` — must stay `"commands"` (the directory Claude Code looks in)
- `plugins[0].source` — must be `"./commands/trading-ideas.md"`
- `plugins[0].version` — bump this when releasing changes

---

## Development Conventions

### Editing the Command Prompt

The body of `commands/trading-ideas.md` is a system prompt. Follow these conventions:

- **Section headers (`##`) are structural** — downstream users and the plugin spec rely on their exact names. Do not rename or reorder existing sections without updating `docs/methodology.md` to match.
- **All financial metrics must be specific** — template placeholders like `[X]%` indicate that Claude should insert real numbers, not that we're leaving things blank.
- **Probability weightings must sum to 100%** — bull/base/bear case percentages are validated by readers; keep the template consistent (e.g., `25%/55%/20%`).
- **The disclaimer block is mandatory** and must appear verbatim at the end of every report. Do not remove or soften it.

### Adding a New Analysis Section

1. Add the section definition to `commands/trading-ideas.md` (OUTPUT FORMAT block).
2. Add corresponding quality standards to the QUALITY STANDARDS block at the bottom of the same file.
3. Document the new section in `docs/methodology.md` with purpose, components, and standards.
4. Update `examples/sample_reports/AAPL_analysis.md` to show a realistic sample.

### Sector-Specific Customizations

Create variant commands by copying `trading-ideas.md` and adjusting metrics — see `docs/customization.md` for patterns. Variants go in `~/.claude/commands/` at the user level, not in this repository, unless they are intended as first-class plugin commands (in which case register them in `marketplace.json`).

### Configuration Changes

When modifying `config/config.example.json`:
- Keep it valid JSON (no comments, no trailing commas).
- All values must be illustrative defaults — never real credentials.
- Update `docs/customization.md` if new keys are added.

---

## No Build, Test, or Lint Steps

This repository has no build system, test runner, or linter. There is no `package.json`, `requirements.txt`, or Makefile.

**Validation is manual:**

```bash
# Verify the command file is well-formed YAML+Markdown
head -10 commands/trading-ideas.md   # Check frontmatter

# Validate marketplace JSON
python3 -m json.tool .claude-plugin/marketplace.json

# Validate config example
python3 -m json.tool config/config.example.json
```

**Functional testing** requires a live Claude Code session:
```bash
/trading-ideas AAPL          # Standard analysis
/trading-ideas HOOD --detailed  # Enhanced analysis
/trading-ideas INVALID       # Error handling
```

---

## Git Workflow

```
main         ← stable releases
master       ← legacy default branch (maps to main in remote)
claude/*     ← AI-generated feature branches (use these for all AI-driven work)
feature/*    ← human contributor branches
```

### Branch Naming

AI-assisted work must use branches starting with `claude/` (required by the remote's push policy). Example: `claude/add-claude-documentation-bujZj`.

### Commit Style

Use short, imperative commit messages. Examples from the project's history:
- `Fix marketplace source path issues`
- `Add Claude Code Plugin support`
- `Create SECURITY.md`

### Signed Commits

Commits are signed with the SSH key at `/home/claude/.ssh/commit_signing_key.pub`. Do not disable signing (`--no-gpg-sign`).

---

## Installation Methods (for reference)

### Plugin Marketplace (recommended for users)
```bash
/plugin marketplace add quant-sentiment-ai/claude-equity-research
/plugin install claude-equity-research@quant-sentiment-ai
```

### Manual
```bash
mkdir -p ~/.claude/commands
cp commands/trading-ideas.md ~/.claude/commands/trading-ideas.md
```

### Prerequisites
- Claude Code CLI ≥ 2.0.11
- Claude paid subscription (Pro, Team, or Enterprise)
- Internet connection (required at analysis time)

---

## Compliance and Legal Conventions

Every generated report **must** include the disclaimer exactly as written in the command template:

> **IMPORTANT DISCLAIMER**: This analysis is for educational and research purposes only. Not financial advice. Past performance does not guarantee future results. Consult qualified financial professionals before making investment decisions. All investments carry risk of loss.

**Prohibited terms** (must never appear in output): `guaranteed`, `risk-free`, `sure thing`.

When editing the command prompt, ensure these terms cannot appear in generated output either literally or via rephrasing that carries the same meaning.

---

## Extending the Plugin

### Adding a new command to the marketplace

1. Create `commands/<new-command>.md` with valid YAML frontmatter.
2. Add an entry to `.claude-plugin/marketplace.json` under `plugins`.
3. Document it in `PLUGIN.md` and `commands/README.md`.
4. Bump `metadata.version` in `marketplace.json`.

### Supported tools for commands

Only `WebSearch` and `WebFetch` are currently in `allowed-tools`. If a new command needs filesystem access, add `Read` or `Glob` to its frontmatter — but do not add write tools to research-only commands.

---

## Key Contacts and Resources

- **Issues**: https://github.com/quant-sentiment-ai/claude-equity-research/issues
- **Discussions**: https://github.com/quant-sentiment-ai/claude-equity-research/discussions
- **Security vulnerabilities**: See `SECURITY.md` for responsible disclosure process
- **Analysis methodology**: `docs/methodology.md` is the authoritative reference
