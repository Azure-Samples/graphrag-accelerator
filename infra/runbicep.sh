#!/bin/bash

deployAzureResources () {
    echo "Deploying Azure resources..."
    local datetime="`date +%Y%m%d%H%M%S`"
    local deployName="graphrag-deploy-$datetime"
    local rggoup="harjsin$datetime"
    echo "Deployment name: $deployName"
    az group create -l eastus2 -n  "$rggoup"
    local AZURE_DEPLOY_RESULTS=$(az deployment group create --name "$deployName" \
        --no-prompt \
        --resource-group "$rggoup" \
        --mode Incremental \
        --template-file ./main.bicep \
        --parameters "resourceGroup=$rggoup" \
        --parameters "resourceBaseName=$rggoup" \
        --parameters "apimName=$rggoup" \
        --parameters "apimTier=Developer" \
        --parameters "apiPublisherName=harjsin" \
        --parameters "apiPublisherEmail=harjsin@microsoft.com" \
        --parameters "enablePrivateEndpoints=false" \
        --output json)
    # errors in deployment may not be caught by exitIfCommandFailed function so we also check the output for errors
    exitIfCommandFailed $? "Error deploying Azure resources..."
    exitIfValueEmpty "$AZURE_DEPLOY_RESULTS" "Error deploying Azure resources..."
    AZURE_OUTPUTS=$(jq -r .properties.outputs <<< "$AZURE_DEPLOY_RESULTS")
    exitIfCommandFailed $? "Error parsing outputs from Azure deployment..."
    exitIfValueEmpty "$AZURE_OUTPUTS" "Error parsing outputs from Azure deployment..."
}

deployAzureResources
