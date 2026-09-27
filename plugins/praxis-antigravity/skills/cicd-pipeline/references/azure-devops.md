# CI/CD Pipeline — Azure DevOps Pipelines

Azure DevOps Pipelines–specific implementation.

## File layout

```
azure-pipelines.yml                main pipeline
.azuredevops/
├── templates/
│   ├── ci-stage.yml               reusable stage templates
│   ├── deploy-stage.yml           deploy stage templates
│   └── jobs/                      reusable job definitions
└── variables/
    └── env.yml                    variable groups (referenced from pipelines)
```

## Standard CI pipeline

```yaml
# azure-pipelines.yml
trigger:
  branches:
    include: [main]
pr:
  branches:
    include: [main]

variables:
  - group: project-secrets
  - name: NODE_VERSION
    value: '20.x'

stages:
  - stage: Check
    jobs:
      - job: LintAndTypecheck
        pool:
          vmImage: 'ubuntu-latest'
        steps:
          - task: NodeTool@0
            inputs: { versionSpec: '$(NODE_VERSION)' }
          - task: Cache@2
            inputs:
              key: 'npm | "$(Agent.OS)" | package-lock.json'
              path: ~/.npm
          - script: npm ci
          - script: npm run lint
          - script: npm run typecheck

  - stage: Test
    dependsOn: Check
    jobs:
      - job: UnitTests
        pool: { vmImage: 'ubuntu-latest' }
        steps:
          - task: NodeTool@0
            inputs: { versionSpec: '$(NODE_VERSION)' }
          - script: npm ci
          - script: npm run test:unit -- --coverage
          - task: PublishCodeCoverageResults@2
            inputs:
              summaryFileLocation: coverage/cobertura-coverage.xml

      - job: IntegrationTests
        pool: { vmImage: 'ubuntu-latest' }
        services:
          postgres:
            image: postgres:16-alpine
            env:
              POSTGRES_PASSWORD: test
        steps:
          - task: NodeTool@0
            inputs: { versionSpec: '$(NODE_VERSION)' }
          - script: npm ci
          - script: npm run test:integration

  - stage: Security
    dependsOn: Check
    jobs:
      - job: SAST
        pool: { vmImage: 'ubuntu-latest' }
        steps:
          - script: |
              docker run --rm -v $(System.DefaultWorkingDirectory):/src \
                returntocorp/semgrep semgrep --config=auto --error /src
      - job: SCA
        pool: { vmImage: 'ubuntu-latest' }
        steps:
          - script: |
              docker run --rm -v $(System.DefaultWorkingDirectory):/src \
                aquasec/trivy:latest fs --severity HIGH,CRITICAL --exit-code 1 /src

  - stage: Build
    dependsOn: [Test, Security]
    jobs:
      - job: Build
        pool: { vmImage: 'ubuntu-latest' }
        steps:
          - task: NodeTool@0
            inputs: { versionSpec: '$(NODE_VERSION)' }
          - script: npm ci
          - script: npm run build
          - task: PublishBuildArtifacts@1
            inputs:
              pathToPublish: dist
              artifactName: build

  - stage: Container
    dependsOn: Build
    jobs:
      - job: ContainerBuildSign
        pool: { vmImage: 'ubuntu-latest' }
        steps:
          - task: Docker@2
            inputs:
              command: 'buildAndPush'
              containerRegistry: 'project-acr'
              repository: 'app'
              tags: '$(Build.SourceVersion)'
              arguments: '--provenance=true --sbom=true'
          - script: |
              cosign sign --yes \
                $(ACR_NAME).azurecr.io/app:$(Build.SourceVersion)
```

## Templates for reuse

```yaml
# .azuredevops/templates/ci-stage.yml
parameters:
  - name: nodeVersion
    type: string
    default: '20.x'

stages:
  - stage: CI
    jobs:
      - job: LintAndTest
        steps:
          - task: NodeTool@0
            inputs: { versionSpec: '${{ parameters.nodeVersion }}' }
          - script: npm ci
          - script: npm run lint
          - script: npm run test
```

Referenced from `azure-pipelines.yml`:

```yaml
- template: .azuredevops/templates/ci-stage.yml
  parameters: { nodeVersion: '20.x' }
```

## Variable groups + Key Vault integration

```yaml
variables:
  - group: project-secrets   # variable group linked to Key Vault
```

Variable groups can be linked to Azure Key Vault for centralized secret management.

## Service connections

For deploys (Wave 3 `deploy-release`):

- **Azure Service Connection** via federated identity (OIDC) — no static credentials.
- **Kubernetes Service Connection** with Workload Identity for AKS.
- **Docker Registry Service Connection** for ACR / Docker Hub.

## Branch policies (project settings)

- Required reviewers per `CODEOWNERS`.
- Build validation: the CI pipeline must succeed.
- Required status checks per environment.
- Auto-include `path:` filters for review routing.

## Common violations to flag in review

- Inline scripts when a template would DRY the logic.
- Variables in plain text when they belong in a variable group / Key Vault.
- Stages without `dependsOn:` (incorrect ordering, missed parallelism).
- Missing `Cache@2` task (non-reproducible perf).
- Container builds without provenance/sbom.
- Direct credential use in pipelines (should be federated identity / service connections).
- Pipelines stored only in UI (not as YAML in repo).
