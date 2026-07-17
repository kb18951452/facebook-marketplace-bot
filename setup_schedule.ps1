<#
.SYNOPSIS
    Registers Windows Task Scheduler tasks to run the FB Marketplace bot
    once per day, on 4 of 5 weekdays (Mon-Fri, no weekends).
    Each task launches run_daily_agent.bat, which first runs schedule_gate.py
    (picks a new random day off each week so the skip pattern doesn't repeat
    predictably) and then, on a run day, run_session.py — a 90-min supervised
    window that self-logs-in, lists, gathers stats, and auto-restarts the
    agent (resuming from state.json) if it crashes mid-run.
    Also registers the stats tracker (read-only FB scrape, every 3 days) and
    the local image pipeline (daily, does not touch Facebook).

    Reduced from 2x/day 7-day and an hourly stats scrape after the FB account
    was flagged for suspected automation — fewer, shorter, less predictable
    touches on the account.

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
$StatsBatFile   = Join-Path $RepoDir "run_stats_tracker.bat"
$TaskGroup      = "FacebookMarketplaceBot"

# 1 run per day at 08:00, Mon-Fri. schedule_gate.py skips one rotating day
# off per week, so only 4 of the 5 registered days actually run the agent.
# Session window is 90 min, leaving well over an hour of buffer before the
# ExecutionTimeLimit kicks in.
$Days = @("Monday","Tuesday","Wednesday","Thursday","Friday")
$RunTimes = @("08:00")

# ── Unregister mode ───────────────────────────────────────────────────────────
if ($Unregister) {
    $tasks = Get-ScheduledTask -TaskPath "\" -ErrorAction SilentlyContinue |
             Where-Object { $_.TaskName -like "${TaskGroup}_*" -or $_.TaskName -eq "FacebookStatsTracker_Hourly" }
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

# ── Register 1 task per weekday ───────────────────────────────────────────────
foreach ($time in $RunTimes) {
    foreach ($day in $Days) {
        $taskName = "${TaskGroup}_${day}"

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
            -ExecutionTimeLimit "02:00:00" `
            -MultipleInstances IgnoreNew `
            -StartWhenAvailable

        Register-ScheduledTask `
            -TaskName $taskName `
            -Action $action `
            -Trigger $trigger `
            -Settings $settings `
            -RunLevel Limited `
            -Description "FB Marketplace bot - $day at $time (90 min supervised session, or skipped if $day is this week's rotating day off)" `
            -Force | Out-Null

        Write-Host "Registered: $taskName at $time"
    }
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

# ── Stats tracker task — read-only FB scrape, every 3 days ──────────────────
# Previously hourly/24-7 (set up ad hoc outside this script, undocumented) —
# cut way back since round-the-clock scraping of the account's own selling
# page was a likely contributor to the automation flag.
Unregister-ScheduledTask -TaskName "FacebookStatsTracker_Hourly" -Confirm:$false -ErrorAction SilentlyContinue
$statsTaskName = "${TaskGroup}_StatsTracker"
Unregister-ScheduledTask -TaskName $statsTaskName -Confirm:$false -ErrorAction SilentlyContinue

$action = New-ScheduledTaskAction `
    -Execute "cmd.exe" `
    -Argument "/c `"$StatsBatFile`"" `
    -WorkingDirectory $RepoDir

$trigger = New-ScheduledTaskTrigger `
    -Daily `
    -DaysInterval 3 `
    -At "14:00"

$settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit "00:30:00" `
    -MultipleInstances IgnoreNew `
    -StartWhenAvailable

Register-ScheduledTask `
    -TaskName $statsTaskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -RunLevel Limited `
    -Description "FB Bot stats tracker (read-only scrape) - every 3 days at 14:00" `
    -Force | Out-Null

Write-Host "Registered: $statsTaskName at 14:00, every 3 days"

Write-Host ""
Write-Host "Done. 5 listing tasks + 7 image pipeline tasks + 1 stats tracker task registered."
Write-Host "Listing agent: 08:00 Mon-Fri (90 min supervised session, one rotating day off per week, auto-restart on crash)"
Write-Host "Image pipeline: 06:00 daily (Mon-Sun)"
Write-Host "Stats tracker: 14:00, every 3 days"
Write-Host "To remove all: .\setup_schedule.ps1 -Unregister"
