# Calendar availability monitor

Nintendo Museum's public calendar is checked with Chromium after JavaScript rendering.
The workflow requests execution every five minutes (minutes 2, 7, …, 57). GitHub may delay or skip scheduled runs; this is not a real-time guarantee.

## Setup

In this repository, open **Settings → Secrets and variables → Actions → New repository secret**.

| Secret | Value |
| --- | --- |
| `TARGET_DATES` | Desired dates, comma-separated, in `YYYY-MM-DD` format |
| `SMTP_USER` | Your Gmail address |
| `SMTP_PASSWORD` | A Google app password for this monitor, not your normal password |
| `NOTIFY_EMAIL` | Optional recipient; defaults to `SMTP_USER` |

Google app passwords require 2-Step Verification. Create one at https://myaccount.google.com/apppasswords . Never put credentials in a commit, issue, chat, or workflow input. Then open **Actions → Calendar monitor → Run workflow**. Successful first calendar inspection sends a setup confirmation email. If it is absent, setup is not verified. Enable push notifications for your mail app on your phone.

No personal target dates, addresses, or screenshots should be committed. Live email delivery cannot be tested until secrets are configured. No paid AI API is used.

## Detection and notifications

- Selects each month, checks the full year/month/day, then reads the displayed icon.
- Requires agreement between the circle/dash icon resource and two screenshots' pixel shapes. Blank, unknown, changed layouts and retrieval failures are not sold out.
- Closed dates are excluded. Past dates are skipped in Japan time.
- Alerts on a new circle, suppresses continued circles, and alerts again after a confirmed sold-out state followed by a circle.
- Availability mail includes the date, Japan timestamp, official link and a cell screenshot. Screenshots stay in memory and email, never public Actions artifacts.
- Three consecutive retrieval/interpretation failures send one separate error email. Recovery and routine successful checks do not send email; a new three-failure episode can notify again. SMTP/setup/state failures are reported as generic failed Actions runs. Set up GitHub Actions failure notifications as a secondary check.
- The automated pixel check is not a human inspecting every run. Inspect the emailed screenshot and official page before purchasing.

## State and privacy

Deduplication state is encrypted with Fernet using a key derived from the high-entropy Gmail app password, and saved in `.monitor-state.enc`. Only changed state is committed. Public commit timestamps and ciphertext size can still reveal activity. Keep the app password secret. Rotating it requires deleting the current state file before restarting (history is retained); this resets deduplication. A notification can repeat if SMTP accepts a message but saving state subsequently fails; exact-once delivery cannot be guaranteed.

## Cost and stopping

Uses only a public repository's standard `ubuntu-latest` hosted runner, with a five-minute job timeout. No larger runners, artifact uploads, dependency caches, paid APIs or external notification subscriptions. This workflow does not change billing settings. Do not enable paid services for this project.

Monitoring ends at the end of 2026-11-19 in Japan (cutoff: 2026-11-20 00:00 JST). The program and workflow both refuse monitoring after that cutoff. The first subsequent execution disables this workflow using its temporary GitHub token with Actions write permission. Source remains available for reuse. This final disabling execution can be delayed by GitHub scheduling; no calendar requests or monitor email are sent after the cutoff. You can stop earlier via **Actions → Calendar monitor → … → Disable workflow**. For reuse, change the deadline in `expiry.py` as well as target-date secrets, then re-enable the workflow. GitHub can also disable schedules after 60 days of repository inactivity.

## Tests

`python -m unittest -v` covers blank/dash/circle ambiguity, closure, duplicate suppression, unknown-state preservation and re-opening. A successful unit test does not establish that GitHub can reach the live calendar or deliver email. Complete the initial workflow run and confirm the setup email.
