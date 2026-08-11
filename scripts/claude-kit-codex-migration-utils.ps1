Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-CodexStateFilesToSync {
    param(
        [Parameter(Mandatory = $true)]
        [string]$LegacyCodexHomePath,
        [switch]$IncludeUserConfigFiles
    )

    $files = @(
        "auth.json",
        "installation_id",
        "cap_sid",
        "models_cache.json",
        "session_index.jsonl",
        "version.json",
        ".personality_migration",
        ".sandbox_migration"
    )

    if ($IncludeUserConfigFiles) {
        $files = @("config.toml", "AGENTS.md") + $files
    }

    if (Test-Path -LiteralPath $LegacyCodexHomePath) {
        $sqliteStateFiles = @(
            Get-ChildItem -LiteralPath $LegacyCodexHomePath -File -Force -ErrorAction SilentlyContinue |
                Where-Object {
                    $_.Name -like "*.sqlite" -or
                    $_.Name -like "*.sqlite-shm" -or
                    $_.Name -like "*.sqlite-wal"
                } |
                ForEach-Object { $_.Name }
        )

        $files = @($files + $sqliteStateFiles | Sort-Object -Unique)
    }

    return $files
}

function Get-CodexStateDirectoriesToSync {
    return @(
        "attachments",
        "cache",
        "mcp-oauth-locks",
        "plugins",
        "sessions",
        "tmp",
        "vendor_imports"
    )
}

function Sync-CodexHomeState {
    param(
        [Parameter(Mandatory = $true)]
        [string]$LegacyCodexHomePath,
        [Parameter(Mandatory = $true)]
        [string]$TargetCodexHomePath,
        [switch]$IncludeUserConfigFiles
    )

    $legacyExists = Test-Path -LiteralPath $LegacyCodexHomePath
    Ensure-Directory -Path $TargetCodexHomePath

    $copiedFiles = New-Object System.Collections.Generic.List[string]
    $copiedDirectories = New-Object System.Collections.Generic.List[string]

    if (-not $legacyExists) {
        return [pscustomobject]@{
            legacyExists = $false
            files = @()
            directories = @()
        }
    }

    foreach ($relativePath in (Get-CodexStateFilesToSync -LegacyCodexHomePath $LegacyCodexHomePath -IncludeUserConfigFiles:$IncludeUserConfigFiles)) {
        $sourcePath = Join-Path $LegacyCodexHomePath $relativePath
        if (-not (Test-Path -LiteralPath $sourcePath)) {
            continue
        }

        $targetPath = Join-Path $TargetCodexHomePath $relativePath
        Copy-Item -LiteralPath $sourcePath -Destination $targetPath -Force
        $copiedFiles.Add($relativePath) | Out-Null
    }

    foreach ($relativePath in (Get-CodexStateDirectoriesToSync)) {
        $sourcePath = Join-Path $LegacyCodexHomePath $relativePath
        if (-not (Test-Path -LiteralPath $sourcePath)) {
            continue
        }

        $targetPath = Join-Path $TargetCodexHomePath $relativePath
        if (Test-Path -LiteralPath $targetPath) {
            Remove-Item -LiteralPath $targetPath -Force -Recurse
        }

        $null = robocopy $sourcePath $targetPath /E /R:1 /W:1 /XJ /NFL /NDL /NJH /NJS /NP
        if ($LASTEXITCODE -gt 7) {
            throw "Robocopy failed for $relativePath with exit code $LASTEXITCODE"
        }

        $copiedDirectories.Add($relativePath) | Out-Null
    }

    return [pscustomobject]@{
        legacyExists = $true
        files = @($copiedFiles)
        directories = @($copiedDirectories)
    }
}
