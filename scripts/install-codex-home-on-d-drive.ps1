[CmdletBinding()]
param(
    [string]$TargetCodexHome = "D:\CodexHome",
    [string]$LegacyCodexHome = (Join-Path $HOME ".codex")
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "claude-kit-codex-utils.ps1")
. (Join-Path $PSScriptRoot "claude-kit-codex-migration-utils.ps1")

$targetHome = Resolve-NormalizedPath -Path $TargetCodexHome -AllowMissing
$legacyHome = Resolve-NormalizedPath -Path $LegacyCodexHome -AllowMissing
$syncResult = Sync-CodexHomeState `
    -LegacyCodexHomePath $legacyHome `
    -TargetCodexHomePath $targetHome `
    -IncludeUserConfigFiles
$hasLegacyHome = $syncResult.legacyExists

[Environment]::SetEnvironmentVariable("CODEX_HOME", $targetHome, "User")
$env:CODEX_HOME = $targetHome

Write-Host "CODEX_HOME migrated to $targetHome" -ForegroundColor Green
if ($hasLegacyHome) {
    Write-Host "Important state copied: config, auth, plugins, cache, sessions, SQLite state, and indexes."
} else {
    Write-Host "No legacy Codex home found at $legacyHome. Initialized a fresh CODEX_HOME instead."
}
Write-Host "Claude-Kit skills are intentionally NOT copied into global CODEX_HOME."
Write-Host "Close and reopen VS Code/Codex so new sessions stop using $legacyHome."
Write-Host "After restart, verify with: codex doctor"
