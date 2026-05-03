# Health MCP Add-on

Health MCP exposes a remote MCP server for laboratory data. It stores patient lab results in MariaDB and resolves indicator reference ranges using age and sex when such rules exist.

## Features

- remote MCP endpoint over HTTP
- MariaDB-backed persistence
- indicator catalog with reusable reference ranges
- agent-friendly structured lab report import
- per-user patient ownership for family members
- patient indicator history lookup with normal/low/high status

## Prerequisites

1. Install a MariaDB add-on or provide access to an external MariaDB instance.
2. Create a database and user for this add-on, for example `health_mcp`.
3. If you expose the add-on outside your trusted network, set an `api_key`.

## Configuration

```yaml
port: 8099
db_host: core-mariadb
db_port: 3306
db_name: health_mcp
db_user: health_mcp
db_password: "change-me"
api_key: "optional-bearer-token"
auto_migrate: true
log_level: info
```

## MCP Endpoint

After the add-on starts, the MCP endpoint is available at:

`http://homeassistant.local:8099/mcp`

If `api_key` is configured, clients must send:

`Authorization: Bearer <api_key>`

If MariaDB is unavailable or schema migration fails, the add-on now stays up and returns `503` from `/health` together with the startup error instead of crashing the whole HTTP listener.

## Suggested Workflow

1. Call `list_service_users` first if you need to discover which `owner_user_id` values already exist in the service.
2. Call `list_user_patients(owner_user_id=...)` to browse members linked to one owner.
3. Call `upsert_indicator_catalog_entry` to register an indicator and its reference ranges.
4. Call `import_lab_report` with `owner_user_id` to import patient results for one Home Assistant user.
5. Call `get_patient_indicator_history`, `get_patient_indicators_history`, or `get_indicator_catalog_entry` to read data back.

The same owner list is also exposed as the MCP resource `service://users`.

## Batch History Example

Use `get_patient_indicators_history` when the client needs multiple indicator timelines in one request:

```json
{
  "owner_user_id": "local-family",
  "patient_external_id": "viktor-moroz-1993-12-29",
  "indicator_codes": ["alt", "ast", "bilirubin_total"],
  "limit": 10
}
```

The response returns one `indicators` array plus `missing_indicator_codes`, so a single unknown code does not fail the whole batch request.

## Example Import Shape

```json
{
  "report": {
    "owner_user_id": "e4f6c9f9d5b14a16b8c0c32d22d6f001",
    "owner_display_name": "Roman",
    "patient_external_id": "son-1",
    "patient_name": "Maksym",
    "patient_sex": "male",
    "collected_at": "2026-05-02T08:30:00Z",
    "source_system": "manual",
    "results": [
      {
        "indicator_code": "loinc:13457-7",
        "indicator_name": "Холестерин ЛПНЩ",
        "standard_system": "loinc",
        "standard_code": "13457-7",
        "source_name": "Ліпопротеїди низької щільності (ЛПНЩ, LDL)",
        "value": 3.72,
        "raw_value": "3.72",
        "unit": "ммоль/л",
        "captured_upper_bound": 3.0,
        "reference_text": "<3.0 - для груп низького ризику"
      },
      {
        "indicator_code": "loinc:43583-4",
        "indicator_name": "Ліпопротеїн (a)",
        "standard_system": "loinc",
        "standard_code": "43583-4",
        "source_name": "Ліпопротеїн (a), Lp(a), нефелометрія, кількісний",
        "value": 2.0,
        "raw_value": "<2*",
        "value_operator": "<",
        "unit": "мг/дл",
        "captured_lower_bound": 5.6,
        "captured_upper_bound": 33.8,
        "reference_text": "5,6 - 33,8",
        "flag": "lab_flagged"
      }
    ]
  }
}
```

## Notes

- `import_lab_report` is the recommended ingestion path when an agent or client has already parsed a PDF, OCR, or another upstream source into structured values.
- `list_service_users` is the discovery entrypoint when the caller does not yet know which `owner_user_id` values are present in the database.
- `get_patient_indicators_history` is the batch history entrypoint when the caller needs several indicator timelines for one patient in a single MCP call.
- For cross-lab normalization, prefer an international semantic identity such as `standard_system: "loinc"` plus `standard_code`, and keep `indicator_code` aligned with that identity, for example `loinc:2093-3`.
- If an indicator has no catalog range yet, the service falls back to `captured_lower_bound` and `captured_upper_bound` from the imported result so status can still be classified immediately.
- `raw_value`, `value_operator`, `source_name`, and `reference_text` let the client preserve the source lab wording without sacrificing normalized numeric history.
- `auto_migrate: true` creates missing tables and also applies built-in additive column upgrades used by newer import payloads.
- A manual SQL bootstrap file is bundled at `/usr/src/app/sql/init.sql`.
- The service does not perform unit conversion; if report units differ from the catalog unit, the result is stored and returned with a warning.
- Patient IDs are unique only within `owner_user_id`, so different family members can safely use the same local patient identifier.
- The current version provides ownership scoping at the data model and API level. If you want hard authorization boundaries, the next step is to bind `owner_user_id` to Home Assistant auth identity or per-user API credentials.
