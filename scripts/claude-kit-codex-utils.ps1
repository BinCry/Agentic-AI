Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Resolve-NormalizedPath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,
        [switch]$AllowMissing,
        [switch]$CreateDirectory
    )

    $expanded = [Environment]::ExpandEnvironmentVariables($Path)
    if ($CreateDirectory -and -not (Test-Path -LiteralPath $expanded)) {
        New-Item -ItemType Directory -Path $expanded -Force | Out-Null
    }

    if (Test-Path -LiteralPath $expanded) {
        return [System.IO.Path]::GetFullPath((Resolve-Path -LiteralPath $expanded).Path)
    }

    if ($AllowMissing) {
        return [System.IO.Path]::GetFullPath($expanded)
    }

    throw "Path does not exist: $expanded"
}

function Ensure-Directory {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        New-Item -ItemType Directory -Path $Path -Force | Out-Null
    }
}

function Test-IsReparsePoint {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        return $false
    }

    $item = Get-Item -LiteralPath $Path -Force
    return (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0)
}

function Get-FileSha256 {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash
}

function Get-RelativePath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$BasePath,
        [Parameter(Mandatory = $true)]
        [string]$TargetPath
    )

    $baseUri = [System.Uri]((Resolve-NormalizedPath -Path $BasePath) + [System.IO.Path]::DirectorySeparatorChar)
    $targetUri = [System.Uri](Resolve-NormalizedPath -Path $TargetPath)
    $relativeUri = $baseUri.MakeRelativeUri($targetUri)
    return [System.Uri]::UnescapeDataString($relativeUri.ToString()).Replace("/", "\")
}

function New-ManagedJunction {
    param(
        [Parameter(Mandatory = $true)]
        [string]$TargetPath,
        [Parameter(Mandatory = $true)]
        [string]$SourcePath,
        [switch]$Force
    )

    $targetParent = Split-Path -Parent $TargetPath
    if ($targetParent) {
        Ensure-Directory -Path $targetParent
    }

    if (Test-Path -LiteralPath $TargetPath) {
        if (Test-IsReparsePoint -Path $TargetPath) {
            $existingReparsePoint = Get-Item -LiteralPath $TargetPath -Force
            if ($existingReparsePoint.PSIsContainer) {
                Remove-Item -LiteralPath $TargetPath -Force -Recurse
            } else {
                Remove-Item -LiteralPath $TargetPath -Force
            }
        } elseif ($Force) {
            $existing = Get-Item -LiteralPath $TargetPath -Force
            if ($existing.PSIsContainer) {
                $hasChildren = @(Get-ChildItem -LiteralPath $TargetPath -Force).Count -gt 0
                if ($hasChildren) {
                    throw "Refusing to replace non-empty directory: $TargetPath"
                }
                Remove-Item -LiteralPath $TargetPath -Force
            } else {
                Remove-Item -LiteralPath $TargetPath -Force
            }
        } else {
            throw "Path already exists and is not a junction: $TargetPath"
        }
    }

    New-Item -ItemType Junction -Path $TargetPath -Target $SourcePath | Out-Null
}

function Copy-ManagedFile {
    param(
        [Parameter(Mandatory = $true)]
        [string]$SourcePath,
        [Parameter(Mandatory = $true)]
        [string]$TargetPath,
        [switch]$Force
    )

    $targetParent = Split-Path -Parent $TargetPath
    if ($targetParent) {
        Ensure-Directory -Path $targetParent
    }

    $sourceHash = Get-FileSha256 -Path $SourcePath
    $copied = $true

    if (Test-Path -LiteralPath $TargetPath) {
        if ((Get-Item -LiteralPath $TargetPath -Force).PSIsContainer) {
            throw "Path already exists as a directory: $TargetPath"
        }

        $targetHash = Get-FileSha256 -Path $TargetPath
        if ($targetHash -eq $sourceHash) {
            $copied = $false
        } elseif ($Force) {
            Copy-Item -LiteralPath $SourcePath -Destination $TargetPath -Force
        } else {
            throw "File already exists with different content: $TargetPath"
        }
    } else {
        Copy-Item -LiteralPath $SourcePath -Destination $TargetPath -Force
    }

    return [ordered]@{
        path = $TargetPath
        sourcePath = $SourcePath
        sha256 = $sourceHash
        copied = $copied
    }
}

function Save-JsonFile {
    param(
        [Parameter(Mandatory = $true)]
        $Data,
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    $json = $Data | ConvertTo-Json -Depth 8
    Write-Utf8NoBomFile -Path $Path -Content $json
}

function Write-Utf8NoBomFile {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,
        [Parameter(Mandatory = $true)]
        [AllowEmptyString()]
        [string]$Content
    )

    $targetParent = Split-Path -Parent $Path
    if ($targetParent) {
        Ensure-Directory -Path $targetParent
    }

    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($Path, $Content, $utf8NoBom)
}
