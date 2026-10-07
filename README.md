# logo-maker

A Claude Code driven logo generator for the owner's ventures. Open a terminal in this folder, run `claude`, and the `logo` skill guides you from a venture (named or not) to a verified logo package: strategy, territories, vetted concepts shown in context, refinement, and nearly 190 files with a one-page brand sheet.

Marks are constructed vectors: Python concept modules built on a geometry kit with real font outlines, compiled to paths-only SVG, rendered through Google Chrome, audited automatically, and exported to every format a small company needs. No image-generation APIs are involved.

## Setup

```
uv sync
uv run logomaker setup --check
```

Requires Google Chrome in `/Applications` and Python 3.12 (uv installs it).

## Use

Run `claude` here and ask for a logo. Outside Claude, the CLI works on its own. In outline, with the files you write as comments:

```
uv run logomaker brand new "Harbor"
uv run logomaker fonts fetch Sora
# write brands/harbor/concepts/01-arch/concept.py (see .claude/skills/logo/reference/kit-api.md)
uv run logomaker concept run harbor 01-arch
# score it in brands/harbor/concepts/01-arch/scorecard.json (see .claude/skills/logo/reference/scorecard.md)
uv run logomaker sheet concepts harbor --concepts 01-arch
# copy concept.py into brands/harbor/final/ and add params.json, tokens.json and rationale.md beside it
uv run logomaker concept run harbor final
uv run logomaker package build harbor && uv run logomaker package verify harbor
```

Every brand lives in `brands/<slug>/`; the finished package is `brands/<slug>/package/`. `docs/examples/keystone/` is a complete example.

## Layout

`src/logomaker/` code, `templates/` sheets and documents, `assets/` fonts catalogue and cliché data, `.claude/skills/logo/` the skill and its knowledge base, `docs/research/` the research it is built on, `docs/superpowers/` the spec and plans.

## Tests

`uv run pytest -m "not render and not live"` (fast), `uv run pytest -m render` (Chrome), `uv run pytest -m live` (network).
