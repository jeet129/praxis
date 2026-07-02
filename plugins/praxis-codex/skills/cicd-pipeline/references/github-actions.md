# CI/CD Pipeline — GitHub Actions

GitHub Actions–specific implementation of the standard pipeline chain.

## Project layout

```
.github/
├── workflows/
│   ├── ci.yml                     PR pipeline (lint, test, build, scan)
│   ├── release.yml                main branch → registry publish
│   ├── deploy-staging.yml         staging deploy on tag or main
│   └── deploy-production.yml      manual or tag-triggered prod deploy
├── actions/                       reusable composite actions (project-specific)
└── CODEOWNERS                     review routing
```

## Standard CI workflow

```yaml
# .github/workflows/ci.yml
name: CI

on:
  pull_request:
    branches: [main]
  push:
    branches: [main]

concurrency:
  group: ci-${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

jobs:
  setup:
    runs-on: ubuntu-latest
    outputs:
      cache-key: ${{ steps.cache-key.outputs.value }}
    steps:
      - uses: actions/checkout@v4
      - id: cache-key
        run: echo "value=${{ hashFiles('**/package-lock.json', '**/pom.xml', '**/poetry.lock') }}" >> $GITHUB_OUTPUT

  lint-and-typecheck:
    needs: setup
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version-file: '.nvmrc'
          cache: 'npm'
      - run: npm ci
      - run: npm run lint
      - run: npm run typecheck

  unit-tests:
    needs: setup
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version-file: '.nvmrc'
          cache: 'npm'
      - run: npm ci
      - run: npm run test:unit -- --coverage
      - uses: actions/upload-artifact@v4
        with:
          name: coverage
          path: coverage/

  integration-tests:
    needs: setup
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_PASSWORD: test
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version-file: '.nvmrc'
          cache: 'npm'
      - run: npm ci
      - run: npm run test:integration

  sast:
    needs: setup
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0   # full history for semgrep
      - uses: semgrep/semgrep-action@v1
        with:
          config: 'p/default'
      - uses: github/codeql-action/init@v3
        with: { languages: 'javascript-typescript' }
      - uses: github/codeql-action/analyze@v3

  sca:
    needs: setup
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: aquasecurity/trivy-action@master
        with:
          scan-type: 'fs'
          severity: 'HIGH,CRITICAL'
          exit-code: '1'

  build:
    needs: [lint-and-typecheck, unit-tests]
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version-file: '.nvmrc', cache: 'npm' }
      - run: npm ci
      - run: npm run build
      - uses: actions/upload-artifact@v4
        with: { name: build, path: dist/ }

  container:
    needs: [build, integration-tests, sast, sca]
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write
      id-token: write   # for OIDC + cosign keyless
    steps:
      - uses: actions/checkout@v4
      - uses: docker/setup-buildx-action@v3
      - uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      - uses: docker/build-push-action@v6
        id: build
        with:
          context: .
          push: true
          tags: ghcr.io/${{ github.repository }}:${{ github.sha }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
          provenance: true
          sbom: true
      - name: Scan image
        uses: aquasecurity/trivy-action@master
        with:
          image-ref: ghcr.io/${{ github.repository }}:${{ github.sha }}
          severity: 'HIGH,CRITICAL'
          exit-code: '1'
      - name: Sign image
        uses: sigstore/cosign-installer@v3
      - run: |
          cosign sign --yes ghcr.io/${{ github.repository }}:${{ github.sha }}
```

## Cache discipline

```yaml
# language-specific cache (built into setup-* actions)
- uses: actions/setup-node@v4
  with: { node-version-file: '.nvmrc', cache: 'npm' }

# generic cache (fallback)
- uses: actions/cache@v4
  with:
    path: |
      ~/.npm
      ~/.cache
    key: ${{ runner.os }}-${{ hashFiles('**/package-lock.json') }}
    restore-keys: ${{ runner.os }}-
```

## Branch protection

Configure in repo settings (or via Terraform):

- `main` requires PR.
- Required status checks: `lint-and-typecheck`, `unit-tests`, `integration-tests`, `sast`, `sca`, `build`, `container`.
- Required reviewers: at least 1 from CODEOWNERS for the area.
- Dismiss stale approvals on new commits.
- Require branches up-to-date before merge.

## Secrets management

- GitHub Actions secrets at repo level for project-scoped secrets.
- Environment secrets (staging, production) scoped to environment-protected jobs.
- OIDC federation to cloud providers (no long-lived cloud credentials in CI).

## Common violations to flag in review

- Workflows triggered on `pull_request_target` without explicit context restrictions (auth-bypass risk).
- `secrets.*` in `if:` conditions (secret-bypass risk).
- `actions/checkout@v3` or older (use latest stable).
- Third-party actions pinned to tags (not SHAs) — supply-chain risk; pin to `@<commit-sha>`.
- Container builds without `provenance: true` and `sbom: true`.
- Missing branch-protection on `main`.
- Concurrency group missing (PR re-runs pile up).
- Jobs that don't `cancel-in-progress` on superseded runs.
