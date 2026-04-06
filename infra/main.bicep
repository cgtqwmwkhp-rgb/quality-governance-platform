@description('Azure region for all resources')
param location string = resourceGroup().location

@description('Environment name (dev, staging, production)')
@allowed(['dev', 'staging', 'production'])
param environment string = 'staging'

@description('App Service Plan SKU')
param appServiceSkuName string = environment == 'production' ? 'B2' : 'B1'

@description('PostgreSQL SKU')
param postgresSkuName string = 'Standard_B1ms'

@description('PostgreSQL admin password')
@secure()
param postgresAdminPassword string

var prefix = 'qgp-${environment}'

resource appServicePlan 'Microsoft.Web/serverfarms@2023-01-01' = {
  name: '${prefix}-plan'
  location: location
  kind: 'linux'
  properties: {
    reserved: true
  }
  sku: {
    name: appServiceSkuName
  }
}

resource webApp 'Microsoft.Web/sites@2023-01-01' = {
  name: '${prefix}-api'
  location: location
  properties: {
    serverFarmId: appServicePlan.id
    siteConfig: {
      linuxFxVersion: 'DOCKER'
      alwaysOn: true
      healthCheckPath: '/healthz'
      httpLoggingEnabled: true
    }
    httpsOnly: true
  }
}

resource postgres 'Microsoft.DBforPostgreSQL/flexibleServers@2023-03-01-preview' = {
  name: '${prefix}-db'
  location: location
  sku: {
    name: postgresSkuName
    tier: 'Burstable'
  }
  properties: {
    version: '16'
    administratorLogin: 'qgpadmin'
    administratorLoginPassword: postgresAdminPassword
    storage: {
      storageSizeGB: 32
    }
    backup: {
      backupRetentionDays: 14
      geoRedundantBackup: 'Disabled'
    }
    highAvailability: {
      mode: 'Disabled'
    }
  }
}

resource storageAccount 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: replace('${prefix}store', '-', '')
  location: location
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    supportsHttpsTrafficOnly: true
    minimumTlsVersion: 'TLS1_2'
    allowBlobPublicAccess: false
  }
}

output webAppName string = webApp.name
output webAppUrl string = 'https://${webApp.properties.defaultHostName}'
output postgresHost string = postgres.properties.fullyQualifiedDomainName
output storageAccountName string = storageAccount.name
