// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

@description('The name of the private DNS zone.')
param name string

@description('The name of the virtual networks the DNS zone should be associated with.')
param vnetNames string[]

resource dnsZone 'Microsoft.Network/privateDnsZones@2020-06-01' = {
  name: name
  location: 'global'
  properties: {}
}

resource vnets 'Microsoft.Network/virtualNetworks@2024-01-01' existing = [
  for vnetName in vnetNames: {
    name: vnetName
  }
]

resource dnsZoneLinks 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2020-06-01' = [
  for (vnetName, index) in vnetNames: {
    name: vnetName
    location: 'global'
    parent: dnsZone
    properties: {
      registrationEnabled: false
      virtualNetwork: {
        id: vnets[index].id
      }
    }
  }
]

output name string = dnsZone.name
output id string = dnsZone.id
