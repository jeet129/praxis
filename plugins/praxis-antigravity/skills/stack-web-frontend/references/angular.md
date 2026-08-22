# Stack — Web Frontend — Angular

Framework-specific idioms for Angular 18+ (standalone components, signals, control flow syntax).

## Project layout

```
src/app/
├── app.config.ts            application configuration (providers, routes)
├── app.routes.ts            top-level routes
├── app.component.ts         root component
├── features/                feature folders (bounded contexts)
│   └── orders/
│       ├── components/      standalone components
│       ├── services/        feature services (data, state)
│       ├── routes.ts        feature routes (lazy-loaded)
│       └── types/
├── design-system/           shared components (standalone)
├── core/                    cross-cutting providers (auth, interceptors)
└── shared/                  small utilities
```

Standalone components only (modules deprecated for new code). Lazy-load features via route-level imports.

## Standalone components + signals

```ts
// features/orders/components/orders-list.component.ts
import { Component, computed, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { OrdersService } from '../services/orders.service';

@Component({
  selector: 'app-orders-list',
  standalone: true,
  imports: [CommonModule],
  template: `
    @if (orders.isLoading()) {
      <app-spinner aria-label="Loading orders" />
    } @else if (orders.error()) {
      <app-alert variant="error">{{ orders.error()?.message }}</app-alert>
    } @else {
      <ul>
        @for (order of orders.value(); track order.id) {
          <li>{{ order.id }} — {{ order.amount }}</li>
        } @empty {
          <p>No orders yet.</p>
        }
      </ul>
    }
  `,
})
export class OrdersListComponent {
  private ordersService = inject(OrdersService);
  orders = this.ordersService.ordersResource;   // resource API or signal
}
```

Control flow (`@if` / `@for` / `@switch`) over structural directives.

## State management

- **Server state**: `@tanstack/angular-query` or Angular's new `resource()` API.
- **URL state**: Angular Router + `ActivatedRoute` for params/queryParams.
- **Local state**: signals (`signal()`, `computed()`).
- **Cross-component client state**: services with signals; or NgRx Signal Store for larger global state when justified.
- **Form state**: Reactive Forms (preferred for non-trivial forms).

```ts
// features/orders/services/orders.service.ts
import { Injectable, inject, resource } from '@angular/core';
import { HttpClient } from '@angular/common/http';

@Injectable({ providedIn: 'root' })
export class OrdersService {
  private http = inject(HttpClient);

  ordersResource = resource({
    loader: async () => {
      const data = await firstValueFrom(this.http.get<unknown[]>('/api/orders'));
      return OrdersResponseSchema.parse(data);
    },
  });

  placeOrder(payload: CreateOrder) {
    return this.http.post<Order>('/api/orders', payload);
  }
}
```

## Routing

```ts
// app.routes.ts
import { Routes } from '@angular/router';

export const routes: Routes = [
  {
    path: '',
    loadComponent: () => import('./features/home/home.component').then(m => m.HomeComponent),
  },
  {
    path: 'orders',
    loadChildren: () => import('./features/orders/routes').then(m => m.ORDERS_ROUTES),
    canActivate: [authGuard],
  },
];

// features/orders/routes.ts
export const ORDERS_ROUTES: Routes = [
  { path: '', loadComponent: () => import('./components/orders-list.component').then(m => m.OrdersListComponent) },
  { path: ':id', loadComponent: () => import('./components/order-detail.component').then(m => m.OrderDetailComponent) },
];
```

Functional route guards (`canActivateFn`) over class-based.

## Forms

Reactive Forms with typed forms:

```ts
import { Component, inject } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';

@Component({
  selector: 'app-place-order-form',
  standalone: true,
  imports: [ReactiveFormsModule],
  template: `
    <form [formGroup]="form" (ngSubmit)="submit()">
      <label for="email">Email</label>
      <input id="email" formControlName="email" [attr.aria-invalid]="form.controls.email.invalid && form.controls.email.touched" />
      @if (form.controls.email.invalid && form.controls.email.touched) {
        <p role="alert">Valid email required.</p>
      }
      <button type="submit" [disabled]="form.invalid || form.disabled">Place order</button>
    </form>
  `,
})
export class PlaceOrderFormComponent {
  private fb = inject(FormBuilder);

  form = this.fb.nonNullable.group({
    email: ['', [Validators.required, Validators.email]],
    amount: [0, [Validators.required, Validators.min(0.01)]],
  });

  submit() {
    if (this.form.invalid) return;
    const value = this.form.getRawValue();
    // ...
  }
}
```

## Testing

- **Jest** or **Vitest** (preferred for new projects via `@analogjs/vitest-angular`).
- **Spectator** or `@angular/testing` `TestBed` for components.
- **Playwright** for E2E.
- **@axe-core/playwright** for a11y in E2E.

## Build & tooling

- Angular CLI (`ng build`, `ng test`).
- ESLint with `@angular-eslint`.
- Prettier.
- Bundle analysis via `source-map-explorer` or `webpack-bundle-analyzer`.

## Common violations to flag in review

- `*ngIf` / `*ngFor` instead of `@if` / `@for` in new code.
- NgModules in new code (use standalone components).
- Template-driven forms when reactive forms would be cleaner.
- Subscribing in components without `takeUntilDestroyed` (memory leak).
- Hardcoded text without i18n.
- Direct DOM manipulation outside ElementRef/Renderer2.
- HTTP calls outside services.
- `any` outside boundary code.
