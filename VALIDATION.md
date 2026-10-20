# Release validation · 2026.10.20.1

This release publishes the approved local candidate without changing its 90 Skill files or ZIP bytes. Source, project installation, global installation, archive members and extracted files match the candidate manifest.

The local candidate passed 173 relevant Python tests and 9 tests of the actual reader JavaScript under a synthetic DOM host. An extracted archive passed 31 targeted pipeline, reading-unit, Markdown and section-image checks. The Skill format validator, local Markdown references, ZIP CRC and actual reader structure/self-contained-resource checks also passed.

The new regressions cover inline image rendering and source links, old and explicit reading-unit paths, gallery deduplication, export-relative paths, invalid-input diagnostics, empty modules/filters, optional biography notes and review invalidation after image content changes. Tests do not certify prose quality or the truth of an author's experiments.

Browser automation rejected file-protocol access. No browser pixel, multi-viewport or actual offline-opening pass is claimed. No fresh OS setup, new platform collection, ASR rerun, independent replication of source experiments or speed benchmark was performed for this release.

Private research, original media, local audit records and user configuration are excluded. The existing authorized public project developer credit is unchanged. Existing source records and older release archives are preserved.
