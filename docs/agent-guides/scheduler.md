# Scheduler

The systemd timer calls `run_daily_morning.sh`, which runs `market`, then `net_pnl`, then `trading_volume`. Logs go to `logs/daily_morning.log`. See `README.md` for full systemd setup and control commands.
