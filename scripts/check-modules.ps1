[CmdletBinding()]
param(
    [ValidateSet("all", "dataeye", "youtube", "feishu-sync", "overseas-casual", "meme-hotspot", "scripts")]
    [string]$Module = "all",

    [switch]$SkipTests,

    [switch]$ContinueOnError
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path

function New-CheckCommand {
    param(
        [Parameter(Mandatory = $true)][string]$WorkDir,
        [Parameter(Mandatory = $true)][string]$Command,
        [Parameter(Mandatory = $true)][string[]]$Args
    )

    [pscustomobject]@{
        WorkDir = $WorkDir
        Command = $Command
        Args = $Args
    }
}

function Format-CommandLine {
    param(
        [Parameter(Mandatory = $true)][string]$Command,
        [Parameter(Mandatory = $true)][string[]]$Args
    )

    $parts = @($Command) + $Args
    ($parts | ForEach-Object {
        if ($_ -match '[\s"]') {
            '"' + ($_ -replace '"', '\"') + '"'
        } else {
            $_
        }
    }) -join " "
}

function Get-ModuleCommands {
    param([Parameter(Mandatory = $true)][string]$ModuleName)

    switch ($ModuleName) {
        "scripts" {
            $commands = @()
            $commands += New-CheckCommand -WorkDir $RepoRoot -Command "powershell" -Args @("-ExecutionPolicy", "Bypass", "-File", "scripts/check-readonly.ps1")
            $commands += New-CheckCommand -WorkDir $RepoRoot -Command "powershell" -Args @("-ExecutionPolicy", "Bypass", "-File", "scripts/run-module.ps1", "-Module", "youtube", "-Action", "help")
            $commands += New-CheckCommand -WorkDir $RepoRoot -Command "powershell" -Args @("-ExecutionPolicy", "Bypass", "-File", "scripts/run-module.ps1", "-Module", "feishu-sync", "-Action", "sync", "-Date", "2026-06-04")
            return $commands
        }
        "dataeye" {
            $commands = @()
            if (-not $SkipTests) {
                $commands += New-CheckCommand -WorkDir (Join-Path $RepoRoot "adx") -Command "npm" -Args @("test")
            }
            $commands += New-CheckCommand -WorkDir (Join-Path $RepoRoot "adx") -Command "npm" -Args @("run", "typecheck")
            return $commands
        }
        "youtube" {
            $commands = @()
            $commands += New-CheckCommand -WorkDir (Join-Path $RepoRoot "youtube-newgame-daily") -Command "python" -Args @("main.py", "--help")
            $commands += New-CheckCommand -WorkDir (Join-Path $RepoRoot "youtube-newgame-daily") -Command "python" -Args @("send_feishu_report.py", "--help")
            if (-not $SkipTests) {
                $commands += New-CheckCommand -WorkDir (Join-Path $RepoRoot "youtube-newgame-daily") -Command "python" -Args @("-m", "unittest", "discover", "-s", "tests")
            }
            return $commands
        }
        "feishu-sync" {
            $commands = @()
            $commands += New-CheckCommand -WorkDir (Join-Path $RepoRoot "feishu-sync") -Command "python" -Args @("sync_all.py", "--help")
            return $commands
        }
        "overseas-casual" {
            $commands = @()
            $commands += New-CheckCommand -WorkDir (Join-Path $RepoRoot "overseas-casual-newgame-daily") -Command "python" -Args @("main.py", "--help")
            $commands += New-CheckCommand -WorkDir (Join-Path $RepoRoot "overseas-casual-newgame-daily") -Command "python" -Args @("send_feishu_report.py", "--help")
            if (-not $SkipTests) {
                $commands += New-CheckCommand -WorkDir (Join-Path $RepoRoot "overseas-casual-newgame-daily") -Command "python" -Args @("-m", "unittest", "discover", "-s", "tests")
            }
            return $commands
        }
        "meme-hotspot" {
            $commands = @()
            $commands += New-CheckCommand -WorkDir (Join-Path $RepoRoot "meme-hotspot-daily") -Command "python" -Args @("main.py", "--help")
            $commands += New-CheckCommand -WorkDir (Join-Path $RepoRoot "meme-hotspot-daily") -Command "python" -Args @("judge_material.py", "--help")
            return $commands
        }
    }

    throw "Unsupported module: $ModuleName"
}

function Invoke-CheckCommand {
    param([Parameter(Mandatory = $true)]$CheckCommand)

    $commandLine = Format-CommandLine -Command $CheckCommand.Command -Args $CheckCommand.Args
    Write-Host "WorkDir: $($CheckCommand.WorkDir)"
    Write-Host "Command: $commandLine"

    Push-Location -LiteralPath $CheckCommand.WorkDir
    try {
        & $CheckCommand.Command @($CheckCommand.Args) 2>&1 | ForEach-Object { Write-Host $_ }
        $exitCode = $LASTEXITCODE
    } finally {
        Pop-Location
    }

    if ($null -eq $exitCode) {
        $exitCode = 0
    }
    return $exitCode
}

$modulesToRun = if ($Module -eq "all") {
    @("scripts", "dataeye", "youtube", "feishu-sync", "overseas-casual", "meme-hotspot")
} else {
    @($Module)
}

Write-Host "Module safety checks"
Write-Host "This script does not fetch, send, sync, modify files, stage, or commit."
Write-Host "Repository: $RepoRoot"
Write-Host "SkipTests: $($SkipTests.IsPresent)"
Write-Host "ContinueOnError: $($ContinueOnError.IsPresent)"

$passedModules = New-Object System.Collections.Generic.List[string]
$failedModules = New-Object System.Collections.Generic.List[string]

foreach ($moduleName in $modulesToRun) {
    Write-Host ""
    Write-Host "== $moduleName =="

    $moduleFailed = $false
    $commands = Get-ModuleCommands -ModuleName $moduleName

    foreach ($command in $commands) {
        $exitCode = Invoke-CheckCommand -CheckCommand $command
        if ($exitCode -ne 0) {
            Write-Host "[FAIL] exit code $exitCode"
            $moduleFailed = $true
            break
        }
        Write-Host "[OK]"
    }

    if ($moduleFailed) {
        $failedModules.Add($moduleName) | Out-Null
        if (-not $ContinueOnError) {
            break
        }
    } else {
        $passedModules.Add($moduleName) | Out-Null
    }
}

Write-Host ""
Write-Host "== Summary =="
Write-Host "Passed modules: $($(if ($passedModules.Count -gt 0) { $passedModules -join ', ' } else { 'none' }))"
Write-Host "Failed modules: $($(if ($failedModules.Count -gt 0) { $failedModules -join ', ' } else { 'none' }))"

if ($failedModules.Count -gt 0) {
    exit 1
}
exit 0
