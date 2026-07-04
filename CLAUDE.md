# Hero NutPod — Claude Code project instructions

This repo is connected to Joey's Context Vault.

## First thing to read

Before making changes, read the current project state:

- `D:\vault\projects\hero-nutpod\status.md`
- `D:\vault\wiki\hero-nutpod.md`

Also skim the vault schema:

- `D:\vault\CLAUDE.md`

## Project role

Hero NutPod is the focused reboot of the old NutFlix direction. Treat this as the current active NutPod project, not the older broad NutFlix platform.

## Rules

1. Check `git status --short` before editing.
2. Treat the vault status page as more current than old README/docs.
3. Do not touch existing dirty files unless Joey explicitly asks.
4. Do not make broad rewrites without a plan.
5. Do not commit unless Joey explicitly says to commit.
6. After meaningful work, tell Joey what should be updated in the vault.

## Known caution

If `cameras/camera_manager.py` or `config.yaml` are dirty, assume Joey may have active camera/motion-recording work in progress. Inspect before editing.

## End of session

Report:

- what changed
- tests run
- files modified
- whether anything should be added to the vault
- exact next step
