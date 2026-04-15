# Reports Scheduler

This project uses user-level `systemd` units on Ubuntu to run report scripts on a schedule.

## Files

- Service: `~/.config/systemd/user/reports-daily-morning.service`
- Timer: `~/.config/systemd/user/reports-daily-morning.timer`
- Wrapper script: `/home/newuser1/work/new_project/training/reports/run_daily_morning.sh`

The service calls the wrapper script, and the wrapper runs the morning jobs in order.

## Example service

```ini
[Unit]
Description=Run daily morning report
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
WorkingDirectory=/home/newuser1/work/new_project/training/reports
Environment=HOME=/home/newuser1
Environment=PATH=/home/newuser1/.local/bin:/usr/bin:/bin
ExecStart=/home/newuser1/work/new_project/training/reports/run_daily_morning.sh
StandardOutput=append:/home/newuser1/work/new_project/training/reports/logs/daily_morning.log
StandardError=append:/home/newuser1/work/new_project/training/reports/logs/daily_morning.log

[Install]
WantedBy=default.target
```

## Example timer

```ini
[Unit]
Description=Run daily morning report every day

[Timer]
OnCalendar=*-*-* 04:20:00
Persistent=true

[Install]
WantedBy=timers.target
```

## Environment variables

Sensitive keys must be injected into the systemd user manager environment so they are available to the service via `os.environ`:

```bash
systemctl --user set-environment COINGECKO_API_KEY=<key> INFLUXDB_TOKEN=<token>
```

This persists for the lifetime of the current login session but **does not survive a reboot**. To re-apply automatically on login, add the command to `~/.bashrc` (or `~/.profile` for non-interactive sessions):

To verify the vars are set:

```bash
systemctl --user show-environment | grep -E "COINGECKO|INFLUXDB"
```

## Setup

```bash
mkdir -p ~/.config/systemd/user
mkdir -p /home/newuser1/work/new_project/training/reports/logs
chmod +x /home/newuser1/work/new_project/training/reports/run_daily_morning.sh
systemctl --user daemon-reload
systemctl --user enable --now reports-daily-morning.timer
```

## Common commands

```bash
# start once now
systemctl --user start reports-daily-morning.service

# start the timer now
systemctl --user start reports-daily-morning.timer

# enable timer on login/reboot
systemctl --user enable --now reports-daily-morning.timer

# stop timer
systemctl --user stop reports-daily-morning.timer

# disable timer
systemctl --user disable reports-daily-morning.timer

# reload after editing .service or .timer
systemctl --user daemon-reload

# if the timer schedule changed, restart the timer
systemctl --user restart reports-daily-morning.timer

# if you want to run the job once right now, start the service
systemctl --user start reports-daily-morning.service

# status
systemctl --user status reports-daily-morning.service
systemctl --user status reports-daily-morning.timer
systemctl --user list-timers --all

# logs
tail -n 100 /home/newuser1/work/new_project/training/reports/logs/daily_morning.log
journalctl --user -u reports-daily-morning.service -n 100 --no-pager
```

## Notes

- Use one `.service` and one `.timer` per scheduled script.
- If one schedule should run multiple scripts, put them in a wrapper script and call that script from one `ExecStart`.
- `start` runs now; `enable` makes the timer start automatically in future sessions.
- After editing `.service` or `.timer`, run `systemctl --user daemon-reload`.
- Restart the `.timer` only if you changed the schedule and want the new timing applied immediately.
- Start the `.service` only if you want to run the job now as a manual test.
