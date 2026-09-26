---
name: authn-authz
description: "Identity, authentication, authorization. OIDC / OAuth2 / SAML / MFA / session-vs-token, RBAC / ABAC / ReBAC, token lifecycle and rotation, service-to-service auth (mTLS, workload identity), object-level authorization to prevent BOLA/IDOR — the most common API-level security failure. The Solution Architect designs identity and authorization model; Backend Developer applies via the active stack pack (Spring Security / Passport / NestJS guards / Authlib / etc.); Security Reviewer audits placement. Use whenever a service introduces authenticated surface, when designing the identity model, when adding new authorization rules, or when integrating with an identity provider."
---

# Authentication & Authorization

<!-- praxis:metadata:begin -->
```yaml
capability: quality-and-security
domain: cross-cutting
state: active
dependencies:
  - secure-coding
  - secrets-config
  - threat-modeling
triggers:
  - "designing the identity model for a new project"
  - "choosing authn protocol (OIDC / OAuth2 / SAML / passwordless)"
  - "implementing or revising authorization rules (RBAC / ABAC / ReBAC)"
  - "wiring service-to-service auth (mTLS / workload identity)"
  - "auditing endpoint authorization for BOLA / IDOR"
  - "designing token rotation + revocation"
outputs:
  - identity model document (who can access what, via which mechanism)
  - authn protocol choice + integration design (per identity provider)
  - authz policy model (RBAC / ABAC / ReBAC) with code-level enforcement plan
  - token lifecycle (issuance / refresh / revocation / rotation cadence)
  - service-to-service auth design (mTLS / workload identity / signed tokens)
  - object-level authorization checklist per endpoint
consumers:
  - solution-architect (designs identity + authz)
  - backend-developer (implements via active stack pack)
  - frontend-developer (consumes for auth flows)
  - security-reviewer (audits placement)
  - multi-tenancy (consumes tenant-aware authz)
  - compliance-privacy (consumes for audit-log requirements)
references: []
```
<!-- praxis:metadata:end -->

Two concerns the team must not conflate. **Authentication** = *who you are*. **Authorization** = *what you can do*. Wrong authn lets the wrong identity in; wrong authz lets the right identity do the wrong things.

The principle: **default deny; explicit allow; check at every layer that crosses a trust boundary.**

## When this skill fires

- A new project's identity model is being designed.
- A protocol choice is being made (OIDC / OAuth2 / SAML / passwordless).
- New authorization rules are being added (a new role, a new permission, a new resource type).
- Service-to-service auth is being wired (mTLS, signed tokens, workload identity).
- A PR introduces a new authenticated endpoint — the authz model is reviewed.
- An audit surfaces missing or incorrect authorization (BOLA / IDOR is the most common API security failure).

## Authentication

### Protocol choice

| Protocol | Use when |
|---|---|
| **OIDC** | Modern web/mobile auth with identity provider integration. Default for B2C and B2B SaaS. Provides identity (ID token) + access (access token) + refresh. |
| **OAuth 2.1** | API authorization without OIDC's identity assertion. Less common standalone; usually paired with OIDC. |
| **SAML** | Enterprise SSO; required by many B2B customers. Older, XML-heavy, but ubiquitous in enterprise IT. |
| **Passwordless (magic link / passkey / WebAuthn)** | Better UX + better security. Use for consumer surfaces; pair with another factor for higher-risk operations. |
| **API keys** | Programmatic access from partners / integrations. Scoped, rotatable, revocable. |
| **mTLS** | Service-to-service. Strong identity binding; certificate management overhead. |

Default for new B2B SaaS: **OIDC** for human users; **mTLS or workload identity** for service-to-service.

### Identity provider

- **Hosted** (Auth0 / Cognito / Azure AD / Google Identity / Okta): faster to integrate, vendor cost.
- **Self-hosted** (Keycloak / Ory / ZITADEL / Authentik): more control, more operational responsibility.

Pick once; both are first-class. Migration is expensive — choose deliberately.

### MFA

For any identity that grants meaningful access: TOTP, WebAuthn (preferred), or push-based factors. SMS-as-second-factor is increasingly rejected for high-value targets (SIM-swap attacks).

### Session vs token

| | Session-based | Token-based (JWT) |
|---|---|---|
| **Storage** | Server-side store (Redis); client holds session ID. | Client-side; server verifies signature. |
| **Revocation** | Trivial — delete the session. | Complex — needs revocation list or short TTLs. |
| **Statelessness** | Server has state. | Server stateless (auth-wise). |
| **Best for** | Web apps with low-cardinality sessions. | API gateways; service-to-service; mobile. |

Default: session-based for web app; access tokens (with refresh) for API + mobile.

### Tokens

If using JWT:

- **Short TTL on access tokens** (5–15 minutes). Reduces revocation pressure.
- **Refresh tokens** with longer TTL (days to weeks) + rotation on use. Stored securely (httpOnly cookie for web; secure storage for mobile).
- **Sign with asymmetric keys** (RS256 / ES256). Key rotation via JWKS endpoint.
- **Validate every claim**: issuer, audience, expiration, signature. Never trust unverified payloads.
- **Don't put PII or secrets in the JWT** — they're visible to the client and intermediaries.

## Authorization

### Models

**RBAC** (Role-Based Access Control) — users have roles; roles have permissions. Simple; the right default for most projects.

**ABAC** (Attribute-Based Access Control) — decisions evaluated against attributes (user, resource, action, context). Powerful; more complex. Use when permissions depend on dynamic context (time, location, resource state).

**ReBAC** (Relationship-Based Access Control) — permissions follow from relationships (Google Zanzibar style). Use when "user X can access resource Y if X is in group Z that's shared with Y" is the natural way to think.

Most projects: **RBAC at the API surface**, **per-resource policy checks in the application layer** for the dynamic cases.

### Where to enforce

Authorization is enforced at every layer that crosses a trust boundary. Defense in depth:

1. **API gateway / ingress** — coarse-grained (authenticated, scoped to the API).
2. **Controller / route handler** — endpoint-level (this role can call this endpoint).
3. **Application service** — operation-level (this user can perform this operation on this entity).
4. **Data layer** — for multi-tenancy especially (the user can read only their tenant's rows).

Skipping a layer is a vulnerability. The controller alone is insufficient — application services should re-verify on the chance the controller's check was bypassed or missing.

### Object-level authorization (the BOLA / IDOR failure)

The most common API-level security failure: an authenticated user requests `GET /orders/{id}` for an `id` that doesn't belong to them; the server returns it. Tests for this:

- **Every per-resource endpoint** verifies the resource belongs to the requesting identity.
- Implementation pattern:

```python
# Application service
def get_order(user_id: str, order_id: OrderId) -> Order:
    order = self.orders.find(order_id) or raise NotFoundError()
    if order.customer_id != user_id and not user_is_admin(user_id):
        raise NotFoundError()   # NotFound, not Forbidden, to avoid enumeration
    return order
```

Return `404 Not Found` (not `403 Forbidden`) for cross-tenant or cross-user resources — disclosing existence is itself a leak.

Audit every `GET /resource/{id}`, `PATCH /resource/{id}`, `DELETE /resource/{id}` endpoint for object-level authorization. The Security Reviewer's checklist (per `secure-coding`) flags missing checks.

### Policy as code

Codify authorization rules:

- **Open Policy Agent (OPA)** with Rego — runtime policy engine; rules live in `.rego` files, version-controlled.
- **Cedar** (AWS) — newer; types, deny-by-default semantics.
- **Inline code** — simple authz can live in application code; policies grow into externalized engines.

For projects with non-trivial authorization: externalize to OPA / Cedar. For simple RBAC: inline is fine.

## Service-to-service auth

In-cluster and cross-service:

- **mTLS via service mesh** (Istio, Linkerd) — mutual certificates handled by the mesh. Each pod has a workload identity; certificates rotated automatically.
- **Workload identity binding to cloud IAM** (IRSA on EKS, Workload Identity on GKE, Pod Identity on AKS) — services authenticate to cloud services as themselves.
- **Signed tokens (SPIFFE / SVID)** — workload identity standard.
- **Shared bearer tokens** — only as fallback; rotation discipline applies.

Default for K8s: service mesh mTLS + workload identity binding to cloud.

## Token discipline

- **Rotation** — keys (JWT signing) rotate quarterly; access tokens are short-lived; refresh tokens rotate on use.
- **Revocation** — refresh tokens are revocable (one user, one device, all sessions). Revocation propagates within the access token's TTL — that's the cost of statelessness.
- **Audit logging** — every authn + every authz decision (success or failure) is auditable for the compliance regimes.
- **Rate limiting on auth endpoints** — strict per-IP and per-account rate limits to prevent enumeration and brute-force.

## Per-endpoint authz checklist

For every authenticated endpoint, the design (and code review) verifies:

- Is the caller authenticated? (default deny)
- Is the caller authorized for this endpoint's role/scope?
- Does the caller have permission on the *specific resource* (object-level)?
- Is rate limiting applied?
- Are failed auth attempts logged?
- Are successful auth events logged for sensitive operations?

## Outputs

| Output | Location |
|---|---|
| Identity model | `.project/semantic/identity-model.md` |
| Authn protocol decision + ADR | `.project/decision/` |
| Authz policy (RBAC roles / ABAC attributes / ReBAC relations) | `.project/semantic/authz-policy.md` |
| Token lifecycle policy | `.project/procedural/token-policy.md` |
| Service-to-service auth design | `.project/operational/service-auth.md` |
| Per-endpoint authz checklist | inline in code-review template |

## Mode handling (G/B)

**Greenfield.** Design identity + authz from day one. Default deny; explicit allow.

**Brownfield.** Audit existing authn + authz. Common findings: missing object-level checks (BOLA everywhere); long-lived static tokens; no MFA on admin accounts; service-to-service via shared secrets. Prioritize by attack surface — public-facing first.

## What this skill does not do

- Identity-provider operations (account provisioning, deprovisioning) — typically owned by IT / People Ops in larger orgs.
- Penetration testing — separate practice.
- Secrets at rest (keys, tokens) — that's `secrets-config`.
- Threat-model construction — that's `threat-modeling` (this skill provides the authz design that the threat model evaluates).

## Common rationalizations

| The agent's thought | Counter |
|---|---|
| "Roll our own auth — it's not that hard." | It is that hard. Use a battle-tested IdP (Auth0, Okta, Cognito, Keycloak). Roll your own only with strong justification. |
| "JWT validation is enough." | Validation ≠ authorization. JWT proves identity; the decision about access lives in your code. |
| "RBAC is sufficient." | RBAC fails on row-level questions ("can THIS user read THIS record"). Add ABAC or relationships-based policy. |
| "Session-based and token-based are equivalent." | They aren't — different revocation models, different XSS/CSRF concerns. Pick deliberately. |
| "We'll add MFA when we need to." | MFA after a breach is reactive; before is preventive. The cost is the same; the impact is different. |
| "Authorization at the controller layer catches everything." | Defense in depth: controller + service + repository. A single missed check elsewhere bypasses the controller layer. |
| "Refresh tokens never expire." | They should — and rotate. Long-lived tokens become breach exposure surface. |

## Verification

You are done when:

- [ ] Authentication mechanism chosen and documented (session / JWT / OAuth flow per use case).
- [ ] Identity provider integrated; configuration in `secrets-config`.
- [ ] Authorization model documented (RBAC / ABAC / ReBAC) with policy examples.
- [ ] Authorization checks at every layer (controller, service, repository) for every protected operation.
- [ ] Audit log captures: who, what action, what resource, when, success/failure.
- [ ] MFA required for admin / high-privilege accounts.
- [ ] Token rotation policy: access (short), refresh (medium), API key (long; with rotation procedure).
- [ ] Session revocation on logout actually revokes (not just clears the cookie).

Evidence to check:
- Pen-test verifies broken access control (OWASP A01:2021) is not present.
- Per-endpoint authorization test exists in the test suite.
- Logging captures privilege escalation attempts.

## Anti-patterns

- Authorization at the controller only (no defense in depth).
- Missing object-level checks (BOLA / IDOR).
- Long-lived (months / years) static API tokens with no rotation.
- JWT validation skipping audience or issuer check.
- Roles as enums hardcoded in code (use a policy file / DB).
- Shared service-to-service tokens with cluster-wide blast radius.
- Auth endpoints without rate limiting (enumeration / brute-force).
- Returning `403 Forbidden` for cross-tenant resources (use `404`).
- Storing PII in JWTs (visible to client).
- SMS as a second factor for high-value targets.
