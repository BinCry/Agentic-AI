[CmdletBinding()]
param(
    [string]$TargetCodexHome = "D:\CodexHome",
    [string]$LegacyCodexHome = (Join-Path $HOME ".codex")
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "claude-kit-codex-utils.ps1")

$targetHome = Resolve-NormalizedPath -Path $TargetCodexHome -AllowMissing
$legacyHome = Resolve-NormalizedPath -Path $LegacyCodexHome -AllowMissing
$hasLegacyHome = Test-Path -LiteralPath $legacyHome

Ensure-Directory -Path $targetHome

$filesToCopy = @(
    "auth.json",
    "config.toml",
    "AGENTS.md",
    "installation_id",
    "cap_sid"
)

$dirsToCopy = @(
    "attachments",
    "cache",
    "mcp-oauth-locks",
    "plugins",
    "sessions",
    "tmp",
    "vendor_imports"
)

foreach ($relativePath in $filesToCopy) {
    if (-not $hasLegacyHome) {
        break
    }

    $sourcePath = Join-Path $legacyHome $relativePath
    if (-not (Test-Path -LiteralPath $sourcePath)) {
        continue
    }

    $targetPath = Join-Path $targetHome $relativePath
    Copy-Item -LiteralPath $sourcePath -Destination $targetPath -Force
}

foreach ($relativePath in $dirsToCopy) {
    if (-not $hasLegacyHome) {
        break
    }

    $sourcePath = Join-Path $legacyHome $relativePath
    if (-not (Test-Path -LiteralPath $sourcePath)) {
        continue
    }

    $targetPath = Join-Path $targetHome $relativePath
    if (Test-Path -LiteralPath $targetPath) {
        Remove-Item -LiteralPath $targetPath -Force -Recurse
    }
    $null = robocopy $sourcePath $targetPath /E /R:1 /W:1 /XJ /NFL /NDL /NJH /NJS /NP
    if ($LASTEXITCODE -gt 7) {
        throw "Robocopy failed for $relativePath with exit code $LASTEXITCODE"
    }
}

[Environment]::SetEnvironmentVariable("CODEX_HOME", $targetHome, "User")
$env:CODEX_HOME = $targetHome

Write-Host "CODEX_HOME migrated to $targetHome" -ForegroundColor Green
if ($hasLegacyHome) {
    Write-Host "Important state copied: config, auth, plugins, cache, sessions."
} else {
    Write-Host "No legacy Codex home found at $legacyHome. Initialized a fresh CODEX_HOME instead."
}
Write-Host "Claude-Kit skills are intentionally NOT copied into global CODEX_HOME."
Write-Host "Close and reopen VS Code/Codex so new sessions stop using $legacyHome."
Write-Host "After restart, verify with: codex doctor"
