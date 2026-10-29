# Release validation · 2026.10.29.4

The 90 Skill files and ZIP bytes match the approved 2026.10.29.4-local candidate. Source, project/global installations and ZIP members match its SHA-256 manifest. Generic rules, scripts, reader assets, synthetic examples and authorized public developer attribution are packaged; research inputs, private configuration, credentials, model environments and local logs are excluded. The separate docs website retains the seven previously published example readers unchanged.

Validation: 280 Python regressions passed after the timezone-boundary fix. The unchanged reader assets passed 19 JavaScript/DOM tests with no skips, including annotation export/restore on an actual reader. All 56 Python files parsed using Python 3.10 grammar; relative Markdown file links passed. Installation and synthetic-reader checks passed in a fresh Chinese/space path; a changed same-name installation was rejected without losing the edit. These checks do not establish real source accuracy or editorial quality.

New scope regressions cover target shortfalls, evidence-backed stopping, retained exact requests, unresolved candidates and source boundaries. Additional cases confirm that UTC/+08:00 crossings cannot falsely pass or block same-day coverage, in both total and per-platform scopes. The correction reuses the existing task-timezone normalization; no new research rule or runtime dependency is introduced.

Static inspection covered current package files and reviewed public repository text; 15 historical ZIPs and seven public HTML examples were matched against Git blobs before targeted path/credential checks. This is not a full Git-history secret scan or penetration test. Seven case labels were corrected to 25, 13, 14, 15, 27, 16 and 23 source works (133 total), without changing reader content or gallery layout.

No new live platform collection, login, media-model cold installation, cross-system run, browser visual review or actual offline reopening was performed for publication. Semantic review remains source-based; passing fields, hashes or test counts never proves that an explanation is useful, complete or correct.
