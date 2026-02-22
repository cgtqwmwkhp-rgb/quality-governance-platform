terraform {
  required_version = ">= 1.5.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }
  }

  backend "azurerm" {
    resource_group_name  = "qgp-tfstate-rg"
    storage_account_name = "qgptfstateprod"
    container_name       = "tfstate"
    key                  = "production.terraform.tfstate"
  }
}

provider "azurerm" {
  features {
    key_vault {
      purge_soft_delete_on_destroy = false
    }
  }
}

resource "azurerm_resource_group" "main" {
  name     = "${var.prefix}-${var.environment}-rg"
  location = var.location

  tags = local.tags
}

locals {
  tags = {
    environment = var.environment
    project     = var.project_name
    managed_by  = "terraform"
  }
}

# --- Networking ---

module "networking" {
  source = "../../modules/networking"

  prefix              = "${var.prefix}-${var.environment}"
  vnet_name           = "${var.prefix}-${var.environment}-vnet"
  location            = var.location
  resource_group_name = azurerm_resource_group.main.name
  vnet_address_space  = ["10.0.0.0/16"]
  app_subnet_prefix   = "10.0.1.0/24"
  db_subnet_prefix    = "10.0.2.0/24"
  redis_subnet_prefix = "10.0.3.0/24"
  redis_server_id     = module.redis.redis_id

  tags = local.tags
}

# --- App Service ---

module "app_service" {
  source = "../../modules/app-service"

  app_service_plan_name = "${var.prefix}-${var.environment}-plan"
  web_app_name          = "${var.prefix}-${var.environment}-app"
  location              = var.location
  resource_group_name   = azurerm_resource_group.main.name
  sku_name              = var.app_service_sku
  subnet_id             = module.networking.app_subnet_id

  app_settings = {
    "DATABASE_URL"             = "postgresql://${module.database.server_fqdn}:5432/${module.database.database_name}"
    "REDIS_URL"                = "rediss://${module.redis.redis_hostname}:${module.redis.redis_port}"
    "AZURE_STORAGE_ACCOUNT"    = module.storage.storage_account_name
    "AZURE_KEYVAULT_URI"       = module.keyvault.key_vault_uri
    "ENVIRONMENT"              = var.environment
    "SCM_DO_BUILD_DURING_DEPLOYMENT" = "true"
  }

  tags = local.tags
}

# --- Database ---

module "database" {
  source = "../../modules/database"

  server_name            = "${var.prefix}-${var.environment}-pgdb"
  location               = var.location
  resource_group_name    = azurerm_resource_group.main.name
  sku_name               = var.database_sku
  storage_mb             = var.database_storage_mb
  administrator_login    = var.db_admin_login
  administrator_password = var.db_admin_password
  delegated_subnet_id    = module.networking.db_subnet_id
  private_dns_zone_id    = module.networking.postgres_private_dns_zone_id

  tags = local.tags
}

# --- Redis ---

module "redis" {
  source = "../../modules/redis"

  redis_name          = "${var.prefix}-${var.environment}-redis"
  location            = var.location
  resource_group_name = azurerm_resource_group.main.name
  sku_name            = var.redis_sku
  capacity            = var.redis_capacity
  family              = var.redis_family

  tags = local.tags
}

# --- Storage ---

module "storage" {
  source = "../../modules/storage"

  storage_account_name = "${var.prefix}${var.environment}stor"
  location             = var.location
  resource_group_name  = azurerm_resource_group.main.name

  tags = local.tags
}

# --- Key Vault ---

module "keyvault" {
  source = "../../modules/keyvault"

  key_vault_name      = "${var.prefix}-${var.environment}-kv"
  location            = var.location
  resource_group_name = azurerm_resource_group.main.name

  managed_identity_object_ids = [
    module.app_service.web_app_identity_principal_id,
    module.app_service.staging_slot_identity_principal_id,
  ]

  tags = local.tags
}
