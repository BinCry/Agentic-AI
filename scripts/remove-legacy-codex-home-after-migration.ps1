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

$legacyHome = Resolve-NormalizedPath -Path $LegacyCodexHome -AllowMissing
$expectedHome = Resolve-NormalizedPath -Path $ExpectedCodexHome

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
    Write-Host "Legacy Codex home is already absent: $legacyHome" -ForegroundColor Yellow
    return
}

Remove-Item -LiteralPath $legacyHome -Force -Recurse
Write-Host "Removed legacy Codex home: $legacyHome" -ForegroundColor Green
