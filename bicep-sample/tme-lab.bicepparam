using 'main.bicep'

param apimName = 'apim-api-gateway-500-tme'
param appInsightsLoggerName = 'ins-api-gateway-tme'

// Headers to log in APIM diagnostics
param headersToLog = [
  'X-JWT-ClientID'
  'X-JWT-TenantID'
  'X-JWT-Audience'
  'X-JWT-Status'
  'X-Azure-Ref'
]

// Front Door IDs - Get these from the Front Door resource properties
// You can find this in Azure Portal > Front Door > Overview > Front Door ID
param frontDoorIds = [
  'f271dea0-43ef-47ff-b5ec-6516de1d090c'
]
