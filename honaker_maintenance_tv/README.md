# Honaker Aviation Maintenance TV Board

A Streamlit test board for displaying upcoming aircraft maintenance on a shop TV.

## What it does

- Upload a Traxxall Fleet Due List `.xlsx` export.
- Reads the `Task Export` sheet automatically.
- Rotates through only aircraft that have actionable upcoming maintenance.
- Shows a large **Next Big Inspection** only when its **controlling limit is under 30 hours**.
- Preserves tolerance values such as `(+100)` or `(+350)`.
- Understands Traxxall hour values such as `28:30 Hrs` as 28.5 hours.
- Uses `Next Due Date` versus `Estimated Due Date` when available to determine which calendar/utilization limit is projected to come first.
- Hides rows whose `Compliance Status` is completed/complied/closed/done.

## GitHub setup

1. Create a new GitHub repository, for example `maintenance-tv-board`.
2. Upload every file in this folder, including the `.streamlit` folder.
3. Commit the files.

## Streamlit Community Cloud

1. Sign in to Streamlit Community Cloud with GitHub.
2. Choose **Create app** / **Deploy an app**.
3. Select your GitHub repository.
4. Set the main file to `app.py`.
5. Deploy.
6. Open the resulting Streamlit URL.
7. Upload your newest Fleet Due List in the sidebar.
8. Collapse the sidebar and press **F11** in Chrome/Edge for TV full-screen mode.

## Important test-version limitation

The uploaded Excel file lives in the active Streamlit browser session. For the first test, upload the file from the browser connected to the TV and leave that page open.

For the production version, the next recommended change is to store/read the current due list from a shared source (SharePoint, OneDrive, Google Drive, a network location, or a database) so Kayla can update the data from her office and the TV refreshes without touching the TV browser.

## Display thresholds

Edit these near the top of `maintenance_logic.py`:

```python
COMING_UP_HOURS = 75.0
COMING_UP_DAYS = 30.0
COMING_UP_COUNTER = 75.0
BIG_INSPECTION_HOURS = 30.0
```

Rotation timing is at the top of `app.py`:

```python
ROTATE_SECONDS = 12
MAX_COMING_UP = 5
```

## Current definition of a big inspection

The test logic looks for inspection/package rows containing terms such as:

- Routine Periodic Inspection
- Inspection Document
- Inspection Phase
- Phase Inspection
- Major Inspection
- Continuous Inspection Program

This can be narrowed once the shop confirms exactly which inspection families should appear as the large TV headline.
