# Release validation · 2026.10.22.3

The release contains the approved 84-file local candidate without changing Skill file or archive bytes. The release source, project/global installations and every ZIP member match its SHA-256 manifest. The public package contains only generic rules, references, runtime helpers, synthetic examples, tests and explicitly authorized public project-developer attribution assets. Private research, user settings, models, login state and local audit records are excluded.

241 Python regression tests passed. 9 reader-interaction tests and 10 annotation/export DOM tests passed with no skips, including a generated reader's boot/export/restore flow. The latter test derives the viewpoint count from its input rather than a specific case size.

The documented schema4 import → contract6 review → HTML → verify flow passed; an empty review was rejected. Local isolated copies of 30 supplied works passed unchanged-material reuse, cross-task version/evidence comparison and user-edit protection checks. The generated reader for an existing input remained byte-identical to its previous corrected output. Static checks found no broken package-local Markdown file references, no unreachable runtime module from documented CLI roots and no unused import candidates after manual review.

Source fidelity tests cover word/string spaces, code indentation, block boundaries, exact excerpts and line-ending normalization. Empty-original tests cover plain text, Markdown and structured blocks while preserving real short originals and source links. Fixed public credit, current-only request/review rules, explicit indexing state and consistent IDs are tested.

These tests do not certify semantic truth or whole-web completeness. No fresh-machine cold start, live platform recollection, ASR rerun, actual-browser visual or offline-opening/storage pass is claimed. DOM checks are not browser visual tests. Local equivalence checks do not establish an end-to-end research speedup.
