# SecureVote Prototype — Development Progress

This document summarises exactly what has been built in the SecureVote prototype to date.
It is intended as a technical briefing for Gemini / NotebookLM.

---

## Project Overview

SecureVote is a web-based student union e-voting system built for TU Dublin.
The prototype demonstrates cryptographic ballot integrity, role-based access control,
and a full election lifecycle — from creating an election through to auditing the results.

**Stack:**
- Backend: Python / Flask
- Database: MongoDB
- Frontend: React (Vite / Create React App)
- Containerisation: Docker + Docker Compose
- Cryptography: Python `cryptography` library (AES-256-GCM + RSA-2048), `bcrypt`
- Auth: JWT (PyJWT)
- Rate limiting: Flask-Limiter

---

## 1. Cryptographic Layer (`backend/crypto/`)

### 1.1 AES-256-GCM Cipher (`aes_cipher.py`)
- Implements symmetric encryption using AES-256-GCM (authenticated encryption).
- Each ballot gets its own randomly generated 256-bit AES key.
- A 96-bit random nonce is prepended to every ciphertext — no nonce reuse is possible.
- Supports Associated Authenticated Data (AAD): the `election_id` is passed as AAD so
  that decrypting a ballot with the wrong election ID raises an authentication error.
- Tamper detection: any modification to the ciphertext causes decryption to fail
  (`InvalidTag` exception from the cryptography library).

### 1.2 RSA Key Manager (`key_manager.py`)
- Generates and persists a 2048-bit RSA key pair to `backend/keys/` (PEM files).
- Auto-generates keys on first run if they do not exist.
- Supports optional passphrase protection via the `RSA_KEY_PASSPHRASE` environment variable.
- Encrypts each ballot's AES session key using RSA-OAEP with SHA-256.
- Decrypts AES keys using the RSA private key (admin-only operation at result tallying time).
- `generate_keys(overwrite=False)` prevents accidental key rotation.

### 1.3 Ballot Crypto (`ballot_crypto.py`)
High-level orchestration layer that combines AES + RSA:

1. **`encrypt_ballot(ballot_data, election_id, previous_hash)`**
   - Serialises the ballot dictionary (handles `datetime` → ISO string).
   - Generates a fresh AES key; encrypts the ballot with AES-GCM using `election_id` as AAD.
   - Encrypts the AES key with RSA public key.
   - Generates a SHA-256 chain hash over `(encrypted_ballot, encrypted_aes_key, election_id, previous_hash)`.
   - Returns `encrypted_ballot`, `encrypted_aes_key`, `current_hash`, `previous_hash`, `election_id`.

2. **`decrypt_ballot(encrypted_ballot_b64, encrypted_aes_key_b64, election_id)`**
   - Decrypts the AES key using the RSA private key.
   - Decrypts the ballot ciphertext; verifies AAD matches the `election_id`.

3. **`verify_chain(votes)`**
   - Walks the entire ordered vote list, recomputing each SHA-256 hash.
   - Verifies hash continuity: each `previous_hash` must equal the prior vote's `current_hash`.
   - First vote's `previous_hash` must be the string `"GENESIS"`.
   - Returns `{ valid, verified_count, broken_at, details }`.

4. **`verify_chain_link(...)`** — single-link tamper check (used internally by `verify_chain`).

---

## 2. Backend API (`backend/app.py` + `backend/routes/elections.py`)

### 2.1 Authentication Endpoints (`/auth/`)

| Endpoint | Method | Description |
|---|---|---|
| `/auth/register` | POST | Register a new user with student ID, password, and optional email. Enforces password strength rules. |
| `/auth/login` | POST | Login with student ID + password. Returns a JWT (1-hour expiry) with role embedded. Legacy support: if user has no password set, password-less login is allowed (backward compatibility). |
| `/auth/me` | GET | Returns current user's info (student ID, role, email, has_password flag). Requires auth. |
| `/auth/change-password` | POST | Change password. Verifies existing password first. Requires auth. |
| `/auth/set-password` | POST | Set a password for a legacy (password-less) user. Requires auth. |
| `/auth/password-requirements` | GET | Returns password rules (min length, character requirements) for client-side validation. |

Rate limiting applied: 5 req/min on register, 10 req/min on login.

### 2.2 Voting Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/candidates` | GET | Returns legacy hardcoded candidate list (backward compatibility). |
| `/vote` | POST | Casts a vote. Requires `student` role (or higher). One vote per user per election enforced. |
| `/results` | GET | Decrypts and tallies all votes. Requires `official` or `admin` role. |

**Vote submission flow:**
1. Validates JWT and role.
2. Looks up the election in MongoDB (supports both dynamic DB elections and legacy hardcoded election).
3. Checks election status is `active`.
4. Validates the `candidate_id` against the election's candidate list.
5. Checks the user has not already voted in this election.
6. Reads the latest vote in the chain to get `previous_hash`.
7. Calls `ballot_crypto.encrypt_ballot(...)`.
8. Inserts the vote record; on `DuplicateKeyError` (unique index collision), retries up to 10 times — this handles concurrent submissions to the same chain position.

### 2.3 Audit Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/audit/verify` | GET | Re-runs `verify_chain()` over all stored votes for an election. Reports `valid` or `broken_at`. Requires `admin`. |
| `/audit/stats` | GET | Returns election statistics: total votes, unique voters, registered users, first/last vote timestamps, chain validity. Requires `admin`. |

### 2.4 Admin User Management Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/admin/users` | GET | Lists all users with roles. Requires `admin`. |
| `/admin/users` | POST | Creates a new user with a specified role. Requires `admin`. |
| `/admin/users/<student_id>/role` | PUT | Updates a user's role. Prevents self-demotion. Requires `admin`. |

### 2.5 Election Management Endpoints (`/elections/`)

Full CRUD + lifecycle management for dynamic elections.

| Endpoint | Method | Description |
|---|---|---|
| `/elections` | GET | Lists elections. Students only see `active`/`closed`; officials/admins see all. Supports `?status=` filter, `?limit=`, `?skip=`. |
| `/elections` | POST | Creates a new election in `draft` status. Requires `official` or `admin`. |
| `/elections/<id>` | GET | Gets a single election. Officials/admins also receive `vote_count`. |
| `/elections/<id>` | PUT | Updates election. Draft: all fields. Active: only `end_time` extension. Closed/archived: blocked. |
| `/elections/<id>` | DELETE | Deletes a draft election with zero votes. Requires `admin`. |
| `/elections/<id>/start` | POST | Transitions `draft → active`. Sets `started_at`. Requires `official`/`admin`. |
| `/elections/<id>/end` | POST | Transitions `active → closed`. Sets `ended_at`. Requires `official`/`admin`. |
| `/elections/<id>/results` | GET | Decrypts and tallies results. Officials: closed elections only. Admins: any status. |
| `/elections/<id>/candidates` | POST | Adds a candidate to a draft election. |
| `/elections/<id>/candidates/<id>` | DELETE | Removes a candidate from a draft election (minimum 2 must remain). |

**Election statuses and valid transitions:**
```
draft → active → closed → archived
draft → archived (cancel)
```

---

## 3. Role-Based Access Control (`backend/utils/auth.py`)

Three roles with a hierarchy (higher roles inherit all lower-role permissions):

```
admin  ⊃  official  ⊃  student
```

- **student** — can vote, view their own profile.
- **official** — can create/manage elections, view results of closed elections.
- **admin** — full access: audit chain verification, user management, real-time result viewing.

Implementation:
- `@require_auth` decorator: decodes JWT, looks up user in MongoDB, stores in `flask.g`.
- `@require_role(roles)` decorator: checks the user's role from the database (not the JWT claim)
  — this means a tampered JWT with an elevated role claim is rejected.
- JWT tokens embed role for convenience only; MongoDB is the authoritative source of truth for roles.
- Tokens expire after 1 hour.
- `ROLE_HIERARCHY` dict maps each role to its effective permissions list.

---

## 4. Password Utilities (`backend/utils/password.py`)

- **bcrypt** hashing with work factor 12 (≈250ms per hash).
- Automatic per-password salting.
- Timing-safe comparison via `bcrypt.checkpw`.
- Password strength validation:
  - Minimum 8 characters, maximum 128 characters.
  - Must contain uppercase, lowercase, and a digit.
  - Blocks a short list of common passwords.
- `get_password_requirements()` returns requirements as JSON for client-side validation.

---

## 5. Election Model (`backend/models/election.py`)

- Defines the MongoDB election document schema with fields:
  `election_id`, `title`, `description`, `candidates`, `status`, `created_by`,
  `created_at`, `start_time`, `end_time`, `started_at`, `ended_at`, `settings`.
- `generate_election_id(title)` — creates a human-readable ID from the title + random hex suffix.
- `validate_election_data(data, is_update)` — validates titles, candidate list structure,
  duplicate names/IDs, and `start_time < end_time`.
- `prepare_election_document(data, created_by)` — auto-assigns candidate IDs, parses ISO
  datetime strings, sets initial `draft` status.
- `can_transition_status(current, target)` — enforces valid state machine transitions.
- `format_election_response(election)` — serialises MongoDB document to API-safe dict
  (converts ObjectId and datetime to strings).

---

## 6. Concurrency Handling

The vote submission endpoint handles concurrent writes via:
1. **MongoDB unique compound index** on `(election_id, previous_hash)` — only one vote can
   occupy each position in the chain.
2. **Retry loop** (up to 10 attempts): if a `DuplicateKeyError` is raised (another vote
   claimed the same chain slot simultaneously), the handler re-reads the latest chain tail
   and retries with the updated `previous_hash`.
3. Returns HTTP 503 if all 10 retries are exhausted (signals high-traffic congestion to the client).

---

## 7. Frontend (`frontend/src/`)

React SPA with React Router. Role-aware routing enforced on the client side.

### Pages implemented:

**Public:**
- `Login.jsx` — student ID + password login form, calls `/auth/login`, stores JWT and role in `localStorage`.
- `Register.jsx` — registration form with password requirements display.

**Student (authenticated):**
- `Dashboard.jsx` — shows active elections the student can vote in.
- `CastVote.jsx` — ballot casting interface; submits to `/vote`.
- `Results.jsx` — view results (only shown post-election or for eligible roles).

**Official (`/official/`):**
- `OfficialDashboard.jsx` — overview of elections managed by this official.
- `ElectionManagement.jsx` — create, edit, start, and end elections; add/remove candidates.
- `ElectionResults.jsx` — view detailed results for closed elections.

**Admin (`/admin/`):**
- `AdminDashboard.jsx` — system-level overview.
- `UserManagement.jsx` — list users, assign/change roles, create new users.
- `AuditLog.jsx` — view audit stats and trigger chain verification.

### Routing (`App.jsx`):
- `PrivateRoute` — redirects unauthenticated users to login.
- `RoleRoute` — redirects users without the required role to their own dashboard.
- Catch-all `*` redirects to `/`.

### API Client (`api/apiClient.js`):
- Centralised Axios (or fetch) wrapper; attaches JWT `Authorization: Bearer <token>` header to all requests.

---

## 8. WebAuthn Biometric Authentication (`backend/routes/webauthn.py`)

WebAuthn (passkey) authentication added as a second login method alongside the existing
student ID + password flow. On success, both flows issue the same standard JWT token, leaving
RBAC unchanged.

### MongoDB schema additions (no migration required — absent for legacy users)

```
webauthn_credentials: [
  {
    credential_id:         <base64url string>   # unique per device
    credential_public_key: <base64 string>       # COSE-encoded public key bytes
    sign_count:            <int>                 # increments on every authentication
    transports:            ["internal"]          # usb / nfc / ble / internal
    device_type:           "single_device"
    is_backed_up:          false
    friendly_name:         "MacBook TouchID"     # optional label
    created_at:            <ISO datetime>
  }
]
pending_webauthn_challenge: <base64 string>     # overwritten per request, cleared after use
challenge_expiry:           <ISO datetime>       # 5-minute TTL
```

### Endpoints (all under `/auth/webauthn/`)

| Endpoint | Auth | Description |
|---|---|---|
| `POST /register/begin` | JWT required | Generates `PublicKeyCredentialCreationOptions`; stores challenge with 5-min TTL |
| `POST /register/complete` | JWT required | Verifies attestation; stores `credential_id`, COSE public key, and initial `sign_count` |
| `POST /login/begin` | Public | Generates `PublicKeyCredentialRequestOptions` for a given `student_id` |
| `POST /login/complete` | Public | Verifies ECDSA signature, checks `sign_count` replay counter, issues JWT |

### Signature verification (Chapter 5 narrative)

During the signature verification step, the browser's authenticator (e.g., TouchID or FaceID)
uses its private key — stored in the device's Secure Enclave and never transmitted — to produce
an ECDSA (P-256) digital signature over the concatenation of the SHA-256 hash of `clientDataJSON`
and the raw `authenticatorData` bytes, which together encode the origin, the server's challenge,
and a replay-attack counter. The backend then calls `verify_authentication_response()` from
`py-webauthn`, which decodes the stored COSE-formatted public key and checks that the signature
is mathematically valid; because only the device holding the corresponding private key can produce
a valid signature, this step cryptographically proves the user's physical presence and identity.
Finally, the backend compares the response's `sign_count` against the last persisted value —
if the counter has not incremented, the server detects a cloned or replayed credential and
rejects the request, providing protection against credential copying attacks.

### Libraries

- **Backend:** `webauthn>=2.0.0` (py-webauthn 2.7.1 installed)
- **Frontend:** `@simplewebauthn/browser ^10.0.0`

### Environment variables

| Variable | Default | Description |
|---|---|---|
| `WEBAUTHN_RP_ID` | `localhost` | Domain of the frontend (no protocol, no port) |
| `WEBAUTHN_RP_NAME` | `SecureVote` | Human-readable app name shown in the OS prompt |
| `WEBAUTHN_ORIGIN` | `http://localhost:3000` | Exact origin (protocol + host + port) verified in `clientDataJSON` |

### `/auth/me` extensions

`has_webauthn` (bool), `credential_count` (int), and `webauthn_credentials` (array with
`credential_id`, `friendly_name`, `created_at`, `device_type`) are now included in the response.

### Frontend additions

| File | Change |
|---|---|
| `Login.jsx` | "Login with Biometrics" button; hidden when `window.PublicKeyCredential` is absent |
| `Dashboard.jsx` | "Add Biometric Login" card; hidden on non-WebAuthn browsers |
| `WebAuthnSetup.jsx` | New protected page at `/webauthn-setup` — lists registered devices, triggers registration ceremony |
| `App.jsx` | `/webauthn-setup` route added (PrivateRoute) |

---

## 9. Test Suite (`backend/tests/`)

Twelve test modules covering the full system:

| File | Coverage |
|---|---|
| `test_crypto.py` | AES-256-GCM encrypt/decrypt, nonce uniqueness, tamper detection, AAD mismatch, RSA key management (generate, persist, load, overwrite), full BallotCrypto encrypt/decrypt/chain/verify cycle. |
| `test_api.py` | Login, registration, candidate listing, vote casting, one-vote enforcement, vote chain linking, encrypted result tallying, audit verify (empty + valid + tampered chain), audit stats. |
| `test_rbac.py` | Role returned on login, role hierarchy, student/official/admin permissions on vote/results/audit/admin endpoints, self-demotion prevention, duplicate user creation, expired/invalid token handling. |
| `test_security.py` | MongoDB operator injection probing, JWT wrong-key rejection, JWT role-claim tampering (DB is authoritative), expired token, `alg:none` attack, payload validation (empty body, missing fields, oversized input, weak passwords). |
| `test_elections.py` | Election CRUD (create, list, get, update, delete), status lifecycle (start/end, invalid transitions), voting in draft/active/closed elections, per-election one-vote enforcement, multi-election voting, invalid candidate rejection, result tallying, official vs admin result visibility rules. |
| `test_concurrency.py` | 20-voter sequential chain integrity, 20-voter concurrent submission (≥80% success rate assertion), concurrent chain integrity after parallel writes, duplicate vote rejection under concurrency, vote count = unique voter count. |
| `test_e2e_workflow.py` | End-to-end workflow tests covering the full user journey. |
| `test_password_auth.py` | Password hashing, verification, strength validation, bcrypt work factor, change-password flow. |
| `test_webauthn.py` | WebAuthn endpoint auth boundaries, register/begin options shape and challenge storage, challenge expiry enforcement, login/begin error paths (no credentials, unknown user), login/complete error paths (expired challenge, unrecognised credential ID), `/auth/me` WebAuthn metadata fields. |

All tests use isolated temp directories for RSA keys and clean MongoDB collections per test run.
Rate limiting is disabled in test mode via `FLASK_ENV=testing`.

---

## 10. Frontend Design System (Tailwind CSS — "Civic Terminal" Overhaul)

**Completed:** March 2026
Bootstrap has been fully removed and replaced with a custom Tailwind CSS v3 design system.

### Stack additions
- **Tailwind CSS v3** (JIT) via `src/index.css` — all utilities and components
- **Framer Motion** — `motion.div`, `AnimatePresence`, `whileHover`/`whileTap` throughout
- **Lucide React** — icons across all pages (logo: `Gem` icon)
- **DOMPurify** — XSS sanitization on all user input fields
- **Fonts (Google Fonts):** Syne (display/headings, `font-display`), Epilogue (body), IBM Plex Mono (data, `font-mono`)

### Design tokens (CSS variables in `:root`)
```
--sv-bg #06091A          Main background (dot-grid pattern)
--sv-surface #0D1630     Card surface
--sv-raised #131E42      Raised elements
--sv-border rgba(0,159,227,0.10)
--sv-text #E4EBF8        Default text
--sv-text-dim #8993A8    Dimmed text
--sv-cyan #009FE3        TUD cyan — primary accent
--sv-magenta #C8005A     TUD magenta — admin accent
--sv-lime #84BD00        TUD lime — success / vote confirmed
--sv-blue #004B87        TUD blue
--sv-navy #002147        TUD navy
```

### UI zones
- **Student/Official UI:** `.sv-bg` dot-grid on `#06091A`, `.sv-card` / `.sv-card-interactive` flat dark cards with thin cyan border, `.sv-nav` sticky navbar with blur
- **Admin UI:** `.sv-bg-admin` scanline pattern on `#04050C`, `.sv-sidebar` 210px fixed sidebar, `.sv-terminal` monospace output for AuditLog

### Component library (`@layer components` in `index.css`)
Buttons: `.sv-btn-primary/outline/ghost/lime/danger/amber`
Forms: `.sv-input` (underline), `.sv-input-box` (boxed), `.sv-label`
Badges: `.sv-badge-{active/draft/closed/admin/official/student}`
Alerts: `.sv-alert-error/success`
Vote card: `.sv-vote-card` + `.sv-selected`

### Notable UX details
- CastVote success: full-viewport "VOTE RECORDED." ceremony in Syne black + lime checkmark
- Dashboard cards: large faded ordinal background numbers (01, 02, 03) via absolute-positioned `<span>`
- WebAuthn button hidden via `window.PublicKeyCredential` check (graceful degradation on unsupported browsers)
- Staggered Framer Motion entrance animations on dashboard grids

---

## 11. Infrastructure & CI/CD

### Docker Compose (`docker-compose.yml`)
Three services:
- `mongodb` — Mongo 7, persistent named volume.
- `backend` — Flask app, port 5001, environment-driven config (`SECRET_KEY`, `MONGO_URI`, `FLASK_ENV`, `RSA_KEY_PASSPHRASE`).
- `frontend` — React app served via Nginx, port 3000, depends on backend.

### Environment Variables (`.env.example` files)
Backend: `SECRET_KEY`, `MONGO_URI`, `FLASK_ENV`, `ELECTION_ID`, `FRONTEND_URL`, `RSA_KEY_PASSPHRASE`.
Frontend: `REACT_APP_API_URL`.

### GitHub Actions CI/CD (`.github/workflows/ci.yml`)
Three jobs triggered on push/PR to main:
1. **Lint** — flake8 (Python, max line 120) + ESLint (JavaScript, max warnings 0)
2. **Test** — spins up MongoDB 7 service container, runs `pytest tests/ -v --tb=short`
3. **Docker Build** — builds backend and frontend images, verifies `docker compose config`

### Terraform (`infra/`)
AWS infrastructure as code:
- `ec2.tf` — EC2 instances for backend and frontend containers
- `s3.tf` — S3 bucket for optional vote backups
- `variables.tf` / `outputs.tf` — configurable region, instance types, output IPs

### Utility Scripts (`backend/scripts/`)
- `create_admin.py` — creates an admin user directly in MongoDB.
- `create_official.py` — creates an official user.
- `create_student.py` — creates a student user.

---

## 12. Key Design Decisions & Security Properties

| Property | How it is implemented |
|---|---|
| Ballot secrecy | AES-256-GCM encryption; only the server's RSA private key can decrypt ballots during tallying. |
| Tamper detection | SHA-256 hash chain links every vote to the previous one; any modification breaks all downstream hashes. |
| One-vote enforcement | MongoDB query before insertion checks `{student_id, election_id}`; unique chain index as second guard. |
| Role authority | JWT role claim is ignored for access control; MongoDB document is always re-fetched to verify role. |
| Concurrent safety | MongoDB unique index + optimistic retry loop ensures chain consistency under parallel writes. |
| Password security | bcrypt work factor 12; timing-safe comparison; strength validation on register and change-password. |
| Rate limiting | 5 req/min on register; 10 req/min on login and vote; disabled in test environment. |
| CORS restriction | Only `localhost:3000` (and `FRONTEND_URL` env var) are allowed origins. |

---

| XSS prevention | DOMPurify sanitization on all user-controlled input fields in the React frontend. |
| Input sanitization | Election title/description length limits; candidate structure validation; datetime ordering enforced server-side. |

---

*Last updated: 2026-03-19*
