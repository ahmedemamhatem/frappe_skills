# Data fetching patterns (frappe-react-sdk)

## 1. Typed DocType interfaces

```ts
// src/types/Contract.ts
export interface Contract {
  name: string
  creation: string
  modified: string
  owner: string
  docstatus: 0 | 1 | 2
  tenant: string            // Link → Customer
  space: string             // Link → Space
  start_date: string        // "YYYY-MM-DD"
  end_date: string
  status: 'Draft' | 'Active' | 'Expired' | 'Cancelled'
  monthly_rent: number
  allowed_entries?: number
}
```

## 2. One API module per feature

```ts
// src/api/contracts.ts
import {
  useFrappeGetDocList, useFrappeGetDoc, useFrappeGetCall, useFrappePostCall,
  type Filter,
} from 'frappe-react-sdk'
import type { Contract } from '@/types/Contract'

const LIST_FIELDS: (keyof Contract)[] = ['name', 'tenant', 'space', 'status', 'start_date', 'end_date']

export function useContracts(opts: { status?: Contract['status']; page: number; pageSize?: number }) {
  const pageSize = opts.pageSize ?? 20
  const filters: Filter<Contract>[] = opts.status ? [['status', '=', opts.status]] : []
  return useFrappeGetDocList<Contract>('Contract', {
    fields: LIST_FIELDS,
    filters,
    orderBy: { field: 'modified', order: 'desc' },
    limit: pageSize,
    limit_start: opts.page * pageSize,
  })
}

export const useContract = (name?: string) =>
  useFrappeGetDoc<Contract>('Contract', name ?? '', name ? undefined : null) // null key = don't fetch

// Server-computed data → a whitelisted method, not client math
export const useContractSummary = (name: string) =>
  useFrappeGetCall<{ message: { days_used: number; entries_left: number } }>(
    'my_app.api.v1.contracts.get_summary', { name },
  )

export const useRenewContract = () =>
  useFrappePostCall<{ message: { new_contract: string } }>('my_app.api.v1.contracts.renew')
```

Notes:
- `useFrappeGetCall` / `useFrappePostCall` return Frappe's envelope: the payload is in **`.message`**.
- The 3rd arg of `useFrappeGetDoc`/`useFrappeGetCall` is the SWR key; pass `null` to skip fetching (conditional fetch).
- Keep `fields` explicit — the list API returns only `name` otherwise.

## 3. Mutations

```tsx
const { call: renew, loading } = useRenewContract()
const { mutate } = useContract(name)

async function onRenew() {
  try {
    const r = await renew({ name, months: 12 })
    toast.success(`Renewed → ${r.message.new_contract}`)
    mutate()                    // refetch
  } catch (e) {
    toast.error(frappeError(e)) // see §5
  }
}
```

Doc-level CRUD:

```ts
const { createDoc } = useFrappeCreateDoc<Contract>()
const { updateDoc } = useFrappeUpdateDoc<Contract>()
await createDoc('Contract', { tenant, space, start_date, end_date })
await updateDoc('Contract', name, { end_date })
```

Prefer a **whitelisted method** over raw `createDoc` when the action has business meaning (renew, check-in, approve) — it gives one place for validation, permissions and side effects.

## 4. Global SWR config

```tsx
<FrappeProvider swrConfig={{ revalidateOnFocus: false, dedupingInterval: 5000, shouldRetryOnError: false }}>
```

Turn off focus revalidation for heavy dashboards; keep it on for small, frequently changing lists.

## 5. Errors {#errors}

Frappe errors arrive as `{ httpStatus, exc_type, exception, _server_messages, message }`. `_server_messages` is a JSON string of JSON strings.

```ts
// src/lib/frappeError.ts
export function frappeError(err: any): string {
  try {
    if (err?._server_messages) {
      const msgs = JSON.parse(err._server_messages).map((m: string) => JSON.parse(m).message)
      return stripHtml(msgs.join('\n'))
    }
  } catch { /* fall through */ }
  if (err?.exception) return String(err.exception).split(':').slice(1).join(':').trim() || err.exception
  return err?.message ?? 'Something went wrong'
}
const stripHtml = (s: string) => s.replace(/<[^>]*>/g, '')
```

Status codes worth handling: **403** (`PermissionError` / CSRF — reload session), **417** (`ValidationError` from `frappe.throw` — show message), **409** (`DuplicateEntryError`), **401** (`AuthenticationError` — redirect to `/login?redirect-to=/portal`).

## 6. Pagination & infinite lists

Simple paging: `limit` + `limit_start` + `useFrappeGetDocCount` for total.

Infinite scroll: use `useSWRInfinite` (re-exported by frappe-react-sdk) with the sdk's `getRequestURL`/`getDocListQueryString` helpers, or call a whitelisted method that returns `{ items, next_cursor }` (keyset pagination on `modified,name` — faster than offset on big tables; see `frappe-performance`).

## 7. Search / Link fields

```ts
const [q, setQ] = useState('')
const { data } = useSearch('Customer', q, [['disabled', '=', 0]], 10, 300)
// data?.message → [{ value, label, description }]
```

## 8. TanStack Query alternative

If the team prefers TanStack Query, keep the same `src/api` layer and use the sdk's non-hook client:

```ts
import { FrappeApp } from 'frappe-js-sdk'
const app = new FrappeApp(window.location.origin)
export const db = app.db()
export const call = app.call()

export const useContracts = (page: number) =>
  useQuery({
    queryKey: ['Contract', 'list', page],
    queryFn: () => db.getDocList<Contract>('Contract', { fields: LIST_FIELDS, limit: 20, limit_start: page * 20 }),
    placeholderData: keepPreviousData,
  })
```

Don't mix both libraries in one app.
