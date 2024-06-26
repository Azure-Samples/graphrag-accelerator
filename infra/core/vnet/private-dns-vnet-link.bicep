param privateDnsZoneName string

param vnetResourceIds array

resource dnsZone 'Microsoft.Network/privateDnsZones@2020-06-01' = {
  name: privateDnsZoneName
  location: 'global'
  properties: {}
}

resource dnsZoneLinks 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2020-06-01' = [
  for vnetId in vnetResourceIds: {
    name: uniqueString(vnetId)
    location: 'global'
    parent: dnsZone
    properties: {
      registrationEnabled: false
      virtualNetwork: {
        id: vnetId
      }
    }
  }
]
