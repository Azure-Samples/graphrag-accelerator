param utcValue string
param location string

param acr_login_server string
param acr_token_name string
@secure()
param acr_token_password string

param ai_search_audience string = 'https://search.azure.com'
param ai_search_name string
param ai_search_endpoint_suffix string = 'search.windows.net'

param aks_name string
param aks_kubelet_id string
param aks_service_account_name string

param aoai_endpoint string
param aoai_llm_model string
param aoai_llm_model_deployment_name string
param aoai_llm_model_api_version string
param aoai_embedding_model string
param aoai_embedding_model_deployment_name string
param aoai_embedding_model_api_version string

param app_hostname string
param app_insights_connection_string string
param cosmosdb_endpoint string
param image_name string
param image_version string
param script_file string
param storage_account_blob_url string
param workload_identity_client_id string
param cognitive_services_audience string = 'https://cognitiveservices.azure.com/default'

param public_storage_account_name string
@secure()
param public_storage_account_key string

var clusterAdminRoleDefinitionId = resourceId(
  'Microsoft.Authorization/roleDefinitions',
  '0ab0b1a8-8aac-4efd-b8c2-3ee1fb270be8' // Azure Kubernetes Service Cluster Admin Role
)
var rbacClusterAdminRoleDefinitionId = resourceId(
  'Microsoft.Authorization/roleDefinitions',
  'b1ff04bb-8a4e-4dc4-8eb5-8693973ce19b' // Azure Kubernetes Service RBAC Cluster Admin Role
)
// var containerRegistryRepositoryContributorRoleDefinitionId = resourceId(
//   'Microsoft.Authorization/roleDefinitions',
//   '2efddaa5-3f1f-4df3-97df-af3f13818f4c' // Container Registry Repository Contributor Role
// )

resource aksCluster 'Microsoft.ContainerService/managedClusters@2024-09-02-preview' existing = {
  name: aks_name
}

resource scriptIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: 'deployment-script-identity-${uniqueString(resourceGroup().id)}'
  location: location
}

// var splitId = split(acr_id, '/')
// @description('Assign Container Registry Repository Contributor role to the deployment script identity to access ACR.')
// module acrPullRoleAssignment 'acr-pull-role-assignment.bicep' = {
//   name: 'acrPull-role-assignment-deployment'
//   scope: resourceGroup(splitId[2], splitId[4])
//   params: {
//     principalId: scriptIdentity.properties.principalId
//     principalType: 'ServicePrincipal'
//   }
// }

// var idToSplit = '/subscriptions/e93d3ee6-fac1-412f-92d6-bfb379e81af2/resourceGroups/alfran-redhat/providers/Microsoft.Compute/virtualMachines/adotfrank-rh'
// @description('Assign Container Registry Repository Contributor role to the deployment script identity to access ACR.')
// resource containerRegistryRepositoryContributorRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
//   name: guid(scriptIdentity.id, aksCluster.id, containerRegistryRepositoryContributorRoleDefinitionId)
//   scope: resourceGroup(splitId[2], splitId[4])
//   properties: {
//     principalId: scriptIdentity.properties.principalId
//     principalType: 'ServicePrincipal'
//     roleDefinitionId: containerRegistryRepositoryContributorRoleDefinitionId
//   }
// }

@description('Assign AKS Cluster Admin role to the deployment script identity to access AKS.')
resource clusterAdminRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(scriptIdentity.id, aksCluster.id, clusterAdminRoleDefinitionId)
  scope: aksCluster
  properties: {
    principalId: scriptIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: clusterAdminRoleDefinitionId
  }
}

@description('Assign AKS RBAC Cluster Admin role to the deployment script identity to access AKS.')
resource rbacClusterAdminRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(scriptIdentity.id, aksCluster.id, rbacClusterAdminRoleDefinitionId)
  scope: aksCluster
  properties: {
    principalId: scriptIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: rbacClusterAdminRoleDefinitionId
  }
}

// Must use module version 2020-10-01 and azCliVersion = v2.7.0 to have curl pre-installed
resource deploymentScript 'Microsoft.Resources/deploymentScripts@2020-10-01' = {
  name: 'deployment-script-deployment'
  location: location
  kind: 'AzureCLI'
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${scriptIdentity.id}': {}
    }
  }
  properties: {
    storageAccountSettings: {
      storageAccountName: public_storage_account_name
      storageAccountKey: public_storage_account_key
    }
    forceUpdateTag: utcValue
    azCliVersion: '2.7.0'
    timeout: 'PT1H'
    environmentVariables: [
      {
        name: 'ACR_SERVER'
        value: acr_login_server
      }
      {
        name: 'ACR_TOKEN_NAME'
        value: acr_token_name
      }
      {
        name: 'ACR_TOKEN_PASSWORD'
        value: acr_token_password
      }
      { name: 'AI_SEARCH_AUDIENCE', value: ai_search_audience }
      { name: 'AI_SEARCH_ENDPOINT_SUFFIX', value: ai_search_endpoint_suffix }
      {
        name: 'AI_SEARCH_NAME'
        value: ai_search_name
      }
      {
        name: 'AKS_NAME'
        value: aks_name
      }
      {
        name: 'AKS_KUBELET_ID'
        value: aks_kubelet_id
      }
      {
        name: 'AKS_SERVICE_ACCOUNT_NAME'
        value: aks_service_account_name
      }
      {
        name: 'AOAI_LLM_MODEL'
        value: aoai_llm_model
      }
      {
        name: 'AOAI_LLM_MODEL_DEPLOYMENT_NAME'
        value: aoai_llm_model_deployment_name
      }
      {
        name: 'AOAI_LLM_MODEL_API_VERSION'
        value: aoai_llm_model_api_version
      }
      {
        name: 'AOAI_EMBEDDING_MODEL'
        value: aoai_embedding_model
      }
      {
        name: 'AOAI_EMBEDDING_MODEL_DEPLOYMENT_NAME'
        value: aoai_embedding_model_deployment_name
      }
      { name: 'AOAI_EMBEDDING_MODEL_API_VERSION', value: aoai_embedding_model_api_version }
      { name: 'APP_HOSTNAME', value: app_hostname }
      { name: 'APP_INSIGHTS_CONNECTION_STRING', value: app_insights_connection_string }
      {
        name: 'COGNITIVE_SERVICES_AUDIENCE'
        value: cognitive_services_audience
      }
      {
        name: 'COSMOSDB_ENDPOINT'
        value: cosmosdb_endpoint
      }
      {
        name: 'IMAGE_NAME'
        value: image_name
      }
      {
        name: 'IMAGE_VERSION'
        value: image_version
      }
      {
        name: 'OPENAI_ENDPOINT'
        value: aoai_endpoint
      }
      {
        name: 'RESOURCE_GROUP'
        value: resourceGroup().name
      }
      { name: 'STORAGE_ACCOUNT_BLOB_URL', value: storage_account_blob_url }
      {
        name: 'WORKLOAD_IDENTITY_CLIENT_ID'
        value: workload_identity_client_id
      }
    ]
    cleanupPreference: 'OnSuccess'
    retentionInterval: 'P1D'
    scriptContent: script_file
  }
  dependsOn: [
    aksCluster
  ]
}
