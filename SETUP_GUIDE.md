# Start here — Windows

1. Extract **FlowRelay-GitHub.zip**: right-click → **Extract All**.
2. Open the extracted **FlowRelay** folder containing `server.py`.
3. Click File Explorer's address bar, type `cmd`, and press Enter.
4. Type `py --version`. Python 3.10+ is required. If unavailable, install Python
   from python.org with its launcher and reopen the terminal.
5. Type `py server.py` and press Enter.
6. Open Chrome and enter **http://127.0.0.1:8000**.
7. Choose **Success**, click **Receive event**, then **Process next due event**.
8. Leave the command window open while using the app. Ctrl+C stops it.

If `py` is unavailable but `python --version` works, replace `py` with `python`.
If port 8000 is occupied, run `py server.py --port 8080` and open
http://127.0.0.1:8080. Do not open the HTML file directly.

## Upload to GitHub

1. Create a public repository named **FlowRelay**.
2. Suggested description: **Local webhook event workbench with Python, SQLite,
   JSON validation, duplicate protection, retry simulation, and automated tests.**
3. Choose **uploading an existing file**.
4. Drag the *contents* of the extracted FlowRelay folder into the upload area,
   preserving `static` and `tests` folders. Do not upload the ZIP itself.
5. Include `.gitignore` and `.github/workflows/tests.yml`. If your browser blocks
   the hidden folder, use **Add file → Create new file**, type
   `.github/workflows/tests.yml`, and paste the exact contents from the local
   workflow (open it using Notepad). Do not place tests.yml at the repository root.
6. Commit with **Add FlowRelay event workbench**.
7. Open **Actions** to check the test results.
8. Pin the project on your profile when you can run it and explain its behavior.

Do not upload flowrelay.db or __pycache__ folders. They are excluded by .gitignore.
This is a local server project: enabling GitHub Pages will not run the API.

## Reset the demonstration

Stop the server, then delete `flowrelay.db` from the project folder. This deletes
all your local events. Starting again creates a new empty database.
