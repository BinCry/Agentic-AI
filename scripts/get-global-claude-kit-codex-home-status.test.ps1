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

. (Join-Path $PSScriptRoot "claude-kit-codex-utils.ps1")
. (Join-Path $PSScriptRoot "claude-kit-codex-cleanup-status-utils.ps1")

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
    "legacy-index" | Set-Content -LiteralPath (Join-Path $legacyHome "session_index.jsonl") -Encoding ASCII

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
    Assert-True -Condition (-not $restartStatus.legacyCleanupManagedByWatcher) -Message "Did not expect watcher-managed cleanup when the watcher is not running."
    Assert-True -Condition ($restartStatus.legacyCleanupState -eq "absent") -Message "Did not expect a persisted cleanup status before the watcher was started."
    Assert-True -Condition ($restartStatus.doctorCheckStatus -eq "not-run") -Message "Doctor check should stay opt-in by default."
    Assert-True -Condition ($restartStatus.migrationMissingArtifactCount -eq 1) -Message "Expected one missing migrated artifact before rerunning migration."
    Assert-True -Condition ($restartStatus.migrationMissingArtifacts -contains "session_index.jsonl") -Message "Expected missing migrated artifact list to include session_index.jsonl."

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

    $watcherInferredStatus = & $statusPath `
        -TargetCodexHome $targetHome `
        -LegacyCodexHome $legacyHome `
        -ClaudeKitPath $repoRoot `
        -ConfiguredCodexHome $targetHome `
        -ProcessCodexHome $targetHome `
        -CodexProcessCountOverride 1 `
        -CleanupWatcherCountOverride 1 `
        -PassThru

    Assert-True -Condition ($watcherInferredStatus.legacyCleanupState -eq "waiting") -Message "Expected running cleanup watcher to infer a waiting cleanup state even before the status file exists."

    Copy-Item -LiteralPath (Join-Path $legacyHome "session_index.jsonl") -Destination (Join-Path $targetHome "session_index.jsonl") -Force
    Set-CodexLegacyCleanupStatus `
        -ExpectedCodexHome $targetHome `
        -LegacyCodexHome $legacyHome `
        -State "waiting" `
        -Message "Cleanup watcher is waiting for Codex to exit before removing the legacy home." `
        -WatcherPid 1234 | Out-Null

    $watcherWaitingStatus = & $statusPath `
        -TargetCodexHome $targetHome `
        -LegacyCodexHome $legacyHome `
        -ClaudeKitPath $repoRoot `
        -ConfiguredCodexHome $targetHome `
        -ProcessCodexHome $targetHome `
        -CodexProcessCountOverride 1 `
        -CleanupWatcherCountOverride 1 `
        -PassThru

    Assert-True -Condition (-not $watcherWaitingStatus.canRemoveLegacyHomeNow) -Message "Did not expect manual cleanup to be safe while Codex is still running."
    Assert-True -Condition ($watcherWaitingStatus.cleanupWatcherStatus -eq "running") -Message "Expected cleanup watcher status to report running while waiting for Codex to exit."
    Assert-True -Condition $watcherWaitingStatus.legacyCleanupManagedByWatcher -Message "Expected watcher-managed cleanup flag while the cleanup watcher is running."
    Assert-True -Condition ($watcherWaitingStatus.legacyCleanupState -eq "waiting") -Message "Expected cleanup status to report waiting while the watcher is still active."
    Assert-True -Condition ($watcherWaitingStatus.legacyCleanupWatcherPid -eq 1234) -Message "Expected cleanup status to preserve the watcher PID."
    Assert-True -Condition ($watcherWaitingStatus.nextStep -like "Close Codex and let the running cleanup watcher*") -Message "Expected next step to tell the user that the running watcher will remove the legacy home automatically."

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
    Assert-True -Condition (-not $cleanupReadyStatus.canRemoveLegacyHomeNow) -Message "Did not expect manual cleanup to be recommended once the cleanup watcher is already running."
    Assert-True -Condition ($cleanupReadyStatus.cleanupWatcherStatus -eq "running") -Message "Expected cleanup watcher status to report running."
    Assert-True -Condition $cleanupReadyStatus.legacyCleanupManagedByWatcher -Message "Expected watcher-managed cleanup flag while the cleanup watcher is still running."
    Assert-True -Condition ($cleanupReadyStatus.doctorCheckStatus -eq "matched") -Message "Expected doctor check to report matched when doctor uses the target home."
    Assert-True -Condition $cleanupReadyStatus.doctorMatchesTarget -Message "Expected doctor check to confirm the target home."
    Assert-True -Condition (-not $cleanupReadyStatus.doctorConfigHasLegacySubagentBlock) -Message "Did not expect the normalized target config to keep the legacy [agents.subagent] block."
    Assert-True -Condition ($cleanupReadyStatus.migrationMissingArtifactCount -eq 0) -Message "Did not expect a migration gap once the missing session index was copied into the target home."
    Assert-True -Condition ($cleanupReadyStatus.installBackupCount -ge 1) -Message "Expected at least one install backup snapshot."
    Assert-True -Condition $cleanupReadyStatus.systemSkillsPreserved -Message "Expected built-in .system skills to remain present."
    Assert-True -Condition ($cleanupReadyStatus.nextStep -like "Wait for the running cleanup watcher*") -Message "Expected next step to prefer waiting for the running cleanup watcher once Codex is no longer running."

    Remove-Item -LiteralPath $legacyHome -Force -Recurse
    Set-CodexLegacyCleanupStatus `
        -ExpectedCodexHome $targetHome `
        -LegacyCodexHome $legacyHome `
        -State "completed" `
        -Message "Legacy Codex home was removed successfully." `
        -WatcherPid 1234 | Out-Null

    $cleanupCompletedStatus = & $statusPath `
        -TargetCodexHome $targetHome `
        -LegacyCodexHome $legacyHome `
        -ClaudeKitPath $repoRoot `
        -ConfiguredCodexHome $targetHome `
        -ProcessCodexHome $targetHome `
        -CodexProcessCountOverride 0 `
        -CleanupWatcherCountOverride 0 `
        -PassThru

    Assert-True -Condition (-not $cleanupCompletedStatus.legacyHomeExists) -Message "Did not expect the legacy home to remain present after completed cleanup."
    Assert-True -Condition ($cleanupCompletedStatus.legacyCleanupState -eq "completed") -Message "Expected cleanup status to report completed once the legacy home was removed."
    Assert-True -Condition ($cleanupCompletedStatus.nextStep -eq "Legacy home cleanup already completed. Global Claude-Kit on D: looks healthy.") -Message "Expected next step to confirm completed legacy cleanup."

    New-Item -ItemType Directory -Path $legacyHome -Force | Out-Null
    "failed-state" | Set-Content -LiteralPath (Join-Path $legacyHome "marker.txt") -Encoding ASCII
    Set-CodexLegacyCleanupStatus `
        -ExpectedCodexHome $targetHome `
        -LegacyCodexHome $legacyHome `
        -State "failed" `
        -Message "Legacy cleanup failed: simulated cleanup error." `
        -WatcherPid 5678 | Out-Null

    $cleanupFailedStatus = & $statusPath `
        -TargetCodexHome $targetHome `
        -LegacyCodexHome $legacyHome `
        -ClaudeKitPath $repoRoot `
        -ConfiguredCodexHome $targetHome `
        -ProcessCodexHome $targetHome `
        -CodexProcessCountOverride 0 `
        -CleanupWatcherCountOverride 0 `
        -PassThru

    Assert-True -Condition $cleanupFailedStatus.legacyHomeExists -Message "Expected legacy home to still exist for the failed cleanup scenario."
    Assert-True -Condition ($cleanupFailedStatus.legacyCleanupState -eq "failed") -Message "Expected cleanup status to report failed for the simulated cleanup error."
    Assert-True -Condition ($cleanupFailedStatus.legacyCleanupWatcherPid -eq 5678) -Message "Expected failed cleanup status to preserve the persisted watcher PID."
    Assert-True -Condition ($cleanupFailedStatus.nextStep -eq ("Review the cleanup failure in " + $cleanupFailedStatus.legacyCleanupStatusFilePath + ", then rerun start-codex-home-cleanup-watcher.ps1 or remove-legacy-codex-home-after-migration.ps1.")) -Message "Expected next step to point the user at the persisted cleanup failure status file."

    Write-Host "get-global-claude-kit-codex-home-status: PASS"
} finally {
    if (Test-Path -LiteralPath $testRoot) {
        Remove-Item -LiteralPath $testRoot -Force -Recurse
    }
}
