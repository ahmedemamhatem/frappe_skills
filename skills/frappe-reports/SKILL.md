---
name: frappe-reports
description: Build reports and analytics in Frappe/ERPNext — choosing between Report Builder, Query Report, Script Report, Number Cards, Dashboard Charts and Insights; writing Script Reports (columns, data, filters JS, message, chart, report_summary), prepared reports for heavy data, permission-safe queries, formatting and drill-down links. Use when asked for a report, dashboard, KPI, chart or export, or when an existing report is slow or wrong.
---

# Reports & dashboards

> **TL;DR:** Pick the lightest tool that works: Report Builder → Query Report → Script Report. Do the maths in **one aggregated query**, not Python loops over documents. Apply permissions. Heavy reports → Prepared Report.

## Choose

| Need | Tool |
|---|---|
| Columns from one DocType (+ child), filters, group-by count/sum | **Report Builder** (save as report) — no code |
| A SQL query with filters, few joins, admins maintain it | **Query Report** (SQL in the Report doc) |
| Logic, multiple queries, computed columns, charts, summary cards | **Script Report** (in your app) |
| A single KPI on a workspace | **Number Card** |
| Trend / breakdown chart | **Dashboard Chart** (Count/Sum/Group By/Report source) |
| Exploratory BI, ad-hoc analysis | **Insights** app |

## Script Report — files

`bench --site x` → New Report, Report Type *Script Report*, Is Standard *Yes*, Module (developer mode) → creates:

```
my_app/spaces/report/occupancy/
├── occupancy.json
├── occupancy.py
└── occupancy.js
```

### occupancy.py

```python
import frappe
from frappe import _
from frappe.query_builder.functions import Count, Sum


def execute(filters=None):
    filters = frappe._dict(filters or {})
    columns = get_columns()
    data = get_data(filters)
    chart = get_chart(data)
    summary = get_summary(data)
    return columns, data, None, chart, summary     # columns, data, message, chart, report_summary


def get_columns():
    return [
        {"fieldname": "space", "label": _("Space"), "fieldtype": "Link", "options": "Space", "width": 160},
        {"fieldname": "location", "label": _("Location"), "fieldtype": "Link", "options": "Location", "width": 140},
        {"fieldname": "contracts", "label": _("Contracts"), "fieldtype": "Int", "width": 100},
        {"fieldname": "revenue", "label": _("Revenue"), "fieldtype": "Currency", "width": 130},
    ]


def get_data(filters):
    Contract = frappe.qb.DocType("Contract")
    q = (frappe.qb.from_(Contract)
         .select(Contract.space, Contract.location, Count(Contract.name).as_("contracts"),
                 Sum(Contract.monthly_rent).as_("revenue"))
         .where(Contract.docstatus == 1)
         .groupby(Contract.space, Contract.location))
    if filters.location:
        q = q.where(Contract.location == filters.location)
    if filters.from_date:
        q = q.where(Contract.end_date >= filters.from_date)
    if filters.to_date:
        q = q.where(Contract.start_date <= filters.to_date)
    return q.run(as_dict=True)


def get_chart(data):
    top = sorted(data, key=lambda r: r.revenue or 0, reverse=True)[:10]
    return {"data": {"labels": [r.space for r in top],
                     "datasets": [{"name": _("Revenue"), "values": [r.revenue or 0 for r in top]}]},
            "type": "bar"}


def get_summary(data):
    return [
        {"label": _("Spaces"), "value": len(data), "indicator": "Blue"},
        {"label": _("Revenue"), "value": sum(r.revenue or 0 for r in data),
         "datatype": "Currency", "indicator": "Green"},
    ]
```

### occupancy.js

```js
frappe.query_reports["Occupancy"] = {
    filters: [
        { fieldname: "location", label: __("Location"), fieldtype: "Link", options: "Location" },
        { fieldname: "from_date", label: __("From"), fieldtype: "Date", default: frappe.datetime.month_start() },
        { fieldname: "to_date", label: __("To"), fieldtype: "Date", default: frappe.datetime.month_end() },
    ],
    formatter(value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);
        if (column.fieldname === "contracts" && data && data.contracts === 0)
            value = `<span style="color: var(--red-500)">${value}</span>`;
        return value;
    },
};
```

## Permissions in reports

- Report access = **Roles** table on the Report doc + "Ref DocType" read permission.
- A Script Report's query is yours: `frappe.qb`/SQL **does not** apply user permissions. If rows must be restricted (tenant, location), either use `frappe.get_list` for the base set or add the same condition your `permission_query_conditions` uses. User Permissions on Link filters can be applied with `frappe.get_list` or by filtering explicitly.

## Heavy reports

- Tick **Prepared Report** on the Report: it runs in a background job and caches the result; users see the last result and can re-run.
- Index filter columns (see `frappe-performance`); limit default date range.

## Number Cards & Dashboard Charts

Create in Desk (Type: Document Type with aggregate, or Report, or Custom method). For custom: a whitelisted method returning `{"value": n, "fieldtype": "Currency"}` (card) or chart data. Ship them as fixtures or as standard (module-scoped JSON in developer mode) so they're versioned.

## Anti-patterns

| ❌ | ✅ |
|---|---|
| `for d in get_all(...): get_doc(d)` to compute totals | one grouped query |
| Script Report where Report Builder would do | Report Builder |
| Unrestricted SQL showing other tenants' data | apply the same permission condition |
| Default filter = all time on huge tables | default to this month, index dates |
| Currency as Float column | `fieldtype: "Currency"` (+ `options` for currency field) |
