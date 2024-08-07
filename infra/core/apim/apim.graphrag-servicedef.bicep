// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

param backendUrl string
param name string
param apimname string

resource api 'Microsoft.ApiManagement/service/apis@2023-09-01-preview' = {
  name: '${apimname}/${name}'
  properties: {
    displayName: 'GraphRAG'
    apiRevision: '1'
    subscriptionRequired: true
    serviceUrl: backendUrl
    path: ''
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
    format: 'openapi+json'
    value: string(loadJsonContent('graphrag-openapi.json')) // local file will be dynamically created by deployment script
  }
  resource apiPolicy 'policies@2022-08-01' = {
    name: 'policy'
    properties: {
      format: 'rawxml'
      value: loadTextContent('policies/apiPolicy.xml')
    }
  }
}
