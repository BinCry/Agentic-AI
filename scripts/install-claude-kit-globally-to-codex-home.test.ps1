[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$testRoot = Join-Path $repoRoot "tmp-codex-global-test"
$legacyHome = Join-Path $testRoot "legacy-home"
$targetHome = Join-Path $testRoot "target-home"
$installerPath = Join-Path $PSScriptRoot "install-claude-kit-globally-to-codex-home.ps1"

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

    & $installerPath `
        -TargetCodexHome $targetHome `
        -LegacyCodexHome $legacyHome `
        -ClaudeKitPath $repoRoot `
        -SkipStateMigration `
        -SkipEnvironmentUpdate

    & $installerPath `
        -TargetCodexHome $targetHome `
        -LegacyCodexHome $legacyHome `
        -ClaudeKitPath $repoRoot `
        -SkipStateMigration `
        -SkipEnvironmentUpdate

    $configText = Get-Content -LiteralPath (Join-Path $targetHome "config.toml") -Raw
    $hooksPath = Join-Path $targetHome "hooks.json"
    $hooksBytes = [System.IO.File]::ReadAllBytes($hooksPath)
    $scoutSkill = Get-Item -LiteralPath (Join-Path $targetHome "skills\scout") -Force
    $agentsDir = Get-Item -LiteralPath (Join-Path $targetHome "agents") -Force
    $hooksDir = Get-Item -LiteralPath (Join-Path $targetHome "hooks") -Force
    $systemMarker = (Get-Content -LiteralPath (Join-Path $targetHome "skills\.system\marker.txt") -Raw).Trim()
    $backupDirs = @(Get-ChildItem -LiteralPath $targetHome -Directory | Where-Object { $_.Name -like "claudekit-backup-*" })

    Assert-True -Condition (Test-Path -LiteralPath (Join-Path $targetHome "AGENTS.md")) -Message "AGENTS.md was not created."
    Assert-True -Condition ($scoutSkill.LinkType -eq "Junction") -Message "skills\\scout was not created as a junction."
    Assert-True -Condition ($scoutSkill.Target -contains (Join-Path $repoRoot ".codex\skills\scout")) -Message "skills\\scout does not point back to repo .codex."
    Assert-True -Condition ($agentsDir.LinkType -eq "Junction") -Message "agents was not created as a junction."
    Assert-True -Condition ($hooksDir.LinkType -eq "Junction") -Message "hooks was not created as a junction."
    Assert-True -Condition ($systemMarker -eq "keep-system") -Message ".system skills were not preserved."
    Assert-True -Condition (-not $configText.Contains("[agents.subagent]")) -Message "Legacy [agents.subagent] block still exists."
    Assert-True -Condition $configText.Contains('default_subagent_model = "cx/gpt-5.5"') -Message "default_subagent_model was not normalized into config."
    Assert-True -Condition $configText.Contains('# --- ck-managed-agents-start ---') -Message "Managed Claude-Kit config block missing."
    Assert-True -Condition ($backupDirs.Count -ge 1) -Message "Backup snapshot directory was not created."

    $hasBom = $hooksBytes.Length -ge 3 -and $hooksBytes[0] -eq 0xEF -and $hooksBytes[1] -eq 0xBB -and $hooksBytes[2] -eq 0xBF
    Assert-True -Condition (-not $hasBom) -Message "hooks.json was written with a UTF-8 BOM."

    Write-Host "install-claude-kit-globally-to-codex-home: PASS"
} finally {
    if (Test-Path -LiteralPath $testRoot) {
        Remove-Item -LiteralPath $testRoot -Force -Recurse
    }
}
