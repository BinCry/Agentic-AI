[CmdletBinding()]
param(
    [string]$LegacyCodexHome = (Join-Path $HOME ".codex"),
    [string]$ExpectedCodexHome = "D:\CodexHome",
    [string]$ConfiguredCodexHome = "",
    [int]$PollIntervalSeconds = 5,
    [switch]$SkipWait,
    [switch]$Force
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "claude-kit-codex-utils.ps1")
. (Join-Path $PSScriptRoot "claude-kit-codex-cleanup-status-utils.ps1")

if ($PollIntervalSeconds -lt 1) {
    throw "PollIntervalSeconds must be at least 1."
}

Set-CodexLegacyCleanupStatus `
    -ExpectedCodexHome $ExpectedCodexHome `
    -LegacyCodexHome $LegacyCodexHome `
    -State "waiting" `
    -Message $(if ($SkipWait) { "Cleanup watcher is attempting immediate legacy home removal." } else { "Cleanup watcher is waiting for Codex to exit before removing the legacy home." }) `
    -WatcherPid $PID | Out-Null

if (-not $SkipWait) {
    while (Get-Process codex -ErrorAction SilentlyContinue) {
        Write-Host "Codex is still running. Waiting $PollIntervalSeconds second(s) before retrying cleanup..." -ForegroundColor Yellow
        Start-Sleep -Seconds $PollIntervalSeconds
    }
}

& (Join-Path $PSScriptRoot "remove-legacy-codex-home-after-migration.ps1") `
    -LegacyCodexHome $LegacyCodexHome `
    -ExpectedCodexHome $ExpectedCodexHome `
    -ConfiguredCodexHome $ConfiguredCodexHome `
    -Force:$Force
