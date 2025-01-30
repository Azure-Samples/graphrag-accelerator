// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

/*
This bicep script can be used as a starting point and customized to fit the specific needs of an Azure environment.

The script should be executed as a group deployment using Azure CLI (az deployment group ...)

The script will deploy the following resources in a specified resource group:
AI Search
CosmosDB
Blob Storage
AKS
API Management
Log Analytics
Private Endpoints
Managed Identity
*/

@minLength(1)
@maxLength(64)
@description('Name of the resource group that GraphRAG will be deployed in.')
param resourceGroup string

@description('Unique name to append to each resource')
param resourceBaseName string = ''
var resourceBaseNameFinal = !empty(resourceBaseName)
  ? resourceBaseName
  : toLower(uniqueString('${subscription().id}/resourceGroups/${resourceGroup}'))

@description('Cloud region for all resources')
param location string = az.resourceGroup().location

@description('Principal/Object ID of the deployer. Will be used to assign admin roles to the AKS cluster.')
param deployerPrincipalId string

@minLength(1)
@description('Name of the publisher of the API Management instance.')
param apiPublisherName string = 'Microsoft'

@minLength(1)
@description('Email address of the publisher of the API Management instance.')
param apiPublisherEmail string = 'publisher@microsoft.com'

@description('The AKS namespace to install GraphRAG in.')
param aksNamespace string = 'graphrag'

@description('Whether to enable private endpoints.')
param enablePrivateEndpoints bool = true

@description('Whether to restore the API Management instance.')
param restoreAPIM bool = false

// optional parameters that will default to a generated name if not provided
param apimTier string = 'Developer'
param apimName string = ''
param acrName string = ''
param storageAccountName string = ''
param cosmosDbName string = ''
param aiSearchName string = ''

var abbrs = loadJsonContent('abbreviations.json')
var tags = { 'azd-env-name': resourceGroup }
var workloadIdentityName = '${abbrs.managedIdentityUserAssignedIdentities}${resourceBaseNameFinal}'
var aksServiceAccountName = '${aksNamespace}-workload-sa'
var workloadIdentitySubject = 'system:serviceaccount:${aksNamespace}:${aksServiceAccountName}'

// endpoint configuration
var dnsDomain = 'graphrag.io'
var appHostname = 'graphrag.${dnsDomain}'
var appUrl = 'http://${appHostname}'

@description('Role definitions for various RBAC roles that will be assigned at deployment time. Learn more: https://learn.microsoft.com/en-us/azure/role-based-access-control/built-in-roles')
var roles = {
  privateDnsZoneContributor: resourceId(
    'Microsoft.Authorization/roleDefinitions',
    'b12aa53e-6015-4669-85d0-8515ebb3ae7f' // Private DNS Zone Contributor Role
  )
  networkContributor: resourceId(
    'Microsoft.Authorization/roleDefinitions',
    '4d97b98b-1d4f-4787-a291-c67834d212e7' // Network Contributor Role
  )
  acrPull: resourceId(
    'Microsoft.Authorization/roleDefinitions',
    '7f951dda-4ed3-4680-a7ca-43fe172d538d' // ACR Pull Role
  )
}

// apply RBAC role assignments to the AKS workload identity
module aksWorkloadIdentityRBAC 'core/rbac/workload-identity-rbac.bicep' = {
  name: 'aks-workload-identity-rbac-assignments'
  params: {
    principalId: workloadIdentity.outputs.principalId
    principalType: 'ServicePrincipal'
    cosmosDbName: cosmosdb.outputs.name
  }
}

// apply necessary RBAC role assignments to the AKS service
module aksRBAC 'core/rbac/aks-rbac.bicep' = {
  name: 'aks-rbac-assignments'
  params: {
    roleAssignments: [
      {
        principalId: aks.outputs.kubeletPrincipalId
        principalType: 'ServicePrincipal'
        roleDefinitionId: roles.acrPull
      }
      {
        principalId: aks.outputs.ingressWebAppIdentity
        principalType: 'ServicePrincipal'
        roleDefinitionId: roles.privateDnsZoneContributor
      }
      {
        principalId: aks.outputs.systemIdentity
        principalType: 'ServicePrincipal'
        roleDefinitionId: roles.networkContributor
      }
    ]
  }
}

module log 'core/log-analytics/log.bicep' = {
  name: 'log-analytics-deployment'
  params: {
    name: '${abbrs.operationalInsightsWorkspaces}${resourceBaseNameFinal}'
    location: location
    publicNetworkAccessForIngestion: enablePrivateEndpoints ? 'Disabled' : 'Enabled'
  }
}

module nsg 'core/vnet/nsg.bicep' = {
  name: 'nsg-deployment'
  params: {
    nsgName: '${abbrs.networkNetworkSecurityGroups}${resourceBaseNameFinal}'
    location: location
  }
}

module vnet 'core/vnet/vnet.bicep' = {
  name: 'vnet-deployment'
  params: {
    vnetName: '${abbrs.networkVirtualNetworks}${resourceBaseNameFinal}'
    location: location
    subnetPrefix: abbrs.networkVirtualNetworksSubnets
    apimTier: apimTier
    nsgID: nsg.outputs.id
  }
}

module acr 'core/acr/acr.bicep' = {
  name: 'acr-deployment'
  params: {
    registryName: !empty(acrName) ? acrName : '${abbrs.containerRegistryRegistries}${resourceBaseNameFinal}'
    location: location
  }
}

module aks 'core/aks/aks.bicep' = {
  name: 'aks-deployment'
  params: {
    clusterName: '${abbrs.containerServiceManagedClusters}${resourceBaseNameFinal}'
    location: location
    graphragVMSize: 'standard_d8s_v5' // 8 vcpu, 32 GB memory
    graphragIndexingVMSize: 'standard_e8s_v5' // 8 vcpus, 64 GB memory
    clusterAdmins: !empty(deployerPrincipalId) ? ['${deployerPrincipalId}'] : null
    logAnalyticsWorkspaceId: log.outputs.id
    subnetId: vnet.outputs.aksSubnetId
    privateDnsZoneName: privateDnsZone.outputs.name
  }
}

module cosmosdb 'core/cosmosdb/cosmosdb.bicep' = {
  name: 'cosmosdb-deployment'
  params: {
    cosmosDbName: !empty(cosmosDbName) ? cosmosDbName : '${abbrs.documentDBDatabaseAccounts}${resourceBaseNameFinal}'
    location: location
    publicNetworkAccess: enablePrivateEndpoints ? 'Disabled' : 'Enabled'
  }
}

module aiSearch 'core/ai-search/ai-search.bicep' = {
  name: 'aisearch-deployment'
  params: {
    name: !empty(aiSearchName) ? aiSearchName : '${abbrs.searchSearchServices}${resourceBaseNameFinal}'
    location: location
    publicNetworkAccess: enablePrivateEndpoints ? 'disabled' : 'enabled'
  }
}

module storage 'core/storage/storage.bicep' = {
  name: 'storage-deployment'
  params: {
    name: !empty(storageAccountName)
      ? storageAccountName
      : '${abbrs.storageStorageAccounts}${replace(resourceBaseNameFinal, '-', '')}'
    location: location
    publicNetworkAccess: enablePrivateEndpoints ? 'Disabled' : 'Enabled'
    tags: tags
    deleteRetentionPolicy: {
      enabled: true
      days: 5
    }
    defaultToOAuthAuthentication: true
  }
}

module appInsights 'core/monitor/app-insights.bicep' = {
  name: 'app-insights-deployment'
  params: {
    appInsightsName: '${abbrs.insightsComponents}${resourceBaseNameFinal}'
    location: location
    appInsightsPublicNetworkAccessForIngestion: enablePrivateEndpoints ? 'Disabled' : 'Enabled'
    logAnalyticsWorkspaceId: log.outputs.id
  }
}

module apim 'core/apim/apim.bicep' = {
  name: 'apim-deployment'
  params: {
    apiManagementName: !empty(apimName) ? apimName : '${abbrs.apiManagementService}${resourceBaseNameFinal}'
    restoreAPIM: restoreAPIM
    appInsightsId: appInsights.outputs.id
    appInsightsInstrumentationKey: appInsights.outputs.instrumentationKey
    publicIpName: '${abbrs.networkPublicIPAddresses}${resourceBaseNameFinal}'
    location: location
    sku: apimTier
    skuCount: 1 // TODO expose in param for premium sku
    availabilityZones: [] // TODO expose in param for premium sku
    publisherEmail: apiPublisherEmail
    publisherName: apiPublisherName
    subnetId: vnet.outputs.apimSubnetId
  }
}

module graphragApi 'core/apim/apim.graphrag-documentation.bicep' = {
  name: 'graphrag-api-deployment'
  params: {
    apimname: apim.outputs.name
    backendUrl: appUrl
  }
}

module workloadIdentity 'core/identity/identity.bicep' = {
  name: 'workload-identity-deployment'
  params: {
    name: workloadIdentityName
    location: location
    federatedCredentials: {
      'aks-workload-identity': {
        issuer: aks.outputs.issuer
        audiences: ['api://AzureADTokenExchange']
        subject: workloadIdentitySubject
      }
    }
  }
}

module privateDnsZone 'core/vnet/private-dns-zone.bicep' = {
  name: 'private-dns-zone-deployment'
  params: {
    name: dnsDomain
    vnetNames: [
      vnet.outputs.vnetName // name
    ]
  }
}

module privatelinkPrivateDns 'core/vnet/privatelink-private-dns-zones.bicep' = if (enablePrivateEndpoints) {
  name: 'privatelink-private-dns-zones-deployment'
  params: {
    linkedVnetIds: [
      vnet.outputs.vnetId // id
    ]
  }
}

module azureMonitorPrivateLinkScope 'core/monitor/private-link-scope.bicep' = if (enablePrivateEndpoints) {
  name: 'azure-monitor-privatelink-scope-deployment'
  params: {
    privateLinkScopeName: 'pls-${resourceBaseNameFinal}'
    privateLinkScopedResources: [
      log.outputs.id
      appInsights.outputs.id
    ]
  }
}

module cosmosDbPrivateEndpoint 'core/vnet/private-endpoint.bicep' = if (enablePrivateEndpoints) {
  name: 'cosmosDb-private-endpoint-deployment'
  params: {
    privateEndpointName: '${abbrs.privateEndpoint}cosmos-${cosmosdb.outputs.name}'
    location: location
    privateLinkServiceId: cosmosdb.outputs.id
    subnetId: vnet.outputs.aksSubnetId
    groupId: 'Sql'
    privateDnsZoneConfigs: enablePrivateEndpoints ? privatelinkPrivateDns.outputs.cosmosDbPrivateDnsZoneConfigs : []
  }
}

module blobStoragePrivateEndpoint 'core/vnet/private-endpoint.bicep' = if (enablePrivateEndpoints) {
  name: 'blob-storage-private-endpoint-deployment'
  params: {
    privateEndpointName: '${abbrs.privateEndpoint}blob-${storage.outputs.name}'
    location: location
    privateLinkServiceId: storage.outputs.id
    subnetId: vnet.outputs.aksSubnetId
    groupId: 'blob'
    privateDnsZoneConfigs: enablePrivateEndpoints ? privatelinkPrivateDns.outputs.blobStoragePrivateDnsZoneConfigs : []
  }
}

module aiSearchPrivateEndpoint 'core/vnet/private-endpoint.bicep' = if (enablePrivateEndpoints) {
  name: 'ai-search-private-endpoint-deployment'
  params: {
    privateEndpointName: '${abbrs.privateEndpoint}search-${aiSearch.outputs.name}'
    location: location
    privateLinkServiceId: aiSearch.outputs.id
    subnetId: vnet.outputs.aksSubnetId
    groupId: 'searchService'
    privateDnsZoneConfigs: enablePrivateEndpoints ? privatelinkPrivateDns.outputs.aiSearchPrivateDnsZoneConfigs : []
  }
}

module privateLinkScopePrivateEndpoint 'core/vnet/private-endpoint.bicep' = if (enablePrivateEndpoints) {
  name: 'privatelink-scope-private-endpoint-deployment'
  params: {
    privateEndpointName: '${abbrs.privateEndpoint}pls-${resourceBaseNameFinal}'
    location: location
    privateLinkServiceId: enablePrivateEndpoints ? azureMonitorPrivateLinkScope.outputs.id : ''
    subnetId: vnet.outputs.aksSubnetId
    groupId: 'azuremonitor'
    privateDnsZoneConfigs: enablePrivateEndpoints ? privatelinkPrivateDns.outputs.azureMonitorPrivateDnsZoneConfigs : []
  }
}

output azure_location string = location
output azure_tenant_id string = tenant().tenantId
output azure_ai_search_name string = aiSearch.outputs.name
output azure_acr_login_server string = acr.outputs.loginServer
output azure_acr_name string = acr.outputs.name
output azure_aks_name string = aks.outputs.name
output azure_aks_controlplanefqdn string = aks.outputs.controlPlaneFqdn
output azure_aks_managed_rg string = aks.outputs.managedResourceGroup
output azure_aks_service_account_name string = aksServiceAccountName
output azure_storage_account string = storage.outputs.name
output azure_storage_account_blob_url string = storage.outputs.primaryEndpoints.blob
output azure_cosmosdb_endpoint string = cosmosdb.outputs.endpoint
output azure_cosmosdb_name string = cosmosdb.outputs.name
output azure_cosmosdb_id string = cosmosdb.outputs.id
output azure_app_insights_connection_string string = appInsights.outputs.connectionString
output azure_apim_name string = apim.outputs.name
output azure_apim_gateway_url string = apim.outputs.apimGatewayUrl
output azure_dns_zone_name string = privateDnsZone.outputs.name
output azure_app_hostname string = appHostname
output azure_app_url string = appUrl
output azure_workload_identity_client_id string = workloadIdentity.outputs.clientId
output azure_workload_identity_principal_id string = workloadIdentity.outputs.principalId
output azure_workload_identity_name string = workloadIdentity.outputs.name
output azure_private_dns_zones array = enablePrivateEndpoints
  ? union(privatelinkPrivateDns.outputs.privateDnsZones, [privateDnsZone.outputs.name])
  : []
