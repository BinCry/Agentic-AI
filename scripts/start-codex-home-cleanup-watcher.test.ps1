[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$testRoot = Join-Path $repoRoot "tmp-codex-cleanup-launcher-test"
$legacyHome = Join-Path $testRoot "legacy-home"
$targetHome = Join-Path $testRoot "target-home"
$launcherScript = Join-Path $PSScriptRoot "start-codex-home-cleanup-watcher.ps1"

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

    $launchResult = & $launcherScript `
        -LegacyCodexHome $legacyHome `
        -ExpectedCodexHome $targetHome `
        -SkipWait `
        -Force

    $cleanupProcess = Get-Process -Id $launchResult.pid -ErrorAction Stop
    $null = $cleanupProcess.WaitForExit(15000)

    Assert-True -Condition $cleanupProcess.HasExited -Message "Background cleanup watcher did not exit in time."
    Assert-True -Condition (-not (Test-Path -LiteralPath $legacyHome)) -Message "Legacy Codex home was not removed by launcher-started watcher."
    Assert-True -Condition (Test-Path -LiteralPath (Join-Path $targetHome "auth.json")) -Message "Migrated auth.json should remain in target home."
    Assert-True -Condition ($launchResult.skipWait -eq $true) -Message "Launcher result did not preserve SkipWait flag."
    Assert-True -Condition ($launchResult.force -eq $true) -Message "Launcher result did not preserve Force flag."

    Write-Host "start-codex-home-cleanup-watcher: PASS"
} finally {
    if (Test-Path -LiteralPath $testRoot) {
        Remove-Item -LiteralPath $testRoot -Force -Recurse
    }
}
