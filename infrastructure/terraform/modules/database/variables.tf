variable "server_name" {
  description = "Name of the PostgreSQL Flexible Server"
  type        = string
}

variable "location" {
  description = "Azure region"
  type        = string
}

variable "resource_group_name" {
  description = "Name of the resource group"
  type        = string
}

variable "sku_name" {
  description = "SKU name for the PostgreSQL server"
  type        = string
  default     = "GP_Standard_D2s_v3"
}

variable "storage_mb" {
  description = "Storage size in MB"
  type        = number
  default     = 131072
}

variable "administrator_login" {
  description = "Administrator login for the server"
  type        = string
  sensitive   = true
}

variable "administrator_password" {
  description = "Administrator password for the server"
  type        = string
  sensitive   = true
}

variable "database_name" {
  description = "Name of the database to create"
  type        = string
  default     = "qualitygovernance"
}

variable "delegated_subnet_id" {
  description = "Subnet ID for the PostgreSQL server"
  type        = string
  default     = null
}

variable "private_dns_zone_id" {
  description = "Private DNS zone ID for the PostgreSQL server"
  type        = string
  default     = null
}

variable "availability_zone" {
  description = "Availability zone for the server"
  type        = string
  default     = "1"
}

variable "tags" {
  description = "Tags to apply to resources"
  type        = map(string)
  default     = {}
}
