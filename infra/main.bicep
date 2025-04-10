// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

/*
This bicep script can be used as a starting point and customized to fit the specific needs of an Azure environment.

The script should be executed as a resource group deployment using Azure CLI (az deployment group ...)

The script will deploy the following resources in a specified resource group:
AI Search
Application Insights
Azure OpenAI (optional)
Azure Container Registry (optional)
CosmosDB
Blob Storage
Azure Kubernetes Service
API Management
Log Analytics
Private Endpoints
Managed Identity
*/

@minLength(1)
@maxLength(64)
@description('Name of the resource group that GraphRAG will be deployed in.')
param resourceGroupName string = az.resourceGroup().name

// optional parameters with reasonable defaults unless explicitly overridden (most names will be auto-generated if not provided)
@description('Unique name to append to each resource')
param resourceBaseName string = ''
var resourceBaseNameFinal = !empty(resourceBaseName) ? resourceBaseName : toLower(uniqueString(az.resourceGroup().id))

@description('Cloud region for all resources')
param location string = az.resourceGroup().location

//
// start APIM parameters
//
@minLength(1)
@description('Name of the publisher of the API Management service.')
param apiPublisherName string = 'Microsoft'

@minLength(1)
@description('Email address of the publisher of the API Management service.')
param apiPublisherEmail string = 'publisher@microsoft.com'

@description('Whether or not to restore the API Management service from a soft-deleted state.')
param restoreAPIM bool = false
param apimTier string = 'Developer'
param apimName string = ''
//
// end APIM parameters
//

//
// start ACR parameters
//
@description('Whether or not to deploy a new ACR resource instead of connecting to an existing service.')
param deployAcr bool = false
// if existing ACR is used, the login server endpoint (i.e. <registry>.azurecr.io) must be provided
param existingAcrLoginServer string = ''
@description('The ACR token username. This is only used if an existing ACR is used.')
param acrTokenName string = ''
@secure()
@description('The ACR token password. This is only used if an existing ACR is used.')
param acrTokenPassword string = ''
param graphragImageName string = 'graphrag'
param graphragImageVersion string = 'latest'
//
// end ACR parameters
//

//
// start AOAI parameters
//
@description('Whether or not to deploy a new AOAI resource instead of connecting to an existing service.')
param deployAoai bool = true

@description('Resource id of an existing AOAI resource.')
param existingAoaiId string = ''

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
@allowed([
  'text-embedding-ada-002'
  'text-embedding-3-large'
  'text-embedding-3-small'
])
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

//
// start AKS parameters
//
@description('The AKS namespace to install GraphRAG in.')
param aksNamespace string = 'graphrag'
var workloadIdentityName = '${abbrs.managedIdentityUserAssignedIdentities}${resourceBaseNameFinal}'
var aksServiceAccountName = '${aksNamespace}-workload-sa'
var workloadIdentitySubject = 'system:serviceaccount:${aksNamespace}:${aksServiceAccountName}'
var dnsDomain = 'graphrag.io'
var appHostname = 'graphrag.${dnsDomain}'
var appUrl = 'http://${appHostname}'
//
// end AKS parameters
//

//
// start AI Search parameters
//
@description('Whether or not to restore the API Management service from a soft-deleted state.')
param aiSearchTier string = 'Standard'
//
// end AI Search parameters
//

var abbrs = loadJsonContent('abbreviations.json')
var tags = { 'azd-env-name': resourceGroupName }
param utcString string = utcNow()

@description('This parameter will only get defined during a managed app deployment.')
param managedAppStorageAccountName string = ''
@secure()
@description('This parameter will only get defined during a managed app deployment.')
param managedAppStorageAccountKey string = ''

@description('Whether to use private endpoint connections or not.')
param enablePrivateEndpoints bool = true

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
    aoaiId: deployAoai ? aoai.outputs.id : existingAoaiId
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

module acr 'core/acr/acr.bicep' = if (deployAcr) {
  name: 'acr-deployment'
  params: {
    registryName: '${abbrs.containerRegistryRegistries}${resourceBaseNameFinal}'
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
    cosmosDbName: '${abbrs.documentDBDatabaseAccounts}${resourceBaseNameFinal}'
    location: location
    publicNetworkAccess: enablePrivateEndpoints ? 'Disabled' : 'Enabled'
  }
}

module aiSearch 'core/ai-search/ai-search.bicep' = {
  name: 'aisearch-deployment'
  params: {
    name: '${abbrs.searchSearchServices}${resourceBaseNameFinal}'
    location: location
    publicNetworkAccess: enablePrivateEndpoints ? 'disabled' : 'enabled'
    sku: aiSearchTier
  }
}

module storage 'core/storage/storage.bicep' = {
  name: 'storage-deployment'
  params: {
    name: '${abbrs.storageStorageAccounts}${replace(resourceBaseNameFinal, '-', '')}'
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

module graphragApi 'core/apim/apim.graphrag-api.bicep' = if (!empty(managedAppStorageAccountName) && !empty(managedAppStorageAccountKey)) {
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

// The following deploymentScript is meant to only get deployed during a managed app deployment.
// Will not be deployed when performing a manual deployment with the deploy.sh script
module deploymentScript 'core/scripts/deployment-script.bicep' = if (!empty(managedAppStorageAccountName) && !empty(managedAppStorageAccountKey)) {
  name: 'deployScript-deployment-${utcString}'
  params: {
    location: location
    script_file: loadTextContent('managed-app/scripts/install-graphrag.sh')
    public_storage_account_name: managedAppStorageAccountName
    public_storage_account_key: managedAppStorageAccountKey
    acr_login_server: existingAcrLoginServer
    acr_token_name: acrTokenName
    acr_token_password: acrTokenPassword
    ai_search_name: aiSearch.name
    aks_name: aks.outputs.name
    aks_service_account_name: aksServiceAccountName
    deployAoai: deployAoai
    aoai_endpoint: aksWorkloadIdentityRBAC.outputs.aoaiEndpoint
    aoai_llm_model: deployAoai ? aoai.outputs.llmModel : llmModelName
    aoai_llm_model_deployment_name: deployAoai ? aoai.outputs.llmModelDeploymentName : llmModelDeploymentName
    aoai_llm_model_version: deployAoai ? aoai.outputs.llmModelVersion : llmModelVersion
    aoai_embedding_model: deployAoai ? aoai.outputs.embeddingModel : embeddingModelName
    aoai_embedding_model_deployment_name: deployAoai
      ? aoai.outputs.embeddingModelDeploymentName
      : embeddingModelDeploymentName
    app_hostname: appHostname
    app_insights_connection_string: appInsights.outputs.connectionString
    cosmosdb_endpoint: cosmosdb.outputs.endpoint
    image_name: graphragImageName
    image_version: graphragImageVersion
    storage_account_blob_url: storage.outputs.primaryEndpoints.blob
    utcValue: utcString
    workload_identity_client_id: workloadIdentity.outputs.clientId
  }
}

output deployer_principal_id string = deployer().objectId
output azure_location string = location
output azure_tenant_id string = tenant().tenantId
output azure_ai_search_name string = aiSearch.outputs.name
output azure_acr_login_server string = deployAcr ? acr.outputs.loginServer : existingAcrLoginServer
output azure_acr_name string = deployAcr ? acr.outputs.name : ''
output azure_aks_name string = aks.outputs.name
output azure_aks_controlplanefqdn string = aks.outputs.controlPlaneFqdn
output azure_aks_managed_rg string = aks.outputs.managedResourceGroup
output azure_aks_service_account_name string = aksServiceAccountName
// conditionally output AOAI endpoint information if it was deployed
output azure_aoai_endpoint string = deployAoai ? aoai.outputs.endpoint : aksWorkloadIdentityRBAC.outputs.aoaiEndpoint
output azure_aoai_llm_model string = deployAoai ? aoai.outputs.llmModel : llmModelName
output azure_aoai_llm_model_deployment_name string = deployAoai
  ? aoai.outputs.llmModelDeploymentName
  : llmModelDeploymentName
output azure_aoai_llm_model_quota int = deployAoai ? aoai.outputs.llmModelQuota : 0
output azure_aoai_llm_model_api_version string = deployAoai ? aoai.outputs.llmModelVersion : llmModelVersion
output azure_aoai_embedding_model string = deployAoai ? aoai.outputs.embeddingModel : embeddingModelName
output azure_aoai_embedding_model_deployment_name string = deployAoai
  ? aoai.outputs.embeddingModelDeploymentName
  : embeddingModelDeploymentName
output azure_aoai_embedding_model_quota int = deployAoai ? aoai.outputs.embeddingModelQuota : 0
output azure_aoai_embedding_model_api_version string = deployAoai
  ? aoai.outputs.embeddingModelVersion
  : embeddingModelVersion
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
