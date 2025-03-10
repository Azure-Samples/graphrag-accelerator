// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

@description('The name of the private DNS zone.')
param name string

@description('The name of the virtual networks the DNS zone should be associated with.')
param vnetName string

resource vnet 'Microsoft.Network/virtualNetworks@2024-05-01' existing = {
  name: vnetName
}

resource dnsZone 'Microsoft.Network/privateDnsZones@2024-06-01' = {
  name: name
  location: 'global'
  properties: {}
}

resource dnsZoneLinks 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2024-06-01' = {
  name: vnetName
  location: 'global'
  parent: dnsZone
  properties: {
    registrationEnabled: false
    virtualNetwork: {
      id: vnet.id
    }
  }
}

output name string = dnsZone.name
output id string = dnsZone.id
