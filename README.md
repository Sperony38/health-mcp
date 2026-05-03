# Health MCP

Remote MCP service for importing laboratory analyses, storing them in MariaDB, and returning indicator history together with age/sex-aware reference ranges.

## Repository Layout

- `addon/health_mcp/` - Home Assistant add-on package
- `addon/health_mcp/app/` - Python application source, tests, and SQL bootstrap

## What It Does

- imports lab reports for a patient
- scopes patients to an owning Home Assistant user
- exposes service-level user discovery so clients can enumerate `owner_user_id` values before querying patients
- stores indicator catalog entries and reference ranges
- supports international semantic identities such as LOINC for cross-lab normalization
- resolves the best matching reference range by age and sex
- returns indicator catalog metadata and patient indicator history over MCP

## Local Development

```powershell
cd addon/health_mcp/app
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .[dev]
pytest
python -m health_mcp
```

The MCP endpoint is exposed at `http://localhost:8099/mcp`.

## Home Assistant Add-on

The add-on files live in [addon/health_mcp/DOCS.md](/D:/repos/health-mcp/addon/health_mcp/DOCS.md).
