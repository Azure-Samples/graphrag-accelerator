// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

param apiManagementName string
param backendUrl string

resource api_docs 'Microsoft.ApiManagement/service/apis@2024-05-01' = {
  name: '${apiManagementName}/documentation'
  properties: {
    displayName: 'documentation'
    apiRevision: '1'
    subscriptionRequired: false
    serviceUrl: '${backendUrl}/manpage'
    path: 'manpage'
    protocols: ['https']
    authenticationSettings: {
      oAuth2AuthenticationSettings: []
      openidAuthenticationSettings: []
    }
    subscriptionKeyParameterNames: {
      header: 'Ocp-Apim-Subscription-Key'
      query: 'subscription-key'
    }
    isCurrent: true
  }

  resource documentation_docs 'operations@2024-05-01' = {
    name: 'docs'
    properties: {
      displayName: 'docs'
      method: 'GET'
      urlTemplate: '/docs'
      templateParameters: []
      responses: []
    }
  }

  resource documentation_openapi 'operations@2024-05-01' = {
    name: 'openapi'
    properties: {
      displayName: 'openapi'
      method: 'GET'
      urlTemplate: '/openapi.json'
      templateParameters: []
      responses: []
    }
  }
}
