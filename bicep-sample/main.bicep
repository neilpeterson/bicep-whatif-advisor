param apimName string

@description('Name of the existing Application Insights logger in APIM')
param appInsightsLoggerName string

@description('Headers to log in APIM diagnostics (backend request)')
param headersToLog array = []

@description('Name of the storage account')
param storageAccountName string

@description('Name of the Application Insights instance')
param appInsightsName string = 'apim-appinsights'

@description('Name of the Log Analytics workspace')
param logAnalyticsWorkspaceName string = 'apim-law'

@description('Location for resources')
param location string = 'centralus'

// API Definition parameters with default values
param apiName string = 'sample-api'
param apiDisplayName string = 'Sample API'
param apiDescription string = 'A sample API for demonstration purposes'
param apiRevision string = '1'
param apiBackendUrl string = 'https://api.contoso.com'
param apiPath string = 'sample'

// API Operation parameters with default values
param apiOperationSampleName string = 'get-items'
param apiOperationSampleDisplayName string = 'Get Items'
param apiOperstionOperationMethod string = 'GET'
param apiOperationsMethodPath string = '/items'

resource apiManagementInstance 'Microsoft.ApiManagement/service@2022-08-01' existing = {
  name: apimName
}

// Log Analytics Workspace
resource logAnalyticsWorkspace 'Microsoft.OperationalInsights/workspaces@2022-10-01' = {
  name: logAnalyticsWorkspaceName
  location: location
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
  }
}

// Application Insights instance
resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: appInsightsName
  location: location
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logAnalyticsWorkspace.id
  }
}

// APIM Logger for Application Insights
resource apimAppInsightsLogger 'Microsoft.ApiManagement/service/loggers@2022-08-01' = {
  parent: apiManagementInstance
  name: appInsightsName
  properties: {
    loggerType: 'applicationInsights'
    credentials: {
      instrumentationKey: appInsights.properties.InstrumentationKey
    }
    isBuffered: true
    resourceId: appInsights.id
  }
}

// Load the global APIM policy from XML file
var globalPolicyContent = loadTextContent('policy-logic/apim-policy.xml')

// Global APIM Policy
resource globalPolicy 'Microsoft.ApiManagement/service/policies@2023-03-01-preview' = {
  parent: apiManagementInstance
  name: 'policy'
  properties: {
    value: globalPolicyContent
    format: 'rawxml'
  }
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

// API Definition
resource apiDefinition 'Microsoft.ApiManagement/service/apis@2023-09-01-preview' = {
  parent: apiManagementInstance
  name: apiName
  properties: {
    displayName: apiDisplayName
    description: apiDescription
    apiRevision: apiRevision
    subscriptionRequired: true
    serviceUrl: apiBackendUrl
    path: apiPath
    protocols: [
      'https'
    ]
    isCurrent: true

  }
}

// API Operation - duplicate for each operation
resource apimSampleOperation 'Microsoft.ApiManagement/service/apis/operations@2023-09-01-preview' = {
  parent: apiDefinition
  name: apiOperationSampleName
  properties: {
    displayName: apiOperationSampleDisplayName
    method: apiOperstionOperationMethod
    urlTemplate: apiOperationsMethodPath
  }
}

// API-level diagnostics for the sample API
resource sampleApiDiagnostics 'Microsoft.ApiManagement/service/apis/diagnostics@2023-03-01-preview' = {
  parent: apiDefinition
  name: 'applicationinsights'
  properties: {
    alwaysLog: 'allErrors'
    httpCorrelationProtocol: 'W3C'
    verbosity: 'information'
    logClientIp: true
    loggerId: apimAppInsightsLogger.id
    sampling: {
      samplingType: 'fixed'
      percentage: 100
    }
    frontend: {
      request: { headers: headersToLog, body: { bytes: 8192 } }
      response: { headers: headersToLog, body: { bytes: 8192 } }
    }
    backend: {
      request: { headers: headersToLog, body: { bytes: 8192 } }
      response: { headers: headersToLog, body: { bytes: 8192 } }
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


