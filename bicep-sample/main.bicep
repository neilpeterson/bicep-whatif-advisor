// test

param apimName string

@description('Name of the existing Application Insights logger in APIM')
param appInsightsLoggerName string

@description('Headers to log in APIM diagnostics (backend request)')
param headersToLog array = []

@description('Name of the storage account')
param storageAccountName string

resource apiManagementInstance 'Microsoft.ApiManagement/service@2022-08-01' existing = {
  name: apimName
}

// Reference existing Application Insights logger
resource apimLogger 'Microsoft.ApiManagement/service/loggers@2020-12-01' existing = {
  parent: apiManagementInstance
  name: appInsightsLoggerName
}

// Application Insights diagnostics
resource apimDiagnosticsAppInsights 'Microsoft.ApiManagement/service/diagnostics@2023-03-01-preview' = {
  parent: apiManagementInstance
  name: 'applicationinsights'
  properties: {
    alwaysLog: 'allErrors'
    httpCorrelationProtocol: 'Legacy'
    verbosity: 'information'
    logClientIp: true
    loggerId: apimLogger.id
    sampling: {
      samplingType: 'fixed'
      percentage: 100
    }
    frontend: {
      request: { headers: headersToLog, body: { bytes: 0 } }
      response: { headers: headersToLog, body: { bytes: 0 } }
    }
    backend: {
      request: { headers: headersToLog, body: { bytes: 0 } }
      response: { headers: headersToLog, body: { bytes: 0 } }
    }
  }
}

resource storageAccount 'Microsoft.Storage/storageAccounts@2025-01-01' = {
  name: storageAccountName
  location: 'centralus'
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  tags: {
    Environment: 'Production'
    ManagedBy: 'Bicep'
  }
  properties: {
    minimumTlsVersion: 'TLS1_2'
    allowBlobPublicAccess: false
    accessTier: 'Hot'
    publicNetworkAccess: 'Enabled'
  }
}
