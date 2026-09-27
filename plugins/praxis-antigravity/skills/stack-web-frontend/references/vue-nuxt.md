# Stack — Web Frontend — Vue + Nuxt

Framework-specific idioms for Vue 3 + Nuxt 3+ (Composition API, `<script setup>`).

## Project layout

```
/
├── nuxt.config.ts           Nuxt configuration
├── app.vue                  root component
├── pages/                   file-based routing
│   ├── index.vue
│   └── orders/
│       ├── index.vue
│       └── [id].vue
├── layouts/                 shared layouts
├── features/                feature folders (bounded contexts)
│   └── orders/
│       ├── components/
│       ├── composables/
│       ├── api/
│       └── types.ts
├── components/              auto-imported global components (use sparingly)
├── design-system/           shared components
├── composables/             auto-imported global composables
├── server/                  server routes, middleware
├── locales/                 i18n
└── public/
```

## Composition API + `<script setup>`

```vue
<!-- features/orders/components/OrdersList.vue -->
<script setup lang="ts">
import { useOrders } from '../composables/use-orders';

const { data, isLoading, error } = useOrders();
</script>

<template>
  <Spinner v-if="isLoading" aria-label="Loading orders" />
  <Alert v-else-if="error" variant="error">{{ error.message }}</Alert>
  <ul v-else-if="data?.length">
    <li v-for="order in data" :key="order.id">
      {{ order.id }} — {{ order.amount }}
    </li>
  </ul>
  <p v-else>No orders yet.</p>
</template>
```

## State management

- **Server state**: `useFetch`/`useAsyncData` (Nuxt server-side) or `@tanstack/vue-query` (client-side).
- **URL state**: `useRoute`, `useRouter`, `useRouteQuery`.
- **Local state**: `ref()`, `reactive()`.
- **Cross-component client state**: `provide`/`inject` for narrow scope; Pinia for global stores when justified.
- **Form state**: vee-validate + Zod, or VueUse's form helpers, or custom composables.

```ts
// features/orders/composables/use-orders.ts
import { useQuery } from '@tanstack/vue-query';
import { OrdersResponseSchema, type Order } from '../types';

export function useOrders() {
  return useQuery({
    queryKey: ['orders'],
    queryFn: async (): Promise<Order[]> => {
      const res = await $fetch('/api/orders');
      return OrdersResponseSchema.parse(res);
    },
  });
}
```

## Routing

File-based via `pages/`:

- `pages/index.vue` → `/`
- `pages/orders/index.vue` → `/orders`
- `pages/orders/[id].vue` → `/orders/:id`
- `pages/orders/[id]/edit.vue` → `/orders/:id/edit`
- `layouts/default.vue` → default layout

Middleware:

```ts
// middleware/auth.ts
export default defineNuxtRouteMiddleware((to) => {
  const user = useAuth();
  if (!user.value) return navigateTo('/login');
});
```

Server-side data fetching for SSR:

```vue
<script setup lang="ts">
const { data: orders } = await useFetch<Order[]>('/api/orders');
</script>
```

## Forms

vee-validate + Zod:

```vue
<script setup lang="ts">
import { useForm } from 'vee-validate';
import { toTypedSchema } from '@vee-validate/zod';
import { z } from 'zod';

const schema = toTypedSchema(z.object({
  email: z.string().email(),
  amount: z.number().positive(),
}));

const { defineField, handleSubmit, errors } = useForm({ validationSchema: schema });
const [email, emailAttrs] = defineField('email');
const [amount, amountAttrs] = defineField('amount', { props: (s) => ({ 'aria-invalid': !!s.errors[0] }) });

const onSubmit = handleSubmit(async (values) => {
  await placeOrder(values);
});
</script>

<template>
  <form @submit="onSubmit">
    <label for="email">Email</label>
    <input id="email" v-model="email" v-bind="emailAttrs" />
    <p v-if="errors.email" role="alert">{{ errors.email }}</p>
    <button type="submit">Place order</button>
  </form>
</template>
```

## Testing

- **Vitest** for unit + component tests.
- **@vue/test-utils** for component rendering.
- **Playwright** for E2E.
- **@nuxt/test-utils** for Nuxt-aware tests.
- **@axe-core/playwright** for a11y.

## Build & tooling

- `nuxt build` / `nuxt dev`.
- Auto-imports for composables and components (configurable).
- ESLint with `eslint-plugin-vue` + `@typescript-eslint`.
- Prettier.
- Nuxt's built-in DevTools.

## Common violations to flag in review

- Options API in new code (use `<script setup>`).
- Reactive primitives accessed without `.value` outside template (lint catches).
- Server state in `ref()` instead of `useQuery` or `useFetch`.
- Hardcoded text without i18n (`useI18n` / `$t`).
- Direct DOM manipulation outside template refs.
- Component imports bypassing auto-imports without reason.
- `any` outside boundary code.
- Forms without vee-validate (or equivalent) reinventing validation.
