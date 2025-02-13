param name string
param utcValue string
param location string
param subscriptionId string
param tenantid string
param acrserver string
param azure_location string
param azure_acr_login_server string
param azure_acr_name string
param azure_aks_name string
param azure_aks_controlplanefqdn string
param azure_aks_managed_rg string
param azure_aks_service_account_name string
param azure_apim_gateway_url string
param azure_apim_name string
param managed_identity_aks string
param ai_search_name string

param imagename string
param imageversion string
param script_file string


param azure_aoai_endpoint string
param azure_aoai_llm_model string
param azure_aoai_llm_model_deployment_name string
param azure_aoai_llm_model_api_version string
param azure_aoai_embedding_model string
param azure_aoai_embedding_model_deployment_name string
param azure_aoai_embedding_model_api_version string

param azure_app_hostname string
param azure_app_url string
param azure_app_insights_connection_string string

param azure_cosmosdb_endpoint string
param azure_cosmosdb_name string
param azure_cosmosdb_id string
param azure_dns_zone_name string


param azure_storage_account string
param azure_storage_account_blob_url string

param azure_workload_identity_client_id string
param azure_workload_identity_principal_id string
param  azure_workload_identity_name string
param cognitive_services_audience string = 'https://cognitiveservices.azure.com/default'
param public_storage_account_name string
param public_storage_account_key string

var clusterAdminRoleDefinitionId = resourceId('Microsoft.Authorization/roleDefinitions', '0ab0b1a8-8aac-4efd-b8c2-3ee1fb270be8')

// Resources
resource aksCluster 'Microsoft.ContainerService/managedClusters@2022-11-02-preview' existing = {
  name: azure_aks_name
}

resource managedIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: uniqueString(resourceGroup().id)
  location: location
}


resource clusterAdminContributorRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name:  guid(managed_identity_aks, aksCluster.id, clusterAdminRoleDefinitionId)
  scope: aksCluster
  properties: {
    roleDefinitionId: clusterAdminRoleDefinitionId
    principalId: managedIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource deploymentScript 'Microsoft.Resources/deploymentScripts@2020-10-01'= {
  name: name
  location: location
  kind: 'AzureCLI'
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${managedIdentity.id}': {}
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
        name: 'AZURE_SUBSCRIPTION_ID'
        value: subscriptionId
        }
        {
        name: 'AZURE_TENANT_ID'
        value: tenantid
        }
        {
        name: 'ACR_SERVER'
        value: acrserver
        }
        {
        name: 'AZURE_LOCATION'
        value: azure_location
        }
        {
        name: 'AZURE_ACR_LOGIN_SERVER'
        value: azure_acr_login_server
        }
        {
        name: 'AZURE_ACR_NAME'
        value: azure_acr_name
        }
        {
        name: 'AZURE_AKS_NAME'
        value: azure_aks_name
        }
        {
        name: 'AZURE_AKS_CONTROLPLANEFQDN'
        value: azure_aks_controlplanefqdn
        }
        {
        name: 'AZURE_AKS_MANAGED_RG'
        value: azure_aks_managed_rg
        }
        {
        name: 'AZURE_AKS_SERVICE_ACCOUNT_NAME'
        value: azure_aks_service_account_name
        }
        {
        name: 'AZURE_APIM_GATEWAY_URL'
        value: azure_apim_gateway_url
        }
        {
        name: 'AZURE_APIM_NAME'
        value: azure_apim_name
        }
        {
          name: 'MANAGED_IDENTITY_AKS'
          value: managed_identity_aks

        }
        {
          name: 'IMAGE_NAME'
          value: imagename
        }
        {
            name: 'IMAGE_VERSION'
            value: imageversion
        }
        {
          name: 'AI_SEARCH_NAME'
          value: ai_search_name
      }


      { 
        name: 'AZURE_AOAI_LLM_MODEL' 
        value: azure_aoai_llm_model 
      }
  { 
    name: 'AZURE_AOAI_LLM_MODEL_DEPLOYMENT_NAME'
    value: azure_aoai_llm_model_deployment_name 
  }
  { 
    name: 'AZURE_AOAI_LLM_MODEL_API_VERSION' 
    value: azure_aoai_llm_model_api_version 
  }
  { 
      name: 'AZURE_AOAI_EMBEDDING_MODEL' 
      value: azure_aoai_embedding_model 
  }
  { 
    name: 'AZURE_AOAI_EMBEDDING_MODEL_DEPLOYMENT_NAME'
    value: azure_aoai_embedding_model_deployment_name 
}
  { name: 'AZURE_AOAI_EMBEDDING_MODEL_API_VERSION'
  value: azure_aoai_embedding_model_api_version
}
  { name: 'AZURE_APP_HOSTNAME' 
  value: azure_app_hostname 
}
  { name: 'AZURE_APP_URL' 
  value: azure_app_url 
}
  { name: 'AZURE_APP_INSIGHTS_CONNECTION_STRING' 
  value: azure_app_insights_connection_string 
}
  { name: 'AZURE_COSMOSDB_ENDPOINT' 
  
  value: azure_cosmosdb_endpoint }
  { name: 'AZURE_COSMOSDB_NAME' 
  value: azure_cosmosdb_name
  }
  { name: 'AZURE_COSMOSDB_ID' 
  value: azure_cosmosdb_id 
}
  { name: 'AZURE_DNS_ZONE_NAME' 
  value: azure_dns_zone_name 
}
  { name: 'AZURE_STORAGE_ACCOUNT' 
  value: azure_storage_account 
}
  { name: 'AZURE_STORAGE_ACCOUNT_BLOB_URL' 
  value: azure_storage_account_blob_url 
}
  { 
    name: 'AZURE_WORKLOAD_IDENTITY_CLIENT_ID' 
  value: azure_workload_identity_client_id
}
  { 
    name: 'AZURE_WORKLOAD_IDENTITY_PRINCIPAL_ID'
  value: azure_workload_identity_principal_id 
}
  { 
    name: 'AZURE_WORKLOAD_IDENTITY_NAME'
  value: azure_workload_identity_name 
}
  { 
    name: 'COGNITIVE_SERVICES_AUDIENCE'
  value: cognitive_services_audience 
}
  {   
    name: 'AZURE_OPENAI_ENDPOINT'
  
    value: azure_aoai_endpoint 
  }

  {   
    name: 'AZURE_RESOURCE_GROUP'
  
    value: resourceGroup().name 
  }
        
    
      ]
    cleanupPreference: 'OnSuccess'
    retentionInterval: 'P1D'
    //primaryScriptUri: primaryScriptUri
    scriptContent:script_file
    }
    dependsOn: [
      aksCluster
    ]

}

