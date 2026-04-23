# Contributing

Thanks for your interest in Shelf. Contributions are welcome.

## Reporting issues

Open a GitHub issue with:
- What you expected to happen
- What actually happened
- Steps to reproduce
- Browser / OS / Node version if relevant

## Pull requests

1. Fork the repo and create a branch off `main`.
2. Keep changes focused — one concern per PR.
3. Verify the build passes locally: `npm run build`.
4. For pipeline changes, run `./lib --sync` against a test book and confirm `public/data/metadata.json` is regenerated correctly.
5. Open a PR describing what changed and why.

## Code style

No linter enforcement — match the surrounding style. The codebase favors:
- Plain JavaScript (ES modules), no TypeScript
- Small files, shared helpers in `src/utils.js`
- No comments for WHAT the code does; comments only for non-obvious WHY

## Scope

Shelf is a personal search engine; it is deliberately minimal. Before starting
a large change, open an issue to discuss scope — features that add a backend,
require authentication, or couple the app to a specific host are unlikely to
be merged.
