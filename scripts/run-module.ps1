[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("dataeye", "youtube", "feishu-sync", "overseas-casual", "meme-hotspot")]
    [string]$Module,

    [Parameter(Mandatory = $true)]
    [ValidateSet("fetch", "send", "test", "help", "sync", "history", "check", "judge")]
    [string]$Action,

    [string]$Date,

    [switch]$Execute,

    [switch]$Test,

    [switch]$AllowRemote
)

$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path

function New-RunPlan {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$WorkDir,
        [Parameter(Mandatory = $true)][string]$Command,
        [Parameter(Mandatory = $true)][string[]]$Args,
        [Parameter(Mandatory = $true)][string]$Risk,
        [Parameter(Mandatory = $true)][bool]$RequiresAllowRemote
    )

    [pscustomobject]@{
        Name = $Name
        WorkDir = $WorkDir
        Command = $Command
        Args = $Args
        Risk = $Risk
        RequiresAllowRemote = $RequiresAllowRemote
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

function Get-RunPlan {
    $moduleRoot = switch ($Module) {
        "dataeye" { Join-Path $RepoRoot "adx" }
        "youtube" { Join-Path $RepoRoot "youtube-newgame-daily" }
        "feishu-sync" { Join-Path $RepoRoot "feishu-sync" }
        "overseas-casual" { Join-Path $RepoRoot "overseas-casual-newgame-daily" }
        "meme-hotspot" { Join-Path $RepoRoot "meme-hotspot-daily" }
    }

    switch ($Module) {
        "dataeye" {
            switch ($Action) {
                "fetch" {
                    $args = @("run", "fetch:new-games")
                    if ($Date) { $args += @("--", "--date", $Date) }
                    return New-RunPlan -Name "dataeye fetch" -WorkDir $moduleRoot -Command "npm" -Args $args -Risk "fetch" -RequiresAllowRemote $false
                }
                "send" {
                    $args = @("run", "send:feishu")
                    $scriptArgs = @()
                    if ($Test) { $scriptArgs += "--test" }
                    if ($Date) { $scriptArgs += @("--date", $Date) }
                    if ($scriptArgs.Count -gt 0) { $args += @("--") + $scriptArgs }
                    return New-RunPlan -Name "dataeye send" -WorkDir $moduleRoot -Command "npm" -Args $args -Risk "send" -RequiresAllowRemote $true
                }
                "test" {
                    return New-RunPlan -Name "dataeye test" -WorkDir $moduleRoot -Command "npm" -Args @("test") -Risk "local-check" -RequiresAllowRemote $false
                }
            }
        }
        "youtube" {
            switch ($Action) {
                "fetch" {
                    $args = @("main.py")
                    if ($Date) { $args += @("--date", $Date) }
                    return New-RunPlan -Name "youtube fetch" -WorkDir $moduleRoot -Command "python" -Args $args -Risk "fetch" -RequiresAllowRemote $false
                }
                "send" {
                    $args = @("send_feishu_report.py")
                    if ($Test) { $args += "--test" }
                    return New-RunPlan -Name "youtube send" -WorkDir $moduleRoot -Command "python" -Args $args -Risk "send" -RequiresAllowRemote $true
                }
                "test" {
                    return New-RunPlan -Name "youtube test" -WorkDir $moduleRoot -Command "python" -Args @("-m", "unittest", "discover", "-s", "tests") -Risk "local-check" -RequiresAllowRemote $false
                }
                "help" {
                    return New-RunPlan -Name "youtube help" -WorkDir $moduleRoot -Command "python" -Args @("main.py", "--help") -Risk "help" -RequiresAllowRemote $false
                }
            }
        }
        "feishu-sync" {
            switch ($Action) {
                "sync" {
                    $args = @("sync_all.py")
                    if ($Date) { $args += @("--date", $Date) }
                    return New-RunPlan -Name "feishu-sync sync" -WorkDir $moduleRoot -Command "python" -Args $args -Risk "sync" -RequiresAllowRemote $true
                }
                "history" {
                    return New-RunPlan -Name "feishu-sync history" -WorkDir $moduleRoot -Command "python" -Args @("sync_history.py") -Risk "sync-history" -RequiresAllowRemote $true
                }
                "help" {
                    return New-RunPlan -Name "feishu-sync help" -WorkDir $moduleRoot -Command "python" -Args @("sync_all.py", "--help") -Risk "help" -RequiresAllowRemote $false
                }
                "check" {
                    return New-RunPlan -Name "feishu-sync check" -WorkDir $moduleRoot -Command "python" -Args @("-m", "compileall", ".") -Risk "local-check" -RequiresAllowRemote $false
                }
            }
        }
        "overseas-casual" {
            switch ($Action) {
                "fetch" {
                    $args = @("main.py")
                    if ($Date) { $args += @("--date", $Date) }
                    return New-RunPlan -Name "overseas-casual fetch" -WorkDir $moduleRoot -Command "python" -Args $args -Risk "fetch" -RequiresAllowRemote $false
                }
                "send" {
                    $args = @("send_feishu_report.py")
                    if ($Test) { $args += "--test" }
                    return New-RunPlan -Name "overseas-casual send" -WorkDir $moduleRoot -Command "python" -Args $args -Risk "send" -RequiresAllowRemote $true
                }
                "test" {
                    return New-RunPlan -Name "overseas-casual test" -WorkDir $moduleRoot -Command "python" -Args @("-m", "unittest", "discover", "-s", "tests") -Risk "local-check" -RequiresAllowRemote $false
                }
                "help" {
                    return New-RunPlan -Name "overseas-casual help" -WorkDir $moduleRoot -Command "python" -Args @("send_feishu_report.py", "--help") -Risk "help" -RequiresAllowRemote $false
                }
            }
        }
        "meme-hotspot" {
            switch ($Action) {
                "fetch" {
                    $args = @("main.py")
                    if ($Date) { $args += @("--date", $Date) }
                    return New-RunPlan -Name "meme-hotspot fetch" -WorkDir $moduleRoot -Command "python" -Args $args -Risk "fetch" -RequiresAllowRemote $false
                }
                "judge" {
                    $args = @("judge_material.py")
                    if ($Date) { $args += @("--date", $Date) }
                    return New-RunPlan -Name "meme-hotspot judge" -WorkDir $moduleRoot -Command "python" -Args $args -Risk "fetch-or-llm" -RequiresAllowRemote $false
                }
                "help" {
                    return New-RunPlan -Name "meme-hotspot help" -WorkDir $moduleRoot -Command "python" -Args @("main.py", "--help") -Risk "help" -RequiresAllowRemote $false
                }
            }
        }
    }

    throw "Unsupported action '$Action' for module '$Module'."
}

try {
    $plan = Get-RunPlan
} catch {
    Write-Host "[ERROR] $($_.Exception.Message)"
    exit 2
}

if ($Test -and $Action -ne "send") {
    Write-Host "[ERROR] -Test is only valid for send actions."
    exit 2
}

$commandLine = Format-CommandLine -Command $plan.Command -Args $plan.Args

Write-Host "Module: $Module"
Write-Host "Action: $Action"
Write-Host "WorkDir: $($plan.WorkDir)"
Write-Host "Command: $commandLine"
Write-Host "Risk: $($plan.Risk)"
Write-Host "Requires -Execute: yes"
Write-Host ("Requires -AllowRemote: " + ($(if ($plan.RequiresAllowRemote) { "yes" } else { "no" })))

if (-not $Execute) {
    Write-Host ""
    Write-Host "Preview only. Re-run with -Execute to execute this command."
    if ($plan.RequiresAllowRemote) {
        Write-Host "This action may write to a remote service. Re-run with both -Execute and -AllowRemote to execute."
    }
    exit 0
}

if ($plan.RequiresAllowRemote -and -not $AllowRemote) {
    Write-Host ""
    Write-Host "[REFUSED] This action may send or sync to a remote service."
    Write-Host "Add -AllowRemote together with -Execute if you really want to run it."
    exit 1
}

Write-Host ""
Write-Host "Executing command..."
Push-Location -LiteralPath $plan.WorkDir
try {
    & $plan.Command @($plan.Args)
    $exitCode = $LASTEXITCODE
} finally {
    Pop-Location
}

if ($null -eq $exitCode) {
    exit 0
}
exit $exitCode
