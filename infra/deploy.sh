# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
#!/usr/bin/env bash

#set -x  # uncomment this line to debug

aksNamespace="graphrag"

# OPTIONAL PARAMS
AISEARCH_AUDIENCE=""
AISEARCH_ENDPOINT_SUFFIX=""
APIM_NAME=""
RESOURCE_BASE_NAME=""
REPORTERS=""
GRAPHRAG_COGNITIVE_SERVICES_ENDPOINT=""
CONTAINER_REGISTRY_SERVER=""

requiredParams=(
    LOCATION
    GRAPHRAG_API_BASE
    GRAPHRAG_API_VERSION
    GRAPHRAG_LLM_MODEL
    GRAPHRAG_LLM_DEPLOYMENT_NAME
    GRAPHRAG_EMBEDDING_MODEL
    GRAPHRAG_EMBEDDING_DEPLOYMENT_NAME
    RESOURCE_GROUP
)

# Note, setting a command result to a local variable will mark $? as successful.  Use a global variable.
exitIfCommandFailed () {
    local res=$1
    local msg=$2
    if [ 0 -ne $res ]; then
        printf "$msg\n"
        exit 1
    fi
}

exitIfValueEmpty () {
    local value=$1
    local msg=$2
    if [ -z "$value" ]; then
        printf "$msg\n"
        exit 1
    fi
}

versionCheck () {
    # assume the version is in the format major.minor.patch
    local TOOL=$1
    local VERSION=$2
    local MINIMUM_VERSION_REQUIREMENT=$3
    for i in 1 2 3; do
        part1=$(echo $VERSION | cut -d "." -f $i)
        part2=$(echo $MINIMUM_VERSION_REQUIREMENT | cut -d "." -f $i)
        if [ $part1 -gt $part2 ]; then
            return 0
        fi
        if [ $part1 -lt $part2 ]; then
            echo "$TOOL version requirement >= $MINIMUM_VERSION_REQUIREMENT, but you have version $VERSION"
            exit 1
        fi
    done
}

checkRequiredTools () {
    printf "Checking for required tools... "

    which sed > /dev/null
    exitIfCommandFailed $? "sed is required, exiting..."

    which kubectl > /dev/null
    exitIfCommandFailed $? "kubectl is required, exiting..."

    which helm > /dev/null
    exitIfCommandFailed $? "helm is required, exiting..."

    which jq > /dev/null
    exitIfCommandFailed $? "jq is required, exiting..."

    which yq > /dev/null
    exitIfCommandFailed $? "yq is required, exiting..."

    which az > /dev/null
    exitIfCommandFailed $? "azcli is required, exiting..."

    which curl > /dev/null
    exitIfCommandFailed $? "curl is required, exiting..."

    # minimum version check for jq, yq, and az cli
    local JQ_VERSION=$(jq --version | cut -d'-' -f2)
    local major minor patch
    IFS='.' read -r major minor patch <<< "$JQ_VERSION"
    if [ -z $patch ]; then
        # NOTE: older acceptable versions of jq report a version number without the patch number.
        # if patch version is not present, set it to 0
        patch=0
        JQ_VERSION="$major.$minor.$patch"
    fi
    local YQ_VERSION=`yq --version | awk '{print substr($4,2)}'`
    local AZ_VERSION=`az version -o json | jq -r '.["azure-cli"]'`
    versionCheck "jq" $JQ_VERSION "1.6.0"
    versionCheck "yq" $YQ_VERSION "4.40.7"
    versionCheck "az cli" $AZ_VERSION "2.55.0"
    printf "Done.\n"
}

checkRequiredParams () {
    local paramsFile=$1
    for param in "${requiredParams[@]}"; do
        local paramValue=$(jq -r .$param < $paramsFile)
        if [ "null" == "$paramValue" ] || [ -z "$paramValue" ]; then
            echo "Parameter $param is required, exiting..."
            exit 1
        fi
    done
}

populateRequiredParams () {
    local paramsFile=$1
    printf "Checking required parameters... "
    checkRequiredParams $paramsFile
    # The jq command below sets environment variable based on the key-value pairs in a JSON-formatted file
    eval $(jq -r 'to_entries | .[] | "export \(.key)=\(.value)"' $paramsFile)
    printf "Done.\n"
}

populateOptionalParams () {
    # a list of optional environment variables that could be set in the params file.
    # using the default values below is recommended.
    local paramsFile=$1
    echo "Checking optional parameters..."
    value=$(jq -r .APIM_NAME < $paramsFile)
    if [ "null" != "$value" ]; then
        APIM_NAME="$value"
        printf "\setting tAPIM_NAME=$APIM_NAME\n"
    fi
    if [ -z "$AISEARCH_ENDPOINT_SUFFIX" ]; then
        AISEARCH_ENDPOINT_SUFFIX="search.windows.net"
        printf "\tsetting AISEARCH_ENDPOINT_SUFFIX=$AISEARCH_ENDPOINT_SUFFIX\n"
    fi
    if [ -z "$AISEARCH_AUDIENCE" ]; then
        AISEARCH_AUDIENCE="https://search.azure.com"
        printf "\tsetting AISEARCH_AUDIENCE=$AISEARCH_AUDIENCE\n"
    fi
    if [ -z "$PUBLISHER_NAME" ]; then
        PUBLISHER_NAME="publisher"
        printf "\tsetting PUBLISHER_NAME=$PUBLISHER_NAME\n"
    fi
    if [ -z "$PUBLISHER_EMAIL" ]; then
        PUBLISHER_EMAIL="publisher@microsoft.com"
        printf "\tsetting PUBLISHER_EMAIL=$PUBLISHER_EMAIL\n"
    fi
    if [ -z "$CONTAINER_REGISTRY_EMAIL" ]; then
        CONTAINER_REGISTRY_EMAIL="publisher@microsoft.com"
        printf "\tsetting CONTAINER_REGISTRY_EMAIL=$CONTAINER_REGISTRY_EMAIL\n"
    fi
    if [ -z "$CLOUD_NAME" ]; then
        CLOUD_NAME="AzurePublicCloud"
        printf "\tsetting CLOUD_NAME=$CLOUD_NAME\n"
    fi
    if [ ! -z "$RESOURCE_BASE_NAME" ]; then
        printf "\tsetting RESOURCE_BASE_NAME=$RESOURCE_BASE_NAME\n"
    fi
    if [ -z "$REPORTERS" ]; then
        REPORTERS="blob,console,app_insights"
        printf "\tsetting REPORTERS=blob,console,app_insights\n"
    fi
    if [ -z "$GRAPHRAG_COGNITIVE_SERVICES_ENDPOINT" ]; then
        GRAPHRAG_COGNITIVE_SERVICES_ENDPOINT="https://cognitiveservices.azure.com/.default"
        printf "\tsetting GRAPHRAG_COGNITIVE_SERVICES_ENDPOINT=$GRAPHRAG_COGNITIVE_SERVICES_ENDPOINT\n"
    fi
    if [ -z "$GRAPHRAG_IMAGE" ]; then
        GRAPHRAG_IMAGE="graphrag:backend"
        printf "\tsetting GRAPHRAG_IMAGE=$GRAPHRAG_IMAGE\n"
    fi
    printf "Done.\n"
}

populateParams () {
    populateRequiredParams $1
    populateOptionalParams $1
}

createResourceGroupIfNotExists () {
    local location=$1
    local rg=$2
    printf "Checking if resource group $rg exists... "
    az group show -n $rg -o json >/dev/null 2>&1
    if [ $? -ne 0 ]; then
        printf "No.\n"
        printf "Creating resource group... "
        az group create -l $location -n $rg >/dev/null 2>&1
        printf "Done.\n"
    else
        printf "Yes.\n"
    fi
}

createSshkeyIfNotExists () {
    local rg=$1
    local keyName="aks-publickey"
    printf "Checking if sshkey exists... "
    local keyDetails=$(az sshkey show -g $rg --name $keyName -o json 2> /dev/null)
    if [ -z "$keyDetails" ]; then
        printf "No.\n"
        printf "Creating sshkey... "
        local keyDetails=$(az sshkey create -g $rg --name $keyName -o json)
        exitIfCommandFailed $? "Error creating sshkey."
        # TODO Upload private key to keyvault
    else
        printf "Yes.\n"
    fi
    SSHKEY_DETAILS=$keyDetails
}

setupAksCredentials () {
    local rg=$1
    local aks=$2
    printf "Getting AKS credentials... "
    tempResult=$(az aks get-credentials -g $rg -n $aks --overwrite-existing 2>&1)
    exitIfCommandFailed $? "Error getting AKS credentials, exiting...\n$tempResult"
    kubectl config set-context $aks --namespace=$aksNamespace
    printf "Done\n"
}

populateAksVnetInfo () {
    local rg=$1
    local aks=$2
    printf "Retrieving AKS VNet info... "
    local aksDetails=$(AZURE_CLIENTS_SHOW_SECRETS_WARNING=False az aks show -g $rg -n $aks -o json)
    AKS_MANAGED_RG=$(jq -r .networkProfile.loadBalancerProfile.effectiveOutboundIPs[0].resourceGroup <<< $aksDetails)
    AKS_VNET_NAME=$(az network vnet list -g $AKS_MANAGED_RG -o json | jq -r .[0].name)
    AKS_VNET_ID=$(az network vnet list -g $AKS_MANAGED_RG -o json | jq -r .[0].id)
    exitIfValueEmpty "$AKS_MANAGED_RG" "Unable to populate AKS managed resource group name, exiting..."
    exitIfValueEmpty "$AKS_VNET_NAME" "Unable to populate AKS vnet name, exiting..."
    exitIfValueEmpty "$AKS_VNET_ID" "Unable to populate AKS vnet resource id, exiting..."
    printf "Done\n"
}

deployAzureResources () {
    echo "Deploying Azure resources..."
    SSH_PUBLICKEY=$(jq -r .publicKey <<< $SSHKEY_DETAILS)
    exitIfValueEmpty "$SSH_PUBLICKEY" "Unable to read ssh publickey, exiting..."
    datetime="`date +%Y-%m-%d_%H-%M-%S`"
    deploy_name="graphrag-deploy-$datetime"
    echo "Deployment name: $deploy_name"
    AZURE_DEPLOY_RESULTS=$(az deployment group create --name "$deploy_name" --resource-group $RESOURCE_GROUP --no-prompt -o json --template-file ./main.bicep \
        --parameters "resourceBaseName=$RESOURCE_BASE_NAME" \
        --parameters "graphRagName=$RESOURCE_GROUP" \
        --parameters "apimName=$APIM_NAME" \
        --parameters "publisherName=$PUBLISHER_NAME" \
        --parameters "aksSshRsaPublicKey=$SSH_PUBLICKEY" \
        --parameters "publisherEmail=$PUBLISHER_EMAIL" \
        --parameters "enablePrivateEndpoints=$ENABLE_PRIVATE_ENDPOINTS")
    exitIfCommandFailed $? "Error deploying Azure resources..."
    AZURE_OUTPUTS=$(jq -r .properties.outputs <<< $AZURE_DEPLOY_RESULTS)
    exitIfCommandFailed $? "Error parsing outputs from Azure resource deployment..."
}

assignAOAIRoleToManagedIdentity() {
    echo "Assigning 'Cognitive Services OpenAI Contributor' AOAI role to managed identity..."
    local servicePrincipalId=$(jq -r .azure_workload_identity_principal_id.value <<< $AZURE_OUTPUTS)
    exitIfValueEmpty "$servicePrincipalId" "Unable to parse service principal id from azure outputs, exiting..."
    local scope=$(az cognitiveservices account list --query "[?contains(properties.endpoint, '$GRAPHRAG_API_BASE')] | [0].id" -o json)
    scope=$(jq -r <<< $scope) # strip out quotes
    az role assignment create --role "Cognitive Services OpenAI Contributor" --assignee "$servicePrincipalId" --scope "$scope" > /dev/null 2>&1
    exitIfCommandFailed $? "Error assigning role to service principal, exiting..."
}

assignAKSPullRoleToRegistry() {
    echo "Assigning 'ACRPull' role to AKS to access container registry..."
    local rg=$1
    local aks=$2
    local registry=$3
    local registry_id=$(az acr show --name $registry --query id -o json)
    registry_id=$(jq -r <<< $registry_id) # strip out quotes
    exitIfValueEmpty "$registry_id" "Unable to retrieve container registry id, exiting..."
    az aks update --name $aks --resource-group $rg --attach-acr $registry_id -o json > /dev/null 2>&1
    exitIfCommandFailed $? "Error assigning AKS pull role to container registry, exiting..."
}

peerVirtualNetworks () {
    echo "Peering APIM VNet to AKS..."
    local apimVnetName=$(jq -r .azure_apim_vnet_name.value <<< $AZURE_OUTPUTS)
    exitIfValueEmpty "$apimVnetName" "Unable to parse apim vnet name from deployment outputs, exiting..."
    datetime="`date +%Y-%m-%d_%H-%M-%S`"
    AZURE_DEPLOY_RESULTS=$(az deployment group create --name "vnet-apim-to-aks-$datetime" --no-prompt -o json --template-file ./core/vnet/vnet-peering.bicep \
        -g $RESOURCE_GROUP \
        --parameters "name=aks" \
        --parameters "vnetName=$apimVnetName" \
        --parameters "remoteVnetId=$AKS_VNET_ID")
    exitIfCommandFailed $? "Error peering apim vnet to aks..."

    echo "Peering AKS VNet to APIM..."
    local apimVnetId=$(jq -r .azure_apim_vnet_id.value <<< $AZURE_OUTPUTS)
    exitIfValueEmpty "$apimVnetId" "Unable to parse apim vnet resource id from deployment outputs, exiting..."
    datetime="`date +%Y-%m-%d_%H-%M-%S`"
    AZURE_DEPLOY_RESULTS=$(az deployment group create --name "vnet-aks-to-apim-$datetime" --no-prompt -o json --template-file ./core/vnet/vnet-peering.bicep \
        -g $AKS_MANAGED_RG \
        --parameters "name=apim" \
        --parameters "vnetName=$AKS_VNET_NAME" \
        --parameters "remoteVnetId=$apimVnetId")
    exitIfCommandFailed $? "Error peering aks vnet to apim..."
    echo "...peering complete"
}

linkPrivateDnsToAks () {
    echo "Linking private DNS zone to AKS..."
    local privateDnsZoneNames=$(jq -r .azure_private_dns_zones.value <<< $AZURE_OUTPUTS)
    exitIfValueEmpty "$privateDnsZoneNames" "Unable to parse private DNS zone names from deployment outputs, exiting..."
    AZURE_DEPLOY_RESULTS=$(az deployment group create --name "private-dns-to-aks" --no-prompt -o json --template-file ./core/vnet/batch-private-dns-vnet-link.bicep \
        -g $RESOURCE_GROUP \
        --parameters "vnetResourceIds=[\"$AKS_VNET_ID\"]" \
        --parameters "privateDnsZoneNames=$privateDnsZoneNames")
    exitIfCommandFailed $? "Error linking private DNS to AKS vnet..."
    echo "...linking private DNS complete"
}

installGraphRAGHelmChart () {
    printf "Deploying graphrag helm chart... "
    local workloadId=$(jq -r .azure_workload_identity_client_id.value <<< $AZURE_OUTPUTS)
    exitIfValueEmpty "$workloadId" "Unable to parse workload id from Azure outputs, exiting..."

    local serviceAccountName=$(jq -r .azure_aks_service_account_name.value <<< $AZURE_OUTPUTS)
    exitIfValueEmpty "$serviceAccountName" "Unable to parse service account name from Azure outputs, exiting..."

    local appInsightsConnectionString=$(jq -r .azure_app_insights_connection_string.value <<< $AZURE_OUTPUTS)
    exitIfValueEmpty "$appInsightsConnectionString" "Unable to parse app insights connection string from Azure outputs, exiting..."

    local aiSearchName=$(jq -r .azure_ai_search_name.value <<< $AZURE_OUTPUTS)
    exitIfValueEmpty "$aiSearchName" "Unable to parse AI search name from Azure outputs, exiting..."

    local cosmosEndpoint=$(jq -r .azure_cosmosdb_endpoint.value <<< $AZURE_OUTPUTS)
    exitIfValueEmpty "$cosmosEndpoint" "Unable to parse CosmosDB endpoint from Azure outputs, exiting..."
    echo "cosmos endpoint: $cosmosEndpoint"

    local graphragHostname=$(jq -r .azure_graphrag_hostname.value <<< $AZURE_OUTPUTS)
    exitIfValueEmpty "$graphragHostname" "Unable to parse graphrag hostname from deployment outputs, exiting..."

    local storageAccountBlobUrl=$(jq -r .azure_storage_account_blob_url.value <<< $AZURE_OUTPUTS)
    exitIfValueEmpty "$storageAccountBlobUrl" "Unable to parse storage account blob url from deployment outputs, exiting..."
    echo "storage account url: $storageAccountBlobUrl"

    local graphragImageName=$(sed -rn "s/([^:]+).*/\1/p" <<< "$GRAPHRAG_IMAGE")
    local graphragImageVersion=$(sed -rn "s/[^:]+:(.*)/\1/p" <<< "$GRAPHRAG_IMAGE")
    exitIfValueEmpty "$graphragImageName" "Unable to parse graphrag image name, exiting..."
    exitIfValueEmpty "$graphragImageVersion" "Unable to parse graphrag image version, exiting..."

    helm dependency update ./helm/graphrag
    exitIfCommandFailed $? "Error updating helm dependencies, exiting..."
    # Some platforms require manually adding helm repositories to the local helm registry
    # This is a workaround for the issue where the helm chart is not able to add the repository itself
    yq '.dependencies | map(["helm", "repo", "add", .name, .repository] | join(" "))' ./helm/graphrag/Chart.yaml | sed 's/^..//' | sh --;
    helm dependency build ./helm/graphrag --namespace $aksNamespace
    exitIfCommandFailed $? "Error building helm dependencies, exiting..."
    local escapedReporters=$(sed "s/,/\\\,/g" <<< "$REPORTERS")
    reset_x=true
    if ! [ -o xtrace ]; then
        set -x
    else
        reset_x=false
    fi
    # Your script logic goes here
    helm upgrade -i graphrag ./helm/graphrag -f ./helm/graphrag/values.yaml --namespace $aksNamespace --create-namespace \
        --set "serviceAccount.name=$serviceAccountName" \
        --set "serviceAccount.annotations.azure\.workload\.identity/client-id=$workloadId" \
        --set "index.image.repository=$CONTAINER_REGISTRY_SERVER/$graphragImageName" \
        --set "index.image.tag=$graphragImageVersion" \
        --set "query.image.repository=$CONTAINER_REGISTRY_SERVER/$graphragImageName" \
        --set "query.image.tag=$graphragImageVersion" \
        --set "ingress.host=$graphragHostname" \
        --set "graphragConfig.APP_INSIGHTS_CONNECTION_STRING=$appInsightsConnectionString" \
        --set "graphragConfig.AI_SEARCH_URL=https://$aiSearchName.$AISEARCH_ENDPOINT_SUFFIX" \
        --set "graphragConfig.AI_SEARCH_AUDIENCE=$AISEARCH_AUDIENCE" \
        --set "graphragConfig.COSMOS_URI_ENDPOINT=$cosmosEndpoint" \
        --set "graphragConfig.DEBUG_MODE=$DEBUG_MODE" \
        --set "graphragConfig.GRAPHRAG_API_BASE=$GRAPHRAG_API_BASE" \
        --set "graphragConfig.GRAPHRAG_API_VERSION=$GRAPHRAG_API_VERSION" \
        --set "graphragConfig.GRAPHRAG_COGNITIVE_SERVICES_ENDPOINT=$GRAPHRAG_COGNITIVE_SERVICES_ENDPOINT" \
        --set "graphragConfig.GRAPHRAG_LLM_MODEL=$GRAPHRAG_LLM_MODEL" \
        --set "graphragConfig.GRAPHRAG_LLM_DEPLOYMENT_NAME=$GRAPHRAG_LLM_DEPLOYMENT_NAME" \
        --set "graphragConfig.GRAPHRAG_EMBEDDING_MODEL=$GRAPHRAG_EMBEDDING_MODEL" \
        --set "graphragConfig.GRAPHRAG_EMBEDDING_DEPLOYMENT_NAME=$GRAPHRAG_EMBEDDING_DEPLOYMENT_NAME" \
        --set "graphragConfig.REPORTERS=$escapedReporters" \
        --set "graphragConfig.STORAGE_ACCOUNT_BLOB_URL=$storageAccountBlobUrl"

    local helmResult=$?
    "$reset_x" && set +x
    exitIfCommandFailed $helmResult "Error deploying helm chart, exiting..."
}

waitForGraphragExternalIp () {
    local -i maxTries=14
    local available="false"
    printf "Checking for GraphRAG external IP"
    for ((i=0;i < $maxTries; i++)); do
        TMP_GRAPHRAG_SERVICE_IP=$(kubectl get ingress --namespace $aksNamespace graphrag --template "{{ range (index .status.loadBalancer.ingress 0) }}{{.}}{{ end }}" 2> /dev/null)
        if [ $? -eq 0 ]; then
            available="true"
            GRAPHRAG_SERVICE_IP=$TMP_GRAPHRAG_SERVICE_IP
            break
        fi
        sleep 10
        printf "."
    done
    if [ $available == "true" ]; then
        printf " Available.\n"
    else
        printf " Failed.\n"
    fi
}

waitForGraphrag () {
    local backendSwaggerUrl=$1
    local -i maxTries=20
    local available="false"
    printf "Checking for GraphRAG availability"
    for ((i=0;i < $maxTries; i++)); do
        az rest --method get --url $backendSwaggerUrl > /dev/null 2>&1
        if [ $? -eq 0 ]; then
            available="true"
            break
        fi
        sleep 20
        printf "."
    done
    if [ $available == "true" ]; then
        printf " Available.\n"
    else
        printf " Failed.\n"
        exit 1
    fi
}

deployGraphragDnsRecord () {
    waitForGraphragExternalIp
    exitIfValueEmpty "$GRAPHRAG_SERVICE_IP" "Unable to get GraphRAG external IP."

    local dnsZoneName=$(jq -r .azure_dns_zone_name.value <<< $AZURE_OUTPUTS)
    exitIfValueEmpty "$dnsZoneName" "Error parsing DNS zone name from azure outputs, exiting..."
    AZURE_GRAPHRAG_DNS_DEPLOY_RESULT=$(az deployment group create -g $RESOURCE_GROUP --name graphrag-dns --template-file core/vnet/private-dns-zone-a-record.bicep --no-prompt \
        --parameters "name=graphrag" \
        --parameters "dnsZoneName=$dnsZoneName" \
        --parameters "ipv4Address=$GRAPHRAG_SERVICE_IP")
    exitIfCommandFailed $? "Error creating GraphRAG DNS record, exiting..."
}

deployGraphragAPI () {
    echo "Registering GraphRAG API with APIM..."
    local apimGatewayUrl=$(jq -r .azure_apim_url.value <<< $AZURE_OUTPUTS)
    exitIfValueEmpty "$apimGatewayUrl" "Unable to parse APIM gateway url from Azure outputs, exiting..."
    local apimName=$(jq -r .azure_apim_name.value <<< $AZURE_OUTPUTS)
    exitIfValueEmpty "$apimName" "Error parsing apim name from azure outputs, exiting..."
    local backendSwaggerUrl="$apimGatewayUrl/manpage/openapi.json"
    local graphragUrl=$(jq -r .azure_graphrag_url.value <<< $AZURE_OUTPUTS)
    exitIfValueEmpty "$graphragUrl" "Error parsing GraphRAG URL from azure outputs, exiting..."

    waitForGraphrag $backendSwaggerUrl

    # download the openapi spec from the backend and import it into APIM
    az rest --method get --url $backendSwaggerUrl -o json > core/apim/graphrag-openapi.json 2>/dev/null
    AZURE_GRAPHRAG_API_RESULT=$(az deployment group create --resource-group $RESOURCE_GROUP --name graphrag-api --template-file core/apim/apim.graphrag-servicedef.bicep --no-prompt \
        --parameters "backendUrl=$graphragUrl" \
        --parameters "name=GraphRAG" \
        --parameters "apimname=$apimName")
    exitIfCommandFailed $? "Error registering graphrag API, exiting..."
    # cleanup
    rm core/apim/graphrag-openapi.json
}

grantDevAccessToAzureResources() {
    # This function is used to grant the deployer of this script "developer" access to GraphRAG Azure resources
    # by assigning the necessary RBAC roles for Azure Storage, AI Search, and CosmosDB to the signed-in user.
    # This will grant the deployer access to the storage account, cosmos db, and AI search services in the resource group via the Azure portal.
    echo "Granting deployer developer access to Azure resources..."

    # get subscription id of the active subscription
    local azureAccount=$(az account show -o json)
    local subscriptionId=$(jq -r .id <<< $azureAccount)
    exitIfValueEmpty $subscriptionId "Subscription ID not found"

    # get principal/object id of the signed in user
    local azureUserDetails=$(az ad signed-in-user show -o json)
    local principalId=$(jq -r .id <<< $azureUserDetails)
    exitIfValueEmpty $principalId "Principal ID not found"

    # assign storage account roles
    local storageAccountDetails=$(az storage account list --resource-group $RESOURCE_GROUP -o json)
    local storageAccountName=$(jq -r .[0].name <<< $storageAccountDetails)
    exitIfValueEmpty $storageAccountName "Storage account not found"
    az role assignment create --role "Storage Blob Data Contributor" --assignee $principalId --scope "/subscriptions/$subscriptionId/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.Storage/storageAccounts/$storageAccountName" > /dev/null
    az role assignment create --role "Storage Queue Data Contributor" --assignee $principalId --scope "/subscriptions/$subscriptionId/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.Storage/storageAccounts/$storageAccountName" > /dev/null

    # assign cosmos db role
    local cosmosDbDetails=$(az cosmosdb list --resource-group $RESOURCE_GROUP -o json)
    local cosmosDbName=$(jq -r .[0].name <<< $cosmosDbDetails)
    exitIfValueEmpty $cosmosDbName "CosmosDB account not found"
    az cosmosdb sql role assignment create --account-name $cosmosDbName --resource-group $RESOURCE_GROUP --scope "/" --principal-id $principalId --role-definition-id /subscriptions/$subscriptionId/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.DocumentDB/databaseAccounts/graphrag/sqlRoleDefinitions/00000000-0000-0000-0000-000000000002 > /dev/null

    # assign AI search roles
    local searchServiceDetails=$(az search service list --resource-group $RESOURCE_GROUP -o json)
    local searchServiceName=$(jq -r .[0].name <<< $searchServiceDetails)
    exitIfValueEmpty $searchServiceName "AI Search service not found"
    az role assignment create --role "Contributor" --assignee $principalId --scope "/subscriptions/$subscriptionId/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.Search/searchServices/$searchServiceName" > /dev/null
    az role assignment create --role "Search Index Data Contributor" --assignee $principalId --scope "/subscriptions/$subscriptionId/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.Search/searchServices/$searchServiceName" > /dev/null
    az role assignment create --role "Search Index Data Reader" --assignee $principalId --scope "/subscriptions/$subscriptionId/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.Search/searchServices/$searchServiceName" > /dev/null
}

createAcrIfNotExists() {
    # check if container registry exists
    printf "Checking if container registry exists... "
    local existingRegistry
    existingRegistry=$(az acr show --name $CONTAINER_REGISTRY_SERVER --query loginServer -o tsv 2>/dev/null)
    if [ $? -eq 0 ]; then
        printf "Yes. Using existing registry '$existingRegistry'.\n"
        CONTAINER_REGISTRY_SERVER=$existingRegistry
        return 0
    fi
    # else deploy a new container registry
    printf "Creating container registry... "
    AZURE_ACR_DEPLOY_RESULT=$(az deployment group create --resource-group $RESOURCE_GROUP --name "acr-deployment" --template-file core/acr/acr.bicep --only-show-errors --no-prompt -o json \
        --parameters "name=$CONTAINER_REGISTRY_SERVER")
    exitIfCommandFailed $? "Error creating container registry, exiting..."
    CONTAINER_REGISTRY_SERVER=$(jq -r .properties.outputs.loginServer.value <<< $AZURE_ACR_DEPLOY_RESULT)
    exitIfValueEmpty "$CONTAINER_REGISTRY_SERVER" "Unable to parse container registry login server from deployment, exiting..."
    printf "container registry '$CONTAINER_REGISTRY_SERVER' created.\n"
}

deployDockerImageToACR() {
    printf "Deploying docker image '${GRAPHRAG_IMAGE}' to container registry '${CONTAINER_REGISTRY_SERVER}'..."
    local SCRIPT_DIR="$( cd -- "$( dirname -- "${BASH_SOURCE[0]:-$0}"; )" &> /dev/null && pwd 2> /dev/null; )";
    az acr build --registry $CONTAINER_REGISTRY_SERVER -f $SCRIPT_DIR/../docker/Dockerfile-backend --image $GRAPHRAG_IMAGE $SCRIPT_DIR/../ > /dev/null 2>&1
    exitIfCommandFailed $? "Error deploying docker image, exiting..."
    printf " Done.\n"
}

################################################################################
# Help menu                                                                    #
################################################################################
usage() {
   echo
   echo "Usage: bash $0 [-h|d|g] -p <deploy.parameters.json>"
   echo "Description: Deployment script for the GraphRAG Solution Accelerator."
   echo "options:"
   echo "  -h     Print this help menu."
   echo "  -d     Disable private endpoint usage."
   echo "  -g     Developer use only. Grants deployer of this script access to Azure Storage, AI Search, and CosmosDB. Will disable private endpoints (-d) and enable debug mode."
   echo "  -p     A JSON file containing the deployment parameters (deploy.parameters.json)."
   echo
}
# print usage if no arguments are supplied
[ $# -eq 0 ] && usage && exit 0
# parse arguments
ENABLE_PRIVATE_ENDPOINTS=true
DEBUG_MODE=off
GRANT_DEV_ACCESS=0 # false
PARAMS_FILE=""
while getopts ":dgp:h" option; do
    case "${option}" in
        d)
            ENABLE_PRIVATE_ENDPOINTS=false
            ;;
        g)
            ENABLE_PRIVATE_ENDPOINTS=false
            GRANT_DEV_ACCESS=1 # true
            DEBUG_MODE=on
            ;;
        p)
            PARAMS_FILE=${OPTARG}
            ;;
        h | *)
            usage
            exit 0
            ;;
    esac
done
shift $((OPTIND-1))
# check if required arguments are supplied
if [ ! -f $PARAMS_FILE ]; then
    echo "Error: invalid required argument."
    usage
    exit 1
fi
################################################################################
# Main Program                                                                 #
################################################################################
checkRequiredTools

populateParams $PARAMS_FILE

# Create resource group
createResourceGroupIfNotExists $LOCATION $RESOURCE_GROUP

# Create azure container registry if it does not exist
createAcrIfNotExists

# Deploy the graphrag backend docker image to ACR
deployDockerImageToACR

# Generate ssh key for AKS
createSshkeyIfNotExists $RESOURCE_GROUP

# Deploy Azure resources
deployAzureResources

# Setup RBAC roles to access an already deployed Azure OpenAI service.
AKS_NAME=$(jq -r .azure_aks_name.value <<< $AZURE_OUTPUTS)
exitIfValueEmpty "$AKS_NAME" "Unable to parse AKS name from azure deployment outputs, exiting..."
assignAOAIRoleToManagedIdentity
assignAKSPullRoleToRegistry $RESOURCE_GROUP $AKS_NAME $CONTAINER_REGISTRY_SERVER

# Deploy kubernetes resources
setupAksCredentials $RESOURCE_GROUP $AKS_NAME
populateAksVnetInfo $RESOURCE_GROUP $AKS_NAME
if [ "$ENABLE_PRIVATE_ENDPOINTS" = "true" ]; then
    linkPrivateDnsToAks
fi
peerVirtualNetworks

# Install GraphRAG helm chart
installGraphRAGHelmChart

# Import and setup GraphRAG API in APIM
deployGraphragDnsRecord
deployGraphragAPI

if [ $GRANT_DEV_ACCESS -eq 1 ]; then
    grantDevAccessToAzureResources
fi

echo "SUCCESS: GraphRAG deployment to resource group $RESOURCE_GROUP complete"
