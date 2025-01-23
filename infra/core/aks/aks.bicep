// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

@description('The name of the Managed Cluster resource.')
param clusterName string

@description('The location of the Managed Cluster resource.')
param location string = resourceGroup().location

@description('The workspace id of the Log Analytics resource.')
param logAnalyticsWorkspaceId string

@description('The auto-upgrade profile.')
param autoUpgradeProfile object = {
  nodeOsUpgradeChannel: 'NodeImage'
  upgradeChannel: 'stable'
}

@description('Optional DNS prefix to use with hosted Kubernetes API server FQDN.')
param dnsPrefix string = ''

@description('Disk size (in GB) to provision for each of the agent pool nodes. This value ranges from 0 to 1023. Specifying 0 will apply the default disk size for that agentVMSize.')
@minValue(0)
@maxValue(1023)
param systemOsDiskSizeGB int = 128

@description('The number of nodes for the system node pool.')
@minValue(1)
@maxValue(20)
param systemNodeCount int = 1

@description('The size of the system Virtual Machine.')
param systemVMSize string = 'standard_d4s_v5' // 4 vcpu, 16 GB memory

@description('The number of nodes for the graphrag node pool.')
@minValue(1)
@maxValue(50)
param graphragNodeCount int = 1

@description('The VM size of nodes running the GraphRAG API.')
param graphragVMSize string = 'standard_d8s_v5' // 8 vcpu, 32 GB memory

@description('The VM size of nodes running GraphRAG indexing jobs.')
param graphragIndexingVMSize string = 'standard_e8s_v5' // 8 vcpus, 64 GB memory

@description('Enable encryption at host')
param enableEncryptionAtHost bool = false

param subnetId string

param privateDnsZoneName string

@description('Array of object ids that will have admin role of the cluster')
param clusterAdmins array = []

resource privateDnsZone 'Microsoft.Network/privateDnsZones@2020-06-01' existing = {
  name: privateDnsZoneName
}

resource aks 'Microsoft.ContainerService/managedClusters@2024-09-02-preview' = {
  name: clusterName
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    enableRBAC: true
    disableLocalAccounts: true
    dnsPrefix: !empty(dnsPrefix) ? dnsPrefix : toLower(clusterName)
    aadProfile: {
      managed: true
      enableAzureRBAC: true
      adminGroupObjectIDs: clusterAdmins
    }
    addonProfiles: {
      omsagent: {
        enabled: true
        config: {
          logAnalyticsWorkspaceResourceID: logAnalyticsWorkspaceId
        }
      }
    }
    agentPoolProfiles: [
      {
        name: 'agentpool'
        enableAutoScaling: true
        upgradeSettings: {
          maxSurge: '50%'
        }
        minCount: 1
        maxCount: 10
        osDiskSizeGB: systemOsDiskSizeGB
        count: systemNodeCount
        vmSize: systemVMSize
        osType: 'Linux'
        mode: 'System'
        enableEncryptionAtHost: enableEncryptionAtHost
        vnetSubnetID: subnetId
        type: 'VirtualMachineScaleSets'
      }
    ]
    autoScalerProfile: {
      expander: 'least-waste'
    }
    ingressProfile: {
      webAppRouting: {
        enabled: true
        dnsZoneResourceIds: [
          privateDnsZone.id
        ]
      }
    }
    networkProfile: {
      serviceCidr: '10.3.0.0/16' // must not overlap with any subnet IP ranges
      dnsServiceIP: '10.3.0.10' // must be within the range specified in serviceCidr
      podCidr: '10.244.0.0/16' // IP range from which to assign pod IPs
    }
    autoUpgradeProfile: autoUpgradeProfile
    oidcIssuerProfile: {
      enabled: true
    }
    securityProfile: {
      workloadIdentity: {
        enabled: true
      }
    }
  }

  resource graphragNodePool 'agentPools@2024-02-01' = {
    name: 'graphrag'
    properties: {
      enableAutoScaling: true
      upgradeSettings: {
        maxSurge: '50%'
      }
      minCount: 1
      maxCount: 10
      osDiskSizeGB: systemOsDiskSizeGB
      count: graphragNodeCount
      vmSize: graphragVMSize
      osType: 'Linux'
      mode: 'User'
      enableEncryptionAtHost: enableEncryptionAtHost
      vnetSubnetID: subnetId
      nodeLabels: {
        workload: 'graphrag'
      }
      tags: {
        workload: 'graphrag'
      }
      type: 'VirtualMachineScaleSets'
    }
  }

  resource graphragIndexingNodePool 'agentPools@2024-02-01' = {
    name: 'indexing'
    properties: {
      enableAutoScaling: true
      upgradeSettings: {
        maxSurge: '50%'
      }
      minCount: 0
      maxCount: 10
      osDiskSizeGB: systemOsDiskSizeGB
      count: 0
      vmSize: graphragIndexingVMSize
      osType: 'Linux'
      mode: 'User'
      enableEncryptionAtHost: enableEncryptionAtHost
      vnetSubnetID: subnetId
      nodeLabels: {
        workload: 'graphrag-indexing'
      }
      tags: {
        workload: 'graphrag'
      }
      type: 'VirtualMachineScaleSets'
    }
  }
}

resource aksManagedAutoUpgradeSchedule 'Microsoft.ContainerService/managedClusters/maintenanceConfigurations@2024-09-02-preview' = {
  parent: aks
  name: 'aksManagedAutoUpgradeSchedule'
  properties: {
    maintenanceWindow: {
      schedule: {
        weekly: {
          intervalWeeks: 1
          dayOfWeek: 'Monday'
        }
      }
      durationHours: 4
      startDate: '2024-06-11'
      startTime: '12:00'
    }
  }
}

resource aksManagedNodeOSUpgradeSchedule 'Microsoft.ContainerService/managedClusters/maintenanceConfigurations@2024-09-02-preview' = {
  parent: aks
  name: 'aksManagedNodeOSUpgradeSchedule'
  properties: {
    maintenanceWindow: {
      schedule: {
        weekly: {
          intervalWeeks: 1
          dayOfWeek: 'Saturday'
        }
      }
      durationHours: 4
      startDate: '2024-06-11'
      startTime: '12:00'
    }
  }
}

output name string = aks.name
output id string = aks.id
output managedResourceGroup string = aks.properties.nodeResourceGroup
output controlPlaneFqdn string = aks.properties.fqdn
output kubeletPrincipalId string = aks.properties.identityProfile.kubeletidentity.objectId
output ingressWebAppIdentity string = aks.properties.ingressProfile.webAppRouting.identity.objectId
output systemIdentity string = aks.identity.principalId
output issuer string = aks.properties.oidcIssuerProfile.issuerURL
