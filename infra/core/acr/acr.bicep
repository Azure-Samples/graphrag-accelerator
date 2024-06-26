@description('The name of the Container Registry resource. Will be automatically generated if not provided.')
param name string = ''

@description('The location of the Container Registry resource.')
param location string = resourceGroup().location

var resourceBaseNameFinal = !empty(name) ? name : toLower(uniqueString('${subscription().id}/resourceGroups/${resourceGroup().name}'))
var abbrs = loadJsonContent('../../abbreviations.json')

resource registry 'Microsoft.ContainerRegistry/registries@2023-11-01-preview' = {
  name: !empty(name) ? name : '${abbrs.containerRegistryRegistries}${resourceBaseNameFinal}'
  location: location
  sku: {
    name: 'Standard'
  }
  properties: {
    adminUserEnabled: true
    encryption: {
      status: 'disabled'
    }
    dataEndpointEnabled: false
    publicNetworkAccess: 'Enabled'
    networkRuleBypassOptions: 'AzureServices'
    zoneRedundancy: 'Disabled'
    anonymousPullEnabled: false
    metadataSearch: 'Disabled'
  }
}

output name string = registry.name
output loginServer string = registry.properties.loginServer
