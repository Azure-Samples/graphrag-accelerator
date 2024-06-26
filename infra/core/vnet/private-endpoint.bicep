@description('Resource ID of service the private endpoint is for')
param privateLinkServiceId string

param privateEndpointName string

@description('The resource ID of the subnet to deploy the private endpoint to')
param subnetId string

param groupId string

param location string = resourceGroup().location

@description('map of group id to array of private dns zone configs to associate with the private endpoint')
param privateDnsZoneConfigs array

resource privateEndpoint 'Microsoft.Network/privateEndpoints@2021-05-01' = {
  name: privateEndpointName
  location: location
  properties: {
    privateLinkServiceConnections: [
      {
        name: privateEndpointName
        properties: {
          privateLinkServiceId: privateLinkServiceId
          groupIds: [groupId]
        }
      }
    ]
    subnet: {
      id: subnetId
    }
  }
}

resource privateDnsZoneGroup 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2021-05-01' = {
  name: groupId
  parent: privateEndpoint
  properties: {
    privateDnsZoneConfigs: privateDnsZoneConfigs
  }
}
