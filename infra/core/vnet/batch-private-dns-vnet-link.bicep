@description('The resource id of the vnet.')
param vnetId string
@description('The name of the private DNS zone.')
param privateDnsZoneNames array

module privateDnsVnetLinks 'private-dns-vnet-link.bicep' = [
  for (privateDnsZoneName, i) in privateDnsZoneNames: {
    name: '${privateDnsZoneName}-vnet-link-${i}'
    params: {
      vnetId: vnetId
      privateDnsZoneName: privateDnsZoneName
    }
  }
]
