$ErrorActionPreference = 'Stop'
$folder = Split-Path -Parent $MyInvocation.MyCommand.Path
$executable = Join-Path $folder 'ShiguangCapture.exe'
if (-not (Test-Path $executable)) { throw 'Keep this script beside ShiguangCapture.exe.' }
$shell = New-Object -ComObject WScript.Shell
foreach ($location in @([Environment]::GetFolderPath('Desktop'), [Environment]::GetFolderPath('Programs'))) {
    $shortcut = $shell.CreateShortcut((Join-Path $location 'Shiguang Capture.lnk'))
    $shortcut.TargetPath = $executable
    $shortcut.WorkingDirectory = $folder
    $shortcut.IconLocation = "$executable,0"
    $shortcut.Save()
}
Write-Output 'Desktop and Start menu shortcuts created. Keep the application folder in this location.'
