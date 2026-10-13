# React tests (Vitest + Testing Library + MSW)

```bash
cd apps/my_app/portal
yarn add -D vitest @testing-library/react @testing-library/user-event @testing-library/jest-dom jsdom msw
```

`vite.config.ts`:

```ts
test: { environment: 'jsdom', setupFiles: ['./src/test/setup.ts'], globals: true }
```

## Mock Frappe with MSW

Mock at the HTTP layer so the real frappe-react-sdk code runs.

```ts
// src/test/handlers.ts
import { http, HttpResponse } from 'msw'

export const handlers = [
  http.get('/api/method/frappe.auth.get_logged_user', () =>
    HttpResponse.json({ message: 'tenant@example.com' })),

  http.get('/api/resource/Contract', () =>
    HttpResponse.json({ data: [{ name: 'CON-0001', tenant: 'ACME', status: 'Active' }] })),

  http.post('/api/method/my_app.api.v1.contracts.renew', async ({ request }) => {
    const body = await request.json() as any
    if (body.months === 0)
      return HttpResponse.json(
        { exc_type: 'ValidationError',
          _server_messages: JSON.stringify([JSON.stringify({ message: 'Months must be 1, 3, 6 or 12' })]) },
        { status: 417 })
    return HttpResponse.json({ message: { new_contract: 'CON-0002' } })
  }),
]
```

```ts
// src/test/setup.ts
import '@testing-library/jest-dom/vitest'
import { setupServer } from 'msw/node'
import { handlers } from './handlers'
export const server = setupServer(...handlers)
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => server.resetHandlers())
afterAll(() => server.close())
```

## Render helper

```tsx
// src/test/render.tsx
export function renderWithFrappe(ui: React.ReactElement) {
  return render(
    <FrappeProvider swrConfig={{ provider: () => new Map(), dedupingInterval: 0 }}>
      <MemoryRouter>{ui}</MemoryRouter>
    </FrappeProvider>)
}
```

`provider: () => new Map()` gives every test a fresh SWR cache.

## What to test

- Lists render data from the API and show empty / error states.
- Forms show server validation messages (417) to the user.
- Buttons hidden for roles that can't use them (UX) — server permission is tested in Python.
- Mutations call the right method with the right body and refresh the list.

Keep E2E (Playwright/Cypress against a real test site) for a handful of critical flows: login → create contract → renew.
