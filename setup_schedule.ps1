<#
.SYNOPSIS
    Registers Windows Task Scheduler tasks to run the FB Marketplace bot
    2 times per day, Tuesday through Sunday.
    Agent adds 0-10 min random jitter and runs 210-250 min per session.
    2 runs x ~230 min = ~460 min/day of active listing time.

.NOTES
    Run once from an elevated PowerShell prompt:
        .\setup_schedule.ps1
    To remove all tasks:
        .\setup_schedule.ps1 -Unregister
#>

param(
    [switch]$Unregister
)

$RepoDir        = "C:\Users\kenne\gitrepo\facebook-marketplace-bot"
$BatFile        = Join-Path $RepoDir "run_daily_agent.bat"
$ImageBatFile   = Join-Path $RepoDir "run_image_pipeline.bat"
$TaskGroup      = "FacebookMarketplaceBot"

# 2 runs per day, 6-hour gap. Max run = jitter(10) + budget(250) = 260 min < 360 min gap.
$Days = @("Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday")
$RunTimes = @("09:00","16:00")

# ── Unregister mode ───────────────────────────────────────────────────────────
if ($Unregister) {
    $tasks = Get-ScheduledTask -TaskPath "\" -ErrorAction SilentlyContinue |
             Where-Object { $_.TaskName -like "${TaskGroup}_*" }
    foreach ($t in $tasks) {
        Unregister-ScheduledTask -TaskName $t.TaskName -Confirm:$false
        Write-Host "Removed: $($t.TaskName)"
    }
    Write-Host "All tasks removed."
    exit 0
}

# ── Validate pre-conditions ───────────────────────────────────────────────────
if (-not (Test-Path $BatFile)) {
    Write-Error "run_daily_agent.bat not found at: $BatFile"
    exit 1
}
if (-not (Test-Path $ImageBatFile)) {
    Write-Error "run_image_pipeline.bat not found at: $ImageBatFile"
    exit 1
}

$PythonExe = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $PythonExe) {
    Write-Error "Python not found in PATH."
    exit 1
}
Write-Host "Using Python: $PythonExe"

# ── Register 4 tasks per day ──────────────────────────────────────────────────
$runIndex = 1
foreach ($time in $RunTimes) {
    foreach ($day in $Days) {
        $taskName = "${TaskGroup}_${day}_Run${runIndex}"

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
            -ExecutionTimeLimit "05:00:00" `
            -MultipleInstances IgnoreNew `
            -StartWhenAvailable

        Register-ScheduledTask `
            -TaskName $taskName `
            -Action $action `
            -Trigger $trigger `
            -Settings $settings `
            -RunLevel Limited `
            -Description "FB Marketplace bot - $day run $runIndex at $time" `
            -Force | Out-Null

        Write-Host "Registered: $taskName at $time"
    }
    $runIndex++
}

# ── Image pipeline task — runs once daily at 06:00 Mon-Sun ───────────────────
# Runs before the first listing agent window (08:00) so fresh images are ready.
$imageDays = @("Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday")
foreach ($day in $imageDays) {
    $taskName = "${TaskGroup}_ImagePipeline_${day}"

    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue

    $action = New-ScheduledTaskAction `
        -Execute "cmd.exe" `
        -Argument "/c `"$ImageBatFile`"" `
        -WorkingDirectory $RepoDir

    $trigger = New-ScheduledTaskTrigger `
        -Weekly `
        -DaysOfWeek $day `
        -At "06:00"

    $settings = New-ScheduledTaskSettingsSet `
        -ExecutionTimeLimit "02:00:00" `
        -MultipleInstances IgnoreNew `
        -StartWhenAvailable

    Register-ScheduledTask `
        -TaskName $taskName `
        -Action $action `
        -Trigger $trigger `
        -Settings $settings `
        -RunLevel Limited `
        -Description "FB Bot image pipeline (harvest+verify) - $day at 06:00" `
        -Force | Out-Null

    Write-Host "Registered: $taskName at 06:00"
}

Write-Host ""
Write-Host "Done. 12 listing tasks + 7 image pipeline tasks registered."
Write-Host "Listing agent: 09:00, 16:00 Tue-Sun (+0-10 min jitter, 210-250 min budget)"
Write-Host "Image pipeline: 06:00 daily (Mon-Sun)"
Write-Host "To remove all: .\setup_schedule.ps1 -Unregister"
