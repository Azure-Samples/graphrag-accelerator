@description('Name of the Azure OpenAI instance')
param openAiName string

@description('Location for the Azure OpenAI instance')
param location string = resourceGroup().location

@description('LLM model name')
param llmModelName string = 'gpt-4o'

@description('LLM model deployment name')
param llmModelDeploymentName string = 'gpt-4o'

@description('LLM Model API version')
param llmModelVersion string

@description('Embedding model name')
param embeddingModelName string = 'text-embedding-ada-002'

@description('Embedding model deployment name')
param embeddingModelDeploymentName string = 'text-embedding-ada-002'

@description('Embedding Model API version')
param embeddingModelVersion string

@description('TPM quota for the LLM model (x1000)')
param llmTpmQuota int = 1

@description('TPM quota for the embedding model (x1000)')
param embeddingTpmQuota int = 1

resource aoai 'Microsoft.CognitiveServices/accounts@2024-10-01' = {
  name: openAiName
  location: location
  sku: {
    name: 'S0'
  }
  kind: 'OpenAI'
  properties: {
    publicNetworkAccess: 'Enabled'
    disableLocalAuth: true
  }
}

resource llmDeployment 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = {
  parent: aoai
  name: llmModelDeploymentName // model deployment name
  sku: {
    name: 'GlobalStandard'
    capacity: llmTpmQuota
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: llmModelName // model name
      version: llmModelVersion
    }
    currentCapacity: llmTpmQuota
  }
}

resource embeddingDeployment 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = {
  parent: aoai
  name: embeddingModelDeploymentName // model deployment name
  // NOTE: simultaneous AOAI model deployments are not supported at this time. As a workaround, use dependsOn to force the models to get deployed sequentially.
  dependsOn: [llmDeployment]
  sku: {
    name: 'Standard'
    capacity: embeddingTpmQuota
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: embeddingModelName // model name
      version: embeddingModelVersion
    }
    currentCapacity: embeddingTpmQuota
  }
}

output name string = aoai.name
output id string = aoai.id
output endpoint string = aoai.properties.endpoint
output llmModel string = llmDeployment.properties.model.name
output llmModelDeploymentName string = llmDeployment.name
output llmModelQuota int = llmDeployment.sku.capacity
output llmModelVersion string = llmDeployment.apiVersion
output embeddingModel string = embeddingDeployment.properties.model.name
output embeddingModelDeploymentName string = embeddingDeployment.name
output embeddingModelQuota int = embeddingDeployment.sku.capacity
output embeddingModelVersion string = embeddingDeployment.apiVersion
