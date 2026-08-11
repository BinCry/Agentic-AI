[CmdletBinding()]
param(
    [string]$ProjectPath = (Get-Location).Path,
    [switch]$Force
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "claude-kit-codex-utils.ps1")

$projectRoot = Resolve-NormalizedPath -Path $ProjectPath
$manifestPath = Join-Path $projectRoot ".codex\claudekit-project-manifest.json"

if (-not (Test-Path -LiteralPath $manifestPath)) {
    throw "Managed manifest not found: $manifestPath"
}

$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
$skipped = @()

foreach ($fileEntry in $manifest.files) {
    $targetPath = Join-Path $projectRoot $fileEntry.path
    if (-not (Test-Path -LiteralPath $targetPath)) {
        continue
    }

    if ((Get-Item -LiteralPath $targetPath -Force).PSIsContainer) {
        $skipped += "Skipping directory recorded as file: $($fileEntry.path)"
        continue
    }

    $currentHash = Get-FileSha256 -Path $targetPath
    if (-not $Force -and $currentHash -ne $fileEntry.sha256) {
        $skipped += "Modified file kept: $($fileEntry.path)"
        continue
    }

    Remove-Item -LiteralPath $targetPath -Force
}

foreach ($junctionEntry in $manifest.junctions) {
    $targetPath = Join-Path $projectRoot $junctionEntry.path
    if (-not (Test-Path -LiteralPath $targetPath)) {
        continue
    }

    if (-not (Test-IsReparsePoint -Path $targetPath) -and -not $Force) {
        $skipped += "Path is no longer a junction: $($junctionEntry.path)"
        continue
    }

    Remove-Item -LiteralPath $targetPath -Force -Recurse
}

if ($skipped.Count -eq 0) {
    Remove-Item -LiteralPath $manifestPath -Force
}

$candidateDirs = @(
    ".codex",
    ".claude\command-archive",
    ".claude\session-state",
    ".claude",
    "plans\reports",
    "plans"
)

foreach ($relativeDir in $candidateDirs) {
    $dirPath = Join-Path $projectRoot $relativeDir
    if (-not (Test-Path -LiteralPath $dirPath)) {
        continue
    }

    if (-not (Get-Item -LiteralPath $dirPath -Force).PSIsContainer) {
        continue
    }

    if (@(Get-ChildItem -LiteralPath $dirPath -Force).Count -eq 0) {
        Remove-Item -LiteralPath $dirPath -Force
    }
}

if ($skipped.Count -gt 0) {
    Write-Warning "Claude-Kit detach completed with warnings:"
    $skipped | ForEach-Object { Write-Warning $_ }
    Write-Warning "Rerun with -Force if you want to remove modified files too."
} else {
    Write-Host "Claude-Kit detached from $projectRoot" -ForegroundColor Green
}
