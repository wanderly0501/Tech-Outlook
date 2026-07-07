"""
scheduler.py

Triggers pipeline_agent.py daily at 00:01 for *yesterday's* date — by
00:01 today's articles have barely started publishing, so the run
targets the day that just fully closed out. Run as a background process:
    python scheduler.py &
"""

import schedule
import subprocess
import sys
import time
from datetime import date, timedelta


def run_pipeline_for_yesterday():
    target_date = (date.today() - timedelta(days=1)).isoformat()
    subprocess.run([sys.executable, "pipeline_agent.py", target_date])


schedule.every().day.at("00:01").do(run_pipeline_for_yesterday)

if __name__ == "__main__":
    print("[scheduler] Waiting for daily 00:01 trigger (crawls the previous day's articles)...")
    while True:
        schedule.run_pending()
        time.sleep(3600)
