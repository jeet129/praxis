---
name: secure-coding
description: "OWASP-aligned secure coding practice. Input validation at boundaries, output encoding, parameterized queries, safe deserialization, authn/authz checks at the right layer, crypto usage, SSRF/XXE defenses, secrets-in-code prevention, PII handling at log boundaries. Applied during code writing (developer agents) and at code review (Security Reviewer agent) as a merge gate. Use whenever code is being written that handles input from any external boundary, persists or transmits sensitive data, or makes authorization decisions. Pushy trigger because security findings are the most expensive failure mode to discover post-deployment."
---

# Secure Coding

<!-- praxis:metadata:begin -->
```yaml
capability: quality-and-security
domain: cross-cutting
state: active
dependencies:
 - engineering-standards
triggers:
 - "writing code that accepts external input"
 - "writing code that persists or transmits user data"
 - "writing code that makes authorization decisions"
 - "writing code that uses cryptography"
 - "reviewing a PR for security findings"
 - "implementing a new API endpoint"
 - "handling file uploads, deserialization, or template rendering"
outputs:
 - secure code (when used during writing)
 - severity-tagged security findings (when used at review): blocker / major / minor / nit
 - concrete fix suggestions
 - pass/fail verdict (used as merge gate)
consumers:
 - backend-developer (applies during writing)
 - frontend-developer (applies during writing — FE-specific checks)
 - security-reviewer (uses as review baseline)
 - code-review (uses for security-aspect of reviews)
references:
 - java-spring.md
 - node-ts.md
 - python.md
 - web-frontend.md
```
<!-- praxis:metadata:end -->

OWASP-aligned, language-aware, applied continuously. This skill produces *secure code by construction* during writing, and *severity-tagged findings* during review. It is one of three skills that gate merges (alongside `code-review` and `supply-chain-security`).

The principle: **inputs are hostile until validated; outputs are dangerous until encoded; secrets are sacred always.**

## When this skill fires

- During code writing — any code accepting external input, persisting sensitive data, making authorization decisions, using crypto, rendering templates, handling files, deserializing data.
- During code review — every PR runs through this skill's checklist as part of the merge gate.
- During architecture design (lightweight inline check by SA) — preview the security implications of the chosen pattern.
- During threat modeling (`threat-modeling` skill,) — this skill provides the language-specific defenses for each threat surfaced.

## The discipline

### 1. Input validation at boundaries

Every input is hostile until proven otherwise. Validate at the **boundary** (API controller, message handler, file uploader) — not deep inside the application.

Validation includes:
- **Shape** — required fields, types, ranges, lengths, enum values. Schema-driven (zod, pydantic, Bean Validation).
- **Format** — emails, URLs, UUIDs, dates. Use canonical validators, not hand-rolled regexes.
- **Semantic constraints** — business rules (this customer can place this order in this state). Enforced in the domain layer.
- **Size limits** — max payload size, max array length, max string length. DoS prevention.

After the boundary validation, downstream code can trust the types. Re-validating internally is a smell (you should be able to *prove* the input was validated).

### 2. Output encoding

Every piece of user-controlled data sent to a context where it could be interpreted as code or markup is encoded for that context:

- **HTML** — HTML-encode user content in templates. Frameworks default to encoded; verify the framework is doing it (React JSX is encoded by default; `dangerouslySetInnerHTML` is the violation surface).
- **SQL** — *never* string-concatenate user input into queries. Parameterized queries / prepared statements only. ORMs enforce this when used idiomatically.
- **Shell commands** — *never* string-concatenate user input into shell commands. Use language APIs that accept arguments as separate parameters.
- **URL** — URL-encode parameters. Don't put user data in URL paths unless it's an identifier already validated by shape.
- **Headers** — strip control characters from user-provided header values (CRLF injection).
- **JSON / XML in responses** — frameworks serialize safely; don't hand-roll.

### 3. Injection defenses

Per category:

- **SQL injection** — parameterized queries. ORMs (JPA, Prisma, SQLAlchemy, Drizzle) used idiomatically prevent this; raw SQL must use parameters.
- **Command injection** — never pass user input through `Runtime.exec(string)`, `subprocess.shell=True`, `child_process.exec`. Use APIs that take argument arrays.
- **LDAP injection** — escape user input per the LDAP filter syntax; use library functions that handle escaping.
- **Template injection** — never render user input *as template*; render it as data inside the template.
- **Header injection** — strip or reject CR / LF in user-provided header values.
- **NoSQL injection** — typed query builders / ORMs; never concatenate user input into MongoDB filters.

### 4. Authentication and authorization

Authentication is *who you are*; authorization is *what you can do*. They are separate concerns.

- **Authentication** — handled by `authn-authz` skill; this skill ensures every authenticated path *checks* the token's identity and that protected paths require authentication.
- **Authorization** — **enforced at every layer that crosses a trust boundary**. Don't rely on the controller alone; the application service also checks (defense in depth). The data layer enforces tenant isolation when relevant (multi-tenancy).
- **No default-allow** — endpoints opt into being public, not opt-out. Frameworks: configure default-deny, then explicitly allow public routes.
- **Object-level authorization** — when an authenticated user requests `GET /orders/{id}`, verify the order belongs to them. *Broken object-level authorization* (BOLA / IDOR) is the most common API-level security failure.

### 5. Cryptography

- **Don't roll your own.** Use the language's canonical crypto library (Java `javax.crypto`, Node `crypto`, Python `cryptography`).
- **Hashing for passwords**: Argon2id (preferred), bcrypt (acceptable). Never MD5, SHA-1, raw SHA-256 for passwords.
- **Hashing for integrity**: SHA-256 or SHA-3.
- **Symmetric encryption**: AES-GCM with a random IV per message.
- **Asymmetric**: RSA-OAEP (2048+ bit) or X25519/Ed25519. ECDSA / EdDSA for signatures.
- **Random**: cryptographically-secure PRNG (`SecureRandom`, `crypto.randomBytes`, `secrets`). Never `Math.random` / `java.util.Random` for security tokens.
- **Key management**: keys live in the secret store (`secrets-config`), not in code or config files.
- **TLS**: minimum 1.2; prefer 1.3. Validate certificates; never disable verification "to make it work."

### 6. SSRF, XXE, deserialization

- **SSRF** (Server-Side Request Forgery) — if the application makes HTTP requests to user-supplied URLs, restrict to an allowlist of hosts/IPs. Block private IP ranges (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16, 169.254.0.0/16 for cloud metadata) unless intentional.
- **XXE** (XML External Entity) — disable external entity processing in XML parsers. Most parsers are unsafe by default; explicitly secure them.
- **Insecure deserialization** — *don't deserialize untrusted data into typed objects*. If you must, use safe formats (JSON with pydantic / zod; never Java native serialization, Python pickle, .NET BinaryFormatter on untrusted data).

### 7. Secrets discipline

- **No secrets in code, ever.** No exceptions. Not in config files, not in commit messages, not in test fixtures, not in CI logs.
- Secrets come from the secret store at runtime via `secrets-config` skill.
- Secrets-in-code detection runs in CI (`gitleaks`, `trufflehog`); pre-commit hooks reject obvious patterns.
- Rotated regularly (`secrets-config` defines the rotation cadence).
- Never log secrets, never include them in error messages, never echo to stdout.

### 8. PII handling

- **Identify PII at the data-modeling phase** — every field that's PII is tagged in the schema or model.
- **Don't log PII** unless explicitly cleared by `compliance-privacy`. Redact at the log boundary.
- **Encrypt PII at rest** when the compliance regime requires (HIPAA, certain GDPR scenarios).
- **Mask in non-prod environments** — staging and dev databases use anonymized or synthetic data.
- **Right to erasure** — GDPR / CCPA require deletable PII; data-modeling decisions support this (no PII spread across denormalized copies without a deletion plan).

### 9. Error handling that doesn't leak

- Error messages to clients are domain-meaningful but don't leak internals (no stack traces, no SQL errors, no file paths).
- Internal logs may include detail (correlation ID lets the support team link a client error to the full internal context).
- A 500 to a client is "Internal error, request ID: req-abc123." A 500 in the logs is the full stack trace.

### 10. Rate limiting and abuse prevention

- Every authenticated endpoint has a per-user rate limit.
- Every public endpoint has a per-IP rate limit.
- Auth endpoints (login, signup, password reset) have strict per-IP and per-account rate limits to prevent enumeration and brute force.
- Implementation + infrastructure layer (`platform-aws/azure/gcp/k8s` packs), but the *requirement* is set here.

## Severity tagging (for review mode)

When this skill is run as a review (Security Reviewer agent or code-review pre-merge gate):

| Severity | Definition |
|---|---|
| **blocker** | Must be fixed before merge. SQL injection, broken authentication, secrets in code, unencrypted PII storage where required. |
| **major** | Fix in this PR or before next release. Missing rate limiting on a new endpoint, weak crypto choice that isn't yet exploitable, missing object-level authorization where the bug class is present. |
| **minor** | Fix soon; track in `tech-debt-management`. Inconsistent error response shape, missing security header, hardening opportunity. |
| **nit** | Style; non-blocking. |

The pass/fail verdict: **any `blocker` fails the gate**. Major findings require explicit acceptance (a `security_finding_waiver` per the governance matrix). Minor and nit are advisory.

## Stack-specific references

Concrete sinks, safe APIs, and common violations per language live in the references:

- `references/java-spring.md` — Spring Security configuration, JPA parameterization, Jackson safety, common Spring security pitfalls.
- `references/node-ts.md` — Express/Fastify/NestJS specifics, prototype-pollution, npm security tooling.
- `references/python.md` — Django / FastAPI / Flask specifics, pickle/yaml load safety, SQLAlchemy parameterization.
- `references/web-frontend.md` — XSS, CSRF, CSP, secure cookies, SRI, postMessage hardening.

## Mode handling (G/B)

**Greenfield.** Apply the discipline by construction; the code is secure on first write.

**Brownfield.** Audit-and-fix mode. Read `.repo-intel/` for the existing security posture. Produce a prioritized findings list rather than blanket-rewriting; integrate fixes into slices that touch the affected code. Outstanding high-severity findings become entries in `.project/working/security-debt.md` and are tracked into `tech-debt-management`.

## What this skill does not do

- Threat modeling — that's `threat-modeling`; this skill applies *defenses* against threats; that skill *enumerates* them.
- Authentication implementation — that's `authn-authz`; this skill ensures *uses* of authn/authz are correct.
- Dependency security — that's `supply-chain-security`; this skill is about the code your team writes.
- Compliance evidence — that's `compliance-privacy`; this skill produces secure code, that one produces audit artifacts.
- Penetration testing — that's a separate practice.

## Verification

You are done when:

- [ ] All inputs validated at trust boundaries.
- [ ] All outputs encoded for their consumer (HTML / SQL / OS command / etc.).
- [ ] Authentication enforced at every protected endpoint.
- [ ] Authorization checks at every layer (defense in depth) per `authn-authz`.
- [ ] Secrets handled per `secrets-config`.
- [ ] Cryptographic primitives use the language's standard library; no custom crypto.
- [ ] Error messages don't leak sensitive context (stack traces, IDs of other users' resources).
- [ ] Dependencies scanned for CVEs (per `supply-chain-security`).
- [ ] OWASP Top 10 considered and mitigated per applicable category.

Evidence to check:
- SAST scan in CI; severity threshold blocks merge.
- Security Reviewer (per `code-review`) ran and findings classified.

## Common rationalizations

| The agent's thought | Counter |
|---|---|
| "Internal users only — input validation is overkill." | Insider threats are 30%+ of incidents. Internal callers can also be compromised externally. Validate inputs at trust boundaries regardless. |
| "The framework escapes this for me." | Frameworks escape what they know to escape (HTML in templates; SQL via parameterized queries). They don't escape what you're doing manually. |
| "Hashing user IDs is enough; no need for proper auth." | Hashes are not authentication. They're identifiers. Auth proves identity; hashes don't. |
| "We'll fix the secrets later; they're just in dev." | Secrets in dev get committed. Committed secrets get pulled by everyone. Rotate-and-vault from day one. |
| "Logs don't have PII." | Stack traces, request bodies, audit context. Logs accumulate PII unless explicitly filtered. |
| "We trust this third-party API to return safe data." | Treat external data as untrusted input. Period. Schema-validate, length-limit, type-check. |
| "Crypto from scratch is fine; I read a paper." | No. Use the standard library's primitives. Crypto-from-scratch is one of the most-cited engineering failures. |

## Common violations (always-flag patterns)

- String concatenation into SQL.
- `eval`, `new Function`, `pickle.load`, `ObjectInputStream.readObject` on untrusted data.
- Secrets in code, config files, or commit messages.
- `Math.random` for security tokens.
- Disabled TLS certificate verification.
- Stack traces in HTTP error responses.
- Missing object-level authorization on `GET /resource/{id}` style endpoints.
- Logging request bodies or response bodies that may contain PII.
- `dangerouslySetInnerHTML` with user content.
- File uploads without size limits and MIME-type allowlists.
