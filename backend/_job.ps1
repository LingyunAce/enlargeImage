# _job.ps1
# Runs a command inside a Windows Job Object with KILL_ON_JOB_CLOSE.
# When this script exits (window close, Ctrl+C, End Task, normal completion),
# the job is destroyed and the child process tree is automatically killed.
#
# Usage:
#   . .\backend\_job.ps1
#   Start-InJob -FilePath 'python' -ArgumentList @('run.py') -WorkingDirectory 'D:\path'
#
# Or invoke directly (one-shot):
#   powershell -File _job.ps1 -FilePath 'python' -ArgumentList @('run.py') -WorkingDirectory 'D:\path'

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$FilePath,

    [Parameter()]
    [string[]]$ArgumentList = @(),

    [Parameter()]
    [string]$WorkingDirectory,

    [Parameter()]
    [int]$MaxStartupWaitSeconds = 600
)

$ErrorActionPreference = "Stop"

# P/Invoke for Windows Job Objects
if (-not ("Win32.Job" -as [type])) {
    Add-Type -Namespace Win32 -Name Job -MemberDefinition @"
        [System.Runtime.InteropServices.DllImport("kernel32.dll", SetLastError = true)]
        public static extern System.IntPtr CreateJobObject(System.IntPtr a, System.IntPtr n);

        [System.Runtime.InteropServices.DllImport("kernel32.dll", SetLastError = true)]
        [return: System.Runtime.InteropServices.MarshalAs(System.Runtime.InteropServices.UnmanagedType.Bool)]
        public static extern bool SetInformationJobObject(System.IntPtr h, int t, System.IntPtr i, uint l);

        [System.Runtime.InteropServices.DllImport("kernel32.dll", SetLastError = true)]
        [return: System.Runtime.InteropServices.MarshalAs(System.Runtime.InteropServices.UnmanagedType.Bool)]
        public static extern bool AssignProcessToJobObject(System.IntPtr h, System.IntPtr p);

        [System.Runtime.InteropServices.DllImport("kernel32.dll", SetLastError = true)]
        [return: System.Runtime.InteropServices.MarshalAs(System.Runtime.InteropServices.UnmanagedType.Bool)]
        public static extern bool CloseHandle(System.IntPtr h);

        public const int JobObjectExtendedLimitInformation = 9;
        public const int JobObjectLimitKillOnJobClose = 0x2000;
"@

    Add-Type -Namespace Win32 -Name JobLimit -MemberDefinition @"
        [System.Runtime.InteropServices.StructLayout(System.Runtime.InteropServices.LayoutKind.Sequential)]
        public struct JOBOBJECT_BASIC_LIMIT_INFORMATION {
            public long PerProcessUserTimeLimit;
            public long PerJobUserTimeLimit;
            public uint LimitFlags;
            public System.UIntPtr MinimumWorkingSetSize;
            public System.UIntPtr MaximumWorkingSetSize;
            public uint ActiveProcessLimit;
            public System.UIntPtr Affinity;
            public uint PriorityClass;
            public uint SchedulingClass;
        }

        [System.Runtime.InteropServices.StructLayout(System.Runtime.InteropServices.LayoutKind.Sequential)]
        public struct IO_COUNTERS {
            public ulong ReadOperationCount;
            public ulong WriteOperationCount;
            public ulong OtherOperationCount;
            public ulong ReadTransferCount;
            public ulong WriteTransferCount;
            public ulong OtherTransferCount;
        }

        [System.Runtime.InteropServices.StructLayout(System.Runtime.InteropServices.LayoutKind.Sequential)]
        public struct JOBOBJECT_EXTENDED_LIMIT_INFORMATION {
            public JOBOBJECT_BASIC_LIMIT_INFORMATION BasicLimitInformation;
            public IO_COUNTERS IoInfo;
            public System.UIntPtr ProcessMemoryLimit;
            public System.UIntPtr JobMemoryLimit;
            public System.UIntPtr PeakProcessMemoryUsed;
            public System.UIntPtr PeakJobMemoryUsed;
        }
"@
}

# Create the job object
$jobHandle = [Win32.Job]::CreateJobObject([IntPtr]::Zero, [IntPtr]::Zero)
if ($jobHandle -eq [IntPtr]::Zero) {
    throw "Failed to create job object. Win32 error: $([System.Runtime.InteropServices.Marshal]::GetLastWin32Error())"
}

# Configure it to kill children when the job is closed
$info = New-Object Win32.JobLimit+JOBOBJECT_EXTENDED_LIMIT_INFORMATION
$info.BasicLimitInformation.LimitFlags = [Win32.Job]::JobObjectLimitKillOnJobClose

$infoSize = [System.Runtime.InteropServices.Marshal]::SizeOf([Type]([Win32.JobLimit+JOBOBJECT_EXTENDED_LIMIT_INFORMATION]))
$infoPtr = [System.Runtime.InteropServices.Marshal]::AllocHGlobal($infoSize)
try {
    [System.Runtime.InteropServices.Marshal]::StructureToPtr($info, $infoPtr, $false)
    $ok = [Win32.Job]::SetInformationJobObject($jobHandle, [Win32.Job]::JobObjectExtendedLimitInformation, $infoPtr, $infoSize)
    if (-not $ok) {
        throw "Failed to set job info. Win32 error: $([System.Runtime.InteropServices.Marshal]::GetLastWin32Error())"
    }
} finally {
    [System.Runtime.InteropServices.Marshal]::FreeHGlobal($infoPtr)
}

# Start the process
$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = $FilePath
$psi.UseShellExecute = $false
$psi.RedirectStandardOutput = $false
$psi.RedirectStandardError = $false
$psi.CreateNoWindow = $false
$psi.WorkingDirectory = if ($WorkingDirectory) { $WorkingDirectory } else { (Get-Location).Path }
if ($ArgumentList -and $ArgumentList.Count -gt 0) {
    # Quote any argument that contains whitespace or double quotes, and
    # escape any embedded double quotes with a backslash. This matches the
    # standard CommandLineToArgvW quoting rules.
    $quoted = $ArgumentList | ForEach-Object {
        $a = [string]$_
        if ($a -match '[\s"]') {
            '"' + ($a -replace '"', '\"') + '"'
        } else {
            $a
        }
    }
    $psi.Arguments = ($quoted -join ' ')
}

try {
    $proc = [System.Diagnostics.Process]::Start($psi)
} catch {
    [Win32.Job]::CloseHandle($jobHandle) | Out-Null
    throw
}

# Assign the new process to the job (so it dies with us)
$ok = [Win32.Job]::AssignProcessToJobObject($jobHandle, $proc.Handle)
if (-not $ok) {
    # If assignment failed, kill the child and rethrow
    try { $proc.Kill() } catch {}
    $proc.Dispose()
    [Win32.Job]::CloseHandle($jobHandle) | Out-Null
    throw "Failed to assign process to job. Win32 error: $([System.Runtime.InteropServices.Marshal]::GetLastWin32Error())"
}

# Register cleanup on script exit (best-effort; the job is the real guarantee)
$cleanup = {
    try {
        if (-not $proc.HasExited) { $proc.Kill() }
    } catch {}
    try { $proc.Dispose() } catch {}
    [Win32.Job]::CloseHandle($jobHandle) | Out-Null
}
Register-EngineEvent -SourceIdentifier PowerShell.Exiting -Action $cleanup | Out-Null
Register-EngineEvent -SourceIdentifier PowerShell.OnIdle -Action $cleanup | Out-Null  # window close

# Wait for the child to finish naturally
try {
    $proc.WaitForExit()
} finally {
    $cleanup.Invoke()
}
