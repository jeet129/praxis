# IaC — Pulumi

Pulumi-specific patterns for the shared IaC discipline. Pulumi expresses infrastructure as code in real programming languages (TypeScript, Python, Go, .NET, Java) — preferred when the team wants IDE support, language-native abstractions, and full programming-language testability for infrastructure.

## Project layout

```
infra/
├── pulumi/
│   ├── stacks/                       per-environment stacks
│   │   ├── Pulumi.dev.yaml           dev stack config
│   │   ├── Pulumi.test.yaml
│   │   ├── Pulumi.staging.yaml
│   │   └── Pulumi.production.yaml
│   ├── components/                   reusable component resources
│   │   ├── network.ts
│   │   ├── cluster.ts
│   │   ├── database.ts
│   │   └── ...
│   ├── policies/                     CrossGuard policy packs
│   ├── index.ts                      stack entry point
│   ├── Pulumi.yaml                   project manifest
│   ├── package.json                  (TypeScript)
│   └── tsconfig.json
└── shared/                           cross-env resources
```

## Component resources

Components are the Pulumi equivalent of Terraform modules — reusable building blocks. They're regular language classes:

```typescript
// components/cluster.ts
import * as pulumi from '@pulumi/pulumi';
import * as aws from '@pulumi/aws';
import * as eks from '@pulumi/eks';

export interface ClusterArgs {
  name: string;
  vpcId: pulumi.Input<string>;
  subnetIds: pulumi.Input<string[]>;
  nodePoolSize?: number;
  nodeInstanceType?: string;
  autoscalerMax?: number;
  tags: { [key: string]: string };
}

export class Cluster extends pulumi.ComponentResource {
  public readonly id: pulumi.Output<string>;
  public readonly endpoint: pulumi.Output<string>;
  public readonly kubeconfig: pulumi.Output<string>;

  constructor(name: string, args: ClusterArgs, opts?: pulumi.ComponentResourceOptions) {
    super('myorg:infra:Cluster', name, args, opts);

    const cluster = new eks.Cluster(`${name}-cluster`, {
      vpcId: args.vpcId,
      subnetIds: args.subnetIds,
      instanceType: args.nodeInstanceType ?? 't3.large',
      desiredCapacity: args.nodePoolSize ?? 3,
      maxSize: args.autoscalerMax ?? 10,
      tags: args.tags,
    }, { parent: this });

    this.id = cluster.eksCluster.id;
    this.endpoint = cluster.eksCluster.endpoint;
    this.kubeconfig = cluster.kubeconfig;

    this.registerOutputs({
      id: this.id,
      endpoint: this.endpoint,
      kubeconfig: this.kubeconfig,
    });
  }
}
```

The `ComponentResource` pattern is the abstraction unit. Stack code composes components.

## Stack composition

```typescript
// index.ts — entry point; same code, different stack configs
import * as pulumi from '@pulumi/pulumi';
import { Network } from './components/network';
import { Cluster } from './components/cluster';
import { Database } from './components/database';
import { SecretStore } from './components/secret-store';

const config = new pulumi.Config();
const env = pulumi.getStack();  // 'dev' | 'test' | 'staging' | 'production'

const commonTags = {
  project: config.require('project'),
  environment: env,
  owner: config.require('owner'),
  costCenter: config.require('costCenter'),
  criticality: config.require('criticality'),
  managedBy: 'pulumi',
};

const network = new Network(`${env}-network`, {
  cidr: config.require('networkCidr'),
  azCount: config.requireNumber('azCount'),
  tags: commonTags,
});

const cluster = new Cluster(`${env}-cluster`, {
  vpcId: network.id,
  subnetIds: network.privateSubnetIds,
  nodePoolSize: config.getNumber('nodePoolSize') ?? 3,
  nodeInstanceType: config.get('nodeInstanceType') ?? 't3.large',
  autoscalerMax: config.getNumber('autoscalerMax') ?? 10,
  tags: commonTags,
});

const database = new Database(`${env}-database`, {
  vpcId: network.id,
  subnetIds: network.privateSubnetIds,
  instanceClass: config.require('dbInstanceClass'),
  multiAZ: config.getBoolean('dbMultiAZ') ?? false,
  backupRetentionDays: config.getNumber('dbBackupDays') ?? 7,
  tags: commonTags,
});

const secretStore = new SecretStore(`${env}-secrets`, {
  rotationEnabled: env === 'production' || env === 'staging',
  tags: commonTags,
});

export const kubeconfig = cluster.kubeconfig;
export const dbEndpoint = database.endpoint;
```

## Stack config

```yaml
# stacks/Pulumi.production.yaml
config:
  myproject:project: myapp
  myproject:owner: platform-team
  myproject:costCenter: engineering
  myproject:criticality: critical
  myproject:networkCidr: 10.0.0.0/16
  myproject:azCount: '3'
  myproject:nodePoolSize: '10'
  myproject:nodeInstanceType: m5.2xlarge
  myproject:autoscalerMax: '50'
  myproject:dbInstanceClass: db.r5.2xlarge
  myproject:dbMultiAZ: 'true'
  myproject:dbBackupDays: '30'
```

```yaml
# stacks/Pulumi.dev.yaml
config:
  myproject:project: myapp
  myproject:owner: platform-team
  myproject:costCenter: engineering
  myproject:criticality: low
  myproject:networkCidr: 10.10.0.0/16
  myproject:azCount: '1'
  myproject:nodePoolSize: '2'
  myproject:nodeInstanceType: t3.medium
  myproject:autoscalerMax: '5'
  myproject:dbInstanceClass: db.t3.medium
  myproject:dbMultiAZ: 'false'
  myproject:dbBackupDays: '1'
```

Same code, different stacks, different scale.

## State backend

Pulumi defaults to Pulumi Cloud for managed state. Alternatives:

- **Pulumi Cloud** — managed; encrypted at rest; supports OIDC; simplest.
- **Self-hosted (S3 / Azure Blob / GCS)** — `pulumi login s3://bucket/path` etc.

Per-stack state isolation is built in. State locking is automatic for the Pulumi Cloud backend.

## Sensitive config

```yaml
# pulumi config set with --secret encrypts at rest in stack config
pulumi config set --secret dbAdminPassword <value>
```

In code:

```typescript
const dbPassword = config.requireSecret('dbAdminPassword');
// dbPassword is pulumi.Output<string>; never serialized in plain text
```

But, as with Terraform, the better pattern is to have Pulumi *create* the secret and store it in the secret store directly:

```typescript
import * as random from '@pulumi/random';
import * as aws from '@pulumi/aws';

const dbPassword = new random.RandomPassword(`${env}-db-password`, {
  length: 32,
  special: false,
});

const dbSecret = new aws.secretsmanager.Secret(`${env}-db-password`, {
  name: `${env}/db/password`,
});

new aws.secretsmanager.SecretVersion(`${env}-db-password-v`, {
  secretId: dbSecret.id,
  secretString: dbPassword.result,
});
```

## Preview + up in CI

```yaml
# (GitHub Actions example)
- name: Pulumi preview
  uses: pulumi/actions@v5
  with:
    command: preview
    stack-name: myorg/myproject/${{ matrix.env }}
    work-dir: infra/pulumi
    comment-on-pr: true

# Up only on merge to main, gated for production
- name: Pulumi up
  if: github.event_name == 'push' && github.ref == 'refs/heads/main'
  uses: pulumi/actions@v5
  with:
    command: up
    stack-name: myorg/myproject/${{ matrix.env }}
    work-dir: infra/pulumi
```

## Policy-as-code with CrossGuard

```typescript
// policies/required-tags.ts
import * as awsClassic from '@pulumi/aws';
import { ResourceValidationPolicy, validateResourceOfType } from '@pulumi/policy';

export const requiredTags: ResourceValidationPolicy = {
  name: 'required-tags',
  description: 'Resources must carry required tags.',
  enforcementLevel: 'mandatory',
  validateResource: (args, reportViolation) => {
    if (!args.props.tags) {
      reportViolation('Resource is missing required tags.');
      return;
    }
    const required = ['project', 'environment', 'owner', 'costCenter', 'criticality'];
    for (const tag of required) {
      if (!args.props.tags[tag]) {
        reportViolation(`Resource is missing required tag '${tag}'.`);
      }
    }
  },
};
```

Apply the policy pack in `pulumi up`:

```bash
pulumi policy publish myorg/policies
pulumi policy enable myorg/policies <version>
```

## Drift detection

```bash
pulumi refresh --diff   # show drift without applying
```

Schedule this in CI; alert on non-zero diff.

## Testing infrastructure code

Pulumi's killer feature for many teams. Component resources are regular classes; mock them and test:

```typescript
// components/cluster.test.ts
import * as pulumi from '@pulumi/pulumi';
import { describe, it, expect, beforeAll } from 'vitest';
import { Cluster } from './cluster';

pulumi.runtime.setMocks({
  newResource: (args) => ({
    id: `${args.name}-id`,
    state: { ...args.inputs },
  }),
  call: () => ({}),
});

describe('Cluster', () => {
  it('creates an EKS cluster with the requested node count', async () => {
    const cluster = new Cluster('test', {
      name: 'test',
      vpcId: 'vpc-123',
      subnetIds: ['subnet-1', 'subnet-2'],
      nodePoolSize: 5,
      tags: { project: 't', environment: 'test', owner: 'o', costCenter: 'c', criticality: 'low' },
    });

    const id = await new Promise((resolve) => cluster.id.apply(resolve));
    expect(id).toBeDefined();
  });
});
```

This is genuinely useful and is a key reason teams choose Pulumi over Terraform.

## Common violations to flag in review

- Component resources with too many inputs (split them).
- Hardcoded values that should be stack config.
- `apply()` chains that hide logic — break them out.
- Direct use of provider SDKs instead of Pulumi resources (loses state tracking).
- Missing `parent:` on child resources (breaks Pulumi's resource graph).
- Stack outputs that expose secrets without `.apply()` to a non-sensitive transformation.
- Imperative side-effects in component constructors (writing files, calling APIs).
- Stacks named with environment suffixes when they could use stack config (e.g., `myproject-prod` instead of stack `production`).
- Missing CrossGuard policies.

## Tooling

- **pulumi CLI** — the binary.
- **@pulumi/policy** — CrossGuard policies.
- **vitest / jest / pytest / Go's testing** — language-native unit tests for components.
- **infracost** — also works with Pulumi.
- **pulumi-esc** — Pulumi's secret management (alternative to cloud-native secret stores for some flows).
