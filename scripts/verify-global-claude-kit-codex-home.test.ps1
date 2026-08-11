[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$testRoot = Join-Path $repoRoot "tmp-codex-verify-test"
$legacyHome = Join-Path $testRoot "legacy-home"
$targetHome = Join-Path $testRoot "target-home"
$installerPath = Join-Path $PSScriptRoot "install-claude-kit-globally-to-codex-home.ps1"
$verifyPath = Join-Path $PSScriptRoot "verify-global-claude-kit-codex-home.ps1"

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

    $verifyResult = & $verifyPath `
        -TargetCodexHome $targetHome `
        -ClaudeKitPath $repoRoot `
        -ConfiguredCodexHome $targetHome `
        -PassThru

    Assert-True -Condition $verifyResult.allPassed -Message "Verification script did not pass against a valid global install fixture."
    Assert-True -Condition ($verifyResult.failedChecks.Count -eq 0) -Message "Verification script reported failing checks for a valid fixture."

    $mismatchResult = & $verifyPath `
        -TargetCodexHome $targetHome `
        -ClaudeKitPath $repoRoot `
        -ConfiguredCodexHome $legacyHome `
        -PassThru

    Assert-True -Condition (-not $mismatchResult.allPassed) -Message "Verification script should fail when ConfiguredCodexHome points elsewhere."
    $configuredHomeFailures = @($mismatchResult.failedChecks | Where-Object { $_.name -eq "configured-codex-home" })
    Assert-True -Condition ($configuredHomeFailures.Count -eq 1) -Message "Expected configured-codex-home check to fail for mismatched ConfiguredCodexHome."

    Write-Host "verify-global-claude-kit-codex-home: PASS"
} finally {
    if (Test-Path -LiteralPath $testRoot) {
        Remove-Item -LiteralPath $testRoot -Force -Recurse
    }
}
