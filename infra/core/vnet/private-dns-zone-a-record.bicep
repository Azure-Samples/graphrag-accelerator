// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

@description('DNS name')
param name string

@description('DNS zone name to create the record in')
param dnsZoneName string

@description('TTL in seconds')
param ttl int = 900

@description('The IP address')
param ipv4Address string


resource dnsZone 'Microsoft.Network/privateDnsZones@2020-06-01' existing = {
  name: dnsZoneName
}

resource aRecord 'Microsoft.Network/privateDnsZones/A@2020-06-01' = {
  name: name
  parent: dnsZone
  properties: {
    ttl: ttl
    aRecords: [
      {
        ipv4Address: ipv4Address
      }
    ]
  }
}
