# SecureVote — Cryptographic E-Voting System

A full-stack web-based student union e-voting system built for TU Dublin, demonstrating cryptographic ballot integrity, role-based access control, and a complete election lifecycle from creation through to audited results.

## Technologies

**Backend**
- Python / Flask with Blueprint-based routing
- MongoDB (PyMongo) with compound unique indexes for chain integrity
- JWT authentication (PyJWT, HS256, 1-hour expiry) + bcrypt (work factor 12)
- AES-256-GCM + RSA-2048 hybrid ballot encryption (`cryptography` library)
- SHA-256 hash-linked vote chain
- WebAuthn / FIDO2 biometric authentication (`py-webauthn`)
- Flask-Limiter rate limiting

**Frontend**
- React 18 + React Router 6
- Tailwind CSS v3 (JIT) with custom "Civic Terminal" design system
- Framer Motion animations, Lucide React icons
- DOMPurify XSS sanitization
- `@simplewebauthn/browser` for passkey/biometric login

**Infrastructure & Tooling**
- Docker + Docker Compose (local dev)
- GitHub Actions CI/CD (lint → test → Docker build)
- Terraform (AWS EC2 + S3)
- pytest with 12 test modules

## Features

### Authentication & Access Control
- Student ID + password login (bcrypt, strength-validated)
- WebAuthn biometric login (TouchID / FaceID / Windows Hello)
- Three-role RBAC hierarchy: `admin ⊃ official ⊃ student`
- Database-authoritative role verification (JWT role claims never trusted)

### Voting & Ballot Security
- Hybrid AES-256-GCM + RSA-2048 ballot encryption
- Unique AES key and nonce per ballot; election ID as authenticated AAD
- SHA-256 hash-linked vote chain with tamper detection
- One-vote-per-user-per-election enforcement
- Concurrent write safety via MongoDB unique index + optimistic retry loop

### Election Management
- Full election lifecycle: `draft → active → closed → archived`
- Candidate management (add/remove on draft elections)
- Role-filtered views (students see active/closed; officials/admins see all)
- Per-election results decryption and tally

### Administration & Audit
- Admin user management (create users, assign/change roles)
- Chain verification endpoint — re-computes all hashes and reports any break
- Audit stats (vote count, unique voters, chain validity, timestamps)
- Admin dashboard with system-wide overview

### Testing
- 12 pytest modules: crypto, API, RBAC, security hardening, election lifecycle, concurrency, password auth, WebAuthn, end-to-end workflow
- Concurrency test: 20 parallel voters, ≥80% success rate, zero chain gaps
- Security tests: JWT tampering, alg:none attack, MongoDB injection probes, role-claim spoofing

## Running Locally

**Via Docker Compose (recommended):**
```bash
docker compose up -d
# Backend: http://localhost:5001
# Frontend: http://localhost:3000
```

**Manual setup:**
```bash
# Backend
cd backend
pip install -r requirements.txt
export SECRET_KEY="dev-key"
export MONGO_URI="mongodb://localhost:27017/securevote"
python app.py

# Frontend (separate terminal)
cd frontend
npm install
npm start
```

**Run tests:**
```bash
cd backend
pytest tests/ -v
```

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `SECRET_KEY` | — | JWT signing secret (required) |
| `MONGO_URI` | `mongodb://localhost:27017/securevote` | MongoDB connection string |
| `FLASK_ENV` | `development` | `testing` disables rate limiting |
| `RSA_KEY_PASSPHRASE` | — | Optional passphrase for RSA private key |
| `FRONTEND_URL` | `http://localhost:3000` | CORS origin whitelist |
| `WEBAUTHN_RP_ID` | `localhost` | WebAuthn relying party domain |
| `WEBAUTHN_RP_NAME` | `SecureVote` | WebAuthn app name shown in OS prompt |
| `WEBAUTHN_ORIGIN` | `http://localhost:3000` | Exact origin verified in WebAuthn ceremony |

## Project Structure

```
securevote-prototype-v1/
├── backend/
│   ├── app.py                  # Core Flask app + auth/voting/audit/admin endpoints
│   ├── routes/
│   │   ├── elections.py        # Election CRUD + lifecycle blueprint
│   │   └── webauthn.py         # WebAuthn registration & authentication blueprint
│   ├── utils/
│   │   ├── auth.py             # JWT decorators, RBAC, role hierarchy
│   │   └── password.py         # bcrypt hashing + strength validation
│   ├── crypto/
│   │   ├── aes_cipher.py       # AES-256-GCM implementation
│   │   ├── key_manager.py      # RSA-2048 key generation & management
│   │   └── ballot_crypto.py    # Hybrid encryption orchestration + chain verification
│   ├── models/
│   │   └── election.py         # Election schema, validation, state machine
│   ├── tests/                  # 12 pytest test modules
│   └── scripts/                # Admin user creation utilities
├── frontend/
│   ├── src/
│   │   ├── pages/              # Login, Register, Dashboard, CastVote, Results
│   │   │   ├── admin/          # AdminDashboard, UserManagement, AuditLog
│   │   │   └── official/       # OfficialDashboard, ElectionManagement, ElectionResults
│   │   ├── api/apiClient.js    # Axios wrapper with JWT interceptor
│   │   └── index.css           # Tailwind design system + custom component classes
│   ├── tailwind.config.js
│   └── Dockerfile
├── infra/                      # Terraform (AWS EC2 + S3)
├── .github/workflows/          # GitHub Actions CI/CD
└── docker-compose.yml
```
