# -*- coding: utf-8 -*-
import os
import subprocess
import time
from datetime import datetime, timedelta

def run_command():
    print(f"[{datetime.now().isoformat()}] Running: flask auto-transition-courses")
    try:
        # Run the flask CLI command
        result = subprocess.run(
            ["flask", "auto-transition-courses"],
            capture_output=True,
            text=True,
            check=True
        )
        print(f"[{datetime.now().isoformat()}] Success: {result.stdout.strip()}")
    except subprocess.CalledProcessError as e:
        print(f"[{datetime.now().isoformat()}] Error running auto-transition-courses command:")
        print(e.stderr)

def main():
    print(f"[{datetime.now().isoformat()}] Course auto-transition scheduler daemon started.")
    
    # Run once immediately on startup to ensure transition state is fresh
    run_command()
    
    while True:
        # Calculate time until next midnight (00:00:00)
        now = datetime.now()
        next_run = datetime(now.year, now.month, now.day) + timedelta(days=1)
        sleep_seconds = (next_run - now).total_seconds()
        
        print(f"[{now.isoformat()}] Next transition scheduled at {next_run.isoformat()} (sleeping for {sleep_seconds:.1f} seconds)")
        
        # Sleep in smaller increments to allow clean shutdown/signals if needed
        # (e.g. sleep 60 seconds at a time)
        while sleep_seconds > 0:
            sleep_chunk = min(sleep_seconds, 60)
            time.sleep(sleep_chunk)
            sleep_seconds -= sleep_chunk
            
        run_command()

if __name__ == "__main__":
    main()
