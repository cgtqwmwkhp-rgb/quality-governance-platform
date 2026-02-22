variable "prefix" {
  description = "Resource name prefix"
  type        = string
}

variable "environment" {
  description = "Environment name"
  type        = string
}

variable "location" {
  description = "Azure region for all resources"
  type        = string
}

variable "project_name" {
  description = "Project name for tagging"
  type        = string
}

# App Service
variable "app_service_sku" {
  description = "SKU for the App Service Plan"
  type        = string
  default     = "P1v2"
}

# Database
variable "database_sku" {
  description = "SKU for PostgreSQL Flexible Server"
  type        = string
  default     = "GP_Standard_D2s_v3"
}

variable "database_storage_mb" {
  description = "Storage size in MB for PostgreSQL"
  type        = number
  default     = 131072
}

variable "db_admin_login" {
  description = "PostgreSQL administrator login"
  type        = string
  sensitive   = true
}

variable "db_admin_password" {
  description = "PostgreSQL administrator password"
  type        = string
  sensitive   = true
}

# Redis
variable "redis_sku" {
  description = "SKU for Redis Cache"
  type        = string
  default     = "Standard"
}

variable "redis_family" {
  description = "Redis family"
  type        = string
  default     = "C"
}

variable "redis_capacity" {
  description = "Redis capacity"
  type        = number
  default     = 1
}
