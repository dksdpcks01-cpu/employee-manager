# CLAUDE.md — Employee Manager

This file provides guidance for AI assistants (Claude and others) working in this repository. It covers project purpose, conventions, development workflows, and rules to follow when contributing code.

---

## Project Overview

**Employee Manager** is a web application for managing employee records, departments, roles, and HR workflows. The repository was initialized on 2026-02-19 and is currently in early setup phase — no application code exists yet.

When code is added, this file should be updated to reflect the actual tech stack, directory structure, and conventions in use.

---

## Repository Status

| Item | Status |
|------|--------|
| Source code | Not yet added |
| Dependencies | Not yet defined |
| Tests | Not yet added |
| CI/CD | Not yet configured |
| Database schema | Not yet defined |

---

## Recommended Tech Stack (to be confirmed when project is bootstrapped)

For a typical employee management system, consider:

- **Backend**: Node.js + TypeScript (Express or Fastify), or Python (FastAPI / Django)
- **Frontend**: React + TypeScript, or Next.js for SSR
- **Database**: PostgreSQL (relational, well-suited for HR data)
- **ORM**: Prisma (Node.js) or SQLAlchemy (Python)
- **Auth**: JWT-based or session-based authentication
- **Testing**: Vitest / Jest (unit + integration), Playwright (e2e)

Update this section once the stack is decided.

---

## Expected Domain Model

An employee management system typically manages:

- **Employees** — personal info, contact details, employment dates, status
- **Departments** — organizational units employees belong to
- **Roles / Positions** — job titles, salary bands, reporting lines
- **Leave / Time Off** — requests, approvals, balances
- **Performance** — reviews, goals, ratings
- **Payroll** — compensation records (optional)

---

## Development Workflow

### Branching Strategy

- `master` / `main` — stable production-ready code
- `develop` — integration branch for features
- `feature/<short-description>` — individual features
- `fix/<short-description>` — bug fixes
- `claude/<session-id>` — branches used by AI assistants for automated changes

Always branch from `develop` for new features. Open a pull request back into `develop` and require at least one review before merging.

### Commit Message Convention

Follow **Conventional Commits** format:

```
<type>(<scope>): <short summary>

[optional body]
[optional footer]
```

**Types:**
- `feat` — new feature
- `fix` — bug fix
- `refactor` — code restructuring without behaviour change
- `test` — adding or updating tests
- `docs` — documentation changes
- `chore` — tooling, config, dependency updates
- `style` — formatting, whitespace (no logic changes)
- `perf` — performance improvements

**Examples:**
```
feat(employees): add pagination to employee list API
fix(auth): correct token expiry check on refresh
test(departments): add unit tests for department service
docs: update CLAUDE.md with API conventions
```

### Pull Request Guidelines

- Keep PRs focused — one concern per PR
- Include a clear description of what changed and why
- Reference related issues (`Closes #123`)
- All CI checks must pass before merging
- Squash commits when merging to keep history clean

---

## Code Conventions

### General

- Prefer explicit over implicit — avoid magic values; use named constants
- Keep functions small and single-purpose (aim for ≤ 40 lines)
- Avoid deep nesting; prefer early returns
- Never commit secrets, credentials, or `.env` files
- Delete dead code rather than commenting it out

### TypeScript (if applicable)

- Strict mode enabled (`"strict": true` in tsconfig)
- Prefer `interface` over `type` for object shapes
- Always type function return values explicitly
- Avoid `any`; use `unknown` and narrow properly
- Use barrel exports (`index.ts`) per module

### Python (if applicable)

- Follow PEP 8; use `black` for formatting
- Type hints required on all public functions
- Use `dataclasses` or Pydantic models for data structures
- Raise specific exceptions, never bare `except:`

### API Design

- Follow REST conventions: `GET /employees`, `POST /employees`, `PATCH /employees/:id`, `DELETE /employees/:id`
- Return consistent JSON response envelopes:
  ```json
  { "data": { ... }, "meta": { ... } }           // success
  { "error": { "code": "...", "message": "..." } } // error
  ```
- Use HTTP status codes correctly (200, 201, 400, 401, 403, 404, 422, 500)
- Paginate list endpoints: `?page=1&limit=20` or cursor-based
- Version the API if breaking changes are needed: `/api/v1/...`

### Database

- Use migrations for all schema changes — never edit the database directly
- Name tables in snake_case plural (`employees`, `departments`)
- Always define indexes on foreign keys and frequently queried columns
- Soft-delete records where possible (`deleted_at` timestamp) rather than hard deletes
- Avoid N+1 queries; use eager loading or batch queries

### Testing

- Unit test pure business logic in isolation
- Integration test API endpoints against a real (test) database
- Aim for meaningful coverage, not 100% for its own sake
- Test file naming: `<module>.test.ts` or `test_<module>.py` co-located with source
- Use factories/fixtures for test data, not hard-coded values

---

## Common Commands

These will be populated once the project is bootstrapped. Expected commands:

```bash
# Install dependencies
npm install           # Node.js
pip install -r requirements.txt  # Python

# Start development server
npm run dev
python -m uvicorn app.main:app --reload

# Run tests
npm test
pytest

# Run linter
npm run lint
flake8 / ruff check .

# Format code
npm run format
black .

# Database migrations
npm run db:migrate
alembic upgrade head

# Build for production
npm run build
```

---

## Environment Configuration

Use a `.env` file for local development. Never commit it — ensure `.env` is in `.gitignore`.

Expected variables (to be documented when project is set up):

```
DATABASE_URL=
JWT_SECRET=
PORT=
NODE_ENV=development
```

Provide a `.env.example` with all required keys (but no real values) as a template for new developers.

---

## AI Assistant Guidelines

When Claude or another AI assistant works in this repository:

1. **Read before editing** — always read the relevant source files before modifying them
2. **Follow conventions** — match existing code style; do not introduce new patterns without reason
3. **Small, focused changes** — make the minimum change needed; avoid unrelated refactors
4. **No secrets** — never hardcode credentials, API keys, or passwords
5. **Update tests** — add or update tests for any logic changed
6. **Update this file** — if you introduce a new convention, dependency, or workflow, add it here
7. **Conventional commits** — use the commit format described above
8. **Use the designated branch** — always push to the branch specified in the task; never push to `master` directly
9. **No over-engineering** — do not add abstractions, helpers, or error handling for hypothetical future cases
10. **Verify correctness** — run tests and lint before pushing when CI is configured

---

## File Structure (Expected, Once Code Is Added)

```
employee-manager/
├── CLAUDE.md                  # This file
├── README.md                  # Human-facing project docs
├── .env.example               # Environment variable template
├── .gitignore
├── package.json               # (or pyproject.toml / requirements.txt)
├── tsconfig.json              # (TypeScript projects)
├── src/
│   ├── employees/             # Employee domain module
│   ├── departments/           # Department domain module
│   ├── auth/                  # Authentication module
│   ├── database/              # DB connection, migrations
│   └── main.ts                # Application entry point
├── tests/
│   ├── unit/
│   └── integration/
└── .github/
    └── workflows/             # CI/CD pipeline definitions
```

Update this tree when the actual structure is established.

---

## Updating This File

This file should be kept current. Update it when:

- A new dependency or tool is added
- A coding convention is established or changed
- New commands are added to the development workflow
- The database schema or domain model changes significantly
- A new team convention is agreed upon

The goal is for this file to always reflect the real state of the project so any AI assistant — or new developer — can onboard quickly without needing to ask questions.
