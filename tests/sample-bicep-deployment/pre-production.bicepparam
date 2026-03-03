using 'main.bicep'

param vnetName = 'vnet-nepeters-pre'
param logAnalyticsName = 'law-nepeters-pre'

param branches = [
  {
    branchOfficeName: 'paris'
    storageAccountName: 'stgparisbranch'
    keyVaultName: 'akv-paris-01-branch'
    nsgRulePriority: 205
    ipAddress: '71.197.100.86'
    storagePublicNetworkAccess: 'Disabled'
    storageAllowSharedKeyAccess: false
    keyVaultPublicNetworkAccess: 'Disabled'
  }
  {
    branchOfficeName: 'berlin'
    storageAccountName: 'stgberlinbranch'
    keyVaultName: 'akv-berlin-01-branch'
    nsgRulePriority: 210
    ipAddress: '71.197.102.86'
    storagePublicNetworkAccess: 'Enabled'
    storageAllowSharedKeyAccess: true
    keyVaultPublicNetworkAccess: 'Enabled'
  }
]
