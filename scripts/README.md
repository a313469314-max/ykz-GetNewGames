# Scripts

This directory contains safe helper entrypoints. They are not one-click full-pipeline runners.

For the broader maintenance handoff, product boundaries, date rules, and forbidden operations, see [../docs/OPERATIONS.md](D:/GetNewGames/docs/OPERATIONS.md).

`check-readonly.ps1` is a pre-commit or pre-change safety check. It reports old naming residue, sensitive example residue, and dirty data/output/db/cache paths. It classifies generated data/reports, local databases, and cache paths separately. Warnings are not automatic cleanup, and the script does not crawl, send, sync, modify files, stage, or commit.

```powershell
powershell -ExecutionPolicy Bypass -File scripts/check-readonly.ps1
```

`run-module.ps1` is a unified module entrypoint. By default it only previews the command it would run. It executes only when `-Execute` is passed, and send/sync/history actions also require `-AllowRemote`.

Preview YouTube fetch:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run-module.ps1 -Module youtube -Action fetch -Date 2026-06-04
```

Execute YouTube fetch:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run-module.ps1 -Module youtube -Action fetch -Date 2026-06-04 -Execute
```

Preview Feishu sync:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run-module.ps1 -Module feishu-sync -Action sync -Date 2026-06-04
```

Execute Feishu sync:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run-module.ps1 -Module feishu-sync -Action sync -Date 2026-06-04 -Execute -AllowRemote
```

`check-modules.ps1` is a batch safety verification entrypoint. It will not trigger real business operations (`不会触发真实业务`): it only runs checks that should not trigger real crawling, sending, or syncing. It reports module pass/fail status and does not install dependencies, clean files, stage, or commit.

Run all safe checks:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/check-modules.ps1
```

Run faster checks without unit tests:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/check-modules.ps1 -SkipTests
```

Run only YouTube checks:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/check-modules.ps1 -Module youtube
```
