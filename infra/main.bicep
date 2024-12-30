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

@description('Unique name to append to each resource')
param resourceBaseName string = ''
var resourceBaseNameFinal = !empty(resourceBaseName) ? resourceBaseName : toLower(uniqueString('${subscription().id}/resourceGroups/${graphRagName}'))

@minLength(1)
@maxLength(64)
@description('Name of the resource group that GraphRAG will be deployed in.')
param graphRagName string

@description('Cloud region for all resources')
param location string = resourceGroup().location

@description('Principal/Object ID of the deployer. Will be used to assign admin roles to the AKS cluster.')
param deployerPrincipalId string

@minLength(1)
@description('Name of the publisher of the API Management instance.')
param publisherName string

@minLength(1)
@description('Email address of the publisher of the API Management instance.')
param publisherEmail string

@description('The AKS namespace the workload identity service account will be created in.')
param aksNamespace string = 'graphrag'

@description('Public key to allow access to AKS Linux nodes.')
param aksSshRsaPublicKey string

@description('Whether to enable private endpoints.')
param enablePrivateEndpoints bool = true

@description('Whether to restore the API Management instance.')
param restoreAPIM bool = false

param acrName string = ''
param apimName string = ''
param apimTier string = 'Developer'
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
@description('Role definitions for various roles that will be assigned at deployment time. Learn more: https://learn.microsoft.com/en-us/azure/role-based-access-control/built-in-roles')
var roles = {
  storageBlobDataContributor: resourceId(
    'Microsoft.Authorization/roleDefinitions',
    'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
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
  privateDnsZoneContributor: resourceId (
    'Microsoft.Authorization/roleDefinitions',
    'b12aa53e-6015-4669-85d0-8515ebb3ae7f'  // Private DNS Zone Contributor Role
  )
  networkContributor: resourceId (
    'Microsoft.Authorization/roleDefinitions',
    '4d97b98b-1d4f-4787-a291-c67834d212e7'  // Network Contributor Role
  )
  cognitiveServicesOpenaiContributor: resourceId (
    'Microsoft.Authorization/roleDefinitions',
    'a001fd3d-188f-4b5d-821b-7da978bf7442'  // Cognitive Services OpenAI Contributor
  )
  acrPull: resourceId (
    'Microsoft.Authorization/roleDefinitions',
    '7f951dda-4ed3-4680-a7ca-43fe172d538d'  // ACR Pull Role
  )
}


module log 'core/log-analytics/log.bicep' = {
  name: 'log-analytics'
  params:{
    name: '${abbrs.operationalInsightsWorkspaces}${resourceBaseNameFinal}'
    location: location
    publicNetworkAccessForIngestion: enablePrivateEndpoints ? 'Disabled' : 'Enabled'
  }
}

module nsg 'core/vnet/nsg.bicep' = {
  name: 'nsg'
  params: {
    nsgName: '${abbrs.networkNetworkSecurityGroups}${resourceBaseNameFinal}'
    location: location
  }
}

resource vnet 'Microsoft.Network/virtualNetworks@2024-01-01' = {
  name: '${abbrs.networkVirtualNetworks}${resourceBaseNameFinal}'
  location: location
  properties: {
    addressSpace: {
      addressPrefixes: [
        '10.1.0.0/16'
      ]
    }
    subnets: [
      {
        name: '${abbrs.networkVirtualNetworksSubnets}apim'
        properties: {
          addressPrefix: '10.1.0.0/24'
          networkSecurityGroup: {
            id: nsg.outputs.id
          }
          delegations: (apimTier=='Developer') ? [] : [
            {
              name: 'Microsoft.Web/serverFarms'
              properties: {
                serviceName: 'Microsoft.Web/serverFarms'
              }
            }
          ]
        }
      }
      {
        name: '${abbrs.networkVirtualNetworksSubnets}aks'
        properties: {
          addressPrefix: '10.1.1.0/24'
          serviceEndpoints: [
            {
              service: 'Microsoft.Storage'
            }
            {
              service: 'Microsoft.Sql'
            }
            {
              service: 'Microsoft.EventHub'
            }
          ]
        }
      }
    ]
  }
}

module acr 'core/acr/acr.bicep' = {
  name: 'acr'
  params: {
    registryName: !empty(acrName) ? acrName : '${abbrs.containerRegistryRegistries}${resourceBaseNameFinal}'
    location: location
    roleAssignments: [
      {
        principalId: aks.outputs.kubeletPrincipalId
        principalType: 'ServicePrincipal'
        roleDefinitionId: roles.acrPull
      }
    ]
  }
}

module aks 'core/aks/aks.bicep' = {
  name: 'aks'
  params:{
    clusterName: '${abbrs.containerServiceManagedClusters}${resourceBaseNameFinal}'
    location: location
    graphragVMSize: 'standard_d8s_v5'           // 8 vcpu, 32 GB memory
    graphragIndexingVMSize: 'standard_e8s_v5'   // 8 vcpus, 64 GB memory
    clusterAdmins: ['${deployerPrincipalId}']
    sshRSAPublicKey: aksSshRsaPublicKey
    logAnalyticsWorkspaceId: log.outputs.id
    subnetId: vnet.properties.subnets[1].id // aks subnet
    privateDnsZoneName: privateDnsZone.outputs.name
    ingressRoleAssignments: [
      {
        principalType: 'ServicePrincipal'
        roleDefinitionId: roles.privateDnsZoneContributor
      }
    ]
    systemRoleAssignments: [
      {
        principalType: 'ServicePrincipal'
        roleDefinitionId: roles.networkContributor
      }
    ]
  }
}

module cosmosdb 'core/cosmosdb/cosmosdb.bicep' = {
  name: 'cosmosdb'
  params: {
    cosmosDbName: !empty(cosmosDbName) ? cosmosDbName : '${abbrs.documentDBDatabaseAccounts}${resourceBaseNameFinal}'
    location: location
    publicNetworkAccess: enablePrivateEndpoints ? 'Disabled' : 'Enabled'
    principalId: workloadIdentity.outputs.principalId
  }
}

module aiSearch 'core/ai-search/ai-search.bicep' = {
  name: 'aisearch'
  params: {
    name: !empty(aiSearchName) ? aiSearchName : '${abbrs.searchSearchServices}${resourceBaseNameFinal}'
    location: location
    publicNetworkAccess: enablePrivateEndpoints ? 'disabled' : 'enabled'
    roleAssignments: [
      {
        principalId: workloadIdentity.outputs.principalId
        principalType: 'ServicePrincipal'
        roleDefinitionId: roles.aiSearchContributor
      }
      {
        principalId: workloadIdentity.outputs.principalId
        principalType: 'ServicePrincipal'
        roleDefinitionId: roles.aiSearchIndexDataContributor
      }
      {
        principalId: workloadIdentity.outputs.principalId
        principalType: 'ServicePrincipal'
        roleDefinitionId: roles.aiSearchIndexDataReader
      }
    ]
  }
}

module storage 'core/storage/storage.bicep' = {
  name: 'storage'
  params: {
    name: !empty(storageAccountName) ? storageAccountName : '${abbrs.storageStorageAccounts}${replace(resourceBaseNameFinal, '-', '')}'
    location: location
    publicNetworkAccess: enablePrivateEndpoints ? 'Disabled' : 'Enabled'
    tags: tags
    roleAssignments: [
      {
        principalId: workloadIdentity.outputs.principalId
        principalType: 'ServicePrincipal'
        roleDefinitionId: roles.storageBlobDataContributor
      }
    ]
    deleteRetentionPolicy: {
      enabled: true
      days: 5
    }
    defaultToOAuthAuthentication: true
  }
}

module apim 'core/apim/apim.bicep' = {
  name: 'apim'
  params: {
    apiManagementName: !empty(apimName) ? apimName : '${abbrs.apiManagementService}${resourceBaseNameFinal}'
    restoreAPIM: restoreAPIM
    appInsightsName: '${abbrs.insightsComponents}${resourceBaseNameFinal}'
    appInsightsPublicNetworkAccessForIngestion: enablePrivateEndpoints ? 'Disabled' : 'Enabled'
    publicIpName: '${abbrs.networkPublicIPAddresses}${resourceBaseNameFinal}'
    location: location
    sku: apimTier
    skuCount: 1 // TODO expose in param for premium sku
    availabilityZones: [] // TODO expose in param for premium sku
    publisherEmail: publisherEmail
    publisherName: publisherName
    logAnalyticsWorkspaceId: log.outputs.id
    subnetId: vnet.properties.subnets[0].id // apim subnet
  }
}

module graphragApi 'core/apim/apim.graphrag-documentation.bicep' = {
  name: 'graphrag-api'
  params: {
    apimname: apim.outputs.name
    backendUrl: graphRagUrl
  }
}

module workloadIdentity 'core/identity/identity.bicep' = {
  name: 'workload-identity'
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
  params: {
    name: dnsDomain
    vnetNames: [
      vnet.name
    ]
  }
}

module privatelinkPrivateDns 'core/vnet/privatelink-private-dns-zones.bicep' = if (enablePrivateEndpoints) {
  name: 'privatelink-private-dns-zones'
  params: {
    linkedVnetIds: [
      vnet.id
    ]
  }
}

module azureMonitorPrivateLinkScope 'core/monitor/private-link-scope.bicep' = if (enablePrivateEndpoints) {
  name: 'azure-monitor-privatelink-scope'
  params: {
    privateLinkScopeName: 'pls-${resourceBaseNameFinal}'
    privateLinkScopedResources: [
      log.outputs.id
      apim.outputs.appInsightsId
    ]
  }
}

module cosmosDbPrivateEndpoint 'core/vnet/private-endpoint.bicep' = if (enablePrivateEndpoints) {
  name: 'cosmosDb-private-endpoint'
  params: {
    privateEndpointName: '${abbrs.privateEndpoint}cosmos-${cosmosdb.outputs.name}'
    location: location
    privateLinkServiceId: cosmosdb.outputs.id
    subnetId: vnet.properties.subnets[1].id // aks subnet
    groupId: 'Sql'
    privateDnsZoneConfigs: enablePrivateEndpoints ? privatelinkPrivateDns.outputs.cosmosDbPrivateDnsZoneConfigs : []
  }
}

module blobStoragePrivateEndpoint 'core/vnet/private-endpoint.bicep' = if (enablePrivateEndpoints) {
  name: 'blob-storage-private-endpoint'
  params: {
    privateEndpointName: '${abbrs.privateEndpoint}blob-${storage.outputs.name}'
    location: location
    privateLinkServiceId: storage.outputs.id
    subnetId: vnet.properties.subnets[1].id // aks subnet
    groupId: 'blob'
    privateDnsZoneConfigs: enablePrivateEndpoints ? privatelinkPrivateDns.outputs.blobStoragePrivateDnsZoneConfigs : []
  }
}

module aiSearchPrivateEndpoint 'core/vnet/private-endpoint.bicep' = if (enablePrivateEndpoints) {
  name: 'ai-search-private-endpoint'
  params: {
    privateEndpointName: '${abbrs.privateEndpoint}search-${aiSearch.outputs.name}'
    location: location
    privateLinkServiceId: aiSearch.outputs.id
    subnetId: vnet.properties.subnets[1].id // aks subnet
    groupId: 'searchService'
    privateDnsZoneConfigs: enablePrivateEndpoints ? privatelinkPrivateDns.outputs.aiSearchPrivateDnsZoneConfigs : []
  }
}

module privateLinkScopePrivateEndpoint 'core/vnet/private-endpoint.bicep' = if (enablePrivateEndpoints) {
  name: 'privatelink-scope-private-endpoint'
  params: {
    privateEndpointName: '${abbrs.privateEndpoint}pls-${resourceBaseNameFinal}'
    location: location
    privateLinkServiceId: enablePrivateEndpoints ? azureMonitorPrivateLinkScope.outputs.id : ''
    subnetId: vnet.properties.subnets[1].id // aks subnet
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
output azure_app_insights_connection_string string = apim.outputs.appInsightsConnectionString
output azure_apim_name string = apim.outputs.name
output azure_apim_gateway_url string = apim.outputs.apimGatewayUrl
output azure_dns_zone_name string = privateDnsZone.outputs.name
output azure_graphrag_hostname string = graphRagHostname
output azure_graphrag_url string = graphRagUrl
output azure_workload_identity_client_id string = workloadIdentity.outputs.clientId
output azure_workload_identity_principal_id string = workloadIdentity.outputs.principalId
output azure_workload_identity_name string = workloadIdentity.outputs.name
output azure_private_dns_zones array = enablePrivateEndpoints ? union(
  privatelinkPrivateDns.outputs.privateDnsZones,
  [privateDnsZone.outputs.name]
) : []
