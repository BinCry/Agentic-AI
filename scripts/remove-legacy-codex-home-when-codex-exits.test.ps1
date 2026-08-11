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
    '{"ok":true}' | Set-Content -LiteralPath (Join-Path $targetHome "auth.json") -Encoding ASCII

    & $cleanupScript `
        -LegacyCodexHome $legacyHome `
        -ExpectedCodexHome $targetHome `
        -ConfiguredCodexHome $targetHome `
        -SkipWait `
        -Force

    Assert-True -Condition (-not (Test-Path -LiteralPath $legacyHome)) -Message "Legacy Codex home was not removed."
    Assert-True -Condition (Test-Path -LiteralPath (Join-Path $targetHome "auth.json")) -Message "Migrated auth.json should remain in target home."
    Assert-True -Condition (Test-Path -LiteralPath $cleanupStatusPath) -Message "Cleanup watcher did not persist a cleanup status file."
    $cleanupStatus = Get-Content -LiteralPath $cleanupStatusPath -Raw | ConvertFrom-Json
    Assert-True -Condition ($cleanupStatus.state -eq "completed") -Message "Cleanup watcher did not record a completed cleanup status."

    Write-Host "remove-legacy-codex-home-when-codex-exits: PASS"
} finally {
    if (Test-Path -LiteralPath $testRoot) {
        Remove-Item -LiteralPath $testRoot -Force -Recurse
    }
}
