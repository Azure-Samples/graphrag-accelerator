// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

param privateDnsZoneName string
param vnetId string

resource privateDnsZone 'Microsoft.Network/privateDnsZones@2024-06-01' existing = {
  name: privateDnsZoneName
}

resource dnsVnetLinks 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2024-06-01' = {
  name: '${replace(privateDnsZoneName, '.', '-')}-${uniqueString(vnetId)}'
  parent: privateDnsZone
  location: 'global'
  properties: {
    registrationEnabled: false
    resolutionPolicy: 'Default'
    virtualNetwork: {
      id: vnetId
    }
  }
}
