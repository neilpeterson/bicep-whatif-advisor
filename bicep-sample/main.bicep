// az deployment group what-if --template-file ./bicep-sample/main.bicep --parameters ./bicep-sample/tme-lab.bicepparam -g rg-api-gateway-tme-two --exclude-change-types NoChange Ignore | python3 -m whatif_explain.cli --provider anthropic

param apimName string
param frontDoorIds array

@description('Name of the existing Application Insights logger in APIM')
param appInsightsLoggerName string

@description('Headers to log in APIM diagnostics (backend request)')
param headersToLog array = []

var policyContent = loadTextContent('policy-logic/apim-policy.xml')
var jwtParsingFragment = loadTextContent('policy-logic/sce-jwt-parsing-and-logging.xml')

// Generate the <value> elements for each Front Door ID
var valueElements = [for id in frontDoorIds: '<value>${id}</value>']
var valuesString = join(valueElements, '\n')

// Replace the placeholder with the dynamically generated values
var policyFormatted = replace(policyContent, '{FRONTDOOR_IDS}', valuesString)

resource apiManagementInstance 'Microsoft.ApiManagement/service@2022-08-01' existing = {
  name: apimName
}

resource jwtParsingLoggingFragment 'Microsoft.ApiManagement/service/policyFragments@2025-03-01-preview' = {
  parent: apiManagementInstance
  name: 'sce-jwt-parsing-and-logging-two'
  properties: {
    description: 'Extracts JWT claims from Authorization header and sets them as headers for native APIM logging'
    format: 'rawxml'
    value: jwtParsingFragment
  }
}

resource validateAFDId 'Microsoft.ApiManagement/service/policies@2023-03-01-preview' = {
  parent: apiManagementInstance
  name: 'policy'
  properties: {
    value: policyFormatted
    format: 'rawxml'
  }
  dependsOn: [
    jwtParsingLoggingFragment
  ]
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
