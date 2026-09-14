# GAS Control Layer V1

GAS is deliberately limited to Sheet control UI, approval, retry, run-log navigation, and email delivery.

It does **not** run Discovery, Verification, Fact QA, Structured Content generation, Teaching QA, or PDF rendering.

## Install

1. Bind this script to the production Google Sheet.
2. Copy `Code.gs` and `appsscript.json`.
3. Run `onOpen` once / reload the Sheet.
4. Run `setupEmailDeliveryTrigger()` once to create the 15-minute email delivery trigger.
5. Optional immediate GitHub workflow dispatch: set Script Properties `GITHUB_OWNER`, `GITHUB_REPO`, `GITHUB_TOKEN`, optionally `GITHUB_WORKFLOW=daily.yml`, `GITHUB_REF=main`.

If GitHub properties are omitted, `Approve Today` / `Publish Ready` still work; the next scheduled GitHub Actions run evaluates the publication gate.

Email sending requires `Status=PUBLISHED` and real HTTP `HTML_URL` / `PDF_URL`.
Failures only change `Email_Status`; article `Status` remains `PUBLISHED`.
`EMAIL_LOG.Delivery_Key = Issue_ID + "|" + lowercase recipient` prevents duplicate sends.
