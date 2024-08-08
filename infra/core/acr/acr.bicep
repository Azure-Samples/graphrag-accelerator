@description('The name of the Container Registry resource. Will be automatically generated if not provided.')
param registryName string

@description('The location of the Container Registry resource.')
param location string = resourceGroup().location

@description('Array of objects with fields principalId, principalType, roleDefinitionId')
param roleAssignments array = []

resource registry 'Microsoft.ContainerRegistry/registries@2023-11-01-preview' = {
  name: registryName
  location: location
  sku: {
    name: 'Standard'
  }
  properties: {
    adminUserEnabled: true
    encryption: {
      status: 'disabled'
    }
    dataEndpointEnabled: false
    publicNetworkAccess: 'Enabled'
    networkRuleBypassOptions: 'AzureServices'
    zoneRedundancy: 'Disabled'
    anonymousPullEnabled: false
    metadataSearch: 'Disabled'
  }
}

resource roleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = [
  for role in roleAssignments: {
    name: guid('${role.principalId}-${role.principalType}-${role.roleDefinitionId}')
    scope: registry
    properties: role
  }
]

output name string = registry.name
output id string = registry.id
output loginServer string = registry.properties.loginServer
