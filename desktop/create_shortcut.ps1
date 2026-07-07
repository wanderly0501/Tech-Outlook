# desktop/create_shortcut.ps1
#
# Creates a Desktop shortcut that launches Tech Lookout's desktop app
# with pythonw.exe (no console window), using logo/icon.ico as its icon.
# Re-run this any time (e.g. after moving the project) to regenerate it.
#
# Usage (from anywhere):
#   powershell -ExecutionPolicy Bypass -File desktop/create_shortcut.ps1

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$AppScript = Join-Path $ProjectRoot "desktop\app.py"
$IconPath = Join-Path $ProjectRoot "logo\icon.ico"

$PythonExe = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $PythonExe) {
    Write-Error "Could not find python.exe on PATH. Install Python or adjust this script."
    exit 1
}
$PythonwExe = Join-Path (Split-Path $PythonExe) "pythonw.exe"
if (-not (Test-Path $PythonwExe)) {
    Write-Error "Could not find pythonw.exe next to $PythonExe"
    exit 1
}

$DesktopDir = [Environment]::GetFolderPath("Desktop")
$ShortcutPath = Join-Path $DesktopDir "Tech Lookout.lnk"

$Shell = New-Object -ComObject WScript.Shell
$Shortcut = $Shell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = $PythonwExe
$Shortcut.Arguments = "`"$AppScript`""
$Shortcut.WorkingDirectory = $ProjectRoot
$Shortcut.IconLocation = $IconPath
$Shortcut.Description = "Tech Lookout - chat window, background scheduler, and manual pipeline trigger"
$Shortcut.Save()

Write-Host "Created shortcut: $ShortcutPath"
Write-Host "Target: $PythonwExe `"$AppScript`""
