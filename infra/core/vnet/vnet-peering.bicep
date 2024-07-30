// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

param vnet1Name string
param vnet2Name string
param allowVirtualNetworkAccess bool = true
param allowForwardedTraffic bool = false
param allowGatewayTransit bool = false
param useRemoteGateways bool = false


resource vnet1 'Microsoft.Network/virtualNetworks@2024-01-01' existing = {
  name: vnet1Name
}

resource vnet2 'Microsoft.Network/virtualNetworks@2024-01-01' existing = {
  name: vnet2Name
}

resource vnet1ToVnet2Peering 'Microsoft.Network/virtualNetworks/virtualNetworkPeerings@2024-01-01' = {
  name: '${vnet1.name}-to-${vnet2.name}'
  parent: vnet1
  properties: {
    remoteVirtualNetwork: {
      id: vnet2.id
    }
    allowVirtualNetworkAccess: allowVirtualNetworkAccess
    allowForwardedTraffic: allowForwardedTraffic
    allowGatewayTransit: allowGatewayTransit
    useRemoteGateways: useRemoteGateways
  }
}

resource vnet2ToVnet1Peering 'Microsoft.Network/virtualNetworks/virtualNetworkPeerings@2024-01-01' = {
  name: '${vnet2.name}-to-${vnet1.name}'
  parent: vnet2
  properties: {
    remoteVirtualNetwork: {
      id: vnet1.id
    }
    allowVirtualNetworkAccess: allowVirtualNetworkAccess
    allowForwardedTraffic: allowForwardedTraffic
    allowGatewayTransit: allowGatewayTransit
    useRemoteGateways: useRemoteGateways
  }
}
