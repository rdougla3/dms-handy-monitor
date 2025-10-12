import time
import controller as cntrl
import parser as pr
import job_store as js
from gspread_updater import SheetClient

def update_in_progress_jobs(store, sheet_client):
    cntrl.go_to_printing_history()
    in_progress = store.get_jobs(status="printing")
    for job in in_progress:
        print(f"Checking inprogress job {job.name}...")
        entry = scroll_to_job(job)
        job.status = entry[1]
        check_machine_errors(job)
        sheet_client.update_job(job)

def check_machine_errors(job):
    print(f"Checking errors on {job.machine}...")
    cntrl.go_to_device_page(job.machine)

    if(cntrl.find_by_desc("Warning")):
        content = list(pr.parse_screen(long_clickable_only=False).keys())
        if content[1] not in job.errors:
            job.errors.append(content[1])

def scroll_to_job(job):
    print(f"Scrolling down to locate job {job.name}...")
    cntrl.go_to_printing_history()
    screen = pr.parse_screen()
    snapshots = list(screen.keys())
    for s in snapshots:
        if s[2] == job.name and pr.parse_job_date(s[5]) == job.date:
            return s

    cntrl.scroll_down(screen)
    scroll_to_job(job)

def check_for_later_jobs(store, sheet_client):
    print(f"Checking for more recent jobs...")
    screen = pr.parse_screen()
    for s in screen.keys():
        j = job_from_screen_entry(s)
        if store.find_job(j.name, j.date) is None: 
            get_job_details(screen[s], j)
            store.add_job(j)
            sheet_client.update_job(j)

    cntrl.scroll_up(screen)
    time.sleep(1)
    screen2 = pr.parse_screen()
    if screen2 != screen:
        check_for_later_jobs(store, sheet_client)

def get_job_details(bounds, job):
    print(f"Getting details for {job.name}...")
    cntrl.tap_by_bounds(bounds)

    content = list(pr.parse_screen(long_clickable_only=False).keys())
    index = content.index("Filaments")
    if index != -1:
        job.weight = float(content[index + 1].replace("g","").strip())
        job.materials.extend(content[index + 2 : len(content)- 1 ][::2])

    cntrl.tap_by_desc("Back")
    return job

def job_from_screen_entry(s):
    _duration: float
    if "s" in s[3].lower():
        _duration = float(s[3].replace("s","")) / 3600
    elif "min" in s[3].lower():
        _duration = float(s[3].replace("min","")) / 60
    else:
        _duration = float(s[3].replace("h",""))

    return js.PrintJob(
        status = s[1],
        name = s[2],
        duration = _duration,
        machine = s[4],
        date = pr.parse_job_date(s[5]),
        weight=0.0,
        materials=[],
        errors=[]
    )

if __name__ == "__main__":
    store = js.JobStore()
    sheet_client = SheetClient()

    cntrl.go_to_printing_history()
    screen = pr.parse_screen()
    snapshot = list(screen.keys())[0]
    latest_job = job_from_screen_entry(snapshot)
    get_job_details(screen[snapshot], latest_job)
    store.add_job(latest_job)
    sheet_client.update_job(latest_job)

    while True:
        try:
            # Check for new jobs since last run
            print("Checking for new jobs...")
            scroll_to_job(store.get_latest_job())
            check_for_later_jobs(store, sheet_client)

            # Update in-progress jobs in memory
            print("Updating in-progress jobs...")
            update_in_progress_jobs(store, sheet_client)

            # Purge very old jobs from in-memory store
            if len(store) > 100:
                store = store[50:]

            # Wait 5 minutes before next check
            print("Waiting 5 minutes before next check")
            time.sleep(300)

        except Exception as e:
            print(f"Error occurred: {e}. Restarting loop...")
            cntrl.go_to_printing_history()
            continue