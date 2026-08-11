[CmdletBinding()]
param(
    [string]$TargetCodexHome = "D:\CodexHome",
    [string]$LegacyCodexHome = (Join-Path $HOME ".codex"),
    [string]$ClaudeKitPath = "",
    [switch]$SkipStateMigration,
    [switch]$SkipEnvironmentUpdate,
    [switch]$Force
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($ClaudeKitPath)) {
    $ClaudeKitPath = Join-Path $PSScriptRoot ".."
}

. (Join-Path $PSScriptRoot "claude-kit-codex-utils.ps1")

function New-BackupSnapshot {
    param(
        [Parameter(Mandatory = $true)]
        [string]$CodexHomePath
    )

    $backupDir = Join-Path $CodexHomePath ("claudekit-backup-" + (Get-Date -Format "yyyyMMdd-HHmmss"))
    Ensure-Directory -Path $backupDir

    foreach ($relativePath in @("config.toml", "hooks.json", "AGENTS.md")) {
        $sourcePath = Join-Path $CodexHomePath $relativePath
        if (-not (Test-Path -LiteralPath $sourcePath)) {
            continue
        }

        Copy-Item -LiteralPath $sourcePath -Destination (Join-Path $backupDir ($relativePath + ".before-claudekit")) -Force
    }

    return $backupDir
}

function Sync-SystemSkills {
    param(
        [Parameter(Mandatory = $true)]
        [string]$LegacyCodexHomePath,
        [Parameter(Mandatory = $true)]
        [string]$TargetCodexHomePath
    )

    $targetSystemPath = Join-Path $TargetCodexHomePath "skills\.system"
    if (Test-Path -LiteralPath $targetSystemPath) {
        return $targetSystemPath
    }

    $legacySystemPath = Join-Path $LegacyCodexHomePath "skills\.system"
    if (-not (Test-Path -LiteralPath $legacySystemPath)) {
        return $null
    }

    $null = robocopy $legacySystemPath $targetSystemPath /E /R:1 /W:1 /XJ /NFL /NDL /NJH /NJS /NP
    if ($LASTEXITCODE -gt 7) {
        throw "Robocopy failed for .system skills with exit code $LASTEXITCODE"
    }

    return $targetSystemPath
}

function Set-ManagedGlobalAgentsFile {
    param(
        [Parameter(Mandatory = $true)]
        [string]$TargetPath,
        [Parameter(Mandatory = $true)]
        [string]$SourcePath
    )

    if (Test-Path -LiteralPath $TargetPath) {
        Remove-Item -LiteralPath $TargetPath -Force
    }

    $sameDrive = [System.StringComparer]::OrdinalIgnoreCase.Equals(
        [System.IO.Path]::GetPathRoot($TargetPath),
        [System.IO.Path]::GetPathRoot($SourcePath)
    )

    if ($sameDrive) {
        try {
            New-Item -ItemType HardLink -Path $TargetPath -Target $SourcePath -Force | Out-Null
            return "hardlink"
        } catch {
            # Fall back to a copy for filesystems that refuse hard links.
        }
    }

    Copy-Item -LiteralPath $SourcePath -Destination $TargetPath -Force
    return "copy"
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

function Normalize-LegacySubagentConfig {
    param(
        [Parameter(Mandatory = $true)]
        [AllowEmptyString()]
        [string]$ConfigText
    )

    $legacyPattern = '(?ms)^\[agents\.subagent\]\r?\n(?<body>.*?)(?=^\[|\z)'
    $legacyMatch = [regex]::Match($ConfigText, $legacyPattern)
    if (-not $legacyMatch.Success) {
        return $ConfigText
    }

    $legacyBody = $legacyMatch.Groups["body"].Value
    $defaultModel = [regex]::Match($legacyBody, '(?m)^\s*model\s*=\s*"(?<value>[^"]+)"').Groups["value"].Value
    $defaultEffort = [regex]::Match($legacyBody, '(?m)^\s*model_reasoning_effort\s*=\s*"(?<value>[^"]+)"').Groups["value"].Value
    $withoutLegacy = [regex]::Replace($ConfigText, $legacyPattern, "").Trim()

    $setDefaultAgentsValue = {
        param(
            [string]$AgentsBody,
            [string]$KeyName,
            [string]$Value
        )

        if ([string]::IsNullOrWhiteSpace($Value)) {
            return $AgentsBody
        }

        $escapedKey = [regex]::Escape($KeyName)
        $line = $KeyName + ' = "' + $Value + '"'
        if ([regex]::IsMatch($AgentsBody, '(?m)^\s*' + $escapedKey + '\s*=')) {
            return [regex]::Replace($AgentsBody, '(?m)^\s*' + $escapedKey + '\s*=.*$', $line)
        }

        if ([string]::IsNullOrWhiteSpace($AgentsBody)) {
            return $line
        }

        return $AgentsBody.TrimEnd() + "`r`n" + $line
    }

    $agentsPattern = '(?ms)^\[agents\]\r?\n(?<body>.*?)(?=^\[|\z)'
    $agentsMatch = [regex]::Match($withoutLegacy, $agentsPattern)
    if ($agentsMatch.Success) {
        $updatedAgentsBody = & $setDefaultAgentsValue $agentsMatch.Groups["body"].Value "default_subagent_model" $defaultModel
        $updatedAgentsBody = & $setDefaultAgentsValue $updatedAgentsBody "default_subagent_reasoning_effort" $defaultEffort
        return [regex]::Replace($withoutLegacy, $agentsPattern, "[agents]`r`n" + $updatedAgentsBody.TrimEnd() + "`r`n")
    }

    $newAgentsBlock = ""
    if (-not [string]::IsNullOrWhiteSpace($defaultModel)) {
        $newAgentsBlock += 'default_subagent_model = "' + $defaultModel + '"' + "`r`n"
    }
    if (-not [string]::IsNullOrWhiteSpace($defaultEffort)) {
        $newAgentsBlock += 'default_subagent_reasoning_effort = "' + $defaultEffort + '"' + "`r`n"
    }
    if ([string]::IsNullOrWhiteSpace($newAgentsBlock)) {
        return $withoutLegacy
    }

    if ([string]::IsNullOrWhiteSpace($withoutLegacy)) {
        return "[agents]`r`n" + $newAgentsBlock.TrimEnd() + "`r`n"
    }

    return $withoutLegacy + "`r`n`r`n[agents]`r`n" + $newAgentsBlock.TrimEnd() + "`r`n"
}

function Merge-ManagedCodexConfig {
    param(
        [Parameter(Mandatory = $true)]
        [string]$TargetConfigPath,
        [Parameter(Mandatory = $true)]
        [string]$ManagedConfigPath
    )

    $baseConfig = ""
    if (Test-Path -LiteralPath $TargetConfigPath) {
        $baseConfig = Get-Content -LiteralPath $TargetConfigPath -Raw
    }

    $baseConfig = Normalize-LegacySubagentConfig -ConfigText $baseConfig
    $baseConfig = [regex]::Replace($baseConfig, '(?ms)^# --- ck-managed-agents-start ---.*?# --- ck-managed-features-end ---\s*', "").Trim()
    $managedConfig = (Get-Content -LiteralPath $ManagedConfigPath -Raw).Trim()

    if ([string]::IsNullOrWhiteSpace($baseConfig)) {
        Write-Utf8NoBomFile -Path $TargetConfigPath -Content ($managedConfig + "`r`n")
        return
    }

    Write-Utf8NoBomFile -Path $TargetConfigPath -Content ($baseConfig + "`r`n`r`n" + $managedConfig + "`r`n")
}

$targetHome = Resolve-NormalizedPath -Path $TargetCodexHome -AllowMissing
$legacyHome = Resolve-NormalizedPath -Path $LegacyCodexHome -AllowMissing
$kitRoot = Resolve-NormalizedPath -Path $ClaudeKitPath

if ([System.StringComparer]::OrdinalIgnoreCase.Equals($targetHome, $legacyHome)) {
    throw "TargetCodexHome and LegacyCodexHome resolve to the same path: $targetHome"
}

if (-not $SkipStateMigration) {
    & (Join-Path $PSScriptRoot "install-codex-home-on-d-drive.ps1") `
        -TargetCodexHome $targetHome `
        -LegacyCodexHome $legacyHome
}

Ensure-Directory -Path $targetHome
$backupDir = New-BackupSnapshot -CodexHomePath $targetHome

$skillsRoot = Join-Path $targetHome "skills"
Ensure-Directory -Path $skillsRoot
$systemSkillsPath = Sync-SystemSkills -LegacyCodexHomePath $legacyHome -TargetCodexHomePath $targetHome

Get-ChildItem -LiteralPath $skillsRoot -Force | Where-Object { $_.Name -ne ".system" } | ForEach-Object {
    Remove-Item -LiteralPath $_.FullName -Force -Recurse
}

Get-ChildItem -LiteralPath (Join-Path $kitRoot ".codex\skills") -Directory | ForEach-Object {
    New-ManagedJunction -TargetPath (Join-Path $skillsRoot $_.Name) -SourcePath $_.FullName -Force:$Force
}

foreach ($name in @("agents", "hooks")) {
    New-ManagedJunction -TargetPath (Join-Path $targetHome $name) -SourcePath (Join-Path $kitRoot (".codex\" + $name)) -Force:$Force
}

$agentsFileMode = Set-ManagedGlobalAgentsFile -TargetPath (Join-Path $targetHome "AGENTS.md") -SourcePath (Join-Path $kitRoot "AGENTS.md")
Save-JsonFile -Data (Get-ManagedGlobalHooksConfig -CodexHomePath $targetHome) -Path (Join-Path $targetHome "hooks.json")
Merge-ManagedCodexConfig -TargetConfigPath (Join-Path $targetHome "config.toml") -ManagedConfigPath (Join-Path $kitRoot ".codex\config.toml")

if (-not $SkipEnvironmentUpdate) {
    [Environment]::SetEnvironmentVariable("CODEX_HOME", $targetHome, "User")
    $env:CODEX_HOME = $targetHome
}

Write-Host "Claude-Kit installed globally into $targetHome" -ForegroundColor Green
Write-Host "Backup snapshot: $backupDir"
if ($systemSkillsPath) {
    Write-Host "Preserved built-in Codex system skills at: $systemSkillsPath"
}
Write-Host "Global AGENTS sync mode: $agentsFileMode"
Write-Host "Global skills, hooks, and agents now point to $kitRoot"
if ($SkipEnvironmentUpdate) {
    Write-Host "Skipped CODEX_HOME environment update because -SkipEnvironmentUpdate was used."
} else {
    Write-Host "Restart VS Code/Codex, then verify with: codex doctor"
    Write-Host "When the new home looks correct, remove the old C drive home with:"
    Write-Host ("powershell -ExecutionPolicy Bypass -File " + (Join-Path $PSScriptRoot "remove-legacy-codex-home-after-migration.ps1") + " -ExpectedCodexHome " + $targetHome)
}
