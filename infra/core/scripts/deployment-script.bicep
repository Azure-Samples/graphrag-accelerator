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
param aks_service_account_name string

param deployAoai bool
param aoai_endpoint string
param aoai_llm_model string
param aoai_llm_model_deployment_name string
param aoai_llm_model_version string
param aoai_embedding_model string
param aoai_embedding_model_deployment_name string

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
var aksContributorRoleDefinitionId = resourceId(
  'Microsoft.Authorization/roleDefinitions',
  'ed7f3fbd-7b88-4dd4-9017-9adb7ce333f8' // Azure Kubernetes Service Contributor Role
)

resource aksCluster 'Microsoft.ContainerService/managedClusters@2024-09-02-preview' existing = {
  name: aks_name
}

resource scriptIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: 'deployment-script-identity-${uniqueString(resourceGroup().id)}'
  location: location
}

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

@description('Assign AKS Contributor role to the deployment script identity to access AKS.')
resource aksContributorRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(scriptIdentity.id, aksCluster.id, aksContributorRoleDefinitionId)
  scope: aksCluster
  properties: {
    principalId: scriptIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: aksContributorRoleDefinitionId
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
        name: 'AKS_SERVICE_ACCOUNT_NAME'
        value: aks_service_account_name
      }
      {
        name: 'DEPLOY_AOAI'
        value: string(deployAoai)
      }
      {
        name: 'AOAI_ENDPOINT'
        value: aoai_endpoint
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
        value: aoai_llm_model_version
      }
      {
        name: 'AOAI_EMBEDDING_MODEL'
        value: aoai_embedding_model
      }
      {
        name: 'AOAI_EMBEDDING_MODEL_DEPLOYMENT_NAME'
        value: aoai_embedding_model_deployment_name
      }
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
