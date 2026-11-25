# PD Uploader 0.3.0

A separate desktop release based on the existing uploader. The 0.2.0 fallback package and its profile are not modified. Distribution remains a **folder application**, built with PyInstaller on Windows, using installed Microsoft Edge.

## Using the app

1. Open one or more CSV files. Each file has its own tab, rows, selection and managed browser profile. The queue starts empty every launch; only the last picker directory is remembered.
2. Select rows before starting. Click **Open PD Board** and log in to the assigned Edge windows as needed. Preparation validates the form and destination; a click is never treated as proof of login. **Back** leaves previously prepared sessions intact.
3. After the selected sessions are prepared, click **Start upload** / **Start all uploads**. Jobs run in addition order, one row at a time. Switching the viewed tab does not change the execution target.
4. **Pause upload** stops before the next row. A row already being submitted finishes waiting for server confirmation first; the UI shows **Pausing**. **Resume upload** continues without repeating confirmed rows.
5. While paused, **Skip current board** affects the execution-current job, even if you are viewing a different tab. **Cancel all uploads** preserves results. Both ask for confirmation.
6. Results remain visible until **New upload**. **Retry failed** appears only for failures known to occur before submission. The global denominator stays fixed; failures, skipped and cancelled images never count as success.

The monitor counts images, while the server operation remains the existing whole CSV row (up to six images). No partial-row upload is attempted when an image is invalid. Double-click a table row or use its context menu to inspect its image slots and diagnostics. Select with the checkboxes or Space. The Activity log can be expanded, copied and exported.

## Slow server and confirmations

A slow login, form, option list or upload confirmation does not cause the next upload to start. The production adapter has no 15-second "continue anyway" fallback for upload confirmation, and does not resubmit just because a response is slow. Pause and cancellation can interrupt preparation; they do not abort a server-side write already submitted.

Success is recognized from a popup explicitly reporting successful upload/save, or the supported "Image(s) ... uploaded" wording. Arbitrary dialogs, including a bare "OK", do not prove success. The exact production popup wording still needs a Windows smoke test. Unexpected/error popups or a closed browser after submission leave an **Outcome unknown** and block automatic continuation.

For an unknown outcome, check the saved images on the assigned board. **Review upload result** only marks the row successful after you explicitly confirm that every image in that row was saved. If unsure, choose No; the row is not automatically retried. You can skip the remaining board or cancel. This confirmation is for verification of an exceptional result, not routine login or normal uploads.

On close during a run, the app first requests a safe pause. Cancelling the exit prompt resumes a previously running queue. If the server never responds, a second close request offers a separate explicit warning: exiting cannot cancel a server-side save. Unconfirmed outcomes are retained as unknown, with no automatic replay.

## CSV compatibility

The schema remains:

```csv
enabled,page_url,tier,department,shift,metric,image_1,image_2,image_3,image_4,image_5,image_6
```

- UTF-8 CSV, comma-separated, with optional BOM. Existing enabled/disabled values are supported.
- Enabled rows require a destination and nonblank Tier, Department, Shift and Metric.
- Only `.jpg` (case-insensitive). Relative paths resolve against the CSV directory; environment variables/user-directory expansion are preserved.
- CSV mappings are snapshotted at load. Missing files remain visible and counted if selected; their row fails before submission. A missing file can be supplied at the original mapped path and retried safely. Existing images are checked for readability, JPG signature and size/modification changes before sending; changed images require a new queue to reload the mapping.
- Each row's `page_url` is used. When the target changes within a job, the managed page navigates to that target before sending. URL origin and `siteid` are checked against the page's existing `#crsite` evidence. A mismatched/unknown target prevents submission. Without a URL `siteid`, initial binding requires the requested document itself and a nonempty `#crsite`; ambiguous redirects require verification rather than guessing.
- Empty image slots are cleared so a previous row's files cannot leak into a later upload.
- Local or approved synced OneDrive/SharePoint paths work through the filesystem. Online-only availability requires an on-site test. Direct SharePoint URLs/Graph integration are not implemented.

No real mappings, site names, internal addresses, credentials or operational logs belong in this repository. The example is deliberately generic and not a usable production mapping.

## Isolation and diagnostics

Each job owns an explicit page and a separate temporary Edge profile. All Playwright operations stay on one permanent worker thread, sharing only the Playwright runtime. Personal Edge windows/profiles are not attached to or closed. Job sessions are kept while needed and cleaned up on removal/New upload/exit. OS file locks or process crashes can leave a temporary profile in the OS temporary directory; cleanup failure is logged, and unrelated Edge processes are never killed. No storage-state export is created.

0.3.0 uses its own `PDUploader030` application-data directory. Logs rotate at 512 KB with six backups. URLs, credential fields and common personal paths are redacted. No default screenshots or raw HTML dumps are taken by the production adapter. Copied/exported diagnostics can still contain operational values or filenames; review them before sharing externally.

`logs/last-result.json` records only job IDs, row numbers, statuses and image counts/statuses. It contains no URLs, file paths, mappings or credentials. It is an informational checkpoint, **not automatic crash recovery** and not proof of an unconfirmed server write. Each new queue replaces the previous summary; the queue is never automatically reloaded.

## Architecture

- `jobs.py`: independent job/row/image records, selection and file preflight.
- `engine.py`: sequential scheduling, pause/resume/skip/cancel, fixed image accounting and monotonic active time.
- `sessions.py`: managed-session ownership, destination checks, production confirmation handling and safe outcome classification.
- `bot.py`: preserved form field/option/AJAX/file-slot automation; the GUI uses `ManagedSession`, not the old `run_rows` orchestration.
- `app.py`: agreed compact two-panel desktop UI, independent selected tab, typed queue events and Activity log.
- `diagnostics.py`: redaction, bounded logging, result summary and picker-directory preference.

The verified field-mapping workflow is preserved rather than replaced with direct upload requests. No new theme settings, dashboard, browser attachment or company-specific configuration is introduced.

## Development and Windows build

Windows requires Microsoft Edge. For source development/building, install Python 3.11, then run `BUILD-WINDOWS.cmd`, or:

```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pip install -e .
python -m unittest discover -s tests
python -m control_room_uploader
pyinstaller --noconfirm control_room_uploader.spec
```

Output: `dist/PDUploader-0.3.0/PDUploader-0.3.0.exe`. Distribute **the entire folder**, including `_internal`, never the EXE alone. End users of the built folder do not need Python. No onefile build is used.

GitHub Actions builds on pull requests to main, pushes to main / uploader-0.3.0 / codex branches, version tags, and manual dispatch. The artifact is `PDUploader-0.3.0-windows`. A version tag also publishes the folder ZIP as a release asset. Build/start from an approved local non-synced directory; CSV and JPG sources may remain on approved synced paths.

## Validation and remaining environment tests

54 automated tests pass locally under Python 3.14, covering the inherited mapping workflow plus independent jobs/duplicate names, sequential execution, frozen selection, row-boundary pause, cancellation settlement, unknown outcomes, reauthentication, safe retry, fixed counts/timer, delayed confirmations/options beyond a minute, file failures/changes, profile ownership, target mismatch and redaction.

The desktop layout was launched and visually inspected on macOS. Automated native interaction through the macOS test surface did not establish a complete two-file GUI acceptance test; independent job data and view/execution separation are covered in code tests.

Not yet tested here: Windows Python 3.11 / packaged EXE, installed corporate Edge, real server popup wording and write semantics, real login/SSO expiry, foreground versus minimized behavior, unrelated personal Edge windows on Windows, and synced/online-only SharePoint files. No production uploads were performed. The first Windows test should use one approved test row before a larger queue. Automatic minimize and View Edge are deliberately omitted until reliable restoration/background behavior is tested. There is no claim of server-side idempotency or automatic recovery from unknown outcomes.
