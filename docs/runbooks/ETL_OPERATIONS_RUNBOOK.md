# ETL Operations Runbook

**Module**: Stage 10 ETL Pipeline  
**Version**: 1.0  
**Last Updated**: 2026-01-30

---

## Overview

This runbook covers operational procedures for the ETL pipeline, including pre-flight checks, validation, and import operations.

---

## 1. Pre-Flight: Contract Probe

**When**: Before any ETL operation  
**Why**: Verify API contracts are available and correct

```bash
# Set environment
export ETL_ENVIRONMENT=staging
export QGP_API_TOKEN=your-token-here

# Run contract probe
python scripts/etl/contract_probe.py staging
```

**Expected Output**:
```json
{
  "all_passed": true,
  "summary": {
    "total": 4,
    "passed": 4,
    "failed": 0
  }
}
```

**If Failed**:
1. Check API availability: `curl -s $BASE_URL/health`
2. Check auth token validity
3. Contact platform team if endpoints changed

---

## 2. Validate Source Data

**When**: Before any import  
**Why**: Identify data quality issues before API calls

```bash
python scripts/etl/pipeline.py \
  --environment staging \
  --validate-only \
  --source /path/to/source.csv \
  --entity-type incident
```

**Review Output**:
```bash
# Check validation report
cat data/etl_output/validation_incident_*.json | jq '.summary'
```

**If Validation Fails**:
1. Review `.invalid_records` in report
2. Fix source data or document exceptions
3. Re-run validation

---

## 3. Dry-Run (Transform Only)

**When**: After validation passes  
**Why**: Verify transformations before API calls

```bash
python scripts/etl/pipeline.py \
  --environment staging \
  --dry-run \
  --source /path/to/source.csv \
  --entity-type incident
```

**Review Output**:
```bash
# Check transformation stats
cat data/etl_output/stats_incident_*.json | jq '.'

# Check audit trail
cat data/etl_output/audit_*.json | jq 'length'
```

---

## 4. Full Import (STAGING ONLY)

**When**: After validation and dry-run pass  
**Why**: Import records to staging API

⚠️ **SAFETY WARNING**: Import is only allowed for staging environment. Production imports are blocked at CLI level.

### Prerequisites

1. API token stored in Key Vault:
   ```bash
   az keyvault secret show --vault-name kv-qgp-staging --name ETL-SERVICE-TOKEN --query value -o tsv
   ```

2. Export token to environment:
   ```bash
   export QGP_API_TOKEN=$(az keyvault secret show --vault-name kv-qgp-staging --name ETL-SERVICE-TOKEN --query value -o tsv)
   ```

### Run Import

```bash
python scripts/etl/pipeline.py \
  --environment staging \
  --import \
  --source data/etl_source/golden_sample_incidents.csv \
  --entity-type incident \
  --batch-size 50
```

### Idempotency

The pipeline uses `reference_number` for idempotency:
- **201 Created**: Record imported successfully
- **409 Conflict**: Record already exists (skip)
- **Other errors**: Logged and counted as failed

### Review Import Results

```bash
# Check import summary
cat data/etl_output/import_summary_*.json | jq '.stats'

# Check individual records
cat data/etl_output/import_summary_*.json | jq '.import_records | length'

# Verify idempotency (second run should show 0 created)
cat data/etl_output/import_summary_*.json | jq '.api_summary'
```

---

## 5. Golden Sample Test

**When**: First deployment to new environment  
**Why**: Verify end-to-end pipeline with known good data

```bash
# Use provided golden sample
python scripts/etl/pipeline.py \
  --environment staging \
  --validate-only \
  --source data/etl_source/golden_sample_incidents.csv \
  --entity-type incident
```

**Expected**:
- 5 records processed
- 0 validation errors
- Deterministic output (same hash each run)

### Idempotency Proof

Run the golden sample import twice to prove idempotency:

```bash
# First run - creates records
python scripts/etl/pipeline.py --environment staging --import \
  --source data/etl_source/golden_sample_incidents.csv --entity-type incident

# Second run - should skip all (409 Conflict)
python scripts/etl/pipeline.py --environment staging --import \
  --source data/etl_source/golden_sample_incidents.csv --entity-type incident

# Verify second run has 0 created
cat data/etl_output/import_summary_*.json | jq 'select(.stats.imported_records == 0)'
```

---

## 6. Troubleshooting

### Contract Probe Fails

| Error | Cause | Fix |
|-------|-------|-----|
| Connection error | API down | Check API health |
| 401/403 | Invalid token | Refresh QGP_API_TOKEN |
| Missing keys | Contract changed | Update field mappings |

### Validation Fails

| Error | Cause | Fix |
|-------|-------|-----|
| Required field missing | Bad source data | Fix CSV or add default |
| Invalid date format | Wrong format | Use YYYY-MM-DD |
| Title too long | Exceeds 300 chars | Will truncate (warning) |

### Transform Fails

| Error | Cause | Fix |
|-------|-------|-----|
| Unknown enum | Invalid value | Check INCIDENT_TYPE_MAP |
| Parse error | Invalid date | Fix source data |

---

## 6. Audit Trail

Every run produces:
- `audit_{run_id}.json`: All actions with source hashes
- `stats_{entity}_{run_id}.json`: Run statistics
- `validation_{entity}_{run_id}.json`: Validation report

**Retention**: Keep for 90 days minimum

---

## 7. Emergency Procedures

### Rollback

ETL is idempotent - no rollback needed. Re-run with corrected data.

### API Rate Limit

If seeing 429 errors:
1. Reduce batch size in config
2. Add delays between batches
3. Contact platform team for rate increase

---

**Runbook Owner**: Platform Team  
**Review Cycle**: Quarterly
