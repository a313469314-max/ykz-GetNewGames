[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
Set-Location -LiteralPath $repoRoot

function Write-Section {
    param([Parameter(Mandatory = $true)][string]$Title)
    Write-Host ""
    Write-Host "== $Title =="
}

function Invoke-RgCheck {
    param(
        [Parameter(Mandatory = $true)][string]$Label,
        [Parameter(Mandatory = $true)][string]$Pattern
    )

    $rgArgs = @(
        "-n",
        "--hidden",
        "-g", "!**/.git/**",
        "-g", "!**/node_modules/**",
        "-g", "!**/data/**",
        "-g", "!**/output/**",
        "-g", "!**/.env",
        "-g", "!**/.env.*",
        "-g", "!scripts/check-readonly.ps1",
        "--",
        $Pattern,
        "."
    )

    $output = & rg @rgArgs 2>&1
    $exitCode = $LASTEXITCODE

    if ($exitCode -eq 0) {
        Write-Host "[FAIL] $Label"
        $output | ForEach-Object { Write-Host $_ }
        return $false
    }

    if ($exitCode -eq 1) {
        Write-Host "[OK] $Label"
        return $true
    }

    Write-Host "[ERROR] $Label"
    $output | ForEach-Object { Write-Host $_ }
    return $false
}

function Invoke-RgCheckOnFiles {
    param(
        [Parameter(Mandatory = $true)][string]$Label,
        [Parameter(Mandatory = $true)][string]$Pattern,
        [Parameter(Mandatory = $true)][string[]]$Files
    )

    if ($Files.Count -eq 0) {
        Write-Host "[OK] $Label (no files to scan)"
        return $true
    }

    $output = & rg -n -- $Pattern @Files 2>&1
    $exitCode = $LASTEXITCODE

    if ($exitCode -eq 0) {
        Write-Host "[FAIL] $Label"
        $output | ForEach-Object { Write-Host $_ }
        return $false
    }

    if ($exitCode -eq 1) {
        Write-Host "[OK] $Label"
        return $true
    }

    Write-Host "[ERROR] $Label"
    $output | ForEach-Object { Write-Host $_ }
    return $false
}

Write-Host "Readonly pre-commit safety check"
Write-Host "This script does not fetch, send, sync, modify files, stage, or commit."
Write-Host "Repository: $repoRoot"

if (-not (Get-Command rg -ErrorAction SilentlyContinue)) {
    Write-Host "[ERROR] ripgrep (rg) is required for this check."
    exit 2
}

$hasBlockingIssue = $false

Write-Section "Naming and secret-example checks"
$checks = @(
    @{ Label = "old Feishu column labels"; Pattern = "ADX 今日新品|YouTube 今日发现" },
    @{ Label = "old project directory names"; Pattern = "fb-newgame-daily|D:\\GetNewGames\\海外休闲新品日报" },
    @{ Label = "valued Feishu Base token examples"; Pattern = "FEISHU_BITABLE_APP_TOKEN=.+" },
    @{ Label = "known Feishu Base token fragments"; Pattern = "IINV" }
)

foreach ($check in $checks) {
    $ok = Invoke-RgCheck -Label $check.Label -Pattern $check.Pattern
    if (-not $ok) {
        $hasBlockingIssue = $true
    }
}

Write-Section "Allowed .env.example checks"
$envExampleFiles = @(
    Get-ChildItem -LiteralPath $repoRoot -Recurse -Force -File -Filter ".env.example" |
        Where-Object {
            $_.FullName -notmatch '\\.git\\' -and
            $_.FullName -notmatch '\\node_modules\\' -and
            $_.FullName -notmatch '\\data\\' -and
            $_.FullName -notmatch '\\output\\'
        } |
        ForEach-Object { $_.FullName }
)

$envExampleChecks = @(
    @{ Label = ".env.example valued Feishu Base token examples"; Pattern = "FEISHU_BITABLE_APP_TOKEN=.+" },
    @{ Label = ".env.example known Feishu Base token fragments"; Pattern = "IINV" }
)

foreach ($check in $envExampleChecks) {
    $ok = Invoke-RgCheckOnFiles -Label $check.Label -Pattern $check.Pattern -Files $envExampleFiles
    if (-not $ok) {
        $hasBlockingIssue = $true
    }
}

Write-Section "Git status"
$statusOutput = & git status --short 2>&1
$gitStatusExitCode = $LASTEXITCODE

if ($gitStatusExitCode -ne 0) {
    Write-Host "[ERROR] git status failed."
    $statusOutput | ForEach-Object { Write-Host $_ }
    exit 2
}

if ($statusOutput) {
    $statusOutput | ForEach-Object { Write-Host $_ }
} else {
    Write-Host "Working tree is clean."
}

Write-Section "Routine commit warnings"
$generatedPattern = '(^|[\s\\/])(data|output)([\\/]|$)'
$databasePattern = '\.(db|sqlite|sqlite3)($|[\s"])'
$cachePattern = '__pycache__([\\/]|$)|\.pytest_cache([\\/]|$)|(^|[\s\\/])\.cache([\\/]|$)'

$warningGroups = @(
    @{ Label = "Generated data/report"; Pattern = $generatedPattern },
    @{ Label = "Local database"; Pattern = $databasePattern },
    @{ Label = "Cache"; Pattern = $cachePattern }
)

$hasRoutineWarning = $false
foreach ($group in $warningGroups) {
    $lines = @($statusOutput | Where-Object { $_ -match $group.Pattern })
    if ($lines.Count -eq 0) {
        Write-Host "[OK] $($group.Label): no dirty paths detected."
        continue
    }

    $hasRoutineWarning = $true
    Write-Host "[WARN] $($group.Label): usually should not be included in routine commits."
    $lines | ForEach-Object { Write-Host $_ }
}

if ($hasRoutineWarning) {
    Write-Host ""
    Write-Host "These warnings do not fail this script."
    Write-Host "If a path is now ignored but still appears in git status, it may be a historically tracked file."
    Write-Host ".gitignore does not automatically untrack existing files; do not handle that in this round."
} else {
    Write-Host "No data/output/db/cache dirty paths detected in git status."
}

Write-Section "Result"
if ($hasBlockingIssue) {
    Write-Host "Blocking issue found: old naming or sensitive example residue was detected."
    exit 1
}

Write-Host "No blocking readonly-check issues found."
exit 0
