[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$testRoot = Join-Path $repoRoot "tmp-codex-uninstall-test"
$legacyHome = Join-Path $testRoot "legacy-home"
$targetHome = Join-Path $testRoot "target-home"
$installerPath = Join-Path $PSScriptRoot "install-claude-kit-globally-to-codex-home.ps1"
$uninstallPath = Join-Path $PSScriptRoot "uninstall-claude-kit-globally-from-codex-home.ps1"

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
    Copy-Item -LiteralPath (Join-Path $legacyHome "AGENTS.md") -Destination (Join-Path $targetHome "AGENTS.md") -Force

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

    $uninstallResult = & $uninstallPath `
        -TargetCodexHome $targetHome `
        -ClaudeKitPath $repoRoot `
        -ConfiguredCodexHome $targetHome `
        -PassThru

    $restoredConfig = Get-Content -LiteralPath (Join-Path $targetHome "config.toml") -Raw
    $restoredAgents = (Get-Content -LiteralPath (Join-Path $targetHome "AGENTS.md") -Raw).Trim()
    $systemMarker = (Get-Content -LiteralPath (Join-Path $targetHome "skills\.system\marker.txt") -Raw).Trim()

    Assert-True -Condition ($restoredConfig -notmatch '# --- ck-managed-agents-start ---') -Message "Managed config block was not removed or restored away."
    Assert-True -Condition ($restoredConfig -match '\[agents\.subagent\]') -Message "Original legacy config was not restored from backup."
    Assert-True -Condition ($restoredAgents -eq "legacy-agents") -Message "Original AGENTS.md was not restored from backup."
    Assert-True -Condition (-not (Test-Path -LiteralPath (Join-Path $targetHome "hooks.json"))) -Message "Managed hooks.json should have been removed."
    Assert-True -Condition (-not (Test-Path -LiteralPath (Join-Path $targetHome "agents"))) -Message "Managed agents junction should have been removed."
    Assert-True -Condition (-not (Test-Path -LiteralPath (Join-Path $targetHome "hooks"))) -Message "Managed hooks junction should have been removed."
    Assert-True -Condition (-not (Test-Path -LiteralPath (Join-Path $targetHome "skills\scout"))) -Message "Managed skills junctions should have been removed."
    Assert-True -Condition ($systemMarker -eq "keep-system") -Message ".system skills should be preserved."
    Assert-True -Condition (Test-Path -LiteralPath (Join-Path $targetHome "auth.json")) -Message "auth.json should remain in the Codex home."
    Assert-True -Condition ($uninstallResult.installBackupCount -ge 2) -Message "Expected uninstall to inspect the install backup snapshots."
    Assert-True -Condition ((Test-Path -LiteralPath $uninstallResult.uninstallBackupDir)) -Message "Pre-uninstall backup snapshot was not created."

    $mismatchFailed = $false
    try {
        & $uninstallPath `
            -TargetCodexHome $targetHome `
            -ClaudeKitPath $repoRoot `
            -ConfiguredCodexHome $legacyHome | Out-Null
    } catch {
        $mismatchFailed = $_.Exception.Message.Contains("Configured CODEX_HOME points to")
    }

    Assert-True -Condition $mismatchFailed -Message "Uninstall should reject a mismatched ConfiguredCodexHome."

    Write-Host "uninstall-claude-kit-globally-from-codex-home: PASS"
} finally {
    if (Test-Path -LiteralPath $testRoot) {
        Remove-Item -LiteralPath $testRoot -Force -Recurse
    }
}
