# Release validation · 2026.10.16.3

| Check | Result |
| --- | --- |
| Python suite, source and extracted ZIP | 122 passed in each copy |
| Actual reader.js under synthetic DOM | 4 passed in each copy |
| Skill scaffold and local references | Passed |
| Local project/global installation and ZIP | 71 file hashes match |
| Timing tests | Cross-process close, nested/parallel accounting, open spans, exceptions, retries/cache, ASR metrics, missing time, payload restrictions, setup timeout and actual CLI failure path |
| Public package scan | Rules/code/synthetic fixture plus explicitly authorized public developer credits only; no private configuration, research logs, credentials, models or environments |

Windows/Python 3.14 was used. A small local instrumentation smoke wrote 100 empty spans (200 events) in about 0.617 seconds; this is local logging overhead only, not an ASR/browser benchmark or a speedup promise. Source/ZIP regression receipts are retained by the maintainer. Initial sandbox execution hit an existing Windows temporary-directory ACL restriction; the same assertions passed with normal filesystem permissions.

GitHub publication-copy installation into a fresh path containing spaces and Chinese characters passed copied-file verification, local references, synthetic reader rendering and HTML/data validation. Online platform collection, a new latest-30 research run, new browser visual/offline checks, and fresh-OS/media deployment were not rerun. Local spans must be recorded during the next real task before unlogged historical time can be attributed.

The repository cover is illustrative AI artwork, not a research subject or evidence. Public developer avatar/links are intentional authorized credits, not installer account configuration.

This reader patch adds five date/source presentation tests and reuses an actual 30-work data set for static/structural checks. Long timestamps remain in data, not visible map labels; same-account thread entries are folded for display. No new end-to-end task, semantic rewrite or multi-viewport browser pass is claimed.
