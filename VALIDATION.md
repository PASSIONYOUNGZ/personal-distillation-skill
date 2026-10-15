# Release validation · 2026-10-15

This report describes checks actually run on this publication copy. Synthetic tests validate workflow and rendering invariants; they do not certify the truth of a person's profile, live source access, or every host's deployment.

| Check | Result |
| --- | --- |
| Skill frontmatter and scaffold validation | Passed using the skill-creator validator |
| Python regression suite | 98 tests passed |
| Reader JavaScript interaction suite | 4 tests passed |
| Clean install in a path containing spaces and Chinese characters | Passed; copied-file hashes and local references checked |
| Reader render plus HTML/data validator | Passed with the packaged synthetic fixture |
| Repeat installation of identical files | Passed without replacing different content |
| Conflicting local installation | Refused as designed; original contents preserved |
| Publication content scan | No research datasets, real avatars, local account settings, credentials, models, environments or personal absolute paths in the skill directory |

The core checks ran on Windows with Python 3.14. The packaged skill frontmatter validator ran in a separate Python environment with PyYAML; PyYAML is not a runtime dependency of this skill. The Node suite ran with the available bundled Node runtime. Other operating systems were not executed during this release.

The first regression attempt used the sandbox's OS temporary location and encountered two filesystem permission errors. Running the same suite in an explicit writable test directory passed all 98 tests; no assertions were weakened or removed.

This release does not claim a fresh installation of optional media/ASR dependencies on every supported Python version. Browser tools, site permissions, captions and transcription quality must be checked in the user's actual host and research task. See `AGENT_INSTALL.md` for base deployment versus source-access readiness.

The cover is an AI-generated illustration for this repository. It does not depict a real research subject.
