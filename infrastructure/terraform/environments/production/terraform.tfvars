prefix       = "qgp"
environment  = "production"
location     = "eastus2"
project_name = "quality-governance-platform"

# App Service - higher capacity for production
app_service_sku = "P2v2"

# Database - larger tier for production
database_sku        = "GP_Standard_D4s_v3"
database_storage_mb = 262144

# Redis - Premium P1 for production (enables clustering, persistence, VNet)
redis_sku      = "Premium"
redis_family   = "P"
redis_capacity = 1
