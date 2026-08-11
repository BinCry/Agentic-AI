[CmdletBinding()]
param(
    [string]$TargetCodexHome = "D:\CodexHome",
    [string]$LegacyCodexHome = (Join-Path $HOME ".codex"),
    [string]$ClaudeKitPath = "",
    [string]$ConfiguredCodexHome = "",
    [string]$ProcessCodexHome = "",
    [int]$CodexProcessCountOverride = -1,
    [int]$CleanupWatcherCountOverride = -1,
    [switch]$RunCodexDoctor,
    [string]$DoctorCodexHomeOverride = "",
    [switch]$PassThru
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($ClaudeKitPath)) {
    $ClaudeKitPath = Join-Path $PSScriptRoot ".."
}
. (Join-Path $PSScriptRoot "claude-kit-codex-utils.ps1")
. (Join-Path $PSScriptRoot "claude-kit-codex-cleanup-status-utils.ps1")
. (Join-Path $PSScriptRoot "claude-kit-codex-status-utils.ps1")

function Test-LinkMatches {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,
        [Parameter(Mandatory = $true)]
        [string]$ExpectedTargetPath
    )
    $expectedTarget = Resolve-NormalizedPath -Path $ExpectedTargetPath
    if (-not (Test-Path -LiteralPath $Path)) {
        return [pscustomobject]@{ exists = $false; isReparsePoint = $false; matches = $false; expectedTarget = $expectedTarget; actualTargets = @() }
    }
    if (-not (Test-IsReparsePoint -Path $Path)) {
        return [pscustomobject]@{ exists = $true; isReparsePoint = $false; matches = $false; expectedTarget = $expectedTarget; actualTargets = @() }
    }
    $item = Get-Item -LiteralPath $Path -Force
    $actualTargets = @($item.Target) | Where-Object { -not [string]::IsNullOrWhiteSpace($_) } | ForEach-Object {
        [System.IO.Path]::GetFullPath($_)
    }
    return [pscustomobject]@{ exists = $true; isReparsePoint = $true; matches = ($actualTargets -contains $expectedTarget); expectedTarget = $expectedTarget; actualTargets = $actualTargets }
}

function Test-ManagedHooksJson {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,
        [Parameter(Mandatory = $true)]
        [string]$CodexHomePath
    )
    $expectedCommand = 'node "' + (Join-Path $CodexHomePath "hooks\6cbdb017-simplify-gate.cjs") + '"'
    if (-not (Test-Path -LiteralPath $Path)) {
        return [pscustomobject]@{ exists = $false; isManaged = $false; expectedCommand = $expectedCommand; actualCommand = $null }
    }

    try {
        $hooksJson = Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json
        $actualCommand = $hooksJson.hooks.UserPromptSubmit[0].hooks[0].command
        $isManaged = ($hooksJson.description -eq "Global Claude-Kit Codex hooks") -and ($actualCommand -eq $expectedCommand)
        return [pscustomobject]@{ exists = $true; isManaged = $isManaged; expectedCommand = $expectedCommand; actualCommand = $actualCommand }
    } catch {
        return [pscustomobject]@{ exists = $true; isManaged = $false; expectedCommand = $expectedCommand; actualCommand = $null }
    }
}

$targetHome = Resolve-NormalizedPath -Path $TargetCodexHome -AllowMissing
$legacyHome = Resolve-NormalizedPath -Path $LegacyCodexHome -AllowMissing
$kitRoot = Resolve-NormalizedPath -Path $ClaudeKitPath
$resolvedConfiguredHome = if ([string]::IsNullOrWhiteSpace($ConfiguredCodexHome)) { [Environment]::GetEnvironmentVariable("CODEX_HOME", "User") } else { $ConfiguredCodexHome }
$resolvedProcessHome = if ([string]::IsNullOrWhiteSpace($ProcessCodexHome)) { $env:CODEX_HOME } else { $ProcessCodexHome }
$normalizedConfiguredHome = Resolve-OptionalNormalizedPath -Path $resolvedConfiguredHome
$normalizedProcessHome = Resolve-OptionalNormalizedPath -Path $resolvedProcessHome

$targetExists = Test-Path -LiteralPath $targetHome
$legacyExists = Test-Path -LiteralPath $legacyHome
$authExists = Test-Path -LiteralPath (Join-Path $targetHome "auth.json")
$configPath = Join-Path $targetHome "config.toml"
$configExists = Test-Path -LiteralPath $configPath
$configHasManagedBlock = $false
if ($configExists) { $configHasManagedBlock = (Get-Content -LiteralPath $configPath -Raw).Contains("# --- ck-managed-agents-start ---") }

$hooksCheck = Test-ManagedHooksJson -Path (Join-Path $targetHome "hooks.json") -CodexHomePath $targetHome
$scoutCheck = Test-LinkMatches -Path (Join-Path $targetHome "skills\scout") -ExpectedTargetPath (Join-Path $kitRoot ".codex\skills\scout")
$agentsCheck = Test-LinkMatches -Path (Join-Path $targetHome "agents") -ExpectedTargetPath (Join-Path $kitRoot ".codex\agents")
$hooksDirCheck = Test-LinkMatches -Path (Join-Path $targetHome "hooks") -ExpectedTargetPath (Join-Path $kitRoot ".codex\hooks")
$agentsFilePath = Join-Path $targetHome "AGENTS.md"
$repoAgentsPath = Join-Path $kitRoot "AGENTS.md"
$agentsFileInSync = (Test-Path -LiteralPath $agentsFilePath) -and (Test-Path -LiteralPath $repoAgentsPath) -and ((Get-FileSha256 -Path $agentsFilePath) -eq (Get-FileSha256 -Path $repoAgentsPath))
$systemSkillsPreserved = Test-Path -LiteralPath (Join-Path $targetHome "skills\.system")

$installBackupCount = Get-BackupCount -CodexHomePath $targetHome -Pattern "claudekit-backup-*"
$uninstallBackupCount = Get-BackupCount -CodexHomePath $targetHome -Pattern "claudekit-uninstall-backup-*"
$codexProcessCount = if ($CodexProcessCountOverride -ge 0) { $CodexProcessCountOverride } else { @(Get-Process codex -ErrorAction SilentlyContinue).Count }
$cleanupWatcherCount = Get-CleanupWatcherCount -WatcherScriptName "remove-legacy-codex-home-when-codex-exits.ps1" -Override $CleanupWatcherCountOverride
$cleanupWatcherStatus = if ($null -eq $cleanupWatcherCount) { "unknown" } elseif ($cleanupWatcherCount -gt 0) { "running" } else { "not-running" }
$legacyCleanupStatus = Get-CodexLegacyCleanupStatus -ExpectedCodexHome $targetHome
if (($legacyCleanupStatus.state -eq "absent") -and $legacyExists -and ($cleanupWatcherStatus -eq "running")) {
    $legacyCleanupStatus = [pscustomobject]@{
        exists = $false
        path = $legacyCleanupStatus.path
        state = "waiting"
        message = "Cleanup watcher is running, but no persisted cleanup status file exists yet."
        updatedAtUtc = $null
        watcherPid = $null
    }
}
$doctorStatus = Get-CodexDoctorStatus -TargetHome $targetHome -RequestedHome $resolvedConfiguredHome -DoctorHomeOverride $DoctorCodexHomeOverride -RunDoctor:$RunCodexDoctor
$doctorConfigStatus = if ($doctorStatus.codexHome) { Get-CodexHomeConfigStatus -CodexHomePath $doctorStatus.codexHome } else { [pscustomobject]@{ exists = $false; configPath = $null; hasLegacySubagentBlock = $false } }
$migrationGapStatus = if ($legacyExists -and $targetExists) { Get-CodexMigrationGapStatus -LegacyCodexHomePath $legacyHome -TargetCodexHomePath $targetHome } else { [pscustomobject]@{ checked = $false; missingArtifacts = @(); missingArtifactCount = 0 } }

$globalInstallHealthy = ($normalizedConfiguredHome -eq $targetHome) -and $targetExists -and $authExists -and $configHasManagedBlock -and $hooksCheck.isManaged -and $scoutCheck.matches -and $agentsCheck.matches -and $hooksDirCheck.matches -and $agentsFileInSync
$restartRequired = (
    (($null -ne $normalizedConfiguredHome) -and ($null -ne $normalizedProcessHome) -and ($normalizedConfiguredHome -ne $normalizedProcessHome)) -or
    ($doctorStatus.status -eq "mismatch")
)
$legacyCleanupManagedByWatcher = $legacyExists -and ($cleanupWatcherStatus -eq "running")
$canRemoveLegacyHomeNow = $legacyExists -and ($normalizedConfiguredHome -eq $targetHome) -and $authExists -and ($codexProcessCount -eq 0) -and (-not $legacyCleanupManagedByWatcher)

$nextStep = if (-not $targetExists) {
    "Run install-claude-kit-globally-to-codex-home.ps1 to create the target Codex home on D:."
} elseif ($normalizedConfiguredHome -ne $targetHome) {
    "Update user CODEX_HOME to $targetHome by rerunning the global installer."
} elseif ($doctorStatus.status -eq "mismatch") {
    $(if (($doctorStatus.launchMode -eq "requested-home") -and ($doctorStatus.requestedHome -eq $targetHome)) {
        "codex doctor still reported $($doctorStatus.codexHome) even when launched with requested CODEX_HOME $targetHome. Rerun the global installer or inspect Codex wrappers/config files before cleanup."
    } else {
        "Restart VS Code/Codex or open a fresh shell so codex doctor stops using $($doctorStatus.codexHome) and picks up $targetHome." + $(if ($doctorConfigStatus.hasLegacySubagentBlock) { " The current codex doctor warning is likely coming from $($doctorConfigStatus.configPath) still containing [agents.subagent]." } else { "" })
    })
} elseif ($restartRequired) {
    "Restart VS Code/Codex so the current process stops using $normalizedProcessHome and picks up $targetHome."
} elseif ($migrationGapStatus.missingArtifactCount -gt 0) {
    "Rerun the installer or migration script before cleanup because $targetHome is still missing legacy state artifacts: " + ($migrationGapStatus.missingArtifacts -join ", ")
} elseif ($legacyExists -and ($legacyCleanupStatus.state -eq "failed")) {
    "Review the cleanup failure in $($legacyCleanupStatus.path), then rerun start-codex-home-cleanup-watcher.ps1 or remove-legacy-codex-home-after-migration.ps1."
} elseif ($legacyExists -and ($cleanupWatcherStatus -eq "running") -and $codexProcessCount -gt 0) {
    "Close Codex and let the running cleanup watcher remove the legacy home on C: automatically."
} elseif ($legacyExists -and ($cleanupWatcherStatus -eq "running")) {
    "Wait for the running cleanup watcher to remove the legacy home on C: automatically."
} elseif ($legacyExists -and $codexProcessCount -gt 0) {
    "Close Codex or start the cleanup watcher before removing the legacy home on C:."
} elseif ($legacyExists) {
    "Legacy home can be removed now with remove-legacy-codex-home-after-migration.ps1."
} elseif ($legacyCleanupStatus.state -eq "completed") {
    "Legacy home cleanup already completed. Global Claude-Kit on D: looks healthy."
} else {
    "Global Claude-Kit on D: looks healthy."
}

$status = [pscustomobject]@{
    targetCodexHome = $targetHome
    legacyCodexHome = $legacyHome
    userCodexHome = $normalizedConfiguredHome
    processCodexHome = $normalizedProcessHome
    targetHomeExists = $targetExists
    legacyHomeExists = $legacyExists
    targetAuthExists = $authExists
    targetConfigExists = $configExists
    configHasManagedBlock = $configHasManagedBlock
    hooksJsonManaged = $hooksCheck.isManaged
    scoutSkillLinked = $scoutCheck.matches
    agentsLinked = $agentsCheck.matches
    hooksLinked = $hooksDirCheck.matches
    agentsFileInSync = $agentsFileInSync
    systemSkillsPreserved = $systemSkillsPreserved
    installBackupCount = $installBackupCount
    uninstallBackupCount = $uninstallBackupCount
    codexProcessCount = $codexProcessCount
    cleanupWatcherCount = $cleanupWatcherCount
    cleanupWatcherStatus = $cleanupWatcherStatus
    legacyCleanupManagedByWatcher = $legacyCleanupManagedByWatcher
    legacyCleanupStatusFilePath = $legacyCleanupStatus.path
    legacyCleanupStatusExists = $legacyCleanupStatus.exists
    legacyCleanupState = $legacyCleanupStatus.state
    legacyCleanupMessage = $legacyCleanupStatus.message
    legacyCleanupUpdatedAtUtc = $legacyCleanupStatus.updatedAtUtc
    legacyCleanupWatcherPid = $legacyCleanupStatus.watcherPid
    doctorCheckStatus = $doctorStatus.status
    doctorCodexHome = $doctorStatus.codexHome
    doctorMatchesTarget = $doctorStatus.matchesTarget
    doctorRequestedHome = $doctorStatus.requestedHome
    doctorLaunchMode = $doctorStatus.launchMode
    doctorConfigPath = $doctorConfigStatus.configPath
    doctorConfigHasLegacySubagentBlock = $doctorConfigStatus.hasLegacySubagentBlock
    migrationGapChecked = $migrationGapStatus.checked
    migrationMissingArtifacts = $migrationGapStatus.missingArtifacts
    migrationMissingArtifactCount = $migrationGapStatus.missingArtifactCount
    globalInstallHealthy = $globalInstallHealthy
    restartRequired = $restartRequired
    canRemoveLegacyHomeNow = $canRemoveLegacyHomeNow
    nextStep = $nextStep
}
if ($PassThru) {
    $status
    return
}

Write-Host "Global Claude-Kit Codex status" -ForegroundColor Cyan
Write-Host ("Target CODEX_HOME: " + $status.targetCodexHome)
Write-Host ("User CODEX_HOME: " + $(if ($status.userCodexHome) { $status.userCodexHome } else { "<empty>" }))
Write-Host ("Process CODEX_HOME: " + $(if ($status.processCodexHome) { $status.processCodexHome } else { "<empty>" }))
Write-Host ("Global wiring healthy: " + $status.globalInstallHealthy)
Write-Host ("Restart required: " + $status.restartRequired)
Write-Host ("Legacy home exists: " + $status.legacyHomeExists)
Write-Host ("Safe to remove legacy home now: " + $status.canRemoveLegacyHomeNow)
Write-Host ("Codex processes: " + $status.codexProcessCount)
Write-Host ("Cleanup watcher: " + $status.cleanupWatcherStatus)
Write-Host ("Watcher manages legacy cleanup: " + $status.legacyCleanupManagedByWatcher)
Write-Host ("Legacy cleanup state: " + $status.legacyCleanupState)
if ($status.legacyCleanupUpdatedAtUtc) {
    Write-Host ("Legacy cleanup updated: " + $status.legacyCleanupUpdatedAtUtc)
}
if ($status.legacyCleanupMessage) {
    Write-Host ("Legacy cleanup message: " + $status.legacyCleanupMessage)
}
Write-Host ("Codex doctor: " + $status.doctorCheckStatus + $(if ($status.doctorCodexHome) { " (" + $status.doctorCodexHome + ")" } else { "" }))
if ($status.doctorLaunchMode -and ($status.doctorLaunchMode -ne "not-run")) {
    Write-Host ("Codex doctor launch mode: " + $status.doctorLaunchMode + $(if ($status.doctorRequestedHome) { " (" + $status.doctorRequestedHome + ")" } else { "" }))
}
if ($status.doctorConfigPath) {
    Write-Host ("Doctor config legacy subagent block: " + $status.doctorConfigHasLegacySubagentBlock)
}
Write-Host ("Missing migrated artifacts: " + $status.migrationMissingArtifactCount)
if ($status.migrationMissingArtifactCount -gt 0) {
    Write-Host ("Missing artifact names: " + ($status.migrationMissingArtifacts -join ", "))
}
Write-Host ("Install backups: " + $status.installBackupCount)
Write-Host ("Uninstall backups: " + $status.uninstallBackupCount)
Write-Host ("Next step: " + $status.nextStep) -ForegroundColor Yellow
