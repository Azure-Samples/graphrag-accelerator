@description('Name of the Azure OpenAI instance')
param openAiName string = 'openai${uniqueString(resourceGroup().id)}'

@description('Location for the Azure OpenAI instance')
param location string = resourceGroup().location

@description('LLM model deployment name')
param llmModelDeploymentName string = 'gpt-4o'

@description('Embedding model deployment name')
param embeddingModelDeploymentName string = 'text-embedding-ada-002'

@description('TPM quota for GPT-4o deployment')
param gpt4oTpm int = 10

@description('TPM quota for text-embedding-ada-002 deployment')
param textEmbeddingAdaTpm int = 10

@description('Array of objects with fields principalId, roleDefinitionId')
param roleAssignments array = []


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

resource gpt4oDeployment 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = {
  parent: aoai
  name: llmModelDeploymentName
  sku: {
    name: 'GlobalStandard'
    capacity: gpt4oTpm
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: 'gpt-4o'
      version: '2024-05-13'
    }
    currentCapacity: gpt4oTpm
  }
}

resource textEmbeddingAdaDeployment 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = {
  parent: aoai
  name: embeddingModelDeploymentName
  sku: {
    name: 'Standard'
    capacity: textEmbeddingAdaTpm
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: 'text-embedding-ada-002'
      version: '2'
    }
    currentCapacity: textEmbeddingAdaTpm
  }
}

resource roleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = [
  for role in roleAssignments: {
    name: guid('${role.principalId}-${role.roleDefinitionId}')
    scope: resourceGroup()
    properties: role
  }
]

output openAiEndpoint string = aoai.properties.endpoint
output gpt4oDeploymentName string = gpt4oDeployment.name
output textEmbeddingAdaDeploymentName string = textEmbeddingAdaDeployment.name
