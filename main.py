from datetime import datetime
import time
import controller as cntrl
import parser as pr
import job_store as js
from gspread_updater import SheetClient

def update_in_progress_jobs(store, sheet_client):
    """
    Update all jobs in progress by checking their current status and errors, then sync to the sheet.
    """
    in_progress = store.get_jobs(status="Printing")
    for job in in_progress:
        print(f"Checking inprogress job {job.name}...")
        cntrl.go_to_printing_history()
        _job = scroll_to_job(job)
        if _job.status == "Printing":
            check_machine_errors(job)
        job.status = _job.status
        sheet_client.update_job(job)


def check_machine_errors(job):
    """
    Check the assigned machine for warnings and append new errors to the job.
    """
    print(f"Checking errors on {job.machine}...")
    cntrl.go_to_device_page(job.machine)

    if cntrl.find_by_desc("Warning"):
        # Pull the second element of the parsed screen as the error content
        content = list(pr.parse_screen(long_clickable_only=False).keys())
        if content[1] not in job.errors:
            job.errors.append(content[1])


def scroll_to_job(job, prev_screen=None):
    """
    Scroll through the print history to locate a specific job by name and date, returning the job or None.
    """
    print(f"Scrolling down to locate job {job.name}...")
    screen = pr.parse_screen()
    snapshots = list(screen.keys())

    # Stop scrolling if the screen has not changed
    if prev_screen is not None and screen.keys() == prev_screen.keys():
        print(f"Job {job.name} not found.")
        return None

    for s in snapshots:
        _job = job_from_screen_entry(s)
        if _job.name == job.name and _job.date == job.date:
            return _job

    cntrl.scroll_down(screen)
    return scroll_to_job(job, screen)


def check_for_later_jobs(store, sheet_client):
    """
    Scan for newer jobs not yet in the store and add them, updating the sheet.
    """
    print(f"Checking for more recent jobs...")
    screen = pr.parse_screen()
    for s in screen.keys():
        j = job_from_screen_entry(s)
        if store.find_job(j.name, j.date) is None: 
            get_job_details(screen[s], j)
            store.add_job(j)
            sheet_client.update_job(j)

    # Scroll up and repeat as long as the screen keeps changing
    cntrl.scroll_up(screen)
    time.sleep(1)
    screen2 = pr.parse_screen()
    if screen2 != screen:
        check_for_later_jobs(store, sheet_client)


def get_job_details(bounds, job):
    """
    Tap into a job to extract weight and material details, then return to history.
    """
    print(f"Getting details for {job.name}...")
    cntrl.tap_by_bounds(bounds)

    content = list(pr.parse_screen(long_clickable_only=False).keys())
    index = content.index("Filaments")
    if index != -1:
        job.weight = float(content[index + 1].replace("g","").strip())
        _materials = content[index + 2 : len(content) -1]
        materials = _materials[:len(_materials) // 2]  # First half is materials, second is AMS slots
        job.materials.extend(materials)
        
    cntrl.tap_by_desc("Back")
    return job


def job_from_screen_entry(s):
    """
    Convert a parsed screen entry list into a PrintJob object.
    """
    if s is None:
        return None 
    
    s = list(s)
    if len(s) == 7: del s[3]  # Remove extra element if present

    # Convert duration string to hours
    _duration: float
    if "s" in s[3].lower():
        _duration = float(s[3].replace("s","")) / 3600
    elif "min" in s[3].lower():
        _duration = float(s[3].replace("min","")) / 60
    else:
        _duration = float(s[3].replace("h",""))        
    _duration = round(_duration, 1)

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


def get_init_job():
    """
    Return the job to resume on startup: earliest in-progress, most recent in sheets, or first GUI entry.
    """
    
    latest_job = sheet_client.get_oldest_in_progress_job()

    # Fallback to most recent job recorded jobs are in progress
    if latest_job is None:
        latest_job = sheet_client.get_most_recent_job()

        # Fallback to GUI if no jobs recorded at all
        # This becomes the first entry.
        if latest_job is None:
            latest_job = get_first_gui_entry()
            latest_job = get_job_details(latest_job)
            sheet_client.update_job(latest_job)

    return latest_job


def get_first_gui_entry():
    """
    Return the first job entry visible in the GUI.
    """
    cntrl.go_to_printing_history()
    screen = pr.parse_screen()
    snapshot = list(screen.keys())[0]
    job = job_from_screen_entry(snapshot)
    get_job_details(screen[snapshot], job)
    return job


if __name__ == "__main__":
    store = js.JobStore()
    sheet_client = SheetClient()
    
    store.add_job(get_init_job())  # Initialize with the earliest/resumable job

    while True:
        try:
            # Check for new jobs since last run
            print("Checking for new jobs...")
            cntrl.go_to_printing_history()
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