[CmdletBinding()]
param(
    [string]$TargetCodexHome = "D:\CodexHome",
    [string]$ClaudeKitPath = "",
    [string]$ConfiguredCodexHome = "",
    [switch]$RunCodexDoctor,
    [switch]$PassThru
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($ClaudeKitPath)) {
    $ClaudeKitPath = Join-Path $PSScriptRoot ".."
}

. (Join-Path $PSScriptRoot "claude-kit-codex-utils.ps1")
. (Join-Path $PSScriptRoot "claude-kit-codex-status-utils.ps1")

$targetHome = Resolve-NormalizedPath -Path $TargetCodexHome -AllowMissing
$kitRoot = Resolve-NormalizedPath -Path $ClaudeKitPath
$resolvedConfiguredHome = $ConfiguredCodexHome
if ([string]::IsNullOrWhiteSpace($resolvedConfiguredHome)) {
    $resolvedConfiguredHome = [Environment]::GetEnvironmentVariable("CODEX_HOME", "User")
}

$results = New-Object System.Collections.Generic.List[object]

function Add-CheckResult {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name,
        [Parameter(Mandatory = $true)]
        [ValidateSet("pass", "fail", "warn")]
        [string]$Status,
        [Parameter(Mandatory = $true)]
        [string]$Detail
    )

    $results.Add([pscustomobject]@{
        name = $Name
        status = $Status
        detail = $Detail
    }) | Out-Null
}

function Test-LinkTarget {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,
        [Parameter(Mandatory = $true)]
        [string]$ExpectedTargetPath,
        [Parameter(Mandatory = $true)]
        [string]$CheckName
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        Add-CheckResult -Name $CheckName -Status "fail" -Detail "Missing path: $Path"
        return
    }

    if (-not (Test-IsReparsePoint -Path $Path)) {
        Add-CheckResult -Name $CheckName -Status "fail" -Detail "Path exists but is not a junction/reparse point: $Path"
        return
    }

    $item = Get-Item -LiteralPath $Path -Force
    $expectedTarget = Resolve-NormalizedPath -Path $ExpectedTargetPath
    $actualTargets = @($item.Target) | Where-Object { -not [string]::IsNullOrWhiteSpace($_) } | ForEach-Object {
        [System.IO.Path]::GetFullPath($_)
    }

    if ($actualTargets -contains $expectedTarget) {
        Add-CheckResult -Name $CheckName -Status "pass" -Detail "Points to $expectedTarget"
        return
    }

    $detail = if ($actualTargets.Count -gt 0) {
        "Targets: " + ($actualTargets -join ", ")
    } else {
        "Target path metadata was empty."
    }
    Add-CheckResult -Name $CheckName -Status "fail" -Detail $detail
}

if ([string]::IsNullOrWhiteSpace($resolvedConfiguredHome)) {
    Add-CheckResult -Name "configured-codex-home" -Status "fail" -Detail "User CODEX_HOME is empty."
} else {
    $normalizedConfiguredHome = Resolve-NormalizedPath -Path $resolvedConfiguredHome -AllowMissing
    if ($normalizedConfiguredHome -eq $targetHome) {
        Add-CheckResult -Name "configured-codex-home" -Status "pass" -Detail "User CODEX_HOME points to $targetHome"
    } else {
        Add-CheckResult -Name "configured-codex-home" -Status "fail" -Detail "User CODEX_HOME points to $normalizedConfiguredHome instead of $targetHome"
    }
}

$normalizedRequestedHome = Resolve-OptionalNormalizedPath -Path $resolvedConfiguredHome

if (Test-Path -LiteralPath $targetHome) {
    Add-CheckResult -Name "target-home-exists" -Status "pass" -Detail "Found $targetHome"
} else {
    Add-CheckResult -Name "target-home-exists" -Status "fail" -Detail "Missing $targetHome"
}

$configPath = Join-Path $targetHome "config.toml"
if (Test-Path -LiteralPath $configPath) {
    $configText = Get-Content -LiteralPath $configPath -Raw
    Add-CheckResult -Name "config-file-exists" -Status "pass" -Detail "Found $configPath"

    if ($configText.Contains("# --- ck-managed-agents-start ---")) {
        Add-CheckResult -Name "config-managed-block" -Status "pass" -Detail "Managed Claude-Kit block present in config.toml"
    } else {
        Add-CheckResult -Name "config-managed-block" -Status "fail" -Detail "Managed Claude-Kit block missing from config.toml"
    }

    if ($configText.Contains("[agents.subagent]")) {
        Add-CheckResult -Name "config-legacy-subagent-block" -Status "fail" -Detail "Legacy [agents.subagent] block still exists."
    } else {
        Add-CheckResult -Name "config-legacy-subagent-block" -Status "pass" -Detail "Legacy [agents.subagent] block was normalized away."
    }
} else {
    Add-CheckResult -Name "config-file-exists" -Status "fail" -Detail "Missing $configPath"
    Add-CheckResult -Name "config-managed-block" -Status "fail" -Detail "Cannot inspect managed block because config.toml is missing."
    Add-CheckResult -Name "config-legacy-subagent-block" -Status "fail" -Detail "Cannot inspect legacy subagent block because config.toml is missing."
}

$hooksJsonPath = Join-Path $targetHome "hooks.json"
if (Test-Path -LiteralPath $hooksJsonPath) {
    Add-CheckResult -Name "hooks-json-exists" -Status "pass" -Detail "Found $hooksJsonPath"
    $hooksBytes = [System.IO.File]::ReadAllBytes($hooksJsonPath)
    $hasBom = $hooksBytes.Length -ge 3 -and $hooksBytes[0] -eq 0xEF -and $hooksBytes[1] -eq 0xBB -and $hooksBytes[2] -eq 0xBF
    if ($hasBom) {
        Add-CheckResult -Name "hooks-json-bom" -Status "fail" -Detail "hooks.json still has a UTF-8 BOM."
    } else {
        Add-CheckResult -Name "hooks-json-bom" -Status "pass" -Detail "hooks.json is UTF-8 without BOM."
    }

    try {
        $hooksJson = Get-Content -LiteralPath $hooksJsonPath -Raw | ConvertFrom-Json
        $hookCommand = $hooksJson.hooks.UserPromptSubmit[0].hooks[0].command
        $expectedHookCommand = 'node "' + (Join-Path $targetHome "hooks\6cbdb017-simplify-gate.cjs") + '"'
        if ($hookCommand -eq $expectedHookCommand) {
            Add-CheckResult -Name "hooks-json-command" -Status "pass" -Detail "hooks.json points at $expectedHookCommand"
        } else {
            Add-CheckResult -Name "hooks-json-command" -Status "fail" -Detail "hooks.json command is '$hookCommand'"
        }
    } catch {
        Add-CheckResult -Name "hooks-json-command" -Status "fail" -Detail ("Failed to parse hooks.json: " + $_.Exception.Message)
    }
} else {
    Add-CheckResult -Name "hooks-json-exists" -Status "fail" -Detail "Missing $hooksJsonPath"
    Add-CheckResult -Name "hooks-json-bom" -Status "fail" -Detail "Cannot inspect BOM because hooks.json is missing."
    Add-CheckResult -Name "hooks-json-command" -Status "fail" -Detail "Cannot inspect hook command because hooks.json is missing."
}

Test-LinkTarget -Path (Join-Path $targetHome "skills\scout") -ExpectedTargetPath (Join-Path $kitRoot ".codex\skills\scout") -CheckName "skills-scout-link"
Test-LinkTarget -Path (Join-Path $targetHome "agents") -ExpectedTargetPath (Join-Path $kitRoot ".codex\agents") -CheckName "agents-link"
Test-LinkTarget -Path (Join-Path $targetHome "hooks") -ExpectedTargetPath (Join-Path $kitRoot ".codex\hooks") -CheckName "hooks-link"

$targetAgentsPath = Join-Path $targetHome "AGENTS.md"
$sourceAgentsPath = Join-Path $kitRoot "AGENTS.md"
if ((Test-Path -LiteralPath $targetAgentsPath) -and (Test-Path -LiteralPath $sourceAgentsPath)) {
    $targetHash = Get-FileSha256 -Path $targetAgentsPath
    $sourceHash = Get-FileSha256 -Path $sourceAgentsPath
    if ($targetHash -eq $sourceHash) {
        Add-CheckResult -Name "agents-file-sync" -Status "pass" -Detail "AGENTS.md content matches repo copy."
    } else {
        Add-CheckResult -Name "agents-file-sync" -Status "fail" -Detail "AGENTS.md content differs from repo copy."
    }
} else {
    Add-CheckResult -Name "agents-file-sync" -Status "fail" -Detail "Cannot compare AGENTS.md because one side is missing."
}

if ($RunCodexDoctor) {
    $doctorStatus = Get-CodexDoctorStatus `
        -TargetHome $targetHome `
        -RequestedHome $resolvedConfiguredHome `
        -RunDoctor

    $doctorDetail = switch ($doctorStatus.status) {
        "matched" {
            "codex doctor reported CODEX_HOME = $($doctorStatus.codexHome) from $($doctorStatus.launchMode) launch."
        }
        "mismatch" {
            "codex doctor reported CODEX_HOME = $($doctorStatus.codexHome) instead of $targetHome from $($doctorStatus.launchMode) launch."
        }
        "command-missing" {
            "codex command was not found on PATH."
        }
        "requested-home-empty" {
            "Cannot run codex doctor because the requested CODEX_HOME was empty."
        }
        "parse-failed" {
            "codex doctor output could not be parsed for CODEX_HOME."
        }
        default {
            "codex doctor check failed with status '$($doctorStatus.status)'."
        }
    }

    Add-CheckResult `
        -Name "codex-doctor" `
        -Status $(if ($doctorStatus.matchesTarget) { "pass" } else { "fail" }) `
        -Detail $doctorDetail
}

$failedChecks = @($results | Where-Object { $_.status -eq "fail" })
foreach ($result in $results) {
    $prefix = switch ($result.status) {
        "pass" { "[PASS]" }
        "warn" { "[WARN]" }
        default { "[FAIL]" }
    }
    Write-Host ($prefix + " " + $result.name + " - " + $result.detail)
}

$summary = [pscustomobject]@{
    allPassed = ($failedChecks.Count -eq 0)
    targetCodexHome = $targetHome
    configuredCodexHome = $resolvedConfiguredHome
    doctorRequestedHome = $normalizedRequestedHome
    doctorCheckStatus = $(if ($RunCodexDoctor) { $doctorStatus.status } else { "not-run" })
    doctorCodexHome = $(if ($RunCodexDoctor) { $doctorStatus.codexHome } else { $null })
    doctorLaunchMode = $(if ($RunCodexDoctor) { $doctorStatus.launchMode } else { "not-run" })
    failedChecks = $failedChecks
    results = $results
}

if ($PassThru) {
    $summary
    return
}

if ($failedChecks.Count -gt 0) {
    throw ("Global Claude-Kit Codex verification failed with " + $failedChecks.Count + " failing check(s).")
}

Write-Host "Global Claude-Kit Codex verification passed." -ForegroundColor Green
