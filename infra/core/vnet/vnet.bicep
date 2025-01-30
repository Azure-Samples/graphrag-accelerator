// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

@description('Name of the vnet resource.')
param vnetName string

@description('Azure region where the resource will be deployed.')
param location string = resourceGroup().location

@description('Optional prefix to prepend to subnet names.')
param subnetPrefix string = 'snet-'

@description('APIM tier - used to determine if subnet delegations are required.')
@allowed(['Developer', 'StandardV2'])
param apimTier string

@description('NSG resource ID.')
param nsgID string

resource vnet 'Microsoft.Network/virtualNetworks@2024-01-01' = {
  name: vnetName
  location: location
  properties: {
    addressSpace: {
      addressPrefixes: [
        '10.1.0.0/16'
      ]
    }
    subnets: [
      {
        name: '${subnetPrefix}apim'
        properties: {
          addressPrefix: '10.1.0.0/24'
          networkSecurityGroup: {
            id: nsgID
          }
          delegations: (apimTier == 'Developer')
            ? []
            : [
                {
                  name: 'Microsoft.Web/serverFarms'
                  properties: {
                    serviceName: 'Microsoft.Web/serverFarms'
                  }
                }
              ]
        }
      }
      {
        name: '${subnetPrefix}aks'
        properties: {
          addressPrefix: '10.1.1.0/24'
          serviceEndpoints: [
            {
              service: 'Microsoft.Storage'
            }
            {
              service: 'Microsoft.Sql'
            }
            {
              service: 'Microsoft.EventHub'
            }
          ]
        }
      }
    ]
  }
}

output vnetId string = vnet.id
output vnetName string = vnet.name
output apimSubnetId string = vnet.properties.subnets[0].id
output aksSubnetId string = vnet.properties.subnets[1].id
