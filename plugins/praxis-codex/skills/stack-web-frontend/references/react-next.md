# Stack — Web Frontend — React + Next.js

Framework-specific idioms for React 19 + Next.js 15 (App Router).

## Project layout

```
src/
├── app/                     Next.js App Router root
│   ├── layout.tsx           root layout
│   ├── page.tsx             root route
│   ├── error.tsx            error boundary
│   ├── loading.tsx          loading UI
│   └── (groups)/            route groups for shared layouts
├── features/                feature folders (bounded contexts)
│   └── orders/
│       ├── components/
│       ├── hooks/
│       ├── api/             TanStack Query hooks
│       └── types/
├── design-system/           shared components
├── lib/                     small utilities
├── locales/                 i18n catalogs (next-intl or similar)
└── styles/
```

App Router (RSC + client components) for new projects. Pages Router only when migrating from older Next.js.

## Server vs. client components (RSC)

Default to **Server Components** (no directive needed). Add `'use client'` only when interactivity, state, or browser APIs are required.

```tsx
// app/orders/page.tsx — Server Component by default
import { OrdersList } from '@/features/orders/components/OrdersList';
import { getOrders } from '@/features/orders/api/get-orders';

export default async function OrdersPage() {
  const orders = await getOrders();   // runs on server
  return <OrdersList orders={orders} />;
}

// features/orders/components/OrderActions.tsx — explicit client
'use client';
import { useState } from 'react';

export function OrderActions({ orderId }: { orderId: string }) {
  const [isLoading, setLoading] = useState(false);
  // ...
}
```

Push the `'use client'` boundary as far down the tree as possible. Server components above; client islands below.

## State management

- **Server state**: TanStack Query (for client-fetched data) or Server Components (for SSR-fetched data).
- **URL state**: `useSearchParams`, `usePathname`, `useRouter` from `next/navigation`.
- **Local state**: `useState`, `useReducer`.
- **Cross-component client state**: Context for low-frequency global state (theme, locale). Zustand for higher-frequency or larger global state when justified.
- **Form state**: React Hook Form + Zod resolver.

```tsx
// features/orders/api/use-orders.ts
'use client';
import { useQuery } from '@tanstack/react-query';
import { z } from 'zod';

const OrderSchema = z.object({
  id: z.string(),
  customerId: z.string(),
  amount: z.number(),
  status: z.enum(['pending', 'paid', 'shipped']),
});
export const OrdersResponseSchema = z.array(OrderSchema);
export type Order = z.infer<typeof OrderSchema>;

export function useOrders() {
  return useQuery({
    queryKey: ['orders'],
    queryFn: async (): Promise<Order[]> => {
      const res = await fetch('/api/orders');
      if (!res.ok) throw new Error('failed to load orders');
      const data = await res.json();
      return OrdersResponseSchema.parse(data);
    },
  });
}
```

## Routing

File-based. Conventions:

- `app/orders/page.tsx` → `/orders`
- `app/orders/[id]/page.tsx` → `/orders/:id`
- `app/orders/[id]/edit/page.tsx` → `/orders/:id/edit`
- `app/(auth)/login/page.tsx` → `/login` with the `(auth)` group's layout
- `app/orders/layout.tsx` → shared layout for `/orders/*`
- `app/orders/loading.tsx` → loading UI while routes load
- `app/orders/error.tsx` → error boundary

Server actions for mutations:

```tsx
// app/orders/actions.ts
'use server';
import { CreateOrderSchema } from '@/features/orders/types';
import { createOrder } from '@/features/orders/api/create-order';

export async function placeOrder(formData: FormData) {
  const parsed = CreateOrderSchema.safeParse({
    customerId: formData.get('customerId'),
    amount: Number(formData.get('amount')),
  });
  if (!parsed.success) return { error: parsed.error.format() };
  const order = await createOrder(parsed.data);
  return { order };
}
```

## Forms

React Hook Form + Zod:

```tsx
'use client';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';

const Schema = z.object({
  email: z.string().email(),
  amount: z.number().positive(),
});
type FormValues = z.infer<typeof Schema>;

export function PlaceOrderForm({ onSubmit }: { onSubmit: (v: FormValues) => Promise<void> }) {
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<FormValues>({
    resolver: zodResolver(Schema),
  });
  return (
    <form onSubmit={handleSubmit(onSubmit)}>
      <label htmlFor="email">Email</label>
      <input id="email" {...register('email')} aria-invalid={!!errors.email} aria-describedby={errors.email ? 'email-error' : undefined} />
      {errors.email && <p id="email-error" role="alert">{errors.email.message}</p>}
      <button type="submit" disabled={isSubmitting}>Place order</button>
    </form>
  );
}
```

## Testing

- **Vitest** for unit + component tests.
- **React Testing Library** for component rendering.
- **Playwright** for E2E.
- **MSW** (Mock Service Worker) for API mocking in tests.
- **@axe-core/playwright** for E2E a11y checks.

```tsx
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { PlaceOrderForm } from './PlaceOrderForm';

describe('PlaceOrderForm', () => {
  it('submits when valid', async () => {
    const onSubmit = vi.fn();
    render(<PlaceOrderForm onSubmit={onSubmit} />);
    await userEvent.type(screen.getByLabelText(/email/i), 'a@b.co');
    await userEvent.type(screen.getByLabelText(/amount/i), '50');
    await userEvent.click(screen.getByRole('button', { name: /place order/i }));
    expect(onSubmit).toHaveBeenCalledWith({ email: 'a@b.co', amount: 50 });
  });
});
```

## Build & tooling

- `next build` for production; `next dev` for development.
- Tailwind or CSS-in-JS (Stitches, vanilla-extract); team-choice.
- ESLint + `eslint-config-next` + `@typescript-eslint`.
- Prettier or Biome.
- Bundle analysis via `@next/bundle-analyzer`.
- Lighthouse CI configured per release.

## Common violations to flag in review

- `'use client'` higher in the tree than necessary (forces unnecessary client bundle).
- Server state in `useState` (use TanStack Query or Server Components).
- `useEffect` for data fetching (use TanStack Query).
- Form validation hand-rolled with `useState` (use React Hook Form).
- Hardcoded user-facing text (no i18n).
- Direct DOM manipulation outside refs.
- `<a>` for in-app navigation (use `<Link>` from `next/link`).
- Image elements without `next/image`.
