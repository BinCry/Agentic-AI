[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$testRoot = Join-Path $repoRoot "tmp-codex-final-cleanup-test"
$cleanupScript = Join-Path $PSScriptRoot "remove-legacy-codex-home-after-migration.ps1"

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

    $successLegacyHome = Join-Path $testRoot "success-legacy-home"
    $successTargetHome = Join-Path $testRoot "success-target-home"
    $successStatusPath = Join-Path $successTargetHome "claudekit-legacy-codex-home-cleanup-status.json"

    New-Item -ItemType Directory -Path $successLegacyHome -Force | Out-Null
    New-Item -ItemType Directory -Path $successTargetHome -Force | Out-Null
    "old-state" | Set-Content -LiteralPath (Join-Path $successLegacyHome "marker.txt") -Encoding ASCII
    '{"ok":true}' | Set-Content -LiteralPath (Join-Path $successTargetHome "auth.json") -Encoding ASCII

    & $cleanupScript `
        -LegacyCodexHome $successLegacyHome `
        -ExpectedCodexHome $successTargetHome `
        -ConfiguredCodexHome $successTargetHome `
        -Force

    Assert-True -Condition (-not (Test-Path -LiteralPath $successLegacyHome)) -Message "Cleanup script did not remove the legacy home on the success path."
    Assert-True -Condition (Test-Path -LiteralPath $successStatusPath) -Message "Cleanup script did not persist a cleanup status file on the success path."
    $successStatus = Get-Content -LiteralPath $successStatusPath -Raw | ConvertFrom-Json
    Assert-True -Condition ($successStatus.state -eq "completed") -Message "Cleanup script did not record a completed status after removing the legacy home."
    Assert-True -Condition ($successStatus.message -like "*removed successfully*") -Message "Cleanup script did not record the expected success message."

    & $cleanupScript `
        -LegacyCodexHome $successLegacyHome `
        -ExpectedCodexHome $successTargetHome `
        -ConfiguredCodexHome $successTargetHome `
        -Force

    $alreadyAbsentStatus = Get-Content -LiteralPath $successStatusPath -Raw | ConvertFrom-Json
    Assert-True -Condition ($alreadyAbsentStatus.state -eq "completed") -Message "Cleanup script did not keep a completed status when the legacy home was already absent."
    Assert-True -Condition ($alreadyAbsentStatus.message -like "*already absent*") -Message "Cleanup script did not record the expected already-absent message."

    $failedLegacyHome = Join-Path $testRoot "failed-legacy-home"
    $failedTargetHome = Join-Path $testRoot "failed-target-home"
    $failedStatusPath = Join-Path $failedTargetHome "claudekit-legacy-codex-home-cleanup-status.json"

    New-Item -ItemType Directory -Path $failedLegacyHome -Force | Out-Null
    New-Item -ItemType Directory -Path $failedTargetHome -Force | Out-Null
    "old-state" | Set-Content -LiteralPath (Join-Path $failedLegacyHome "marker.txt") -Encoding ASCII
    '{"ok":true}' | Set-Content -LiteralPath (Join-Path $failedTargetHome "auth.json") -Encoding ASCII

    $mismatchFailed = $false
    try {
        & $cleanupScript `
            -LegacyCodexHome $failedLegacyHome `
            -ExpectedCodexHome $failedTargetHome `
            -ConfiguredCodexHome $failedLegacyHome `
            -Force | Out-Null
    } catch {
        $mismatchFailed = $_.Exception.Message.Contains("Configured CODEX_HOME points to")
    }

    Assert-True -Condition $mismatchFailed -Message "Cleanup script did not fail when ConfiguredCodexHome pointed at the wrong path."
    Assert-True -Condition (Test-Path -LiteralPath $failedLegacyHome) -Message "Cleanup script should not remove the legacy home when validation fails before cleanup."
    Assert-True -Condition (Test-Path -LiteralPath $failedStatusPath) -Message "Cleanup script did not persist a cleanup status file on the failure path."
    $failedStatus = Get-Content -LiteralPath $failedStatusPath -Raw | ConvertFrom-Json
    Assert-True -Condition ($failedStatus.state -eq "failed") -Message "Cleanup script did not record a failed cleanup status."
    Assert-True -Condition ($failedStatus.message -like "*Configured CODEX_HOME points to*") -Message "Cleanup script did not record the expected mismatch failure message."

    Write-Host "remove-legacy-codex-home-after-migration: PASS"
} finally {
    if (Test-Path -LiteralPath $testRoot) {
        Remove-Item -LiteralPath $testRoot -Force -Recurse
    }
}
