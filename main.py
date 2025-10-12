import os
import time

from controller import tap_by_desc, tap_by_bounds, find_by_desc
from parser import parse_screen, parse_job_date
import job_store as js
from gspread_updater import SheetClient

class RestartLoop(Exception):
    pass

if __name__ == "__main__":  
    store = js.JobStore()
    sheet_client = SheetClient()

    while True:
        try:
            # Enter Printing History
            os.system("adb shell input keyevent KEYCODE_BACK")
            tap_by_desc("Me")
            tap_by_desc("Printing History")
            snapshots = parse_screen()
        
            for s in snapshots.keys():   
                try:
                    current_screen = parse_screen()
                    if snapshots != current_screen:
                        print("Screen changed during scraping, restarting loop")
                        raise RestartLoop()

                    job = js.PrintJob(
                        status = s[1],
                        name = s[2],
                        duration = float(s[3].replace("h","")) if "min" not in s[3] else float(s[3].replace("min","")) / 60.0,
                        machine = s[4],
                        date = parse_job_date(s[5]),
                        weight=0.0,
                        materials=[],
                        errors=[]
                    )

                    if store.job_exists(job.name, job.date):
                        # Update existing job (if needed)
                        status = job.status
                        job = store.find_job(job.name, job.date)
                        if job.status != status:
                            print(f"Updating job status: {job.name} {job.status} -> {status}")
                            job.status = status
                    else:
                        # Store new job
                        # Tap on job to get details
                        bounds = snapshots[s]
                        tap_by_bounds(bounds)

                        content = list(parse_screen(long_clickable_only=False).keys())
                        index = content.index("Filaments")
                        if index != -1:
                            job.weight = float(content[index + 1].replace("g","").strip())
                            job.materials.extend(content[index + 2 : len(content)- 1 ][::2])

                        store.add_job(job)
                        tap_by_desc("Back")

                    if job.status.lower() == "printing".lower():
                        # If job is currently printing,
                        # Go to device page to check errors
                        tap_by_desc("Back")
                        tap_by_desc("Devices")
                        tap_by_desc("brand_logo")
                        tap_by_desc(job.machine)

                        if(find_by_desc("Warning")):
                            content = list(parse_screen(long_clickable_only=False).keys())
                            if content[1] not in job.errors:
                                job.errors.append(content[1])
                            os.system("adb shell input keyevent KEYCODE_BACK")

                        tap_by_desc("Me")
                        tap_by_desc("Printing History")

                    sheet_client.update_job(job)
                    print(f"Updated job: {job.name} {job.status} {job.date} {job.duration}h on {job.machine}")

                except Exception as e:
                    # If RestartLoop was raised, re-raise so the outer handler restarts the while loop
                    if isinstance(e, RestartLoop):
                        raise
                    print(f"Error processing job entry {s}: {e}")
                    # Return to Printing History
                    os.system("adb shell input keyevent KEYCODE_BACK")
                    tap_by_desc("Me")
                    tap_by_desc("Printing History")
                    continue
        except RestartLoop:
            # Immediately restart the outer while loop (skip sleep)
            continue
            
        time.sleep(300)  # Wait 5 minutes before next check