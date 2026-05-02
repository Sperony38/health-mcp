# Health MCP Add-on

Health MCP exposes a remote MCP server for laboratory data. It stores patient lab results in MariaDB and resolves indicator reference ranges using age and sex when such rules exist.

## Features

- remote MCP endpoint over HTTP
- MariaDB-backed persistence
- indicator catalog with reusable reference ranges
- lab report import
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

## Suggested Workflow

1. Call `upsert_indicator_catalog_entry` to register an indicator and its reference ranges.
2. Call `import_lab_report` with `owner_user_id` to import patient results for one Home Assistant user.
3. Call `list_user_patients` to browse members linked to that user.
4. Call `get_patient_indicator_history` or `get_indicator_catalog_entry` to read data back.

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
        "indicator_code": "HGB",
        "indicator_name": "Hemoglobin",
        "value": 132,
        "unit": "g/L"
      }
    ]
  }
}
```

## Notes

- `auto_migrate: true` uses the built-in SQLAlchemy schema creation on startup.
- A manual SQL bootstrap file is bundled at `/usr/src/app/sql/init.sql`.
- The service does not perform unit conversion; if report units differ from the catalog unit, the result is stored and returned with a warning.
- Patient IDs are unique only within `owner_user_id`, so different family members can safely use the same local patient identifier.
- The current version provides ownership scoping at the data model and API level. If you want hard authorization boundaries, the next step is to bind `owner_user_id` to Home Assistant auth identity or per-user API credentials.
