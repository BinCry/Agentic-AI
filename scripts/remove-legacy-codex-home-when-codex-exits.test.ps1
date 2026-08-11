[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$testRoot = Join-Path $repoRoot "tmp-codex-cleanup-test"
$legacyHome = Join-Path $testRoot "legacy-home"
$targetHome = Join-Path $testRoot "target-home"
$cleanupScript = Join-Path $PSScriptRoot "remove-legacy-codex-home-when-codex-exits.ps1"
$cleanupStatusPath = Join-Path $targetHome "claudekit-legacy-codex-home-cleanup-status.json"

function Assert-True {
    param(
        [Parameter(Mandatory = $true)]
        [bool]$Condition,
        [Parameter(Mandatory = $true)]
        [string]$Message
    )

    if (-not $Condition) {
        throw $Message
    }
}

try {
    if (Test-Path -LiteralPath $testRoot) {
        Remove-Item -LiteralPath $testRoot -Force -Recurse
    }

    New-Item -ItemType Directory -Path $legacyHome -Force | Out-Null
    New-Item -ItemType Directory -Path $targetHome -Force | Out-Null
    "old-state" | Set-Content -LiteralPath (Join-Path $legacyHome "marker.txt") -Encoding ASCII
    "legacy-db" | Set-Content -LiteralPath (Join-Path $legacyHome "state_5.sqlite") -Encoding ASCII
    "legacy-index" | Set-Content -LiteralPath (Join-Path $legacyHome "session_index.jsonl") -Encoding ASCII
    New-Item -ItemType Directory -Path (Join-Path $legacyHome "sessions") -Force | Out-Null
    "legacy-session" | Set-Content -LiteralPath (Join-Path $legacyHome "sessions\rollout.jsonl") -Encoding ASCII
    '{"ok":true}' | Set-Content -LiteralPath (Join-Path $targetHome "auth.json") -Encoding ASCII
    "managed-db" | Set-Content -LiteralPath (Join-Path $targetHome "state_5.sqlite") -Encoding ASCII
    "managed-index" | Set-Content -LiteralPath (Join-Path $targetHome "session_index.jsonl") -Encoding ASCII
    New-Item -ItemType Directory -Path (Join-Path $targetHome "sessions") -Force | Out-Null
    "managed-session" | Set-Content -LiteralPath (Join-Path $targetHome "sessions\rollout.jsonl") -Encoding ASCII
    "# managed config" | Set-Content -LiteralPath (Join-Path $targetHome "config.toml") -Encoding ASCII

    & $cleanupScript `
        -LegacyCodexHome $legacyHome `
        -ExpectedCodexHome $targetHome `
        -ConfiguredCodexHome $targetHome `
        -SkipWait `
        -Force

    Assert-True -Condition (-not (Test-Path -LiteralPath $legacyHome)) -Message "Legacy Codex home was not removed."
    Assert-True -Condition (Test-Path -LiteralPath (Join-Path $targetHome "auth.json")) -Message "Migrated auth.json should remain in target home."
    Assert-True -Condition ((Get-Content -LiteralPath (Join-Path $targetHome "state_5.sqlite") -Raw) -eq "legacy-db`r`n") -Message "Cleanup watcher did not sync the latest SQLite state into the target home."
    Assert-True -Condition ((Get-Content -LiteralPath (Join-Path $targetHome "session_index.jsonl") -Raw) -eq "legacy-index`r`n") -Message "Cleanup watcher did not sync the latest session index into the target home."
    Assert-True -Condition ((Get-Content -LiteralPath (Join-Path $targetHome "sessions\rollout.jsonl") -Raw) -eq "legacy-session`r`n") -Message "Cleanup watcher did not sync the latest session files into the target home."
    Assert-True -Condition ((Get-Content -LiteralPath (Join-Path $targetHome "config.toml") -Raw) -eq "# managed config`r`n") -Message "Cleanup watcher should preserve the managed target config."
    Assert-True -Condition (Test-Path -LiteralPath $cleanupStatusPath) -Message "Cleanup watcher did not persist a cleanup status file."
    $cleanupStatus = Get-Content -LiteralPath $cleanupStatusPath -Raw | ConvertFrom-Json
    Assert-True -Condition ($cleanupStatus.state -eq "completed") -Message "Cleanup watcher did not record a completed cleanup status."

    Write-Host "remove-legacy-codex-home-when-codex-exits: PASS"
} finally {
    if (Test-Path -LiteralPath $testRoot) {
        Remove-Item -LiteralPath $testRoot -Force -Recurse
    }
}
