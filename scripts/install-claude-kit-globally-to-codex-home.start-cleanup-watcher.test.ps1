[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$testRoot = Join-Path $repoRoot "tmp-codex-installer-watcher-test"
$legacyHome = Join-Path $testRoot "legacy-home"
$invalidLegacyHome = Join-Path $testRoot "legacy-home-invalid"
$targetHome = Join-Path $testRoot "target-home"
$installerPath = Join-Path $PSScriptRoot "install-claude-kit-globally-to-codex-home.ps1"
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

    New-Item -ItemType Directory -Path (Join-Path $legacyHome "skills\.system") -Force | Out-Null
    New-Item -ItemType Directory -Path $targetHome -Force | Out-Null

    @'
model = "gpt-5.4"

[projects."d:\demo"]
trust_level = "trusted"
'@ | Set-Content -LiteralPath (Join-Path $legacyHome "config.toml") -Encoding ASCII

    '{"ok":true}' | Set-Content -LiteralPath (Join-Path $legacyHome "auth.json") -Encoding ASCII
    "legacy-agents" | Set-Content -LiteralPath (Join-Path $legacyHome "AGENTS.md") -Encoding ASCII
    "keep-system" | Set-Content -LiteralPath (Join-Path $legacyHome "skills\.system\marker.txt") -Encoding ASCII
    Copy-Item -LiteralPath (Join-Path $legacyHome "config.toml") -Destination (Join-Path $targetHome "config.toml") -Force
    Copy-Item -LiteralPath (Join-Path $legacyHome "auth.json") -Destination (Join-Path $targetHome "auth.json") -Force

    $installResult = & $installerPath `
        -TargetCodexHome $targetHome `
        -LegacyCodexHome $legacyHome `
        -ClaudeKitPath $repoRoot `
        -SkipStateMigration `
        -StartCleanupWatcher `
        -CleanupWatcherSkipWait `
        -CleanupWatcherForce `
        -PassThru

    Assert-True -Condition ($installResult.cleanupWatcherStarted -eq $true) -Message "Installer did not report a launched cleanup watcher."
    Assert-True -Condition ($installResult.cleanupWatcherPid -is [int]) -Message "Installer did not return a cleanup watcher PID."
    Assert-True -Condition ($installResult.cleanupWatcherPid -gt 0) -Message "Installer returned an invalid cleanup watcher PID."
    Assert-True -Condition ([Environment]::GetEnvironmentVariable("CODEX_HOME", "User") -eq $targetHome) -Message "Installer did not update user CODEX_HOME to target home."
    Assert-True -Condition ($installResult.environmentChangeSupported -eq $true) -Message "Global installer should report Windows environment broadcast support."
    Assert-True -Condition ($installResult.environmentChangeBroadcasted -eq $true) -Message "Global installer did not report a successful environment broadcast."
    Assert-True -Condition (Test-Path -LiteralPath (Join-Path $targetHome "auth.json")) -Message "Migrated auth.json should remain in target home."

    New-Item -ItemType Directory -Path $invalidLegacyHome -Force | Out-Null
    $invalidCombinationFailed = $false
    try {
        & $installerPath `
            -TargetCodexHome $targetHome `
            -LegacyCodexHome $invalidLegacyHome `
            -ClaudeKitPath $repoRoot `
            -SkipStateMigration `
            -SkipEnvironmentUpdate `
            -StartCleanupWatcher | Out-Null
    } catch {
        $invalidCombinationFailed = $_.Exception.Message.Contains("Cannot use -StartCleanupWatcher together with -SkipEnvironmentUpdate.")
    }

    Assert-True -Condition $invalidCombinationFailed -Message "Installer did not block -StartCleanupWatcher with -SkipEnvironmentUpdate."

    Write-Host "install-claude-kit-globally-to-codex-home.start-cleanup-watcher: PASS"
} finally {
    [Environment]::SetEnvironmentVariable("CODEX_HOME", $originalCodexHome, "User")
    if (Test-Path -LiteralPath $testRoot) {
        Remove-Item -LiteralPath $testRoot -Force -Recurse
    }
}
