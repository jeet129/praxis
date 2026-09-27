# CI/CD Pipeline — GitLab CI

GitLab CI–specific implementation of the standard pipeline chain.

## File layout

```
.gitlab-ci.yml                    main pipeline
.gitlab/
├── ci/
│   ├── jobs.yml                  reusable job definitions (extends:)
│   ├── rules.yml                 reusable rule definitions
│   └── variables.yml             shared variables
└── CODEOWNERS                    review routing
```

## Standard CI pipeline

```yaml
# .gitlab-ci.yml
include:
  - local: '.gitlab/ci/jobs.yml'

stages:
  - setup
  - check
  - test
  - security
  - build
  - container
  - publish

variables:
  CACHE_KEY: "${CI_COMMIT_REF_SLUG}-${CI_COMMIT_SHORT_SHA}"

default:
  image: node:20-alpine
  cache: &node_cache
    key:
      files: [package-lock.json]
    paths: [node_modules/, ~/.npm]
    policy: pull

# Stage: check
lint:
  stage: check
  script:
    - npm ci
    - npm run lint
  cache:
    <<: *node_cache
    policy: pull-push

typecheck:
  stage: check
  script:
    - npm ci
    - npm run typecheck
  cache: *node_cache

# Stage: test
unit-tests:
  stage: test
  script:
    - npm ci
    - npm run test:unit -- --coverage
  cache: *node_cache
  artifacts:
    paths: [coverage/]
    reports:
      coverage_report:
        coverage_format: cobertura
        path: coverage/cobertura-coverage.xml
  coverage: '/Lines\s*:\s*([0-9.]+)/'

integration-tests:
  stage: test
  services:
    - name: postgres:16-alpine
      alias: postgres
  variables:
    POSTGRES_DB: test
    POSTGRES_PASSWORD: test
    DB_URL: postgres://postgres:test@postgres/test
  script:
    - npm ci
    - npm run test:integration
  cache: *node_cache

# Stage: security
sast:
  stage: security
  image: returntocorp/semgrep
  script:
    - semgrep --config=auto --error

sca:
  stage: security
  image: aquasec/trivy:latest
  script:
    - trivy fs --severity HIGH,CRITICAL --exit-code 1 .

# Stage: build
build:
  stage: build
  script:
    - npm ci
    - npm run build
  cache: *node_cache
  artifacts:
    paths: [dist/]

# Stage: container
container-build:
  stage: container
  image: docker:24
  services:
    - docker:24-dind
  variables:
    DOCKER_HOST: tcp://docker:2376
    DOCKER_TLS_CERTDIR: /certs
  needs: [build, integration-tests, sast, sca]
  script:
    - docker buildx create --use
    - docker login -u $CI_REGISTRY_USER -p $CI_REGISTRY_PASSWORD $CI_REGISTRY
    - docker buildx build
        --cache-from type=registry,ref=$CI_REGISTRY_IMAGE:cache
        --cache-to type=registry,ref=$CI_REGISTRY_IMAGE:cache,mode=max
        --provenance=true
        --sbom=true
        --tag $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA
        --push
        .
    - trivy image --severity HIGH,CRITICAL --exit-code 1 $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA

container-sign:
  stage: container
  image: gcr.io/projectsigstore/cosign
  needs: [container-build]
  script:
    - cosign sign --yes $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA

# Stage: publish (main branch only)
tag-release:
  stage: publish
  only: [main]
  script:
    - docker tag $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA $CI_REGISTRY_IMAGE:latest
    - docker push $CI_REGISTRY_IMAGE:latest
```

## Reusable job templates

```yaml
# .gitlab/ci/jobs.yml
.node-job:
  image: node:20-alpine
  cache:
    key:
      files: [package-lock.json]
    paths: [node_modules/, ~/.npm]
  before_script:
    - npm ci

.security-job:
  stage: security
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
    - if: $CI_COMMIT_BRANCH == "main"
```

## Branch protection (via project settings or Terraform)

- Protected branch: `main`.
- Merge requires successful pipeline.
- Required approvers per CODEOWNERS.
- No fast-forward; require merge commits with full history.

## Secrets management

- Group-level or project-level CI variables.
- Masked + protected for production secrets.
- OIDC integration for cloud provider auth (`id_tokens:` in jobs).

## Common violations to flag in review

- Jobs without explicit `image:` (uses runner default — non-reproducible).
- Cache without explicit `key:` (cache pollution across branches).
- `script:` blocks that don't fail-fast (missing `set -euo pipefail`).
- `only:`/`except:` deprecated patterns (use `rules:` instead).
- Container build without provenance/sbom.
- Pipeline secrets unprotected (visible in unprotected branches).
- Missing `needs:` causing unnecessary serialization.
