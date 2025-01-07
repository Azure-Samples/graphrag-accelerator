// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

param privateLinkScopeName string
param privateLinkScopedResources array = []
param queryAccessMode string = 'Open'
param ingestionAccessMode string = 'PrivateOnly'

resource privateLinkScope 'microsoft.insights/privateLinkScopes@2021-07-01-preview' = {
  name: privateLinkScopeName
  location: 'global'
  properties: {
    accessModeSettings: {
      queryAccessMode: queryAccessMode
      ingestionAccessMode: ingestionAccessMode
    }
  }
}

resource scopedResources 'microsoft.insights/privateLinkScopes/scopedResources@2021-07-01-preview' = [
  for id in privateLinkScopedResources: {
    name: uniqueString(id)
    parent: privateLinkScope
    properties: {
      linkedResourceId: id
    }
  }
]

output name string = privateLinkScope.name
output id string = privateLinkScope.id
