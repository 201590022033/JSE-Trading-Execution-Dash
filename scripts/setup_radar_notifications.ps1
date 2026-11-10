[CmdletBinding(SupportsShouldProcess=$true)]
param([switch]$Install)
$ErrorActionPreference = 'Stop'
$appId = 'Strategy Radar'
$programs = [Environment]::GetFolderPath('Programs')
if (-not $programs) { throw 'Per-user Start menu location unavailable.' }
$shortcut = Join-Path $programs 'Strategy Radar.lnk'
if (-not $Install) {
    Write-Output "Proposed per-user shortcut: $shortcut"
    Write-Output 'Run with -Install to register the Strategy Radar Windows notification sender. Existing shortcuts will not be overwritten.'
    exit 0
}
if (Test-Path -LiteralPath $shortcut) { throw 'Shortcut already exists; no existing file was overwritten. Inspect it before proceeding.' }
if (-not $PSCmdlet.ShouldProcess($shortcut, 'Create per-user notification sender shortcut')) { exit 0 }

# The shortcut opens the local dashboard; it does not enable the worker or start a model.
# The Windows property store binds the desktop shortcut to the toast AppUserModelID.
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
[StructLayout(LayoutKind.Sequential, Pack=4)]
public struct RadarPropertyKey { public Guid fmtid; public uint pid; }
[StructLayout(LayoutKind.Explicit)]
public struct RadarPropVariant {
    [FieldOffset(0)] public ushort vt;
    [FieldOffset(8)] public IntPtr pointer;
}
[ComImport, Guid("886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
public interface IRadarPropertyStore {
    void GetCount(out uint count);
    void GetAt(uint index, out RadarPropertyKey key);
    void GetValue(ref RadarPropertyKey key, out RadarPropVariant value);
    void SetValue(ref RadarPropertyKey key, ref RadarPropVariant value);
    void Commit();
}
public static class RadarShortcutId {
    [DllImport("shell32.dll", CharSet=CharSet.Unicode, PreserveSig=false)]
    private static extern void SHGetPropertyStoreFromParsingName(string path, IntPtr bind, uint flags, ref Guid iid, [MarshalAs(UnmanagedType.Interface)] out IRadarPropertyStore store);
    public static void Set(string path, string appId) {
        Guid iid = typeof(IRadarPropertyStore).GUID;
        IRadarPropertyStore store;
        SHGetPropertyStoreFromParsingName(path, IntPtr.Zero, 2, ref iid, out store);
        var key = new RadarPropertyKey { fmtid = new Guid("9F4C2855-9F79-4B39-A8D0-E1D42DE1D5F3"), pid = 5 };
        var value = new RadarPropVariant { vt = 31, pointer = Marshal.StringToCoTaskMemUni(appId) };
        try { store.SetValue(ref key, ref value); store.Commit(); }
        finally { Marshal.FreeCoTaskMem(value.pointer); Marshal.ReleaseComObject(store); }
    }
}
'@
$temp = Join-Path $programs ('.radar-notification-' + [Guid]::NewGuid().ToString('N') + '.lnk')
try {
    $shell = New-Object -ComObject WScript.Shell
    $link = $shell.CreateShortcut($temp)
    $link.TargetPath = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
    $link.Arguments = '-NoProfile -WindowStyle Hidden -Command Start-Process ''http://127.0.0.1:5000/'''
    $link.Description = 'Open the local Strategy Radar dashboard'
    $link.Save()
    [RadarShortcutId]::Set($temp, $appId)
    # Move without overwrite after the complete shortcut is prepared.
    [IO.File]::Move($temp, $shortcut)
    Write-Output 'Strategy Radar sender shortcut registered. Windows notification settings and visible delivery still require verification.'
} finally {
    if (Test-Path -LiteralPath $temp) { Remove-Item -LiteralPath $temp -Force }
}
