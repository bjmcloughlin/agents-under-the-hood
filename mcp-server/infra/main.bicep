// Everything one hosted MCP server needs on Azure, in one file.
// It compiles, but it has never been deployed: read it as a map of the parts
// and of who is allowed to do what, not as a tested template.

param location string = resourceGroup().location
param suffix string = uniqueString(resourceGroup().id)

@description('Full image reference, e.g. <registry>.azurecr.io/books-mcp:<git sha>')
param image string

@description('What the token must be issued for: the client ID of this server\'s app registration in Entra ID')
param audience string

var name = 'books-mcp'
var tenantId = tenant().tenantId
var login = environment().authentication.loginEndpoint
var issuer = '${login}${tenantId}/v2.0'

// Built-in role IDs
var acrPull = '7f951dda-4ed3-4680-a7ca-43fe172d538d'
var keyVaultSecretsUser = '4633458b-17de-408a-b874-0445c86b69e6'

// --- Log store: everything the container writes to stderr ends up here ---
resource logs 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: 'log-${name}'
  location: location
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: 90
  }
}

// --- Registry: where the image lives. No admin user, so no password to leak ---
resource registry 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: 'acr${replace(name, '-', '')}${suffix}'
  location: location
  sku: { name: 'Basic' }
  properties: { adminUserEnabled: false }
}

// --- Secret store: access is by role, not by a shared access policy ---
resource vault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: 'kv-${take(name, 8)}-${take(suffix, 10)}'
  location: location
  properties: {
    tenantId: tenantId
    sku: { family: 'A', name: 'standard' }
    enableRbacAuthorization: true
    enablePurgeProtection: true
  }
}

// The secret's value is set by hand after the vault exists, so it never appears in this file
resource contact 'Microsoft.KeyVault/vaults/secrets@2023-07-01' existing = {
  parent: vault
  name: 'openlibrary-contact'
}

// --- Workload identity: what the running server is, as far as Azure is concerned ---
resource identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: 'id-${name}'
  location: location
}

// It may pull images from this registry...
resource pullImages 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: registry
  name: guid(registry.id, identity.id, acrPull)
  properties: {
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', acrPull)
  }
}

// ...and read this one secret. Not the vault: the one secret.
resource readContact 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: contact
  name: guid(contact.id, identity.id, keyVaultSecretsUser)
  properties: {
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', keyVaultSecretsUser)
  }
}

// --- Container runtime ---
resource environment_ 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: 'cae-${name}'
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logs.properties.customerId
        sharedKey: logs.listKeys().primarySharedKey
      }
    }
  }
}

var publicUrl = 'https://ca-${name}.${environment_.properties.defaultDomain}/mcp'

resource app 'Microsoft.App/containerApps@2024-03-01' = {
  name: 'ca-${name}'
  location: location
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: { '${identity.id}': {} }
  }
  properties: {
    environmentId: environment_.id
    configuration: {
      // Public HTTPS in, plain HTTP refused. The token check in the server is the gate.
      ingress: {
        external: true
        targetPort: 8000
        allowInsecure: false
      }
      // Pull the image as the identity, with no registry password anywhere
      registries: [
        { server: registry.properties.loginServer, identity: identity.id }
      ]
      // A reference to the secret, resolved by the platform as the identity
      secrets: [
        { name: 'openlibrary-contact', keyVaultUrl: contact.properties.secretUri, identity: identity.id }
      ]
    }
    template: {
      containers: [
        {
          name: name
          image: image
          resources: { cpu: json('0.25'), memory: '0.5Gi' }
          env: [
            { name: 'OPENLIBRARY_CONTACT', secretRef: 'openlibrary-contact' }
            { name: 'MCP_PUBLIC_URL', value: publicUrl }
            { name: 'MCP_AUTH_ISSUER', value: issuer }
            { name: 'MCP_AUTH_JWKS_URL', value: '${login}${tenantId}/discovery/v2.0/keys' }
            { name: 'MCP_AUTH_AUDIENCE', value: audience }
          ]
        }
      ]
      // Sessions live in the server's memory, so a second replica would not know
      // about a session the first one opened. One replica, and none when idle.
      scale: { minReplicas: 0, maxReplicas: 1 }
    }
  }
  dependsOn: [ pullImages, readContact ]
}

output url string = publicUrl
