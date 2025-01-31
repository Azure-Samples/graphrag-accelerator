@description('Name of the Azure OpenAI instance')
param openAiName string = 'openai${uniqueString(resourceGroup().id)}'

@description('Location for the Azure OpenAI instance')
param location string = resourceGroup().location

@description('LLM model name')
param llmModelName string = 'gpt-4o'

@description('LLM Model API version')
param llmModelVersion string

@description('Embedding model name')
param embeddingModelName string = 'text-embedding-ada-002'

@description('Embedding Model API version')
param embeddingModelVersion string

@description('TPM quota for llm model deployment (x1000)')
param llmTpmQuota int = 10

@description('TPM quota for embedding model deployment (x1000)')
param embeddingTpmQuota int = 10

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
  name: llmModelName
  sku: {
    name: 'GlobalStandard'
    capacity: llmTpmQuota
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: llmModelName
      version: llmModelVersion
    }
    currentCapacity: llmTpmQuota
  }
}

resource embeddingDeployment 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = {
  parent: aoai
  name: embeddingModelName
  // NOTE: simultaneous model deployments are not supported at this time. As a workaround, use dependsOn to force the models to be deployed in a sequential manner.
  dependsOn: [llmDeployment]
  sku: {
    name: 'Standard'
    capacity: embeddingTpmQuota
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: embeddingModelName
      version: embeddingModelVersion
    }
    currentCapacity: embeddingTpmQuota
  }
}

output openAiEndpoint string = aoai.properties.endpoint
output llmModel string = llmDeployment.properties.model.name
output llmModelDeploymentName string = llmDeployment.name
output llmModelApiVersion string = llmDeployment.apiVersion
output textEmbeddingModel string = embeddingDeployment.properties.model.name
output textEmbeddingModelDeploymentName string = embeddingDeployment.name
output textEmbeddingModelApiVersion string = embeddingDeployment.apiVersion
