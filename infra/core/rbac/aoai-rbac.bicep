// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.
// This generic Bicep module can be  used to assign RBAC roles to an Azure OpenAI resource at any defined scope

param name string

@description('Array of objects with fields principalId, principalType, roleDefinitionId')
param roleAssignments array = []

resource aoai 'Microsoft.CognitiveServices/accounts@2024-10-01' existing = {
  name: name
}

resource roleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = [
  for role in roleAssignments: {
    // note: the guid must be globally unique and deterministic (reproducible) across Azure
    name: guid(aoai.id, role.principalId, role.principalType, role.roleDefinitionId)
    scope: aoai
    properties: {
      principalId: role.principalId
      roleDefinitionId: resourceId('Microsoft.Authorization/roleDefinitions', role.roleDefinitionId)
      principalType: role.principalType
    }
  }
]

// output the name, id, and endpoint of the Azure OpenAI resource
output name string = aoai.name
output id string = aoai.id
output endpoint string = aoai.properties.endpoint
