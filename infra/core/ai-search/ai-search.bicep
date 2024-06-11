// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

@description('The name of the AI Search instance.')
param name string

@description('The location of the Managed Cluster resource.')
param location string = resourceGroup().location

@description('Array of objects with fields principalId, principalType, roleDefinitionId')
param roleAssignments array = []

resource aiSearch 'Microsoft.Search/searchServices@2024-03-01-preview' = {
  name: name
  location: location
  sku: {
    name: 'standard'
  }
  properties: {
    disableLocalAuth: true
    replicaCount: 1
    partitionCount: 1
    publicNetworkAccess: 'disabled'
    semanticSearch: 'disabled'
  }
}

resource roleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = [
  for roleAssignment in roleAssignments: {
    name: guid('${roleAssignment.principalId}-${roleAssignment.principalType}-${roleAssignment.roleDefinitionId}')
    scope: aiSearch
    properties: roleAssignment
  }
]

output id string = aiSearch.id
output name string = aiSearch.name
