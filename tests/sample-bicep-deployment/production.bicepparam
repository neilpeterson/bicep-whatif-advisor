using 'main.bicep'

param vnetName = 'vnet-nepeters-prd'
param logAnalyticsName = 'law-nepeters-prd'

param branches = [
  {
    branchOfficeName: 'paris-prd'
    storageAccountName: 'stgprdparisbranch'
    keyVaultName: 'akv-prd-paris-branch'
    nsgRulePriority: 205
    ipAddress: '71.197.100.86'
  }
]
