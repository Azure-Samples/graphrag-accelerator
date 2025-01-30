// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

@description('The name of the Storage Account resource.')
param name string

@description('The location of the Storage Account resource.')
param location string = resourceGroup().location

@allowed(['Hot', 'Cool', 'Premium'])
param accessTier string = 'Hot'

@allowed(['AzureDnsZone', 'Standard'])
param dnsEndpointType string = 'Standard'

@allowed(['Enabled', 'Disabled'])
param publicNetworkAccess string = 'Disabled'

param tags object = {}
param allowBlobPublicAccess bool = false
param allowCrossTenantReplication bool = true
param allowSharedKeyAccess bool = false
param defaultToOAuthAuthentication bool = false
param deleteRetentionPolicy object = {}
param kind string = 'StorageV2'
param minimumTlsVersion string = 'TLS1_2'
param containers array = []

resource storage 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: name
  location: location
  tags: tags
  kind: kind
  sku: { name: 'Standard_LRS' }
  properties: {
    accessTier: accessTier
    allowBlobPublicAccess: allowBlobPublicAccess
    allowCrossTenantReplication: allowCrossTenantReplication
    allowSharedKeyAccess: allowSharedKeyAccess
    defaultToOAuthAuthentication: defaultToOAuthAuthentication
    dnsEndpointType: dnsEndpointType
    isHnsEnabled: true
    minimumTlsVersion: minimumTlsVersion
    networkAcls: {
      bypass: 'AzureServices'
      defaultAction: 'Allow'
    }
    publicNetworkAccess: publicNetworkAccess
  }

  resource blobServices 'blobServices' = if (!empty(containers)) {
    name: 'default'
    properties: {
      deleteRetentionPolicy: deleteRetentionPolicy
    }
    resource container 'containers' = [
      for container in containers: {
        name: container.name
        properties: {
          publicAccess: container.?publicAccess ?? 'None'
        }
      }
    ]
  }
}

output name string = storage.name
output id string = storage.id
output primaryEndpoints object = storage.properties.primaryEndpoints
