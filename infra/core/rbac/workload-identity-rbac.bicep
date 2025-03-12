// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

@description('ID of the service principal to assign the RBAC roles to.')
param principalId string

@description('Type of principal to assign the RBAC roles to.')
@allowed(['ServicePrincipal', 'User', 'Group', 'Device', 'ForeignGroup'])
param principalType string

@description('Name of an existing AI Search resource.')
param aiSearchName string

@description('Name of an existing AppInsights resource.')
param appInsightsName string

@description('Name of an existing CosmosDB resource.')
param cosmosDbName string

@description('Name of an existing Azure Storage resource.')
param storageName string

@description('Role definitions for various roles that will be assigned. Learn more: https://learn.microsoft.com/en-us/azure/role-based-access-control/built-in-roles')
var roleIds = {
  contributor: 'b24988ac-6180-42a0-ab88-20f7382dd24c' // Contributor Role
  aiSearchIndexDataContributor: '8ebe5a00-799e-43f5-93ac-243d3dce84a7' // AI Search Index Data Contributor Role
  aiSearchIndexDataReader: '1407120a-92aa-4202-b7e9-c0e197c71c8f' // AI Search Index Data Reader Role
  cognitiveServicesOpenAIContributor: 'a001fd3d-188f-4b5d-821b-7da978bf7442' // Cognitive Services OpenAI Contributor Role
  cosmosDBOperator: '230815da-be43-4aae-9cb4-875f7bd000aa' // Cosmos DB Operator Role - cosmos control plane operations
  cosmosDbBuiltInDataContributor: '00000000-0000-0000-0000-000000000002' // Cosmos Built-in Data Contributor Role - cosmos data plane operations
  documentDBAccountContributor: '5bd9cd88-fe45-4216-938b-f97437e15450' // DocumentDB Account Contributor Role - cosmos control plane operations
  monitoringMetricsPublisher: '3913510d-42f4-4e42-8a64-420c390055eb' // Monitoring Metrics Publisher Role
  storageBlobDataContributor: 'ba92f5b4-2d11-453d-a403-e96b0029c9fe' // Storage Blob Data Contributor Role
  sqlDBContributor: '9b7fa17d-e63e-47b0-bb0a-15c516ac86ec' // SQL DB Contributor Role - cosmos control plane operations
}

// get references to existing resources
resource aiSearch 'Microsoft.Search/searchServices@2024-03-01-preview' existing = {
  name: aiSearchName
}
resource appInsights 'Microsoft.Insights/components@2020-02-02' existing = {
  name: appInsightsName
}
resource cosmosDb 'Microsoft.DocumentDB/databaseAccounts@2024-11-15' existing = {
  name: cosmosDbName
}
resource storage 'Microsoft.Storage/storageAccounts@2023-01-01' existing = {
  name: storageName
}

// make RBAC role assignments to each resource
resource contributorRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  // note: the guid must be globally unique and deterministic across Azure
  name: guid(aiSearch.id, principalId, principalType, roleIds.contributor)
  scope: aiSearch
  properties: {
    principalId: principalId
    principalType: principalType
    roleDefinitionId: resourceId('Microsoft.Authorization/roleDefinitions', roleIds.contributor)
  }
}

resource cognitiveServicesOpenAIContributorRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  // note: the guid must be globally unique and deterministic across Azure
  name: guid(resourceGroup().id, principalId, principalType, roleIds.cognitiveServicesOpenAIContributor)
  scope: resourceGroup()
  properties: {
    principalId: principalId
    principalType: principalType
    roleDefinitionId: resourceId('Microsoft.Authorization/roleDefinitions', roleIds.cognitiveServicesOpenAIContributor)
  }
}

resource aiSearchIndexDataContributorRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  // note: the guid must be globally unique and deterministic across Azure
  name: guid(aiSearch.id, principalId, principalType, roleIds.aiSearchIndexDataContributor)
  scope: aiSearch
  properties: {
    principalId: principalId
    principalType: principalType
    roleDefinitionId: resourceId('Microsoft.Authorization/roleDefinitions', roleIds.aiSearchIndexDataContributor)
  }
}

resource aiSearchIndexDataReaderRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  // note: the guid must be globally unique and deterministic across Azure
  name: guid(aiSearch.id, principalId, principalType, roleIds.aiSearchIndexDataReader)
  scope: aiSearch
  properties: {
    principalId: principalId
    principalType: principalType
    roleDefinitionId: resourceId('Microsoft.Authorization/roleDefinitions', roleIds.aiSearchIndexDataReader)
  }
}

resource cosmosDbOperatorRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  // note: the guid must be globally unique and deterministic across Azure
  name: guid(cosmosDb.id, principalId, principalType, roleIds.cosmosDBOperator)
  scope: cosmosDb
  properties: {
    principalId: principalId
    principalType: principalType
    roleDefinitionId: resourceId('Microsoft.Authorization/roleDefinitions', roleIds.cosmosDBOperator)
  }
}

resource documentDbAccountContributorRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  // note: the guid must be globally unique and deterministic across Azure
  name: guid(cosmosDb.id, principalId, principalType, roleIds.documentDBAccountContributor)
  scope: cosmosDb
  properties: {
    principalId: principalId
    principalType: principalType
    roleDefinitionId: resourceId('Microsoft.Authorization/roleDefinitions', roleIds.documentDBAccountContributor)
  }
}

resource sqlDbContributorRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  // note: the guid must be globally unique and deterministic across Azure
  name: guid(cosmosDb.id, principalId, principalType, roleIds.sqlDBContributor)
  scope: cosmosDb
  properties: {
    principalId: principalId
    principalType: principalType
    roleDefinitionId: resourceId('Microsoft.Authorization/roleDefinitions', roleIds.sqlDBContributor)
  }
}

resource storageBlobDataContributorRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  // note: the guid must be globally unique and deterministic across Azure
  name: guid(storage.id, principalId, principalType, roleIds.storageBlobDataContributor)
  scope: storage
  properties: {
    principalId: principalId
    principalType: principalType
    roleDefinitionId: resourceId('Microsoft.Authorization/roleDefinitions', roleIds.storageBlobDataContributor)
  }
}

resource monitoringMetricsPublisherRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  // note: the guid must be globally unique and deterministic across Azure
  name: guid(appInsights.id, principalId, roleIds.monitoringMetricsPublisher)
  scope: appInsights
  properties: {
    principalId: principalId
    principalType: principalType
    roleDefinitionId: resourceId('Microsoft.Authorization/roleDefinitions', roleIds.monitoringMetricsPublisher)
  }
}

// NOTE: The SQL role assignment below can be flaky due to a known race condition issue at deployment time when assigning Cosmos DB built-in roles to an identity.
// For more information: https://github.com/pulumi/pulumi-azure-native/issues/2816
// In practice, one option that may not have such flaky behavior is to create a custom role defintion with the same permissions as the built-in role and use it instead
resource sqlRoleAssignment 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2024-11-15' = {
  name: guid(cosmosDb.id, principalId, principalType, roleIds.cosmosDbBuiltInDataContributor)
  parent: cosmosDb
  properties: {
    principalId: principalId
    roleDefinitionId: '${cosmosDb.id}/sqlRoleDefinitions/${roleIds.cosmosDbBuiltInDataContributor}'
    scope: cosmosDb.id
  }
}

// var customRoleName = 'Custom cosmosDB role for graphrag - adds read/write permissions at the container level'
// resource customCosmosRoleDefinition 'Microsoft.DocumentDB/databaseAccounts/sqlRoleDefinitions@2024-12-01-preview' = {
//   // note: the guid must be globally unique and deterministic (reproducible) across Azure
//   name: guid(cosmosDb.id, customRoleName)
//   parent: cosmosDb
//   properties: {
//     roleName: customRoleName
//     type: 'CustomRole'
//     assignableScopes: [
//       cosmosDb.id
//     ]
//     permissions: [
//       {
//         dataActions: [
//           'Microsoft.DocumentDB/databaseAccounts/readMetadata'
//           'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers/*'
//           'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers/items/*'
//         ]
//       }
//     ]
//   }
// }

// resource customRoleAssignment 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2024-12-01-preview' = {
//   // note: the guid must be globally unique and deterministic (reproducible) across Azure
//   name: guid(cosmosDb.id, principalId, principalType, customCosmosRoleDefinition.id)
//   parent: cosmosDb
//   properties: {
//     principalId: principalId
//     roleDefinitionId: customCosmosRoleDefinition.id
//     scope: cosmosDb.id
//   }
// }
