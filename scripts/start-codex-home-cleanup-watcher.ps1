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

. (Join-Path $PSScriptRoot "claude-kit-codex-utils.ps1")
. (Join-Path $PSScriptRoot "claude-kit-codex-cleanup-status-utils.ps1")

if ($PollIntervalSeconds -lt 1) {
    throw "PollIntervalSeconds must be at least 1."
}

$watcherScriptPath = Join-Path $PSScriptRoot "remove-legacy-codex-home-when-codex-exits.ps1"
if (-not (Test-Path -LiteralPath $watcherScriptPath)) {
    throw "Cleanup watcher script not found: $watcherScriptPath"
}

$argumentList = @(
    "-NoProfile",
    "-ExecutionPolicy", "Bypass",
    "-File", $watcherScriptPath,
    "-LegacyCodexHome", $LegacyCodexHome,
    "-ExpectedCodexHome", $ExpectedCodexHome,
    "-ConfiguredCodexHome", $ExpectedCodexHome,
    "-PollIntervalSeconds", $PollIntervalSeconds.ToString()
)

if ($SkipWait) {
    $argumentList += "-SkipWait"
}

if ($Force) {
    $argumentList += "-Force"
}

$process = Start-Process -FilePath "powershell.exe" -ArgumentList $argumentList -WindowStyle Hidden -PassThru
$statusFilePath = Set-CodexLegacyCleanupStatus `
    -ExpectedCodexHome $ExpectedCodexHome `
    -LegacyCodexHome $LegacyCodexHome `
    -State "waiting" `
    -Message "Cleanup watcher started and is waiting for Codex to exit before removing the legacy home." `
    -WatcherPid $process.Id

Write-Host "Started Codex cleanup watcher in the background." -ForegroundColor Green
Write-Host ("PID: " + $process.Id)
Write-Host ("Watcher script: " + $watcherScriptPath)
Write-Host ("ExpectedCodexHome: " + $ExpectedCodexHome)
Write-Host ("Cleanup status file: " + $statusFilePath)
if (-not $SkipWait) {
    Write-Host "It will wait until Codex exits before removing the legacy home."
}

[pscustomobject]@{
    pid = $process.Id
    watcherScript = $watcherScriptPath
    legacyCodexHome = $LegacyCodexHome
    expectedCodexHome = $ExpectedCodexHome
    cleanupStatusFilePath = $statusFilePath
    skipWait = [bool]$SkipWait
    force = [bool]$Force
}
