@description('The name of the private DNS zone.')
param privateDnsZoneNames array

param vnetResourceIds array

module privateDnsVnetLinks 'private-dns-vnet-link.bicep' = [
  for (privateDnsZoneName, i) in privateDnsZoneNames: {
    name: '${privateDnsZoneName}-vnet-link-${i}'
    params: {
      privateDnsZoneName: privateDnsZoneName
      vnetResourceIds: vnetResourceIds
    }
  }
]
