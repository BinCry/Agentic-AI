Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Publish-WindowsEnvironmentChange {
    param(
        [int]$TimeoutMilliseconds = 5000
    )

    $isWindows = $false
    try {
        $isWindows = [System.OperatingSystem]::IsWindows()
    } catch {
        $isWindows = ($env:OS -eq "Windows_NT")
    }

    if (-not $isWindows) {
        return [pscustomobject]@{
            supported = $false
            broadcasted = $false
            message = "Windows environment broadcast is only supported on Windows."
        }
    }

    if (-not ("ClaudeKitWindowsEnvironmentNativeMethods" -as [type])) {
        Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;

public static class ClaudeKitWindowsEnvironmentNativeMethods
{
    public static readonly IntPtr HWND_BROADCAST = new IntPtr(0xffff);
    public const int WM_SETTINGCHANGE = 0x001A;
    public const int SMTO_ABORTIFHUNG = 0x0002;

    [DllImport("user32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
    public static extern IntPtr SendMessageTimeout(
        IntPtr hWnd,
        int Msg,
        IntPtr wParam,
        string lParam,
        int fuFlags,
        int uTimeout,
        out IntPtr lpdwResult
    );
}
"@
    }

    $messageResult = [System.IntPtr]::Zero
    $sendResult = [ClaudeKitWindowsEnvironmentNativeMethods]::SendMessageTimeout(
        [ClaudeKitWindowsEnvironmentNativeMethods]::HWND_BROADCAST,
        [ClaudeKitWindowsEnvironmentNativeMethods]::WM_SETTINGCHANGE,
        [System.IntPtr]::Zero,
        "Environment",
        [ClaudeKitWindowsEnvironmentNativeMethods]::SMTO_ABORTIFHUNG,
        $TimeoutMilliseconds,
        [ref]$messageResult
    )

    if ($sendResult -eq [System.IntPtr]::Zero) {
        $lastError = [System.Runtime.InteropServices.Marshal]::GetLastWin32Error()
        return [pscustomobject]@{
            supported = $true
            broadcasted = $false
            message = "Failed to broadcast the updated Windows environment. Win32 error: $lastError."
        }
    }

    return [pscustomobject]@{
        supported = $true
        broadcasted = $true
        message = "Broadcasted the updated Windows environment to other Windows processes."
    }
}
