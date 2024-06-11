var blobStoragePrivateDnsZoneName = 'privatelink.blob.${environment().suffixes.storage}'
var queueStoragePrivateDnsZoneName = 'privatelink.queue.${environment().suffixes.storage}'
var cosmosDbPrivateDnsZoneName = 'privatelink.documents.azure.com'
var storagePrivateDnsZoneNames = [blobStoragePrivateDnsZoneName, queueStoragePrivateDnsZoneName]

var cloudName = toLower(environment().name)
var privateDnsZoneData = loadJsonContent('private-dns-zone-groups.json')

var azureMonitorPrivateDnsZones = privateDnsZoneData[cloudName].azureMonitor

var privateDnsZones = union(azureMonitorPrivateDnsZones, storagePrivateDnsZoneNames, [cosmosDbPrivateDnsZoneName])

@description('Virtual Network IDs to link to')
param linkedVnetResourceIds array

resource privateDnsZoneResources 'Microsoft.Network/privateDnsZones@2020-06-01' = [
  for name in privateDnsZones: {
    name: name
    location: 'global'
  }
]

module dnsVnetLinks 'vnet-dns-link.bicep' = [
  for (privateDnsZoneName, index) in privateDnsZones: {
    name: replace(privateDnsZoneName, '.', '-')
    params: {
      privateDnsZoneName: privateDnsZoneResources[index].name
      vnetResourceIds: linkedVnetResourceIds
    }
  }
]

output azureMonitorPrivateDnsZoneConfigs array = [
  for zoneName in union(azureMonitorPrivateDnsZones, [blobStoragePrivateDnsZoneName]): {
    name: privateDnsZoneResources[indexOf(privateDnsZones, zoneName)].name
    properties: {
      #disable-next-line use-resource-id-functions
      privateDnsZoneId: privateDnsZoneResources[indexOf(privateDnsZones, zoneName)].id
    }
  }
]

output blobStoragePrivateDnsZoneConfigs array = [
  {
    name: blobStoragePrivateDnsZoneName
    properties: {
      #disable-next-line use-resource-id-functions
      privateDnsZoneId: privateDnsZoneResources[indexOf(privateDnsZones, blobStoragePrivateDnsZoneName)].id
    }
  }
]

output queueStoragePrivateDnsZoneConfigs array = [
  {
    name: queueStoragePrivateDnsZoneName
    properties: {
      #disable-next-line use-resource-id-functions
      privateDnsZoneId: privateDnsZoneResources[indexOf(privateDnsZones, queueStoragePrivateDnsZoneName)].id
    }
  }
]

output cosmosDbPrivateDnsZoneConfigs array = [
  {
    name: privateDnsZoneResources[indexOf(privateDnsZones, cosmosDbPrivateDnsZoneName)].name
    properties: {
      #disable-next-line use-resource-id-functions
      privateDnsZoneId: privateDnsZoneResources[indexOf(privateDnsZones, cosmosDbPrivateDnsZoneName)].id
    }
  }
]

output privateDnsZones array = privateDnsZones
