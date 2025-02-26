// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

@description('The name of the CosmosDB resource.')
param cosmosDbName string

@description('The location of the CosmosDB resource.')
param location string = resourceGroup().location

@allowed(['Enabled', 'Disabled'])
param publicNetworkAccess string = 'Disabled'

var maxThroughput = 1000

resource cosmosDb 'Microsoft.DocumentDB/databaseAccounts@2024-11-15' = {
  name: cosmosDbName
  location: location
  tags: {
    defaultExperience: 'Core (SQL)'
    'hidden-cosmos-mmspecial': ''
  }
  kind: 'GlobalDocumentDB'
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    publicNetworkAccess: publicNetworkAccess
    enableAutomaticFailover: false
    enableMultipleWriteLocations: false
    isVirtualNetworkFilterEnabled: false
    virtualNetworkRules: []
    disableKeyBasedMetadataWriteAccess: false
    enableFreeTier: false
    enableAnalyticalStorage: false
    analyticalStorageConfiguration: {
      schemaType: 'WellDefined'
    }
    databaseAccountOfferType: 'Standard'
    defaultIdentity: 'FirstPartyIdentity'
    networkAclBypass: 'None'
    disableLocalAuth: true
    enablePartitionMerge: false
    minimalTlsVersion: 'Tls12'
    consistencyPolicy: {
      defaultConsistencyLevel: 'Session'
      maxIntervalInSeconds: 5
      maxStalenessPrefix: 100
    }
    locations: [
      {
        locationName: location
        failoverPriority: 0
        isZoneRedundant: false
      }
    ]
    cors: []
    capabilities: []
    ipRules: []
    backupPolicy: {
      type: 'Periodic'
      periodicModeProperties: {
        backupIntervalInMinutes: 240
        backupRetentionIntervalInHours: 8
        backupStorageRedundancy: 'Geo'
      }
    }
    networkAclBypassResourceIds: []
    capacity: {
      totalThroughputLimit: maxThroughput
    }
  }
}

// create a single database that is used to maintain state information for graphrag indexing
// NOTE: The current CosmosDB role assignments are not sufficient to allow the aks workload identity to create databases so we must do it in bicep at deployment time.
// TODO: Identify and assign appropriate RBAC roles that allow the workload identity to create new databases instead of relying on this bicep implementation.
resource graphragDatabase 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2024-11-15' = {
  parent: cosmosDb
  name: 'graphrag'
  properties: {
    options: {
      autoscaleSettings: {
        maxThroughput: maxThroughput
      }
    }
    resource: {
      id: 'graphrag'
    }
  }
}

output name string = cosmosDb.name
output id string = cosmosDb.id
output endpoint string = cosmosDb.properties.documentEndpoint
