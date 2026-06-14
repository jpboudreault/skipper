# Contributing to Skipper

Thank you for your interest in contributing!

## Getting started

1. Fork the repository and clone it locally.
2. Follow the setup steps in [README.md](README.md).
3. Create a branch for your change: `git checkout -b my-feature`.

## Development workflow

- Run backend tests: `bash scripts/test_backend.sh`
- Run frontend type-check: `cd frontend && npm run check`
- Keep changes focused — one feature or fix per PR.

## Code style

- Match existing patterns in the file you are editing.
- Python: follow existing FastAPI/SQLModel conventions.
- TypeScript/Svelte: follow existing Svelte 5 runes patterns (`$state`, `$derived`, `$props`).

## Pull requests

1. Describe what changed and why.
2. Note how you tested it.
3. Ensure tests pass locally before opening the PR.

## Reporting issues

Open a GitHub issue with:
- Steps to reproduce
- Expected vs actual behavior
- Environment (OS, browser, dev vs production)

For security issues, see [SECURITY.md](SECURITY.md).
