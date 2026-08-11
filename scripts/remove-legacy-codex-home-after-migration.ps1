[CmdletBinding()]
param(
    [string]$LegacyCodexHome = (Join-Path $HOME ".codex"),
    [string]$ExpectedCodexHome = "D:\CodexHome",
    [string]$ConfiguredCodexHome = "",
    [switch]$Force
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "claude-kit-codex-utils.ps1")
. (Join-Path $PSScriptRoot "claude-kit-codex-migration-utils.ps1")
. (Join-Path $PSScriptRoot "claude-kit-codex-cleanup-status-utils.ps1")

try {
    $legacyHome = Resolve-NormalizedPath -Path $LegacyCodexHome -AllowMissing
    $expectedHome = Resolve-NormalizedPath -Path $ExpectedCodexHome
    $statusPath = Get-CodexLegacyCleanupStatusPath -ExpectedCodexHome $expectedHome

    if ([string]::IsNullOrWhiteSpace($ConfiguredCodexHome)) {
        $configuredHome = [Environment]::GetEnvironmentVariable("CODEX_HOME", "User")
    } else {
        $configuredHome = $ConfiguredCodexHome
    }

    if ([string]::IsNullOrWhiteSpace($configuredHome)) {
        throw "Configured CODEX_HOME is empty. Migration is not complete yet."
    }

    $normalizedConfiguredHome = Resolve-NormalizedPath -Path $configuredHome
    if ($normalizedConfiguredHome -ne $expectedHome) {
        throw "Configured CODEX_HOME points to $normalizedConfiguredHome, not $expectedHome."
    }

    if (-not $Force) {
        $activeCodex = Get-Process codex -ErrorAction SilentlyContinue
        if ($activeCodex) {
            throw "Codex is still running. Close VS Code/Codex first, then rerun this cleanup script."
        }
    }

    if (-not (Test-Path -LiteralPath (Join-Path $expectedHome "auth.json"))) {
        throw "Expected migrated auth.json was not found in $expectedHome."
    }

    if (-not (Test-Path -LiteralPath $legacyHome)) {
        Set-CodexLegacyCleanupStatus `
            -ExpectedCodexHome $expectedHome `
            -LegacyCodexHome $legacyHome `
            -State "completed" `
            -Message "Legacy Codex home was already absent." | Out-Null
        Write-Host "Legacy Codex home is already absent: $legacyHome" -ForegroundColor Yellow
        Write-Host ("Cleanup status file: " + $statusPath)
        return
    }

    $finalSyncResult = Sync-CodexHomeState `
        -LegacyCodexHomePath $legacyHome `
        -TargetCodexHomePath $expectedHome

    Remove-Item -LiteralPath $legacyHome -Force -Recurse
    Set-CodexLegacyCleanupStatus `
        -ExpectedCodexHome $expectedHome `
        -LegacyCodexHome $legacyHome `
        -State "completed" `
        -Message "Legacy Codex home was synced and removed successfully." | Out-Null
    Write-Host ("Final state sync copied " + $finalSyncResult.files.Count + " file(s) and " + $finalSyncResult.directories.Count + " directorie(s).")
    Write-Host "Removed legacy Codex home: $legacyHome" -ForegroundColor Green
    Write-Host ("Cleanup status file: " + $statusPath)
} catch {
    try {
        Set-CodexLegacyCleanupStatus `
            -ExpectedCodexHome $ExpectedCodexHome `
            -LegacyCodexHome $LegacyCodexHome `
            -State "failed" `
            -Message ("Legacy cleanup failed: " + $_.Exception.Message) | Out-Null
    } catch {
        # Preserve the original cleanup error when status persistence also fails.
    }
    throw
}
