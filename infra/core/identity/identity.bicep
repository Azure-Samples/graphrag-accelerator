// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

@description('The name of the identity')
param name string

@description('The location of the identity')
param location string = resourceGroup().location

@description('federated name: FederatedIdentityCredentialProperties.  See https://learn.microsoft.com/en-us/azure/templates/microsoft.managedidentity/userassignedidentities/federatedidentitycredentials?pivots=deployment-language-bicep#federatedidentitycredentialproperties')
param federatedCredentials object = {}

resource identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: name
  location: location
}

resource federatedCredentialResources 'Microsoft.ManagedIdentity/userAssignedIdentities/federatedIdentityCredentials@2023-01-31' = [
  for federatedCredential in items(federatedCredentials): {
    name: federatedCredential.key
    parent: identity
    properties: federatedCredential.value
  }
]

output name string = identity.name
output clientId string = identity.properties.clientId
output principalId string = identity.properties.principalId
