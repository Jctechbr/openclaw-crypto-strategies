# HEARTBEAT.md

# Daily System Update Check
- Check for new log files matching `~/scripts/update_log_$(date +%F).txt`.
- If a log file exists for today and does NOT contain the line "REPORT_SENT":
  1. Read the log content.
  2. Summarize the update: start time, number of packages upgraded (count lines containing "upgraded"), disk usage, and check for "error" or "fail".
  3. Send a concise report to Telegram user `195050411` using the `message` tool (channel="telegram").
  4. Append "REPORT_SENT" to the log file to prevent duplicate reports.