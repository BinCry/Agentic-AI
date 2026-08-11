[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$testRoot = Join-Path $repoRoot "tmp-codex-cleanup-test"
$legacyHome = Join-Path $testRoot "legacy-home"
$targetHome = Join-Path $testRoot "target-home"
$cleanupScript = Join-Path $PSScriptRoot "remove-legacy-codex-home-when-codex-exits.ps1"
$originalCodexHome = [Environment]::GetEnvironmentVariable("CODEX_HOME", "User")

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

    [Environment]::SetEnvironmentVariable("CODEX_HOME", $targetHome, "User")

    & $cleanupScript `
        -LegacyCodexHome $legacyHome `
        -ExpectedCodexHome $targetHome `
        -SkipWait `
        -Force

    Assert-True -Condition (-not (Test-Path -LiteralPath $legacyHome)) -Message "Legacy Codex home was not removed."
    Assert-True -Condition (Test-Path -LiteralPath (Join-Path $targetHome "auth.json")) -Message "Migrated auth.json should remain in target home."

    Write-Host "remove-legacy-codex-home-when-codex-exits: PASS"
} finally {
    [Environment]::SetEnvironmentVariable("CODEX_HOME", $originalCodexHome, "User")
    if (Test-Path -LiteralPath $testRoot) {
        Remove-Item -LiteralPath $testRoot -Force -Recurse
    }
}
