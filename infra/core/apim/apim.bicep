// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

@description('The name of the API Management service instance')
param apiManagementName string = 'apiservice${uniqueString(resourceGroup().id)}'

@description('The email address of the owner of the service')
@minLength(1)
param publisherEmail string

@description('The name of the owner of the service')
@minLength(1)
param publisherName string

@description('The pricing tier of this API Management service')
@allowed([
  'Developer'
  'StandardV2'
])
param sku string = 'Developer'

@description('The instance size of this API Management service. This should be a multiple of the number of availability zones getting deployed.')
param skuCount int = 1

@description('Application Insights resource ID')
param appInsightsId string

@description('Application Insights instrumentation key')
param appInsightsInstrumentationKey string

@description('Azure region where the resources will be deployed')
param location string = resourceGroup().location

@description('Numbers for availability zones, for example, 1,2,3.')
param availabilityZones array = [
  '1'
  '2'
]

@description('Name for the public IP address used to access the API Management service.')
param publicIpName string = 'apimPublicIP'

@description('SKU for the public IP address used to access the API Management service.')
@allowed([
  'Standard'
])
param publicIpSku string = 'Standard'

@description('Allocation method for the public IP address used to access the API Management service. Standard SKU public IP requires `Static` allocation.')
@allowed([
  'Static'
])
param publicIPAllocationMethod string = 'Static'

@description('Unique DNS name for the public IP address used to access the API management service.')
param dnsLabelPrefix string = toLower('${publicIpName}-${uniqueString(resourceGroup().id)}')

param restoreAPIM bool = false
param subnetId string

resource publicIp 'Microsoft.Network/publicIPAddresses@2024-01-01' = {
  name: publicIpName
  location: location
  sku: {
    name: publicIpSku
  }
  properties: {
    publicIPAllocationMethod: publicIPAllocationMethod
    publicIPAddressVersion: 'IPv4'
    dnsSettings: {
      domainNameLabel: dnsLabelPrefix
    }
  }
}

resource apiManagementService 'Microsoft.ApiManagement/service@2023-09-01-preview' = {
  name: apiManagementName
  location: location
  sku: {
    name: sku
    capacity: skuCount
  }
  zones: ((length(availabilityZones) == 0) ? null : availabilityZones)
  properties: {
    restore: restoreAPIM
    publisherEmail: publisherEmail
    publisherName: publisherName
    virtualNetworkType: 'External'
    publicIpAddressId: publicIp.id
    virtualNetworkConfiguration: {
      subnetResourceId: subnetId
    }
    customProperties: {
      'Microsoft.WindowsAzure.ApiManagement.Gateway.Security.Ciphers.TLS_ECDHE_RSA_WITH_AES_256_CBC_SHA': 'false'
      'Microsoft.WindowsAzure.ApiManagement.Gateway.Security.Ciphers.TLS_ECDHE_RSA_WITH_AES_128_CBC_SHA': 'false'
      'Microsoft.WindowsAzure.ApiManagement.Gateway.Security.Ciphers.TLS_RSA_WITH_AES_128_GCM_SHA256': 'false'
      'Microsoft.WindowsAzure.ApiManagement.Gateway.Security.Ciphers.TLS_RSA_WITH_AES_256_CBC_SHA256': 'false'
      'Microsoft.WindowsAzure.ApiManagement.Gateway.Security.Ciphers.TLS_RSA_WITH_AES_128_CBC_SHA256': 'false'
      'Microsoft.WindowsAzure.ApiManagement.Gateway.Security.Ciphers.TLS_RSA_WITH_AES_256_CBC_SHA': 'false'
      'Microsoft.WindowsAzure.ApiManagement.Gateway.Security.Ciphers.TLS_RSA_WITH_AES_128_CBC_SHA': 'false'
      'Microsoft.WindowsAzure.ApiManagement.Gateway.Security.Ciphers.TripleDes168': 'false'
      'Microsoft.WindowsAzure.ApiManagement.Gateway.Security.Protocols.Tls10': 'false'
      'Microsoft.WindowsAzure.ApiManagement.Gateway.Security.Protocols.Tls11': 'false'
      'Microsoft.WindowsAzure.ApiManagement.Gateway.Security.Protocols.Ssl30': 'false'
      'Microsoft.WindowsAzure.ApiManagement.Gateway.Security.Backend.Protocols.Tls10': 'false'
      'Microsoft.WindowsAzure.ApiManagement.Gateway.Security.Backend.Protocols.Tls11': 'false'
      'Microsoft.WindowsAzure.ApiManagement.Gateway.Security.Backend.Protocols.Ssl30': 'false'
      'Microsoft.WindowsAzure.ApiManagement.Gateway.Protocols.Server.Http2': 'false'
    }
  }
}

resource apimLogger 'Microsoft.ApiManagement/service/loggers@2024-06-01-preview' = {
  name: 'apimLogger'
  parent: apiManagementService
  properties: {
    credentials: {
      instrumentationKey: appInsightsInstrumentationKey
    }
    description: 'Application Insights for APIM'
    loggerType: 'applicationInsights'
    resourceId: appInsightsId
  }
}

resource apimDiagnostics 'Microsoft.ApiManagement/service/diagnostics@2023-09-01-preview' = {
  name: 'applicationinsights'
  parent: apiManagementService
  properties: {
    loggerId: apimLogger.id
    alwaysLog: 'allErrors'
    verbosity: 'information'
    sampling: {
      percentage: 100
      samplingType: 'fixed'
    }
  }
}

output name string = apiManagementService.name
output id string = apiManagementService.id
output apimGatewayUrl string = apiManagementService.properties.gatewayUrl
