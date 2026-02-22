output "web_app_id" {
  description = "ID of the Web App"
  value       = azurerm_linux_web_app.main.id
}

output "web_app_name" {
  description = "Name of the Web App"
  value       = azurerm_linux_web_app.main.name
}

output "web_app_default_hostname" {
  description = "Default hostname of the Web App"
  value       = azurerm_linux_web_app.main.default_hostname
}

output "web_app_identity_principal_id" {
  description = "Principal ID of the Web App managed identity"
  value       = azurerm_linux_web_app.main.identity[0].principal_id
}

output "web_app_identity_tenant_id" {
  description = "Tenant ID of the Web App managed identity"
  value       = azurerm_linux_web_app.main.identity[0].tenant_id
}

output "staging_slot_identity_principal_id" {
  description = "Principal ID of the staging slot managed identity"
  value       = azurerm_linux_web_app_slot.staging.identity[0].principal_id
}

output "app_service_plan_id" {
  description = "ID of the App Service Plan"
  value       = azurerm_service_plan.main.id
}
