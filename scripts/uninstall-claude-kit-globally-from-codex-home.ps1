[CmdletBinding()]
param(
    [string]$TargetCodexHome = "D:\CodexHome",
    [string]$ClaudeKitPath = "",
    [string]$ConfiguredCodexHome = "",
    [switch]$PassThru,
    [switch]$Force
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($ClaudeKitPath)) {
    $ClaudeKitPath = Join-Path $PSScriptRoot ".."
}

. (Join-Path $PSScriptRoot "claude-kit-codex-utils.ps1")

function New-UninstallBackupSnapshot {
    param(
        [Parameter(Mandatory = $true)]
        [string]$CodexHomePath
    )

    $backupBaseName = "claudekit-uninstall-backup-" + (Get-Date -Format "yyyyMMdd-HHmmss")
    $backupDir = Join-Path $CodexHomePath $backupBaseName
    $suffix = 1
    while (Test-Path -LiteralPath $backupDir) {
        $backupDir = Join-Path $CodexHomePath ($backupBaseName + "-" + $suffix.ToString("00"))
        $suffix++
    }

    Ensure-Directory -Path $backupDir

    foreach ($relativePath in @("config.toml", "hooks.json", "AGENTS.md")) {
        $sourcePath = Join-Path $CodexHomePath $relativePath
        if (-not (Test-Path -LiteralPath $sourcePath)) {
            continue
        }

        Copy-Item -LiteralPath $sourcePath -Destination (Join-Path $backupDir ($relativePath + ".before-uninstall")) -Force
    }

    return $backupDir
}

function Get-InstallBackupSnapshots {
    param(
        [Parameter(Mandatory = $true)]
        [string]$CodexHomePath
    )

    return @(
        Get-ChildItem -LiteralPath $CodexHomePath -Directory -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -like "claudekit-backup-*" } |
            Sort-Object Name -Descending
    )
}

function Get-ManagedGlobalHooksConfig {
    param(
        [Parameter(Mandatory = $true)]
        [string]$CodexHomePath
    )

    $hookPath = Join-Path $CodexHomePath "hooks\6cbdb017-simplify-gate.cjs"
    return [ordered]@{
        description = "Global Claude-Kit Codex hooks"
        hooks = [ordered]@{
            UserPromptSubmit = @(
                [ordered]@{
                    hooks = @(
                        [ordered]@{
                            type = "command"
                            command = ('node "' + $hookPath + '"')
                            _origin = "engineer"
                        }
                    )
                }
            )
        }
    }
}

function Test-IsManagedHooksJsonFile {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,
        [Parameter(Mandatory = $true)]
        [string]$CodexHomePath
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        return $false
    }

    try {
        $current = Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json
        $expected = Get-ManagedGlobalHooksConfig -CodexHomePath $CodexHomePath
        $currentCommand = $current.hooks.UserPromptSubmit[0].hooks[0].command
        $expectedCommand = $expected.hooks.UserPromptSubmit[0].hooks[0].command
        return ($current.description -eq $expected.description) -and ($currentCommand -eq $expectedCommand)
    } catch {
        return $false
    }
}

function Select-RestoreBackupFile {
    param(
        [Parameter(Mandatory = $true)]
        [object[]]$Snapshots,
        [Parameter(Mandatory = $true)]
        [string]$BackupFileName,
        [Parameter(Mandatory = $true)]
        [scriptblock]$CandidateIsUsable
    )

    foreach ($snapshot in $Snapshots) {
        $candidatePath = Join-Path $snapshot.FullName $BackupFileName
        if (-not (Test-Path -LiteralPath $candidatePath)) {
            continue
        }

        if (& $CandidateIsUsable $candidatePath) {
            return $candidatePath
        }
    }

    return $null
}

function Remove-ManagedJunctionIfMatches {
    param(
        [Parameter(Mandatory = $true)]
        [string]$TargetPath,
        [Parameter(Mandatory = $true)]
        [string]$ExpectedSourcePath
    )

    if (-not (Test-Path -LiteralPath $TargetPath)) {
        return $false
    }

    if (-not (Test-IsReparsePoint -Path $TargetPath)) {
        return $false
    }

    $item = Get-Item -LiteralPath $TargetPath -Force
    $expectedTarget = Resolve-NormalizedPath -Path $ExpectedSourcePath
    $actualTargets = @($item.Target) | Where-Object { -not [string]::IsNullOrWhiteSpace($_) } | ForEach-Object {
        [System.IO.Path]::GetFullPath($_)
    }

    if ($actualTargets -notcontains $expectedTarget) {
        return $false
    }

    if ($item.PSIsContainer) {
        Remove-Item -LiteralPath $TargetPath -Force -Recurse
    } else {
        Remove-Item -LiteralPath $TargetPath -Force
    }

    return $true
}

function Remove-ManagedConfigBlock {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        return $false
    }

    $configText = Get-Content -LiteralPath $Path -Raw
    $updatedText = [regex]::Replace($configText, '(?ms)^# --- ck-managed-agents-start ---.*?# --- ck-managed-features-end ---\s*', "").Trim()
    if ($updatedText -eq $configText.Trim()) {
        return $false
    }

    if ([string]::IsNullOrWhiteSpace($updatedText)) {
        Remove-Item -LiteralPath $Path -Force
    } else {
        Write-Utf8NoBomFile -Path $Path -Content ($updatedText + "`r`n")
    }

    return $true
}

$targetHome = Resolve-NormalizedPath -Path $TargetCodexHome -AllowMissing
$kitRoot = Resolve-NormalizedPath -Path $ClaudeKitPath
$resolvedConfiguredHome = $ConfiguredCodexHome
if ([string]::IsNullOrWhiteSpace($resolvedConfiguredHome)) {
    $resolvedConfiguredHome = [Environment]::GetEnvironmentVariable("CODEX_HOME", "User")
}

if ([string]::IsNullOrWhiteSpace($resolvedConfiguredHome)) {
    throw "Configured CODEX_HOME is empty. Refusing to uninstall global Claude-Kit."
}

$normalizedConfiguredHome = Resolve-NormalizedPath -Path $resolvedConfiguredHome -AllowMissing
if ($normalizedConfiguredHome -ne $targetHome) {
    throw "Configured CODEX_HOME points to $normalizedConfiguredHome, not $targetHome."
}

if (-not (Test-Path -LiteralPath $targetHome)) {
    throw "Target Codex home does not exist: $targetHome"
}

$installBackups = Get-InstallBackupSnapshots -CodexHomePath $targetHome
$uninstallBackupDir = New-UninstallBackupSnapshot -CodexHomePath $targetHome
$restoredFiles = New-Object System.Collections.Generic.List[string]
$removedPaths = New-Object System.Collections.Generic.List[string]
$warnings = New-Object System.Collections.Generic.List[string]

$skillsRoot = Join-Path $targetHome "skills"
if (Test-Path -LiteralPath $skillsRoot) {
    Get-ChildItem -LiteralPath $skillsRoot -Force | Where-Object { $_.Name -ne ".system" } | ForEach-Object {
        $expectedSource = Join-Path $kitRoot (".codex\skills\" + $_.Name)
        if (Remove-ManagedJunctionIfMatches -TargetPath $_.FullName -ExpectedSourcePath $expectedSource) {
            $removedPaths.Add($_.FullName) | Out-Null
        } elseif ($_.Name -ne ".system") {
            $warnings.Add("Left skill entry untouched: $($_.FullName)") | Out-Null
        }
    }
}

foreach ($name in @("agents", "hooks")) {
    $targetPath = Join-Path $targetHome $name
    $expectedSource = Join-Path $kitRoot (".codex\" + $name)
    if (Remove-ManagedJunctionIfMatches -TargetPath $targetPath -ExpectedSourcePath $expectedSource) {
        $removedPaths.Add($targetPath) | Out-Null
    } elseif (Test-Path -LiteralPath $targetPath) {
        $warnings.Add("Left $targetPath untouched because it no longer points to Claude-Kit.") | Out-Null
    }
}

$repoAgentsPath = Join-Path $kitRoot "AGENTS.md"
$targetAgentsPath = Join-Path $targetHome "AGENTS.md"
$agentsRestoreBackup = Select-RestoreBackupFile `
    -Snapshots $installBackups `
    -BackupFileName "AGENTS.md.before-claudekit" `
    -CandidateIsUsable {
        param($Path)
        return (Get-FileSha256 -Path $Path) -ne (Get-FileSha256 -Path $repoAgentsPath)
    }

if ($agentsRestoreBackup) {
    Copy-Item -LiteralPath $agentsRestoreBackup -Destination $targetAgentsPath -Force
    $restoredFiles.Add("AGENTS.md") | Out-Null
} elseif ((Test-Path -LiteralPath $targetAgentsPath) -and ((Get-FileSha256 -Path $targetAgentsPath) -eq (Get-FileSha256 -Path $repoAgentsPath))) {
    Remove-Item -LiteralPath $targetAgentsPath -Force
    $removedPaths.Add($targetAgentsPath) | Out-Null
} elseif (Test-Path -LiteralPath $targetAgentsPath) {
    $warnings.Add("Left AGENTS.md untouched because no pre-Claude-Kit backup was found.") | Out-Null
}

$configPath = Join-Path $targetHome "config.toml"
$configRestoreBackup = Select-RestoreBackupFile `
    -Snapshots $installBackups `
    -BackupFileName "config.toml.before-claudekit" `
    -CandidateIsUsable {
        param($Path)
        $text = Get-Content -LiteralPath $Path -Raw
        return -not $text.Contains("# --- ck-managed-agents-start ---")
    }

if ($configRestoreBackup) {
    Copy-Item -LiteralPath $configRestoreBackup -Destination $configPath -Force
    $restoredFiles.Add("config.toml") | Out-Null
} elseif (Remove-ManagedConfigBlock -Path $configPath) {
    $restoredFiles.Add("config.toml (managed block stripped)") | Out-Null
} elseif (Test-Path -LiteralPath $configPath) {
    $warnings.Add("Left config.toml untouched because no usable pre-Claude-Kit backup was found.") | Out-Null
}

$hooksJsonPath = Join-Path $targetHome "hooks.json"
$hooksRestoreBackup = Select-RestoreBackupFile `
    -Snapshots $installBackups `
    -BackupFileName "hooks.json.before-claudekit" `
    -CandidateIsUsable {
        param($Path)
        return -not (Test-IsManagedHooksJsonFile -Path $Path -CodexHomePath $targetHome)
    }

if ($hooksRestoreBackup) {
    Copy-Item -LiteralPath $hooksRestoreBackup -Destination $hooksJsonPath -Force
    $restoredFiles.Add("hooks.json") | Out-Null
} elseif (Test-IsManagedHooksJsonFile -Path $hooksJsonPath -CodexHomePath $targetHome) {
    Remove-Item -LiteralPath $hooksJsonPath -Force
    $removedPaths.Add($hooksJsonPath) | Out-Null
} elseif (Test-Path -LiteralPath $hooksJsonPath) {
    $warnings.Add("Left hooks.json untouched because no usable pre-Claude-Kit backup was found.") | Out-Null
}

Write-Host "Removed global Claude-Kit wiring from $targetHome" -ForegroundColor Green
Write-Host "Pre-uninstall backup snapshot: $uninstallBackupDir"
if ($installBackups.Count -gt 0) {
    Write-Host ("Install backups inspected: " + $installBackups.Count)
} else {
    Write-Host "Install backups inspected: 0"
}

if ($restoredFiles.Count -gt 0) {
    Write-Host ("Restored: " + ($restoredFiles -join ", "))
}
if ($removedPaths.Count -gt 0) {
    Write-Host ("Removed managed paths: " + ($removedPaths -join ", "))
}
if ($warnings.Count -gt 0) {
    $warnings | ForEach-Object { Write-Warning $_ }
}

$summary = [pscustomobject]@{
    targetCodexHome = $targetHome
    configuredCodexHome = $normalizedConfiguredHome
    uninstallBackupDir = $uninstallBackupDir
    installBackupCount = $installBackups.Count
    restoredFiles = $restoredFiles
    removedPaths = $removedPaths
    warnings = $warnings
}

if ($PassThru) {
    $summary
}
