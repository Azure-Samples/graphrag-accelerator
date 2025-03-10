// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

@description('The name of the AI Search instance.')
param name string

@description('The location of the Managed Cluster resource.')
param location string = resourceGroup().location

@allowed(['enabled', 'disabled'])
param publicNetworkAccess string = 'enabled'

resource search 'Microsoft.Search/searchServices@2024-06-01-preview' = {
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
    networkRuleSet: {
      ipRules: []
      bypass: 'AzureServices'
    }
    semanticSearch: 'disabled'
  }
}

output name string = search.name
output id string = search.id
