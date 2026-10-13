# API patterns

## Long-running action (enqueue + poll / realtime)

```python
@frappe.whitelist(methods=["POST"])
def generate_statements(month: str) -> dict:
    frappe.only_for("Accounts Manager")
    job = frappe.enqueue(
        "my_app.billing.statements.generate_all",
        queue="long", timeout=3600,
        month=month, user=frappe.session.user,
        job_id=f"statements::{month}", deduplicate=True,  # one run per month at a time
    )
    return {"job_id": job.id if job else f"statements::{month}"}
```

The job publishes progress with `frappe.publish_realtime("statements_progress", {...}, user=user)`; React listens. Don't hold an HTTP request open for minutes.

## Bulk endpoint

```python
@frappe.whitelist(methods=["POST"])
def bulk_update_status(names: list[str], status: str) -> dict:
    if len(names) > 200:
        frappe.throw(_("Max 200 records per call"))
    ok, failed = [], {}
    for name in names:
        frappe.db.savepoint("bulk_row")
        try:
            doc = frappe.get_doc("Contract", name)
            doc.check_permission("write")
            doc.status = status
            doc.save()
            ok.append(name)
        except Exception as e:
            frappe.db.rollback(save_point="bulk_row")   # undo only this record
            failed[name] = str(e)
    return {"updated": ok, "failed": failed}
```

Savepoints isolate each record's failure without losing the others. For more than a few hundred records, enqueue instead.

## File download / export

```python
@frappe.whitelist(methods=["GET"])
def export_contracts_csv(status: str | None = None):
    frappe.only_for("System Manager")
    from frappe.utils.csvutils import to_csv
    rows = [["Contract", "Tenant", "End"]] + frappe.get_list(
        "Contract", filters={"status": status} if status else {},
        fields=["name", "tenant", "end_date"], as_list=True, limit_page_length=0)
    frappe.response["type"] = "download"
    frappe.response["filename"] = "contracts.csv"
    frappe.response["filecontent"] = to_csv(rows)
```

## API key users for integrations

- Create a dedicated **User** per integration (`zk-bridge@yourco`, `payment-gateway@yourco`), give it a narrow custom Role, generate API key/secret.
- Clients send `Authorization: token <api_key>:<api_secret>`.
- Never use Administrator's keys. Rotate on staff changes.

## Response envelope

Frappe returns `{"message": <your return>}` for `/api/method`. Keep your own payloads consistent:

```json
{ "message": { "items": [], "page": 0, "page_size": 20, "total": 0 } }
```

and for actions:

```json
{ "message": { "ok": true, "<entity>": "<name>" } }
```

## Postman / OpenAPI

Keep a Postman collection (or OpenAPI spec) in the repo `docs/api/` generated from the contract table in each `v1/*.py` docstring. Review API changes in PRs like code.
