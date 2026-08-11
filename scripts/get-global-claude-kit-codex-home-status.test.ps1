[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$testRoot = Join-Path $repoRoot "tmp-codex-status-test"
$legacyHome = Join-Path $testRoot "legacy-home"
$targetHome = Join-Path $testRoot "target-home"
$installerPath = Join-Path $PSScriptRoot "install-claude-kit-globally-to-codex-home.ps1"
$statusPath = Join-Path $PSScriptRoot "get-global-claude-kit-codex-home-status.ps1"

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

[agents.subagent]
model = "cx/gpt-5.5"
'@ | Set-Content -LiteralPath (Join-Path $legacyHome "config.toml") -Encoding ASCII

    '{"ok":true}' | Set-Content -LiteralPath (Join-Path $legacyHome "auth.json") -Encoding ASCII
    "legacy-agents" | Set-Content -LiteralPath (Join-Path $legacyHome "AGENTS.md") -Encoding ASCII
    "keep-system" | Set-Content -LiteralPath (Join-Path $legacyHome "skills\.system\marker.txt") -Encoding ASCII

    Copy-Item -LiteralPath (Join-Path $legacyHome "config.toml") -Destination (Join-Path $targetHome "config.toml") -Force
    Copy-Item -LiteralPath (Join-Path $legacyHome "auth.json") -Destination (Join-Path $targetHome "auth.json") -Force

    & $installerPath `
        -TargetCodexHome $targetHome `
        -LegacyCodexHome $legacyHome `
        -ClaudeKitPath $repoRoot `
        -SkipStateMigration `
        -SkipEnvironmentUpdate

    $restartStatus = & $statusPath `
        -TargetCodexHome $targetHome `
        -LegacyCodexHome $legacyHome `
        -ClaudeKitPath $repoRoot `
        -ConfiguredCodexHome $targetHome `
        -ProcessCodexHome $legacyHome `
        -CodexProcessCountOverride 1 `
        -CleanupWatcherCountOverride 0 `
        -PassThru

    Assert-True -Condition $restartStatus.globalInstallHealthy -Message "Expected healthy global install status for installed fixture."
    Assert-True -Condition $restartStatus.restartRequired -Message "Expected restartRequired when process CODEX_HOME still points to legacy home."
    Assert-True -Condition (-not $restartStatus.canRemoveLegacyHomeNow) -Message "Legacy home should not be removable while Codex is still considered running."
    Assert-True -Condition ($restartStatus.cleanupWatcherStatus -eq "not-running") -Message "Expected cleanup watcher status to report not-running."
    Assert-True -Condition ($restartStatus.doctorCheckStatus -eq "not-run") -Message "Doctor check should stay opt-in by default."

    $doctorMismatchStatus = & $statusPath `
        -TargetCodexHome $targetHome `
        -LegacyCodexHome $legacyHome `
        -ClaudeKitPath $repoRoot `
        -ConfiguredCodexHome $targetHome `
        -ProcessCodexHome $targetHome `
        -CodexProcessCountOverride 1 `
        -CleanupWatcherCountOverride 0 `
        -RunCodexDoctor `
        -DoctorCodexHomeOverride $legacyHome `
        -PassThru

    Assert-True -Condition $doctorMismatchStatus.restartRequired -Message "Expected doctor mismatch to force restartRequired even when process CODEX_HOME matches target."
    Assert-True -Condition ($doctorMismatchStatus.doctorCheckStatus -eq "mismatch") -Message "Expected doctor check to report mismatch."
    Assert-True -Condition ($doctorMismatchStatus.doctorCodexHome -eq $legacyHome) -Message "Expected doctor check to report the legacy home path."
    Assert-True -Condition $doctorMismatchStatus.doctorConfigHasLegacySubagentBlock -Message "Expected doctor config check to detect the legacy [agents.subagent] block."

    $cleanupReadyStatus = & $statusPath `
        -TargetCodexHome $targetHome `
        -LegacyCodexHome $legacyHome `
        -ClaudeKitPath $repoRoot `
        -ConfiguredCodexHome $targetHome `
        -ProcessCodexHome $targetHome `
        -CodexProcessCountOverride 0 `
        -CleanupWatcherCountOverride 1 `
        -RunCodexDoctor `
        -DoctorCodexHomeOverride $targetHome `
        -PassThru

    Assert-True -Condition $cleanupReadyStatus.globalInstallHealthy -Message "Expected healthy global install status before cleanup."
    Assert-True -Condition (-not $cleanupReadyStatus.restartRequired) -Message "Did not expect restartRequired once process CODEX_HOME matches target."
    Assert-True -Condition $cleanupReadyStatus.canRemoveLegacyHomeNow -Message "Expected legacy cleanup to be safe once Codex is no longer running."
    Assert-True -Condition ($cleanupReadyStatus.cleanupWatcherStatus -eq "running") -Message "Expected cleanup watcher status to report running."
    Assert-True -Condition ($cleanupReadyStatus.doctorCheckStatus -eq "matched") -Message "Expected doctor check to report matched when doctor uses the target home."
    Assert-True -Condition $cleanupReadyStatus.doctorMatchesTarget -Message "Expected doctor check to confirm the target home."
    Assert-True -Condition (-not $cleanupReadyStatus.doctorConfigHasLegacySubagentBlock) -Message "Did not expect the normalized target config to keep the legacy [agents.subagent] block."
    Assert-True -Condition ($cleanupReadyStatus.installBackupCount -ge 1) -Message "Expected at least one install backup snapshot."
    Assert-True -Condition $cleanupReadyStatus.systemSkillsPreserved -Message "Expected built-in .system skills to remain present."

    Write-Host "get-global-claude-kit-codex-home-status: PASS"
} finally {
    if (Test-Path -LiteralPath $testRoot) {
        Remove-Item -LiteralPath $testRoot -Force -Recurse
    }
}
