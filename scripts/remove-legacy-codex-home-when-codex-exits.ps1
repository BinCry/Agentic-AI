[CmdletBinding()]
param(
    [string]$LegacyCodexHome = (Join-Path $HOME ".codex"),
    [string]$ExpectedCodexHome = "D:\CodexHome",
    [int]$PollIntervalSeconds = 5,
    [switch]$SkipWait,
    [switch]$Force
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if ($PollIntervalSeconds -lt 1) {
    throw "PollIntervalSeconds must be at least 1."
}

if (-not $SkipWait) {
    while (Get-Process codex -ErrorAction SilentlyContinue) {
        Write-Host "Codex is still running. Waiting $PollIntervalSeconds second(s) before retrying cleanup..." -ForegroundColor Yellow
        Start-Sleep -Seconds $PollIntervalSeconds
    }
}

& (Join-Path $PSScriptRoot "remove-legacy-codex-home-after-migration.ps1") `
    -LegacyCodexHome $LegacyCodexHome `
    -ExpectedCodexHome $ExpectedCodexHome `
    -Force:$Force
