# QuoteCompare

An RFQ and supplier comparison workspace built with Streamlit. Create a request,
review source-backed quotes, and compare whole-line buying plans with one to eight
suppliers. AI is optional for drafting/extraction and analyst wording; qualification,
price conversion and allocation are calculated in Python.

## Start on Windows

Use Python 3.12. From this folder:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Open the URL shown by Streamlit. The default config binds to your computer only.
You can also use `run.ps1` after creating the environment. Choose **Explore a sample
request** for a fictional comparison without an API key. Create a manual draft to
use the app without AI; manual quote review still requires original source evidence.

In the Codex workspace where this was developed, a tested environment is already
available at `../../work/venv/Scripts/python.exe`. That environment is outside this
portable package; use the setup above when copying the project elsewhere.

## Optional AI setup

Copy `.streamlit/secrets.example.toml` to `.streamlit/secrets.toml` and enter your
own Gemini API key. Alternatively provide `GEMINI_API_KEY` and `GEMINI_MODEL` as
environment variables, or configure `GCP_SERVICE_ACCOUNT` and `GCP_LOCATION` for
Vertex AI. Keys are never included in exports. The model and provider setup must
be verified against your account; live paid AI calls were not made during testing.

Uploaded content is transmitted to the configured Google service when you choose
an AI action. Manual workflows and deterministic comparison do not transmit quote
documents. Currency refresh contacts Frankfurter / ExchangeRate-API with currency
codes only. Data-provider availability and service billing are outside the app.

## Shared deployment

Private local mode is the default. Before exposing a shared deployment, configure
Streamlit OIDC (`[auth]`), set `QUOTECOMPARE_AUTH_REQUIRED=true`, and configure an
explicit `QUOTECOMPARE_ALLOWED_USERS` list. Sign-in alone is insufficient: the app
also checks the allowlist and scopes SQLite workspaces to issuer/subject identity.
Keep secrets and the `.state` folder out of source control; use HTTPS at the host.
The sign-in/allowlist branches are tested with simulated identity data, not a real
identity-provider handshake. This implementation gives each allowed buyer their
own workspaces; it does not provide shared team workspaces or a role hierarchy.

## Saved work and backups

Committed edits and review drafts autosave to `.state/workspaces.sqlite3` unless
`QUOTECOMPARE_DB` specifies another path. Switching workspaces is owner-scoped.
The last ten database revisions and ten supplier quote revisions are retained.
RFQ revision starts a new workspace, preserving the previous quote scope.

Backup JSON includes original documents, pending review drafts, events, conversations,
and revisions. Form edits are not persisted until **Save draft** or **Save review
draft & recalculate** is pressed. Restoring imported JSON clears confirmations,
historical AI answers and final approval; pending reviews reopen as unchecked drafts. Recheck the quotes
before making decisions. Autosave loading preserves matching internal confirmations.
Version 1 backup schemas remain readable where their published RFQ meets current
validation rules; invalid legacy checkpoints receive a specific rejection rather
than being silently treated as verified.

SQLite and backup JSON are not encrypted or tamper-proof. Source hashes detect
accidental changes; they do not authenticate supplier documents or buyer identity
inside an imported file. Protect the disk and backups using your host controls.

## Decision rules

- Confirmations bind to the exact reviewed fields. Material edits invalidate them.
- Item specifications must be checked; unresolved warnings need a resolution note.
- A matched quote requires a filename, locator and supporting excerpt. Parsed-text
  evidence is checked at its locator; PDFs/images require buyer visual verification.
- Missing required answers remain pending. Verified failures disqualify the supplier.
  N/A never waives a required certificate; certificate content is not independently
  authenticated. Expiry uses the evaluation date, which is included in snapshots.
- Capacity, MOQ, order multiples, lead-time limits and quote validity constrain
  whole-line awards. Constraint quantities use the requested item unit.
- Currency rates must have a date no older than ten days. Missing/stale rates are
  excluded; manually entered rates require a source note.
- Money is calculated using Decimal through extended line cost and rounded per
  line to two decimals, then summed. Every line/subtotal reconciles with its total.
  Input fields remain numeric floats for AI/Streamlit compatibility; Decimal uses
  their canonical decimal string representation, rather than binary arithmetic.
- The exact optimizer uses supplier masks, includes fixed charges once, and prefers
  fewer suppliers on equal total cost. A line's quantity is not split among vendors.
- **Goods prices** exclude freight, tax, duty and financing. **Landed estimate** adds
  checked tax/duty percentages of net goods cost, per-line INR freight and supplier
  fixed charges. It requires explicit confirmation of zero charges too. It is not
  an accounting tax engine: compounded taxes, recoverable tax credits, Incoterms,
  financing and arbitrary customs bases need a separate agreed model.
- Unconditional discounts are applied with evidence. Conditional quotes require an
  evidenced unconditional base price. A checked minimum-line-quantity condition
  can activate its discount; whole-order, minimum supplier-spend and early-payment
  conditions retain the base price and are not automatically modeled.
- No complete single-supplier benchmark means no claimed savings. Partial plans
  cannot be recorded as buyer-approved final plans.
- Final buyer approval requires checked selected-supplier terms and an explicit
  confirmation of capacity/delivery. It creates no order or contractual commitment.

## Review and correction

Any quote line can be rematched in the editable price table. Add missing prices and
answers, correct evidence, or exclude competing alternatives. Scroll right for
discounts, conversions, constraints and line costs. Save the review draft to
recalculate; this leaves the previous committed quote active. Commit after checking
the current version. Commercial terms are editable and source-backed. Changes are
recorded with reviewer/time, and previous quote revisions remain in the backup.

Suggested questions always have local deterministic fallbacks. Optional AI wording
uses the same supported handlers; analyst plans have an explicit unsupported result.
AI evidence IDs are validated, but generated reasoning can still be wrong. Historical
answers are marked as historical. Clarification notes do not alter eligibility until
the underlying quote/evidence is updated.

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q --junitxml=test-results.xml
.\.venv\Scripts\python.exe -m compileall -q app.py core.py engine.py storage.py ui.py
.\.venv\Scripts\python.exe -m pip check
```

Tests cover backend decision rules, adversarial backups and source evidence, exact
optimization against a brute-force oracle, owner isolation, and Streamlit AppTest
workflows. The test report documents execution and external checks not performed.

## Structure

- `app.py`: Streamlit entry point.
- `ui.py`: workflow, manual review, optional AI, previews and comparison interface.
- `core.py`: typed schemas and retained AI analysis/extraction/rendering helpers.
- `engine.py`: deterministic calculations, evidence rules and backup validation.
- `storage.py`: owner-scoped SQLite autosave and revision snapshots.
- `tests/`: backend and Streamlit regression tests.

Email sending, supplier portals, ERP integration and purchase-order issuance are
not connected. Invitations are downloadable drafts. These integrations need their
own credentials, recipient configuration and operational requirements.
