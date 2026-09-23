$ErrorActionPreference = 'Stop'
$version = (Get-Content 'dist/ShiguangCapture/VERSION' -Raw).Trim()
$installer = Join-Path $PWD "dist/ShiguangCapture-v$version-Windows-x86_64-Setup.exe"
$target = Join-Path $env:LOCALAPPDATA 'Programs/ShiguangCapture'
$logs = Join-Path $PWD 'artifacts/installer-tests'
New-Item -ItemType Directory -Force $logs | Out-Null
function Run-Checked($file, $arguments) {
    $process = Start-Process -FilePath $file -ArgumentList $arguments -PassThru
    if (-not $process.WaitForExit(180000)) { $process.Kill($true); throw "Timed out: $file" }
    if ($process.ExitCode -ne 0) { throw "Failed: $file ($($process.ExitCode))" }
}
Run-Checked $installer @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/TASKS=desktopicon', "/LOG=`"$logs/install.log`"")
if ((Get-Content "$target/VERSION" -Raw).Trim() -ne $version) { throw 'Installed version mismatch' }
$desktop = Join-Path ([Environment]::GetFolderPath('Desktop')) 'Shiguang Capture.lnk'
$menu = Join-Path ([Environment]::GetFolderPath('Programs')) 'Shiguang Capture.lnk'
$shell = New-Object -ComObject WScript.Shell
foreach ($shortcut in @($desktop, $menu)) {
    if (-not (Test-Path $shortcut)) { throw "Missing shortcut: $shortcut" }
    if ($shell.CreateShortcut($shortcut).TargetPath -ne "$target\ShiguangCapture.exe") { throw 'Incorrect shortcut target' }
}
$env:SHIGUANG_SELF_TEST_LOG = "$logs/installed-self-test.log"
Run-Checked "$target/ShiguangCapture.exe" @('--self-test')
Get-Content $env:SHIGUANG_SELF_TEST_LOG
# Reinstall and removal must preserve user settings and saved captures.
$config = Join-Path $env:APPDATA 'shiguang-capture/installer-preservation-test.txt'
New-Item -ItemType Directory -Force (Split-Path $config) | Out-Null
Set-Content $config 'preserve-user-settings'
Run-Checked $installer @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', "/LOG=`"$logs/reinstall.log`"")
Run-Checked "$target/unins000.exe" @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', "/LOG=`"$logs/uninstall.log`"")
for ($i = 0; $i -lt 30 -and (Test-Path "$target/ShiguangCapture.exe"); $i++) { Start-Sleep -Seconds 1 }
if (Test-Path "$target/ShiguangCapture.exe") { throw 'Uninstall left the executable' }
if ((Test-Path $desktop) -or (Test-Path $menu)) { throw 'Uninstall left shortcuts' }
if ((Get-Content $config -Raw).Trim() -ne 'preserve-user-settings') { throw 'Uninstall removed user settings' }
Remove-Item $config
'Install, shortcuts, launch, reinstall, uninstall and settings preservation passed.' | Set-Content "$logs/result.txt"
