Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-CodexLegacyCleanupStatusPath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ExpectedCodexHome
    )

    $resolvedExpectedHome = Resolve-NormalizedPath -Path $ExpectedCodexHome -AllowMissing
    return Join-Path $resolvedExpectedHome "claudekit-legacy-codex-home-cleanup-status.json"
}

function Set-CodexLegacyCleanupStatus {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ExpectedCodexHome,
        [Parameter(Mandatory = $true)]
        [string]$LegacyCodexHome,
        [Parameter(Mandatory = $true)]
        [ValidateSet("waiting", "completed", "failed")]
        [string]$State,
        [Parameter(Mandatory = $true)]
        [AllowEmptyString()]
        [string]$Message,
        [int]$WatcherPid = 0
    )

    $resolvedExpectedHome = Resolve-NormalizedPath -Path $ExpectedCodexHome -AllowMissing
    $statusPath = Get-CodexLegacyCleanupStatusPath -ExpectedCodexHome $resolvedExpectedHome
    if (-not (Test-Path -LiteralPath $resolvedExpectedHome)) {
        return $statusPath
    }

    $statusPayload = [ordered]@{
        state = $State
        message = $Message
        updatedAtUtc = (Get-Date).ToUniversalTime().ToString("o")
        expectedCodexHome = $resolvedExpectedHome
        legacyCodexHome = Resolve-NormalizedPath -Path $LegacyCodexHome -AllowMissing
        watcherPid = if ($WatcherPid -gt 0) { $WatcherPid } else { $null }
    }

    Save-JsonFile -Data $statusPayload -Path $statusPath
    return $statusPath
}

function Get-CodexLegacyCleanupStatus {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ExpectedCodexHome
    )

    $statusPath = Get-CodexLegacyCleanupStatusPath -ExpectedCodexHome $ExpectedCodexHome
    if (-not (Test-Path -LiteralPath $statusPath)) {
        return [pscustomobject]@{
            exists = $false
            path = $statusPath
            state = "absent"
            message = $null
            updatedAtUtc = $null
            watcherPid = $null
        }
    }

    try {
        $statusPayload = Get-Content -LiteralPath $statusPath -Raw | ConvertFrom-Json
        return [pscustomobject]@{
            exists = $true
            path = $statusPath
            state = if ($statusPayload.state) { [string]$statusPayload.state } else { "unknown" }
            message = if ($statusPayload.message) { [string]$statusPayload.message } else { $null }
            updatedAtUtc = if ($statusPayload.updatedAtUtc) { [string]$statusPayload.updatedAtUtc } else { $null }
            watcherPid = if ($null -ne $statusPayload.watcherPid) { [int]$statusPayload.watcherPid } else { $null }
        }
    } catch {
        return [pscustomobject]@{
            exists = $true
            path = $statusPath
            state = "unreadable"
            message = $_.Exception.Message
            updatedAtUtc = $null
            watcherPid = $null
        }
    }
}
