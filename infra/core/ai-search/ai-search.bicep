// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

@description('The name of the AI Search instance.')
param name string

@description('The location of the Managed Cluster resource.')
param location string = resourceGroup().location

@allowed(['enabled', 'disabled'])
param publicNetworkAccess string = 'enabled'

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
    publicNetworkAccess: publicNetworkAccess
    semanticSearch: 'disabled'
  }
}

output name string = aiSearch.name
output id string = aiSearch.id
