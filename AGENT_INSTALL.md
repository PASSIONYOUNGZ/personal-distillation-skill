# Install Personal Distillation Skill

This document is for an agent that has been asked by its user to install this skill. Stay within that installation request; do not start person research, sign into websites, publish content, or modify unrelated settings as part of deployment.

## Outcome

Install the complete `person-distillation` directory into the current host's supported skill location, verify its files and the core HTML pipeline, and report separately whether live browsing is available. Keep the invocation name `$person-distillation`.

## Procedure

1. Inspect the host's existing skills location, available Python and browser/network tools. Use the host's actual supported mechanism; do not assume every agent uses Codex paths. Python 3.10+ is required for the core. If missing, use the host's supported installation method with an official Python distribution and applicable approval rules. Do not disable TLS, change proxies or replace system Python as a shortcut.
2. Fetch `https://github.com/PASSIONYOUNGZ/personal-distillation-skill` into a task-local staging directory using Git or the normal GitHub archive download. Read this document and `person-distillation/SKILL.md`; keep all references, scripts and assets in their relative locations.
3. If the host has a built-in skill installer, use it with repository `PASSIONYOUNGZ/personal-distillation-skill` and path `person-distillation`. Otherwise run `python install.py --skills-dir <actual-host-skill-directory>` from the checkout. The helper refuses to overwrite a different same-name installation. On conflict, compare changes and preserve local edits before applying a user-authorized update; do not delete the old skill to make installation pass.
4. The helper checks copied-file hashes, local reference links and runs the synthetic reader plus its validator in a separate temporary directory. If using a host installer instead, run `python install.py --check-only --skill-path <installed-person-distillation-directory>` to perform the same checks without copying. Preserve the result and inspect failures. Passing this proves core files and rendering, not live source access or semantic research quality.
5. Verify the host can discover and read the installed skill. If discovery refreshes on the next turn or requires a supported reload, tell the user accurately. Do not change unrelated global agent configuration to force activation.
6. Probe whether the host offers browser/network tools. The skill does not include a browser API or logged-in accounts. Report this capability separately; do not visit all social platforms before a research subject exists. If a required extension or user connection is missing, explain the exact host-supported action once. Do not claim the skill is fully ready for online research merely because the renderer passed.

## Optional media route

Do not download all dependencies or any model during base installation. Prefer usable original text/subtitles. When a research request actually needs media tools, use a new research workspace and run the packaged plan, then apply within authorization:

```text
python <installed-skill>/scripts/bootstrap.py --workspace <research-workspace> --profile media
python <installed-skill>/scripts/bootstrap.py --workspace <research-workspace> --profile media --apply
```

Only if transcription is needed and Whisper is the chosen suitable route:

```text
python <installed-skill>/scripts/bootstrap.py --workspace <research-workspace> --profile whisper --download-model --apply
```

Use a Python version compatible with the selected package wheels; running core scripts on a newer Python does not prove media compatibility. Follow `references/release-and-validation.md` for actual model/FFmpeg checks. Never package your own virtual environment, cached model, browser profile, credentials or research materials into the skill.

## Report to the user

- Actual installed path and invocation name.
- File verification and synthetic reader results, with the test output path.
- Host discovery status and whether browser/network access is available.
- Any exact remaining user action or failed dependency; distinguish base deployment from source access.

Once installed, normal use only needs a person and quantity/time scope. Example: `使用 $person-distillation，蒸馏某位创作者最近30项公开内容。`
