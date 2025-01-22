// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

@description('Application Insights resource name')
param appInsightsName string = 'appi'

@description('Azure region where the resources will be deployed')
param location string = resourceGroup().location

@description('Application Insights public network access for ingestion')
param appInsightsPublicNetworkAccessForIngestion string = 'Disabled'

@description('Workspace id of a Log Analytics resource.')
param logAnalyticsWorkspaceId string

resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: appInsightsName
  location: location
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logAnalyticsWorkspaceId
    publicNetworkAccessForIngestion: appInsightsPublicNetworkAccessForIngestion
    publicNetworkAccessForQuery: 'Enabled'
  }
}

output id string = appInsights.id
output connectionString string = appInsights.properties.ConnectionString
output instrumentationKey string = appInsights.properties.InstrumentationKey
