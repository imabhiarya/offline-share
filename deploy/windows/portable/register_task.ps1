# Registers OFFLINE SHARE as a Windows startup task: runs as SYSTEM at boot, restarts on failure, no time limit.
param([Parameter(Mandatory=$true)][string]$InstallDir)
$name = 'OfflineShare'
Unregister-ScheduledTask -TaskName $name -Confirm:$false -ErrorAction SilentlyContinue
$action   = New-ScheduledTaskAction -Execute (Join-Path $InstallDir 'python\python.exe') `
            -Argument ('"' + (Join-Path $InstallDir 'backend\offline_share.py') + '" serve') -WorkingDirectory $InstallDir
$trigger  = New-ScheduledTaskTrigger -AtStartup
$principal= New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
            -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName $name -Action $action -Trigger $trigger -Principal $principal -Settings $settings `
  -Description 'OFFLINE SHARE - Local Data Transfer Server (LAN). Starts automatically with Windows.' | Out-Null
Write-Host "Startup task '$name' registered (runs as SYSTEM at boot, restarts on failure)."
