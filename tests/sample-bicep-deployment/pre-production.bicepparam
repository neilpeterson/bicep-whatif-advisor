using 'main.bicep'

param vnetName = 'vnet-nepeters-pre'
param logAnalyticsName = 'law-nepeters-pre'

param branches = [
  {
    branchOfficeName: 'paris'
    storageAccountName: 'stgparisbranch'
    keyVaultName: 'akv-paris-branch'
    nsgRulePriority: 205
    ipAddress: '71.197.100.86'
  }
]

