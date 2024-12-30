// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

@description('The name of the CosmosDB resource.')
param cosmosDbName string

@description('The location of the CosmosDB resource.')
param location string = resourceGroup().location

@allowed([ 'Enabled', 'Disabled' ])
param publicNetworkAccess string = 'Disabled'

@description('Role definition id to assign to the principal. Learn more: https://learn.microsoft.com/en-us/azure/cosmos-db/how-to-setup-rbac')
@allowed([
  '00000000-0000-0000-0000-000000000001' // 'Cosmos DB Built-in Data Reader' role
  '00000000-0000-0000-0000-000000000002' // 'Cosmos DB Built-in Data Contributor' role
])
param roleDefinitionId string = '00000000-0000-0000-0000-000000000002'

param principalId string


resource cosmosDb 'Microsoft.DocumentDB/databaseAccounts@2022-11-15' = {
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
      totalThroughputLimit: 4000
    }
  }
}

resource graphragDatabase 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2022-11-15' = {
  parent: cosmosDb
  name: 'graphrag'
  properties: {
    resource: {
      id: 'graphrag'
    }
  }
}

resource jobsContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2022-11-15' = {
  parent: graphragDatabase
  name: 'jobs'
  properties: {
    resource: {
      id: 'jobs'
      indexingPolicy: {
        indexingMode: 'consistent'
        automatic: true
        includedPaths: [
          {
            path: '/*'
          }
        ]
        excludedPaths: [
          {
            path: '/"_etag"/?'
          }
        ]
      }
      partitionKey: {
        paths: [
          '/id'
        ]
        kind: 'Hash'
        version: 2
      }
      uniqueKeyPolicy: {
        uniqueKeys: []
      }
      conflictResolutionPolicy: {
        mode: 'LastWriterWins'
        conflictResolutionPath: '/_ts'
      }
    }
  }
}

resource containerStoreContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2022-11-15' = {
  parent: graphragDatabase
  name: 'container-store'
  properties: {
    resource: {
      id: 'container-store'
      indexingPolicy: {
        indexingMode: 'consistent'
        automatic: true
        includedPaths: [
          {
            path: '/*'
          }
        ]
        excludedPaths: [
          {
            path: '/"_etag"/?'
          }
        ]
      }
      partitionKey: {
        paths: [
          '/id'
        ]
        kind: 'Hash'
        version: 2
      }
      uniqueKeyPolicy: {
        uniqueKeys: []
      }
      conflictResolutionPolicy: {
        mode: 'LastWriterWins'
        conflictResolutionPath: '/_ts'
      }
    }
  }
}

resource sqlRoleAssignment 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2023-11-15' = {
  name: guid('${roleDefinitionId}-${principalId}-${cosmosDb.id}')
  parent: cosmosDb
  properties: {
    roleDefinitionId: '/${subscription().id}/resourceGroups/${resourceGroup().name}/providers/Microsoft.DocumentDB/databaseAccounts/${cosmosDb.name}/sqlRoleDefinitions/${roleDefinitionId}'
    principalId: principalId
    scope: cosmosDb.id
  }
}

output name string = cosmosDb.name
output id string = cosmosDb.id
output endpoint string = cosmosDb.properties.documentEndpoint
