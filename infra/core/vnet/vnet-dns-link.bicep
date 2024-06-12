param privateDnsZoneName string

param vnetResourceIds array

resource privateDnsZone 'Microsoft.Network/privateDnsZones@2020-06-01' existing = {
  name: privateDnsZoneName
}

resource dnsVnetLinks 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2020-06-01' = [
  for vnetId in vnetResourceIds: {
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
