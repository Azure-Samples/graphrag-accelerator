// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

param vnetId string
param privateDnsZoneName string
var vnet_id_hash = uniqueString(vnetId)

resource dnsZone 'Microsoft.Network/privateDnsZones@2020-06-01' = {
  name: privateDnsZoneName
  location: 'global'
  properties: {}
}

resource dnsZoneLinks 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2020-06-01' = {
  name: 'vnet-link-${privateDnsZoneName}-${vnet_id_hash}' // uniqueString(vnetId)
  location: 'global'
  parent: dnsZone
  properties: {
    registrationEnabled: false
    virtualNetwork: {
      id: vnetId
    }
  }
}

output vnet_id_hash string = vnet_id_hash
