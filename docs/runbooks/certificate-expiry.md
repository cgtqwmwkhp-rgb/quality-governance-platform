# Runbook: Certificate Expiry

## Alert
- **Source:** Azure Monitor / Certificate monitoring
- **Severity:** High (warning at 30 days, critical at 7 days)
- **Symptom:** TLS handshake failures, browser security warnings, API client connection errors

## Certificates to Monitor

| Certificate | Domain | Managed By | Auto-Renew |
|-------------|--------|------------|------------|
| App Service TLS | app-qgp-prod.azurewebsites.net | Azure (managed) | Yes |
| Custom Domain | *.qualitygovernance.com | Azure App Service Managed Certificate / Let's Encrypt | Yes |
| Static Web App | frontend domain | Azure SWA (managed) | Yes |
| PostgreSQL SSL | Database connection | Azure (managed) | Yes |

## Diagnosis

1. Check certificate expiry for the production domain:
   ```bash
   echo | openssl s_client -servername app-qgp-prod.azurewebsites.net \
     -connect app-qgp-prod.azurewebsites.net:443 2>/dev/null | \
     openssl x509 -noout -dates
   ```

2. Check custom domain certificate in Azure:
   ```bash
   az webapp config ssl list --resource-group rg-qgp-prod \
     --query "[].{name:name, expires:expirationDate, thumbprint:thumbprint}" -o table
   ```

3. Check App Service custom domain bindings:
   ```bash
   az webapp config hostname list --webapp-name app-qgp-prod \
     --resource-group rg-qgp-prod -o table
   ```

## Resolution

### Azure Managed Certificate (auto-renew failed):
1. Delete and recreate the managed certificate:
   ```bash
   az webapp config ssl delete --resource-group rg-qgp-prod \
     --certificate-thumbprint <thumbprint>
   az webapp config ssl create --resource-group rg-qgp-prod \
     --name app-qgp-prod --hostname <custom-domain>
   ```
2. Rebind the certificate:
   ```bash
   az webapp config ssl bind --resource-group rg-qgp-prod \
     --name app-qgp-prod --certificate-thumbprint <new-thumbprint> \
     --ssl-type SNI
   ```

### Let's Encrypt Certificate:
1. Verify DNS validation records are still correct
2. Force renewal via the certificate provider
3. Upload and bind the new certificate

### Database SSL Certificate:
1. Azure-managed PostgreSQL certificates rotate automatically
2. If client-side pinning is used, update the trusted CA bundle:
   ```bash
   curl -o /app/certs/DigiCertGlobalRootG2.crt.pem \
     https://cacerts.digicert.com/DigiCertGlobalRootG2.crt.pem
   ```

## Verification

1. Confirm new certificate is active:
   ```bash
   echo | openssl s_client -servername app-qgp-prod.azurewebsites.net \
     -connect app-qgp-prod.azurewebsites.net:443 2>/dev/null | \
     openssl x509 -noout -dates -subject
   ```

2. Test API connectivity:
   ```bash
   curl -s https://app-qgp-prod.azurewebsites.net/readyz | jq .
   ```

3. Verify no certificate warnings in browser

## Prevention
- Azure Managed Certificates auto-renew 60 days before expiry
- Set Azure Monitor alert for certificates expiring within 30 days
- Review certificate inventory quarterly
- Ensure DNS CNAME records remain valid (required for managed cert renewal)

## Escalation
- **L1:** On-call engineer checks certificate status and follows renewal steps
- **L2:** If renewal fails due to DNS issues, page infrastructure team
- **L3:** If production is down due to expired cert, page CTO for emergency response
