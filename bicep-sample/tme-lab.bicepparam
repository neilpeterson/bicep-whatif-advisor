using 'main.bicep'

param apimName = 'apim-nepeters-vs'
param appInsightsLoggerName = 'ins-api-gateway-nepeters'
param storageAccountName = 'nepetersstor'

// Headers to log in APIM diagnostics
param headersToLog = [
  'X-JWT-ClientID'
  'X-JWT-TenantID'
  'X-JWT-Audience'
  'X-JWT-Status'
  'X-Azure-Ref'
]
