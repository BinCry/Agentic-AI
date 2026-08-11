Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Resolve-OptionalNormalizedPath {
    param([string]$Path)
    if ([string]::IsNullOrWhiteSpace($Path)) {
        return $null
    }
    return Resolve-NormalizedPath -Path $Path -AllowMissing
}

function Get-BackupCount {
    param(
        [Parameter(Mandatory = $true)]
        [string]$CodexHomePath,
        [Parameter(Mandatory = $true)]
        [string]$Pattern
    )
    if (-not (Test-Path -LiteralPath $CodexHomePath)) {
        return 0
    }
    return @(
        Get-ChildItem -LiteralPath $CodexHomePath -Directory -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -like $Pattern }
    ).Count
}

function Get-CleanupWatcherCount {
    param(
        [Parameter(Mandatory = $true)]
        [string]$WatcherScriptName,
        [int]$Override = -1
    )
    if ($Override -ge 0) {
        return $Override
    }
    try {
        return @(
            Get-CimInstance Win32_Process -Filter "Name = 'powershell.exe'" -ErrorAction Stop |
                Where-Object { $_.CommandLine -like ("*" + $WatcherScriptName + "*") }
        ).Count
    } catch {
        return $null
    }
}

function ConvertTo-PowerShellEncodedCommand {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ScriptText
    )

    return [Convert]::ToBase64String([System.Text.Encoding]::Unicode.GetBytes($ScriptText))
}

function Invoke-CodexDoctorWithHome {
    param(
        [Parameter(Mandatory = $true)]
        [string]$CodexHome
    )

    $escapedHome = $CodexHome.Replace("'", "''")
    $scriptText = @"
`$env:CODEX_HOME = '$escapedHome'
& codex doctor 2>&1 | Out-String
"@

    $encodedCommand = ConvertTo-PowerShellEncodedCommand -ScriptText $scriptText
    return & powershell.exe -NoProfile -ExecutionPolicy Bypass -EncodedCommand $encodedCommand 2>&1 | Out-String
}

function Get-CodexDoctorStatus {
    param(
        [Parameter(Mandatory = $true)]
        [string]$TargetHome,
        [string]$RequestedHome = "",
        [string]$DoctorHomeOverride = "",
        [switch]$RunDoctor
    )

    if ([string]::IsNullOrWhiteSpace($DoctorHomeOverride) -and -not $RunDoctor) {
        return [pscustomobject]@{ status = "not-run"; codexHome = $null; matchesTarget = $false; requestedHome = $null; launchMode = "not-run" }
    }

    $reportedHome = $null
    $normalizedRequestedHome = Resolve-OptionalNormalizedPath -Path $RequestedHome
    if (-not [string]::IsNullOrWhiteSpace($DoctorHomeOverride)) {
        $reportedHome = Resolve-OptionalNormalizedPath -Path $DoctorHomeOverride
        return [pscustomobject]@{
            status = $(if ($reportedHome -eq $TargetHome) { "matched" } else { "mismatch" })
            codexHome = $reportedHome
            matchesTarget = ($reportedHome -eq $TargetHome)
            requestedHome = $normalizedRequestedHome
            launchMode = "override"
        }
    } elseif (-not (Get-Command codex -ErrorAction SilentlyContinue)) {
        return [pscustomobject]@{ status = "command-missing"; codexHome = $null; matchesTarget = $false; requestedHome = $normalizedRequestedHome; launchMode = "requested-home" }
    } elseif ($null -eq $normalizedRequestedHome) {
        return [pscustomobject]@{ status = "requested-home-empty"; codexHome = $null; matchesTarget = $false; requestedHome = $null; launchMode = "requested-home" }
    } else {
        $doctorOutput = Invoke-CodexDoctorWithHome -CodexHome $normalizedRequestedHome
        $doctorMatch = [regex]::Match($doctorOutput, '(?m)^\s*CODEX_HOME\s+(?<path>.+?)\s+\((dir|missing)\)\s*$')
        if (-not $doctorMatch.Success) {
            return [pscustomobject]@{ status = "parse-failed"; codexHome = $null; matchesTarget = $false; requestedHome = $normalizedRequestedHome; launchMode = "requested-home" }
        }
        $reportedHome = Resolve-OptionalNormalizedPath -Path $doctorMatch.Groups["path"].Value
    }

    return [pscustomobject]@{
        status = $(if ($reportedHome -eq $TargetHome) { "matched" } else { "mismatch" })
        codexHome = $reportedHome
        matchesTarget = ($reportedHome -eq $TargetHome)
        requestedHome = $normalizedRequestedHome
        launchMode = "requested-home"
    }
}

function Get-CodexHomeConfigStatus {
    param(
        [Parameter(Mandatory = $true)]
        [string]$CodexHomePath
    )

    $configPath = Join-Path $CodexHomePath "config.toml"
    if (-not (Test-Path -LiteralPath $configPath)) {
        return [pscustomobject]@{ exists = $false; configPath = $configPath; hasLegacySubagentBlock = $false }
    }

    $configText = Get-Content -LiteralPath $configPath -Raw
    return [pscustomobject]@{
        exists = $true
        configPath = $configPath
        hasLegacySubagentBlock = $configText.Contains("[agents.subagent]")
    }
}

function Get-CodexMigrationGapStatus {
    param(
        [Parameter(Mandatory = $true)]
        [string]$LegacyCodexHomePath,
        [Parameter(Mandatory = $true)]
        [string]$TargetCodexHomePath
    )

    $baseFiles = @(
        "auth.json",
        "config.toml",
        "AGENTS.md",
        "installation_id",
        "cap_sid",
        "models_cache.json",
        "session_index.jsonl",
        "version.json",
        ".personality_migration",
        ".sandbox_migration"
    )

    $baseDirs = @(
        "attachments",
        "cache",
        "mcp-oauth-locks",
        "plugins",
        "sessions",
        "tmp",
        "vendor_imports"
    )

    $legacyStateFiles = @(
        Get-ChildItem -LiteralPath $LegacyCodexHomePath -File -Force -ErrorAction SilentlyContinue |
            Where-Object {
                $_.Name -like "*.sqlite" -or
                $_.Name -like "*.sqlite-shm" -or
                $_.Name -like "*.sqlite-wal"
            } |
            ForEach-Object { $_.Name }
    )

    $missingArtifacts = New-Object System.Collections.Generic.List[string]
    foreach ($name in @($baseFiles + $legacyStateFiles | Sort-Object -Unique)) {
        if ((Test-Path -LiteralPath (Join-Path $LegacyCodexHomePath $name)) -and -not (Test-Path -LiteralPath (Join-Path $TargetCodexHomePath $name))) {
            $missingArtifacts.Add($name) | Out-Null
        }
    }

    foreach ($name in $baseDirs) {
        if ((Test-Path -LiteralPath (Join-Path $LegacyCodexHomePath $name)) -and -not (Test-Path -LiteralPath (Join-Path $TargetCodexHomePath $name))) {
            $missingArtifacts.Add($name + "\") | Out-Null
        }
    }

    [pscustomobject]@{
        checked = $true
        missingArtifacts = @($missingArtifacts)
        missingArtifactCount = $missingArtifacts.Count
    }
}
