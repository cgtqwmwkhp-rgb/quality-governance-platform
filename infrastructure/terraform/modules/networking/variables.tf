variable "prefix" {
  description = "Resource name prefix"
  type        = string
}

variable "vnet_name" {
  description = "Name of the Virtual Network"
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

variable "vnet_address_space" {
  description = "Address space for the VNet"
  type        = list(string)
  default     = ["10.0.0.0/16"]
}

variable "app_subnet_prefix" {
  description = "Address prefix for the app subnet"
  type        = string
  default     = "10.0.1.0/24"
}

variable "db_subnet_prefix" {
  description = "Address prefix for the database subnet"
  type        = string
  default     = "10.0.2.0/24"
}

variable "redis_subnet_prefix" {
  description = "Address prefix for the Redis subnet"
  type        = string
  default     = "10.0.3.0/24"
}

variable "private_endpoint_subnet_prefix" {
  description = "Address prefix for the private endpoint subnet"
  type        = string
  default     = "10.0.4.0/24"
}

variable "redis_server_id" {
  description = "Redis server ID for private endpoint (optional)"
  type        = string
  default     = null
}

variable "tags" {
  description = "Tags to apply to resources"
  type        = map(string)
  default     = {}
}
