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

function Get-CodexDoctorStatus {
    param(
        [Parameter(Mandatory = $true)]
        [string]$TargetHome,
        [string]$DoctorHomeOverride = "",
        [switch]$RunDoctor
    )

    if ([string]::IsNullOrWhiteSpace($DoctorHomeOverride) -and -not $RunDoctor) {
        return [pscustomobject]@{ status = "not-run"; codexHome = $null; matchesTarget = $false }
    }

    $reportedHome = $null
    if (-not [string]::IsNullOrWhiteSpace($DoctorHomeOverride)) {
        $reportedHome = Resolve-OptionalNormalizedPath -Path $DoctorHomeOverride
    } elseif (-not (Get-Command codex -ErrorAction SilentlyContinue)) {
        return [pscustomobject]@{ status = "command-missing"; codexHome = $null; matchesTarget = $false }
    } else {
        $doctorOutput = & codex doctor 2>&1 | Out-String
        $doctorMatch = [regex]::Match($doctorOutput, '(?m)^\s*CODEX_HOME\s+(?<path>.+?)\s+\((dir|missing)\)\s*$')
        if (-not $doctorMatch.Success) {
            return [pscustomobject]@{ status = "parse-failed"; codexHome = $null; matchesTarget = $false }
        }
        $reportedHome = Resolve-OptionalNormalizedPath -Path $doctorMatch.Groups["path"].Value
    }

    return [pscustomobject]@{
        status = $(if ($reportedHome -eq $TargetHome) { "matched" } else { "mismatch" })
        codexHome = $reportedHome
        matchesTarget = ($reportedHome -eq $TargetHome)
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
