# Windows acceptance checks

Use only approved test data and an approved destination; keep operational data out of GitHub. No production upload was performed during local development.

1. Build the `uploader-0.3.0` branch with GitHub Actions. Extract the complete folder locally and start the EXE. Verify version 0.3.0, empty queue and no reuse of the 0.2.0 profile.
2. Open two CSVs with different rows/counts. Switch tabs, change selections, inspect rows and test duplicate basenames. Switching view must not change global progress or execution order.
3. Prepare managed sessions sequentially; check Back, login, correct destination and reconnect after closing a managed window. Leave unrelated Edge windows open; they must be untouched.
4. Upload one approved test row. Verify the actual popup text and saved images. If wording is unrecognized, expect Outcome unknown and no automatic second submit. Use manual result confirmation only after checking all images in that row.
5. Test loading/confirmation delays over one minute. Expect Waiting for server with responsive UI; no next row, re-click or reload before confirmation.
6. Pause before preparation completes and while submit is in flight. Expect no new submit after the safe boundary. Resume must not repeat confirmed rows. Timer must freeze once paused and during login recovery.
7. While paused and viewing another tab, skip the execution-current board. Retain completed rows, mark remaining work skipped and advance to the next job. Cancel must retain results and the original denominator.
8. Close a managed browser after submit / simulate lost confirmation. Expect unknown result and blocked automatic continuation. Verify before any repeat. Test exit cancellation and deliberate exit while waiting.
9. Test missing/unreadable/changed/non-JPG files. No partial row should be sent accidentally. Retry must only include known pre-submit failures, retaining successful counts.
10. Check 106 confirmed + 18 skipped out of 124 => 85%, with no green complete-success ring. All confirmed => green success. No completion popup or automatic clearing.
11. Compare a managed Edge window left behind another window with a minimized window. Background/minimized reliability is not pre-certified; do not enable automatic minimization without evidence.
12. Test CSV/JPGs from approved synced SharePoint paths, including online-only availability. Check startup from a local non-synced application folder. Inspect sanitized diagnostics and the minimal result summary before external sharing.
