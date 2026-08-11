[CmdletBinding()]
param(
    [string]$ProjectPath = (Get-Location).Path,
    [string]$ClaudeKitPath = "",
    [switch]$Force
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($ClaudeKitPath)) {
    $ClaudeKitPath = Join-Path $PSScriptRoot ".."
}

. (Join-Path $PSScriptRoot "claude-kit-codex-utils.ps1")

$projectRoot = Resolve-NormalizedPath -Path $ProjectPath
$kitRoot = Resolve-NormalizedPath -Path $ClaudeKitPath

$manifestPath = Join-Path $projectRoot ".codex\claudekit-project-manifest.json"

$junctions = @(
    @{ target = ".codex\agents"; source = ".codex\agents" },
    @{ target = ".codex\hooks"; source = ".codex\hooks" },
    @{ target = ".codex\skills"; source = ".codex\skills" },
    @{ target = ".claude\agents"; source = ".claude\agents" },
    @{ target = ".claude\hooks"; source = ".claude\hooks" },
    @{ target = ".claude\output-styles"; source = ".claude\output-styles" },
    @{ target = ".claude\rules"; source = ".claude\rules" },
    @{ target = ".claude\schemas"; source = ".claude\schemas" },
    @{ target = ".claude\scripts"; source = ".claude\scripts" },
    @{ target = ".claude\skills"; source = ".claude\skills" },
    @{ target = ".agents"; source = ".agents" },
    @{ target = "plans\templates"; source = "plans\templates" }
)

$filesToCopy = @(
    ".codex\config.toml",
    ".codex\hooks.json",
    ".codex\.ckignore",
    ".claude\.ck.json",
    ".claude\.ckignore",
    ".claude\.env.example",
    ".claude\.gitignore",
    ".claude\.mcp.json.example",
    ".claude\metadata.json",
    ".claude\settings.json",
    ".claude\statusline.cjs",
    "AGENTS.md",
    "CLAUDE.md"
)

$localDirs = @(
    ".codex",
    ".claude",
    ".claude\command-archive",
    ".claude\session-state",
    "plans",
    "plans\reports"
)

foreach ($dir in $localDirs) {
    Ensure-Directory -Path (Join-Path $projectRoot $dir)
}

$manifest = [ordered]@{
    schemaVersion = 1
    installedAt = (Get-Date).ToString("o")
    claudeKitPath = $kitRoot
    projectPath = $projectRoot
    junctions = @()
    files = @()
}

foreach ($entry in $junctions) {
    $targetPath = Join-Path $projectRoot $entry.target
    $sourcePath = Join-Path $kitRoot $entry.source
    New-ManagedJunction -TargetPath $targetPath -SourcePath $sourcePath -Force:$Force
    $manifest.junctions += [ordered]@{
        path = $entry.target
        sourcePath = $entry.source
    }
}

foreach ($relativePath in $filesToCopy) {
    $sourcePath = Join-Path $kitRoot $relativePath
    $targetPath = Join-Path $projectRoot $relativePath
    $copyResult = Copy-ManagedFile -SourcePath $sourcePath -TargetPath $targetPath -Force:$Force
    $manifest.files += [ordered]@{
        path = $relativePath
        sourcePath = $relativePath
        sha256 = $copyResult.sha256
    }
}

Save-JsonFile -Data $manifest -Path $manifestPath

Write-Host "Claude-Kit attached to $projectRoot" -ForegroundColor Green
Write-Host "Managed manifest: $manifestPath"
Write-Host "Next step: open the project in Codex and trust it so project-local .codex config is loaded."
