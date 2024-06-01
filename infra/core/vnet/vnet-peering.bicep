// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

param name string
param vnetName string
param remoteVnetId string

param allowVirtualNetworkAccess bool = true
param allowForwardedTraffic bool = false
param allowGatewayTransit bool = false
param useRemoteGateways bool = false

resource vnet 'Microsoft.Network/virtualNetworks@2023-06-01' existing = {
  name: vnetName
}

resource vnetPeering 'Microsoft.Network/virtualNetworks/virtualNetworkPeerings@2023-06-01' = {
  name: name
  parent: vnet
  properties: {
    remoteVirtualNetwork: {
      id: remoteVnetId
    }
    allowVirtualNetworkAccess: allowVirtualNetworkAccess
    allowForwardedTraffic: allowForwardedTraffic
    allowGatewayTransit: allowGatewayTransit
    useRemoteGateways: useRemoteGateways
  }
}
