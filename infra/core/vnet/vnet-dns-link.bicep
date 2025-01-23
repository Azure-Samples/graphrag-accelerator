// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

param privateDnsZoneName string
param vnetIds array

resource privateDnsZone 'Microsoft.Network/privateDnsZones@2020-06-01' existing = {
  name: privateDnsZoneName
}

resource dnsVnetLinks 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2020-06-01' = [
  for vnetId in vnetIds: {
    name: '${replace(privateDnsZoneName, '.', '-')}-${uniqueString(vnetId)}'
    parent: privateDnsZone
    location: 'global'
    properties: {
      virtualNetwork: {
        id: vnetId
      }
      registrationEnabled: false
    }
  }
]
