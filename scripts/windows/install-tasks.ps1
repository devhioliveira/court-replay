# Registra o agente e o painel para iniciarem sozinhos quando o usuario atual
# fizer login no Windows. Rode UMA vez, no PowerShell, como o usuario que ficara
# logado no computador da quadra (nao precisa ser administrador).
#
#   powershell -ExecutionPolicy Bypass -File scripts\windows\install-tasks.ps1

$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path

$tasks = @(
    @{ Name = 'CourtReplay-Agent';  Script = Join-Path $here 'start-agent.bat'  },
    @{ Name = 'CourtReplay-Server'; Script = Join-Path $here 'start-server.bat' }
)

$user = "$env:USERDOMAIN\$env:USERNAME"

foreach ($t in $tasks) {
    $action    = New-ScheduledTaskAction -Execute 'cmd.exe' -Argument "/c `"$($t.Script)`""
    $trigger   = New-ScheduledTaskTrigger -AtLogOn -User $user
    $trigger.Delay = 'PT20S'   # espera a rede subir
    $settings  = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
                   -ExecutionTimeLimit ([TimeSpan]::Zero) -StartWhenAvailable
    $principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited

    Register-ScheduledTask -TaskName $t.Name -Action $action -Trigger $trigger `
        -Settings $settings -Principal $principal -Force | Out-Null
    Write-Host "Tarefa registrada: $($t.Name)"
}

Write-Host ""
Write-Host "Pronto. Elas iniciam no proximo login. Para iniciar agora:"
Write-Host "  schtasks /Run /TN CourtReplay-Agent"
Write-Host "  schtasks /Run /TN CourtReplay-Server"
