// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

@description('Array of objects with fields principalId, principalType, roleDefinitionId')
param roleAssignments array = []

resource roleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = [
  for role in roleAssignments: {
    // note: the guid must be globally unique and deterministic (reproducible) across Azure
    name: guid(
      subscription().subscriptionId,
      resourceGroup().name,
      role.principalId,
      role.principalType,
      role.roleDefinitionId
    )
    scope: resourceGroup()
    properties: role
  }
]
