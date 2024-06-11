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
@maxValue(50)
param systemNodeCount int = 1

@description('The size of the system Virtual Machine.')
param systemVMSize string = 'standard_d4s_v5'

@description('The number of nodes for the graphrag node pool.')
@minValue(1)
@maxValue(50)
param graphragNodeCount int = 1

@description('The size of the GraphRAG Virtual Machine.')
param graphragVMSize string = 'standard_e16as_v5' // 16 vcpus, 128 GiB memory

@description('User name for the Linux Virtual Machines.')
param linuxAdminUsername string = 'azureuser'

@description('Configure all linux machines with the SSH RSA public key string. Your key should include three parts, for example \'ssh-rsa AAAAB...snip...UcyupgH azureuser@linuxvm\'')
param sshRSAPublicKey string

@description('Enable encryption at host')
param enableEncryptionAtHost bool = false

@description('Resource ID of subnet to use for all node pools.')
param vnetSubnetId string = ''
var vnetSubnetIdVar = !empty(vnetSubnetId) ? vnetSubnetId : null

resource aks 'Microsoft.ContainerService/managedClusters@2023-10-01' = {
  name: clusterName
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    enableRBAC: true
    dnsPrefix: !empty(dnsPrefix) ? dnsPrefix : toLower(clusterName)
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
        minCount: 1
        maxCount: 10
        osDiskSizeGB: systemOsDiskSizeGB
        count: systemNodeCount
        vmSize: systemVMSize
        osType: 'Linux'
        mode: 'System'
        enableEncryptionAtHost: enableEncryptionAtHost
        vnetSubnetID: vnetSubnetIdVar
        type: 'VirtualMachineScaleSets'
      }
    ]
    autoScalerProfile: {
      expander: 'least-waste'
    }
    linuxProfile: {
      adminUsername: linuxAdminUsername
      ssh: {
        publicKeys: [
          {
            keyData: sshRSAPublicKey
          }
        ]
      }
    }
    networkProfile: {
      serviceCidr: '10.2.0.0/16'
      dnsServiceIP: '10.2.0.10'
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
      minCount: 1
      maxCount: 10
      osDiskSizeGB: systemOsDiskSizeGB
      count: graphragNodeCount
      vmSize: graphragVMSize
      osType: 'Linux'
      mode: 'User'
      enableEncryptionAtHost: enableEncryptionAtHost
      vnetSubnetID: vnetSubnetIdVar
      nodeLabels: {
        workload: 'graphrag'
      }
      tags: {
        workload: 'graphrag'
      }
      type: 'VirtualMachineScaleSets'
    }
  }
}

output name string = aks.name
output managedResourceGroup string = aks.properties.nodeResourceGroup
output controlPlaneFQDN string = aks.properties.fqdn
output principalId string = aks.identity.principalId
output kubeletPrincipalId string = aks.properties.identityProfile.kubeletidentity.objectId
output issuer string = aks.properties.oidcIssuerProfile.issuerURL
