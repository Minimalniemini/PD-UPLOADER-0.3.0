# 0.3.0

Separate release based on the local 0.2.0 changes; no mutation of the fallback archive or profile.

- Independent real CSV tabs, per-job selections and temporary managed browser sessions.
- Sequential row uploads using the existing field mapping and six file slots.
- Typed queue state and events instead of progress inferred from log text.
- Row-boundary Pause/Resume, safe Skip/Cancel and exit handling.
- Slow-server waits without a timed "continue anyway" after missing confirmation.
- Conservative popup classification; unknown outcomes block automatic continuation and retry.
- Image-based fixed-denominator progress, retained results and monotonic active time.
- Safe retry for known pre-submit failures; no partial-row or unknown-outcome replay.
- Compact agreed desktop layout, Activity log with copy/export and row inspection.
- Sanitized rotating diagnostics and minimal result checkpoint, with no automatic queue restoration.
- Separate application-data directory and versioned folder-based build/artifact.

Windows Edge and real-server acceptance testing are still required. Automatic minimize/View Edge are not enabled. Production confirmation wording is not hardcoded to an unobserved company-specific message.
