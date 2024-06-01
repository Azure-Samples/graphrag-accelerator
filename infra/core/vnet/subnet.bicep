// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

@description('The name of the new subnet')
param name string
@description('The name of the virtual network the subnet should be created in')
param vnetName string

param addressPrefix string

resource vnet 'Microsoft.Network/virtualNetworks@2023-06-01' existing = {
  name: vnetName
}

resource subnet 'Microsoft.Network/virtualNetworks/subnets@2023-04-01' = {
  name: name
  parent: vnet
  properties: {
    addressPrefix: addressPrefix
  }
}

output id string = subnet.id
