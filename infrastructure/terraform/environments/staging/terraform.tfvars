prefix       = "qgp"
environment  = "staging"
location     = "eastus2"
project_name = "quality-governance-platform"

# App Service - smaller SKU for staging
app_service_sku = "P1v2"

# Database - smaller tier for staging
database_sku        = "GP_Standard_D2s_v3"
database_storage_mb = 131072

# Redis - Standard C1 for staging
redis_sku      = "Standard"
redis_family   = "C"
redis_capacity = 1
