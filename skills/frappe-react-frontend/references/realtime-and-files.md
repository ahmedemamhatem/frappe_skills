# Realtime & files

## Server → React realtime

Server side (anywhere: controller, background job, integration):

```python
frappe.publish_realtime(
    "contract_updated",
    {"name": doc.name, "status": doc.status},
    user=doc.owner,            # target one user…
    # doctype=doc.doctype, docname=doc.name  # …or everyone viewing this doc
    after_commit=True,         # don't emit if the transaction rolls back
)
```

React side:

```ts
const { mutate } = useContracts({ page })
useFrappeEventListener('contract_updated', () => mutate())
```

Built-in events (no server code needed):
- `useFrappeDocTypeEventListener('Contract', cb)` — fires on `list_update` when any Contract changes (user must have read access).
- `useFrappeDocumentEventListener('Contract', name, cb)` — fires on `doc_update`; also returns `viewers` (who else has the doc open).

Rules:
- Always `after_commit=True` when publishing from inside a transaction.
- Send **IDs + minimal data**, then refetch — don't push full documents over the socket (bypasses permission filtering of fields).
- Long jobs: publish progress events (`{"progress": 40}`) from the background job and show a progress bar; final event triggers `mutate()`.

### Socket checklist (when events don't arrive)
1. `bench start` / supervisor shows `socketio` running; Redis (`redis_socketio`/`redis_queue`) up first.
2. In dev, `socketPort` passed to `FrappeProvider` matches `socketio_port` in `common_site_config.json` (default 9000).
3. In production nginx proxies `/socket.io` with `Upgrade`/`Connection` headers (bench-generated config does).
4. `siteName` matches the site — socket rooms are per site.

## File uploads

```tsx
const { upload, progress, loading } = useFrappeFileUpload()

const file = await upload(selectedFile, {
  doctype: 'Contract', docname: name, fieldname: 'signed_copy',
  isPrivate: true,             // private: served only to users with access to the parent doc
})
// file.file_url → "/private/files/xyz.pdf"
```

Rules:
- Contracts, IDs, invoices → **always `isPrivate: true`**.
- Validate type/size on the server too (`frappe-security` → uploads).
- Show `progress` for large files; Frappe's default max upload is set by `max_file_size` in site config.
- Display private files via their `/private/files/...` URL — the session cookie authorises it; don't proxy file bytes through a custom API.
