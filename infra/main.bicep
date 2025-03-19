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

// optional parameters with reasonable defaults unless explicitly overridden (most names will be auto-generated if not provided)
@description('Unique name to append to each resource')
param resourceBaseName string = ''
var resourceBaseNameFinal = !empty(resourceBaseName) ? resourceBaseName : toLower(uniqueString(az.resourceGroup().id))

@description('Cloud region for all resources')
param location string = az.resourceGroup().location

@minLength(1)
@description('Name of the publisher of the API Management instance.')
param apiPublisherName string = 'Microsoft'

@minLength(1)
@description('Email address of the publisher of the API Management instance.')
param apiPublisherEmail string = 'publisher@microsoft.com'

@description('The AKS namespace to install GraphRAG in.')
param aksNamespace string = 'graphrag'

@description('Whether to use private endpoint connections or not.')
param enablePrivateEndpoints bool = true

@description('Whether to restore the API Management instance.')
param restoreAPIM bool = false

@description('The resource id of an existing AOAI service. Deployment of a new AOAI service will be skipped if this parameter is provided.')
param deployAoai bool = true

param apimTier string = 'Developer'
param apimName string = ''
param acrName string = ''
param storageAccountName string = ''
param cosmosDbName string = ''
param aiSearchName string = ''
param utcString string = utcNow()
param graphragImage string = 'graphragbackend'
param graphragImageVersion string = 'latest'

//
// start AOAI parameters
//
@description('Name of the AOAI LLM model to use. Must match official model id. For more information: https://learn.microsoft.com/en-us/azure/ai-services/openai/concepts/models')
@allowed(['gpt-4', 'gpt-4o', 'gpt-4o-mini'])
param llmModelName string = 'gpt-4o'

@description('Deployment name of the AOAI LLM model to use. For more information: https://learn.microsoft.com/en-us/azure/ai-services/openai/concepts/models')
param llmModelDeploymentName string = 'gpt-4o'

@description('Model version of the AOAI LLM model to use.')
@allowed(['2024-08-06', 'turbo-2024-04-09'])
param llmModelVersion string = '2024-08-06'

@description('Quota of the AOAI LLM model to use.')
@minValue(1)
param llmModelQuota int = 1

@description('Name of the AOAI embedding model to use. Must match official model id. For more information: https://learn.microsoft.com/en-us/azure/ai-services/openai/concepts/models')
@allowed(['text-embedding-ada-002', 'text-embedding-3-large'])
param embeddingModelName string = 'text-embedding-ada-002'

@description('Deployment name of the AOAI embedding model to use. Must match official model id. For more information: https://learn.microsoft.com/en-us/azure/ai-services/openai/concepts/models')
param embeddingModelDeploymentName string = 'text-embedding-ada-002'

@description('Model version of the AOAI embedding model to use.')
@allowed(['2', '1'])
param embeddingModelVersion string = '2'

@description('Quota of the AOAI embedding model to use.')
@minValue(1)
param embeddingModelQuota int = 1
//
// end AOAI parameters
//

@description('This parameter will only get defined during a managed app deployment.')
param publicStorageAccountName string = ''
@secure()
@description('This parameter will only get defined during a managed app deployment.')
param publicStorageAccountKey string = ''

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
  acrPull: resourceId(
    'Microsoft.Authorization/roleDefinitions',
    '7f951dda-4ed3-4680-a7ca-43fe172d538d' // ACR Pull Role
  )
  networkContributor: resourceId(
    'Microsoft.Authorization/roleDefinitions',
    '4d97b98b-1d4f-4787-a291-c67834d212e7' // Network Contributor Role
  )
  privateDnsZoneContributor: resourceId(
    'Microsoft.Authorization/roleDefinitions',
    'b12aa53e-6015-4669-85d0-8515ebb3ae7f' // Private DNS Zone Contributor Role
  )
}

// apply RBAC role assignments to the AKS workload identity
module aksWorkloadIdentityRBAC 'core/rbac/workload-identity-rbac.bicep' = {
  name: 'aks-workload-identity-rbac-assignments'
  params: {
    principalId: workloadIdentity.outputs.principalId
    principalType: 'ServicePrincipal'
    aiSearchName: aiSearch.outputs.name
    appInsightsName: appInsights.outputs.name
    cosmosDbName: cosmosdb.outputs.name
    storageName: storage.outputs.name
    aoaiName: deployAoai ? aoai.outputs.name : ''
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

module aoai 'core/aoai/aoai.bicep' = if (deployAoai) {
  name: 'aoai-deployment'
  params: {
    openAiName: '${abbrs.cognitiveServicesAccounts}${resourceBaseNameFinal}'
    location: location
    llmModelName: llmModelName
    llmModelDeploymentName: llmModelDeploymentName
    llmModelVersion: llmModelVersion
    llmTpmQuota: llmModelQuota
    embeddingModelName: embeddingModelName
    embeddingModelDeploymentName: embeddingModelDeploymentName
    embeddingModelVersion: embeddingModelVersion
    embeddingTpmQuota: embeddingModelQuota
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
    clusterAdmins: [deployer().objectId]
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

module graphragDocsApi 'core/apim/apim.graphrag-docs-api.bicep' = {
  name: 'graphrag-docs-api-deployment'
  params: {
    apiManagementName: apim.outputs.name
    backendUrl: appUrl
  }
}

module graphragApi 'core/apim/apim.graphrag-api.bicep' = if (!empty(publicStorageAccountName) && !empty(publicStorageAccountKey)) {
  name: 'graphrag-api-deployment'
  params: {
    name: 'GraphRag'
    apiManagementName: apim.outputs.name
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
    vnetName: vnet.outputs.name
  }
}

module privatelinkPrivateDns 'core/vnet/privatelink-private-dns-zones.bicep' = if (enablePrivateEndpoints) {
  name: 'privatelink-private-dns-zones-deployment'
  params: {
    linkedVnetId: vnet.outputs.id
  }
}

module azureMonitorPrivateLinkScope 'core/monitor/private-link-scope.bicep' = if (enablePrivateEndpoints) {
  name: 'azure-monitor-privatelink-scope-deployment'
  params: {
    privateLinkScopeName: '${abbrs.networkPrivateLinkScope}${resourceBaseNameFinal}'
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

module deploymentScript 'core/scripts/deployment-script.bicep' = if (!empty(publicStorageAccountName) && !empty(publicStorageAccountKey)) {
  name: utcString
  params: {
    name: 'graphragscript'
    location: location
    tenantid: tenant().tenantId
    subscriptionId: subscription().id
    script_file: loadTextContent('managed-app/artifacts/scripts/updategraphrag.sh')
    public_storage_account_name: publicStorageAccountName
    public_storage_account_key: publicStorageAccountKey
    utcValue: utcString
    acrserver: 'graphrag.azure.acr.io'
    ai_search_name: aiSearch.name
    azure_location: location
    azure_acr_login_server: acr.outputs.loginServer
    azure_acr_name: acr.outputs.name
    azure_aks_name: aks.outputs.name
    azure_aks_controlplanefqdn: aks.outputs.controlPlaneFqdn
    azure_aks_managed_rg: aks.outputs.managedResourceGroup
    azure_aks_service_account_name: aksServiceAccountName
    azure_aoai_endpoint: aoai.outputs.endpoint
    azure_aoai_llm_model: aoai.outputs.llmModel
    azure_aoai_llm_model_deployment_name: aoai.outputs.llmModelDeploymentName
    azure_aoai_llm_model_api_version: aoai.outputs.llmModelApiVersion
    azure_aoai_embedding_model: aoai.outputs.embeddingModel
    azure_aoai_embedding_model_deployment_name: aoai.outputs.embeddingModelDeploymentName
    azure_aoai_embedding_model_api_version: aoai.outputs.embeddingModelApiVersion
    azure_apim_gateway_url: apim.outputs.apimGatewayUrl
    azure_apim_name: apim.outputs.name
    azure_app_hostname: appHostname
    azure_app_url: appUrl
    azure_app_insights_connection_string: appInsights.outputs.connectionString
    azure_cosmosdb_endpoint: cosmosdb.outputs.endpoint
    azure_cosmosdb_name: cosmosdb.outputs.name
    azure_cosmosdb_id: cosmosdb.outputs.id
    azure_dns_zone_name: privateDnsZone.outputs.name
    azure_storage_account: storage.outputs.name
    azure_storage_account_blob_url: storage.outputs.primaryEndpoints.blob
    azure_workload_identity_client_id: workloadIdentity.outputs.clientId
    azure_workload_identity_principal_id: workloadIdentity.outputs.principalId
    azure_workload_identity_name: workloadIdentity.outputs.name
    image_name: graphragImage
    image_version: graphragImageVersion
    managed_identity_aks: aks.outputs.systemIdentity
  }
}

output deployer_principal_id string = deployer().objectId
output azure_location string = location
output azure_tenant_id string = tenant().tenantId
output azure_ai_search_name string = aiSearch.outputs.name
output azure_acr_login_server string = acr.outputs.loginServer
output azure_acr_name string = acr.outputs.name
output azure_aks_name string = aks.outputs.name
output azure_aks_controlplanefqdn string = aks.outputs.controlPlaneFqdn
output azure_aks_managed_rg string = aks.outputs.managedResourceGroup
output azure_aks_service_account_name string = aksServiceAccountName
// conditionally output AOAI endpoint information if it was deployed
output azure_aoai_endpoint string = deployAoai ? aoai.outputs.endpoint : ''
output azure_aoai_llm_model string = deployAoai ? aoai.outputs.llmModel : ''
output azure_aoai_llm_model_deployment_name string = deployAoai ? aoai.outputs.llmModelDeploymentName : ''
output azure_aoai_llm_model_quota int = deployAoai ? aoai.outputs.llmModelQuota : 0
output azure_aoai_llm_model_api_version string = deployAoai ? aoai.outputs.llmModelApiVersion : ''
output azure_aoai_embedding_model string = deployAoai ? aoai.outputs.embeddingModel : ''
output azure_aoai_embedding_model_deployment_name string = deployAoai ? aoai.outputs.embeddingModelDeploymentName : ''
output azure_aoai_embedding_model_quota int = deployAoai ? aoai.outputs.embeddingModelQuota : 0
output azure_aoai_embedding_model_api_version string = deployAoai ? aoai.outputs.embeddingModelApiVersion : ''
output azure_apim_gateway_url string = apim.outputs.apimGatewayUrl
output azure_apim_name string = apim.outputs.name
output azure_app_hostname string = appHostname
output azure_app_url string = appUrl
output azure_app_insights_connection_string string = appInsights.outputs.connectionString
output azure_cosmosdb_endpoint string = cosmosdb.outputs.endpoint
output azure_cosmosdb_name string = cosmosdb.outputs.name
output azure_cosmosdb_id string = cosmosdb.outputs.id
output azure_dns_zone_name string = privateDnsZone.outputs.name
output azure_private_dns_zones array = enablePrivateEndpoints
  ? union(privatelinkPrivateDns.outputs.privateDnsZones, [privateDnsZone.outputs.name])
  : []
output azure_storage_account string = storage.outputs.name
output azure_storage_account_blob_url string = storage.outputs.primaryEndpoints.blob
output azure_workload_identity_client_id string = workloadIdentity.outputs.clientId
output azure_workload_identity_principal_id string = workloadIdentity.outputs.principalId
output azure_workload_identity_name string = workloadIdentity.outputs.name
