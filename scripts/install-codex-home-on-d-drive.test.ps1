[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$testRoot = Join-Path $repoRoot "tmp-codex-home-migration-test"
$legacyHome = Join-Path $testRoot "legacy-home"
$targetHome = Join-Path $testRoot "target-home"
$scriptPath = Join-Path $PSScriptRoot "install-codex-home-on-d-drive.ps1"
$originalUserCodexHome = [Environment]::GetEnvironmentVariable("CODEX_HOME", "User")
$originalProcessCodexHome = $env:CODEX_HOME

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

    New-Item -ItemType Directory -Path $legacyHome -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $legacyHome "sessions") -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $legacyHome "attachments") -Force | Out-Null
    New-Item -ItemType Directory -Path $targetHome -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $targetHome "sessions") -Force | Out-Null

    "auth" | Set-Content -LiteralPath (Join-Path $legacyHome "auth.json") -Encoding ASCII
    "config" | Set-Content -LiteralPath (Join-Path $legacyHome "config.toml") -Encoding ASCII
    "agents" | Set-Content -LiteralPath (Join-Path $legacyHome "AGENTS.md") -Encoding ASCII
    "install-id" | Set-Content -LiteralPath (Join-Path $legacyHome "installation_id") -Encoding ASCII
    "cap" | Set-Content -LiteralPath (Join-Path $legacyHome "cap_sid") -Encoding ASCII
    "cache" | Set-Content -LiteralPath (Join-Path $legacyHome "models_cache.json") -Encoding ASCII
    "index" | Set-Content -LiteralPath (Join-Path $legacyHome "session_index.jsonl") -Encoding ASCII
    "personality" | Set-Content -LiteralPath (Join-Path $legacyHome ".personality_migration") -Encoding ASCII
    "sandbox" | Set-Content -LiteralPath (Join-Path $legacyHome ".sandbox_migration") -Encoding ASCII
    "goal-db" | Set-Content -LiteralPath (Join-Path $legacyHome "goals_1.sqlite") -Encoding ASCII
    "log-shm" | Set-Content -LiteralPath (Join-Path $legacyHome "logs_2.sqlite-shm") -Encoding ASCII
    "state-wal" | Set-Content -LiteralPath (Join-Path $legacyHome "state_5.sqlite-wal") -Encoding ASCII
    "new-session" | Set-Content -LiteralPath (Join-Path $legacyHome "sessions\marker.txt") -Encoding ASCII
    "attach" | Set-Content -LiteralPath (Join-Path $legacyHome "attachments\marker.txt") -Encoding ASCII
    "old-session" | Set-Content -LiteralPath (Join-Path $targetHome "sessions\stale.txt") -Encoding ASCII
    "old-goal-db" | Set-Content -LiteralPath (Join-Path $targetHome "goals_1.sqlite") -Encoding ASCII

    $installResult = & $scriptPath -TargetCodexHome $targetHome -LegacyCodexHome $legacyHome -PassThru

    Assert-True -Condition ([Environment]::GetEnvironmentVariable("CODEX_HOME", "User") -eq $targetHome) -Message "User CODEX_HOME was not updated to the target home."
    Assert-True -Condition ($env:CODEX_HOME -eq $targetHome) -Message "Process CODEX_HOME was not updated to the target home."
    Assert-True -Condition ($installResult.environmentChangeSupported -eq $true) -Message "Environment broadcast should be supported on Windows."
    Assert-True -Condition ($installResult.environmentChangeBroadcasted -eq $true) -Message "Environment broadcast did not report success."
    Assert-True -Condition ((Get-Content -LiteralPath (Join-Path $targetHome "models_cache.json") -Raw).Trim() -eq "cache") -Message "models_cache.json was not copied."
    Assert-True -Condition ((Get-Content -LiteralPath (Join-Path $targetHome "session_index.jsonl") -Raw).Trim() -eq "index") -Message "session_index.jsonl was not copied."
    Assert-True -Condition ((Get-Content -LiteralPath (Join-Path $targetHome ".personality_migration") -Raw).Trim() -eq "personality") -Message ".personality_migration was not copied."
    Assert-True -Condition ((Get-Content -LiteralPath (Join-Path $targetHome "goals_1.sqlite") -Raw).Trim() -eq "goal-db") -Message "SQLite state file was not overwritten from the legacy home."
    Assert-True -Condition ((Get-Content -LiteralPath (Join-Path $targetHome "logs_2.sqlite-shm") -Raw).Trim() -eq "log-shm") -Message "SQLite SHM file was not copied."
    Assert-True -Condition ((Get-Content -LiteralPath (Join-Path $targetHome "state_5.sqlite-wal") -Raw).Trim() -eq "state-wal") -Message "SQLite WAL file was not copied."
    Assert-True -Condition ((Get-Content -LiteralPath (Join-Path $targetHome "sessions\marker.txt") -Raw).Trim() -eq "new-session") -Message "sessions directory was not refreshed from the legacy home."
    Assert-True -Condition (-not (Test-Path -LiteralPath (Join-Path $targetHome "sessions\stale.txt"))) -Message "Stale session file in target home should have been replaced."
    Assert-True -Condition ((Get-Content -LiteralPath (Join-Path $targetHome "attachments\marker.txt") -Raw).Trim() -eq "attach") -Message "attachments directory was not copied."

    Write-Host "install-codex-home-on-d-drive: PASS"
} finally {
    if ($null -eq $originalUserCodexHome) {
        [Environment]::SetEnvironmentVariable("CODEX_HOME", $null, "User")
    } else {
        [Environment]::SetEnvironmentVariable("CODEX_HOME", $originalUserCodexHome, "User")
    }
    $env:CODEX_HOME = $originalProcessCodexHome

    if (Test-Path -LiteralPath $testRoot) {
        Remove-Item -LiteralPath $testRoot -Force -Recurse
    }
}
