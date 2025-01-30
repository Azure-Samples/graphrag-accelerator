// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

@description('ID of the service principal to assign the RBAC roles to.')
param principalId string

@description('Type of principal to assign the RBAC roles to.')
@allowed(['ServicePrincipal', 'User', 'Group', 'Device', 'ForeignGroup'])
param principalType string

@description('Name of an existing CosmosDB resource.')
param cosmosDbName string

@description('Role definitions for various roles that will be assigned at deployment time. Learn more: https://learn.microsoft.com/en-us/azure/role-based-access-control/built-in-roles')
var roleDefinitions = [
  {
    id: 'ba92f5b4-2d11-453d-a403-e96b0029c9fe' // Storage Blob Data Contributor Role
  }
  {
    id: 'b24988ac-6180-42a0-ab88-20f7382dd24c' // AI Search Contributor Role
  }
  {
    id: '8ebe5a00-799e-43f5-93ac-243d3dce84a7' // AI Search Index Data Contributor Role
  }
  {
    id: '1407120a-92aa-4202-b7e9-c0e197c71c8f' // AI Search Index Data Reader Role
  }
  {
    id: 'a001fd3d-188f-4b5d-821b-7da978bf7442' // Cognitive Services OpenAI Contributor
  }
  {
    id: '3913510d-42f4-4e42-8a64-420c390055eb' // Monitoring Metrics Publisher Role
  }
]

resource roleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = [
  for roleDef in roleDefinitions: {
    // note: the guid must be globally unique and deterministic (reproducible) across Azure
    name: guid(subscription().subscriptionId, resourceGroup().name, principalId, principalType, roleDef.id)
    scope: resourceGroup()
    properties: {
      principalId: principalId
      principalType: principalType
      roleDefinitionId: resourceId('Microsoft.Authorization/roleDefinitions', roleDef.id)
    }
  }
]

resource cosmosDb 'Microsoft.DocumentDB/databaseAccounts@2024-12-01-preview' existing = {
  name: cosmosDbName
}

var customRoleName = 'Custom cosmosDB role for graphrag - adds read/write permissions at the database and container level'
resource customCosmosRoleDefinition 'Microsoft.DocumentDB/databaseAccounts/sqlRoleDefinitions@2024-12-01-preview' = {
  // note: the guid must be globally unique and deterministic (reproducible) across Azure
  name: guid(subscription().subscriptionId, resourceGroup().name, cosmosDb.id, customRoleName) // guid is used to ensure uniqueness
  parent: cosmosDb
  properties: {
    roleName: customRoleName
    type: 'CustomRole'
    assignableScopes: [
      cosmosDb.id
    ]
    permissions: [
      {
        dataActions: [
          'Microsoft.DocumentDB/databaseAccounts/readMetadata'
          'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers/*'
          'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers/items/*'
          'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/write'
        ]
      }
    ]
  }
}

resource assignment 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2024-12-01-preview' = {
  // note: the guid must be globally unique and deterministic (reproducible) across Azure
  name: guid(
    subscription().subscriptionId,
    resourceGroup().name,
    cosmosDb.id,
    customCosmosRoleDefinition.id,
    principalId
  )
  parent: cosmosDb
  properties: {
    principalId: principalId
    roleDefinitionId: customCosmosRoleDefinition.id
    scope: cosmosDb.id
  }
}
