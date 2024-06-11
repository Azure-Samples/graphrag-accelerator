// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

/* DEPLOYMENT ARTIFACTS - a single resource group with the following resources:
Cosmos DB
Blob Storage
AKS
API Management
Log Analytics
*/
targetScope = 'subscription'

// Allows script to pass empty value by default
@description('Unique name to append to each resource')
param resourceBaseName string = ''
var resourceBaseNameFinal = !empty(resourceBaseName) ? resourceBaseName : toLower(uniqueString('${subscription().id}/resourceGroups/${graphRagName}'))

@minLength(1)
@maxLength(64)
@description('Name of the resource group that GraphRAG will be deployed in.')
param graphRagName string

@description('Location for all resources')
param location string = deployment().location

@minLength(1)
@description('Name of the publisher of the API Management instance')
param publisherName string

@minLength(1)
@description('Email address of the publisher of the API Management instance')
param publisherEmail string

@description('The AKS namespace the workload idenitty service account will be created in.')
param aksNamespace string = 'graphrag'

@description('Public key to allow access to AKS Linux nodes.')
param aksSshRsaPublicKey string

param apimName string = ''
param storageAccountName string = ''
param cosmosDbName string = ''
param aiSearchName string = ''

var graphRagDnsLabel = 'graphrag'
var dnsDomain = 'graphrag.io'
var graphRagHostname = '${graphRagDnsLabel}.${dnsDomain}'
var graphRagUrl = 'http://${graphRagHostname}'

var abbrs = loadJsonContent('abbreviations.json')
var tags = { 'azd-env-name': graphRagName }

var workloadIdentityName = '${abbrs.managedIdentityUserAssignedIdentities}${resourceBaseNameFinal}'
var aksServiceAccountName = '${aksNamespace}-workload-sa'
var workloadIdentitySubject = 'system:serviceaccount:${aksNamespace}:${aksServiceAccountName}'

var roles = {
  storageBlobDataContributor: resourceId(
    'Microsoft.Authorization/roleDefinitions',
    'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
  )
  storageQueueDataContributor: resourceId(
    'Microsoft.Authorization/roleDefinitions',
    '974c5e8b-45b9-4653-ba55-5f855dd0fb88'
  )
  aiSearchContributor: resourceId(
    'Microsoft.Authorization/roleDefinitions',
    'b24988ac-6180-42a0-ab88-20f7382dd24c'  // AI Search Contributor Role
  )
  aiSearchIndexDataContributor: resourceId(
    'Microsoft.Authorization/roleDefinitions',
    '8ebe5a00-799e-43f5-93ac-243d3dce84a7'  // AI Search Index Data Contributor Role
  )
  aiSearchIndexDataReader: resourceId (
    'Microsoft.Authorization/roleDefinitions',
    '1407120a-92aa-4202-b7e9-c0e197c71c8f'  // AI Search Index Data Reader Role
  )
}

resource rg 'Microsoft.Resources/resourceGroups@2023-07-01' = {
  name: graphRagName
  location: location
}

module log 'core/log-analytics/log.bicep' = {
  name: 'log'
  scope: rg
  params:{
    name: '${abbrs.operationalInsightsWorkspaces}${resourceBaseNameFinal}'
    location: rg.location
  }
}

module aks 'core/aks/aks.bicep' = {
  name: 'aks'
  scope: rg
  params:{
    clusterName: '${abbrs.containerServiceManagedClusters}${resourceBaseNameFinal}'
    location: rg.location
    sshRSAPublicKey: aksSshRsaPublicKey
    logAnalyticsWorkspaceId: log.outputs.id
  }
}

module cosmosdb 'core/cosmosdb/cosmosdb.bicep' = {
  name: 'cosmosdb'
  scope: rg
  params: {
    cosmosDbName: !empty(cosmosDbName) ? cosmosDbName : '${abbrs.documentDBDatabaseAccounts}${resourceBaseNameFinal}'
    location: rg.location
    principalId: workloadIdentity.outputs.principal_id
  }
}

module aiSearch 'core/ai-search/ai-search.bicep' = {
  name: 'aisearch'
  scope: rg
  params: {
    name: !empty(aiSearchName) ? aiSearchName : '${abbrs.searchSearchServices}${resourceBaseNameFinal}'
    location: rg.location
    roleAssignments: [
      {
        principalId: workloadIdentity.outputs.principal_id
        principalType: 'ServicePrincipal'
        roleDefinitionId: roles.aiSearchContributor
      }
      {
        principalId: workloadIdentity.outputs.principal_id
        principalType: 'ServicePrincipal'
        roleDefinitionId: roles.aiSearchIndexDataContributor
      }
      {
        principalId: workloadIdentity.outputs.principal_id
        principalType: 'ServicePrincipal'
        roleDefinitionId: roles.aiSearchIndexDataReader
      }
    ]
  }
}

module storage 'core/blob/storage.bicep' = {
  name: 'storage'
  scope: rg
  params: {
    name: !empty(storageAccountName) ? storageAccountName : '${abbrs.storageStorageAccounts}${replace(resourceBaseNameFinal, '-', '')}'
    location: rg.location
    tags: tags
    roleAssignments: [
      {
        principalId: workloadIdentity.outputs.principal_id
        principalType: 'ServicePrincipal'
        roleDefinitionId: roles.storageBlobDataContributor
      }
      {
        principalId: workloadIdentity.outputs.principal_id
        principalType: 'ServicePrincipal'
        roleDefinitionId: roles.storageQueueDataContributor
      }
    ]
    publicNetworkAccess: 'Disabled'
    deleteRetentionPolicy: {
      enabled: true
      days: 5
    }
    defaultToOAuthAuthentication: true
  }
}

module apim 'core/apim/apim.bicep' = {
  name: 'apim'
  scope: rg
  params: {
    apiManagementName: !empty(apimName) ? apimName : '${abbrs.apiManagementService}${resourceBaseNameFinal}'
    appInsightsName: '${abbrs.insightsComponents}${resourceBaseNameFinal}'
    nsgName: '${abbrs.networkNetworkSecurityGroups}${resourceBaseNameFinal}'
    publicIpName: '${abbrs.networkPublicIPAddresses}${resourceBaseNameFinal}'
    virtualNetworkName: '${abbrs.networkVirtualNetworks}${resourceBaseNameFinal}'
    location: rg.location
    sku: 'Developer'
    skuCount: 1 // TODO expose in param for premium sku
    availabilityZones: [] // TODO expose in param for premium sku
    publisherEmail: publisherEmail
    publisherName: publisherName
    logAnalyticsWorkspaceId: log.outputs.id
  }
}

module graphragApi 'core/apim/apim.graphrag-documentation.bicep' = {
  name: 'apimservice'
  scope: rg
  params: {
    apimname: apim.outputs.name
    backendUrl: graphRagUrl
  }
}

module workloadIdentity 'core/identity/identity.bicep' = {
  name: 'workloadIdentity'
  scope: rg
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
  name: 'private-dns-zone'
  scope: rg
  params: {
    name: dnsDomain
    vnetNames: [
      apim.outputs.vnetName
    ]
  }
}

module privatelinkPrivateDns 'core/vnet/privatelink-private-dns-zones.bicep' = {
  name: 'privatelink-private-dns-zones'
  scope: rg
  params: {
    linkedVnetResourceIds: [
      apim.outputs.vnetId
    ]
  }
}

module azureMonitorPrivateLinkScope 'core/monitor/private-link-scope.bicep' = {
  name: 'azureMonitorPrivateLinkScope'
  scope: rg
  params: {
    privateLinkScopeName: 'pls-${resourceBaseNameFinal}'
    privateLinkScopedResources: [
      log.outputs.id
      apim.outputs.appInsightsId
    ]
  }
}

module cosmosDbPrivateEndpoint 'core/vnet/private-endpoint.bicep' = {
  name: 'cosmosDbPrivateEndpoint'
  scope: rg
  params: {
    privateEndpointName: '${abbrs.privateEndpoint}cosmos-${cosmosdb.outputs.name}'
    location: location
    privateLinkServiceId: cosmosdb.outputs.id
    subnetId: apim.outputs.defaultSubnetId
    groupId: 'Sql'
    privateDnsZoneConfigs: privatelinkPrivateDns.outputs.cosmosDbPrivateDnsZoneConfigs
  }
}

module blobStoragePrivateEndpoint 'core/vnet/private-endpoint.bicep' = {
  name: 'blobStoragePrivateEndpoint'
  scope: rg
  params: {
    privateEndpointName: '${abbrs.privateEndpoint}blob-${storage.outputs.name}'
    location: location
    privateLinkServiceId: storage.outputs.id
    subnetId: apim.outputs.defaultSubnetId
    groupId: 'blob'
    privateDnsZoneConfigs: privatelinkPrivateDns.outputs.blobStoragePrivateDnsZoneConfigs
  }
}

module queueStoragePrivateEndpoint 'core/vnet/private-endpoint.bicep' = {
  name: 'queueStoragePrivateEndpoint'
  scope: rg
  params: {
    privateEndpointName: '${abbrs.privateEndpoint}queue-${storage.outputs.name}'
    location: location
    privateLinkServiceId: storage.outputs.id
    subnetId: apim.outputs.defaultSubnetId
    groupId: 'queue'
    privateDnsZoneConfigs: privatelinkPrivateDns.outputs.queueStoragePrivateDnsZoneConfigs
  }
}

module privateLinkScopePrivateEndpoint 'core/vnet/private-endpoint.bicep' = {
  name: 'privateLinkScopePrivateEndpoint'
  scope: rg
  params: {
    privateEndpointName: '${abbrs.privateEndpoint}pls-${resourceBaseNameFinal}'
    location: location
    privateLinkServiceId: azureMonitorPrivateLinkScope.outputs.privateLinkScopeId
    subnetId: apim.outputs.defaultSubnetId
    groupId: 'azuremonitor'
    privateDnsZoneConfigs: privatelinkPrivateDns.outputs.azureMonitorPrivateDnsZoneConfigs
  }
}

output azure_location string = location
output azure_tenant_id string = tenant().tenantId
output azure_ai_search_name string = aiSearch.outputs.name
output azure_aks_name string = aks.outputs.name
output azure_aks_controlplanefqdn string = aks.outputs.controlPlaneFQDN
output azure_aks_managed_rg string = aks.outputs.managedResourceGroup
output azure_aks_service_account_name string = aksServiceAccountName
output azure_storage_account string = storage.outputs.name
output azure_storage_account_blob_url string = storage.outputs.primaryEndpoints.blob
output azure_cosmosdb_endpoint string = cosmosdb.outputs.endpoint
output azure_cosmosdb_name string = cosmosdb.outputs.name
output azure_cosmosdb_id string = cosmosdb.outputs.id
output azure_apim_name string = apim.outputs.name
output azure_apim_url string = apim.outputs.apimGatewayUrl
output azure_apim_vnet_name string = apim.outputs.vnetName
output azure_apim_vnet_id string = apim.outputs.vnetId
output azure_dns_zone_name string = privateDnsZone.outputs.dns_zone_name
output azure_graphrag_hostname string = graphRagHostname
output azure_graphrag_url string = graphRagUrl
output azure_workload_identity_client_id string = workloadIdentity.outputs.client_id
output azure_workload_identity_principal_id string = workloadIdentity.outputs.principal_id
output azure_workload_identity_name string = workloadIdentity.outputs.name
output azure_private_dns_zones array = union(
  privatelinkPrivateDns.outputs.privateDnsZones,
  [privateDnsZone.outputs.dns_zone_name]
)
