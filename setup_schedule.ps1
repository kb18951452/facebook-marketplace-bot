#Requires -RunAsAdministrator
<#
.SYNOPSIS
    Registers Windows Task Scheduler tasks to run the FB Marketplace bot
    Tuesday through Sunday around midday, with per-day base times.
    The agent itself adds 0-25 min random jitter and runs 50-75 min.

.NOTES
    Run once from an elevated PowerShell prompt:
        .\setup_schedule.ps1
    To remove all tasks:
        .\setup_schedule.ps1 -Unregister
#>

param(
    [switch]$Unregister
)

$RepoDir   = "C:\Users\kenne\gitrepo\facebook-marketplace-bot"
$BatFile   = Join-Path $RepoDir "run_daily_agent.bat"
$TaskGroup = "FacebookMarketplaceBot"

# Per-day base times (HH:mm). Agent jitter shifts actual start up to +25 min.
$Schedule = [ordered]@{
    Tuesday   = "11:00"
    Wednesday = "11:30"
    Thursday  = "10:45"
    Friday    = "11:15"
    Saturday  = "11:45"
    Sunday    = "11:00"
}

# ── Unregister mode ───────────────────────────────────────────────────────────
if ($Unregister) {
    foreach ($day in $Schedule.Keys) {
        $name = "${TaskGroup}_${day}"
        Unregister-ScheduledTask -TaskName $name -Confirm:$false -ErrorAction SilentlyContinue
        Write-Host "Removed: $name"
    }
    Write-Host "All tasks removed."
    exit 0
}

# ── Validate pre-conditions ───────────────────────────────────────────────────
if (-not (Test-Path $BatFile)) {
    Write-Error "run_daily_agent.bat not found at: $BatFile"
    exit 1
}

# Detect Python executable
$PythonExe = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $PythonExe) {
    Write-Error "Python not found in PATH. Install Python or set the PATH and re-run."
    exit 1
}
Write-Host "Using Python: $PythonExe"

# ── Register one task per day ─────────────────────────────────────────────────
foreach ($day in $Schedule.Keys) {
    $time     = $Schedule[$day]
    $taskName = "${TaskGroup}_${day}"

    # Remove stale entry if present
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue

    $action = New-ScheduledTaskAction `
        -Execute "cmd.exe" `
        -Argument "/c `"$BatFile`"" `
        -WorkingDirectory $RepoDir

    $trigger = New-ScheduledTaskTrigger `
        -Weekly `
        -DaysOfWeek $day `
        -At $time

    $settings = New-ScheduledTaskSettingsSet `
        -ExecutionTimeLimit "02:30:00" `
        -MultipleInstances IgnoreNew `
        -StartWhenAvailable

    Register-ScheduledTask `
        -TaskName $taskName `
        -Action $action `
        -Trigger $trigger `
        -Settings $settings `
        -RunLevel Highest `
        -Description "FB Marketplace bot — $day run" `
        -Force | Out-Null

    Write-Host "Registered: $taskName at $time (+ 0-25 min agent jitter)"
}

Write-Host ""
Write-Host "Done. Tasks will run Tue-Sun. Verify in Task Scheduler > $TaskGroup."
Write-Host "To remove all tasks: .\setup_schedule.ps1 -Unregister"
