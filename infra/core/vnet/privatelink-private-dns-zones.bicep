// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

@description('The virtual network ID to link to')
param linkedVnetId string

var privateDnsZoneData = loadJsonContent('private-dns-zone-groups.json') // for more information: https://learn.microsoft.com/en-us/azure/azure-government/compare-azure-government-global-azure
var cloudName = toLower(environment().name)

var aiSearchPrivateDnsZoneName = privateDnsZoneData[cloudName].aiSearch
var blobStoragePrivateDnsZoneName = privateDnsZoneData[cloudName].blobStorage
var cosmosDbPrivateDnsZoneName = privateDnsZoneData[cloudName].cosmosDb
var storagePrivateDnsZoneNames = [blobStoragePrivateDnsZoneName]
var azureMonitorPrivateDnsZones = privateDnsZoneData[cloudName].azureMonitor

var privateDnsZones = union(
  azureMonitorPrivateDnsZones,
  storagePrivateDnsZoneNames,
  [cosmosDbPrivateDnsZoneName],
  [aiSearchPrivateDnsZoneName]
)

resource privateDnsZoneResources 'Microsoft.Network/privateDnsZones@2024-06-01' = [
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
      vnetId: linkedVnetId
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

output cosmosDbPrivateDnsZoneConfigs array = [
  {
    name: privateDnsZoneResources[indexOf(privateDnsZones, cosmosDbPrivateDnsZoneName)].name
    properties: {
      #disable-next-line use-resource-id-functions
      privateDnsZoneId: privateDnsZoneResources[indexOf(privateDnsZones, cosmosDbPrivateDnsZoneName)].id
    }
  }
]

output aiSearchPrivateDnsZoneConfigs array = [
  {
    name: privateDnsZoneResources[indexOf(privateDnsZones, aiSearchPrivateDnsZoneName)].name
    properties: {
      #disable-next-line use-resource-id-functions
      privateDnsZoneId: privateDnsZoneResources[indexOf(privateDnsZones, aiSearchPrivateDnsZoneName)].id
    }
  }
]

output privateDnsZones array = privateDnsZones
