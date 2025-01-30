// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

@description('The name of the Log Analytics resource.')
param name string

@description('The location of the Log Analytics resource.')
param location string = resourceGroup().location

@description('The public network access for ingestion.')
param publicNetworkAccessForIngestion string = 'Disabled'

resource logAnalyticsWorkspace 'Microsoft.OperationalInsights/workspaces@2022-10-01' = {
  name: name
  location: location
  properties: {
    retentionInDays: 30
    publicNetworkAccessForIngestion: publicNetworkAccessForIngestion
    publicNetworkAccessForQuery: 'Enabled'
    features: {
      immediatePurgeDataOn30Days: true
    }
  }
}

output name string = logAnalyticsWorkspace.name
output id string = logAnalyticsWorkspace.id
