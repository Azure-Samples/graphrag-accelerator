# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
#!/usr/bin/env bash

# set -ux # uncomment this line to debug

aksNamespace="graphrag"

# OPTIONAL PARAMS
AISEARCH_AUDIENCE=""
AISEARCH_ENDPOINT_SUFFIX=""
APIM_NAME=""
APIM_TIER=""
CLOUD_NAME=""
GRAPHRAG_IMAGE=""
PUBLISHER_EMAIL=""
PUBLISHER_NAME=""
RESOURCE_BASE_NAME=""
COGNITIVE_SERVICES_AUDIENCE=""
CONTAINER_REGISTRY_NAME=""

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

errorBanner () {
# https://cowsay-svelte.vercel.app
cat << "EOF"
 ________________________________
/  Uh oh, an error has occurred. \
\  Please see message below.     /
 ‾‾‾‾‾‾‾‾‾‾/‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾
          /
      __ /
     /  \
    ~    ~
   / \  /_\
   \o/  \o/
    |    |
    ||   |/
    ||   ||
    ||   ||
    | \_/ |
    \     /
     \___/
EOF
printf "\n"
}

successBanner () {
# https://patorjk.com/software/taag
cat << "EOF"
   _____                             __       _
  / ____|                           / _|     | |
 | (___  _   _  ___ ___ ___ ___ ___| |_ _   _| |
  \___ \| | | |/ __/ __/ _ / __/ __|  _| | | | |
  ____) | |_| | (_| (_|  __\__ \__ | | | |_| | |
 |_____/ \__,_|\___\___\___|___|___|_|  \__,_|_|      _   _
     | |          | |                                | | | |
   __| | ___ _ __ | | ___  _   _ _ __ ___   ___ _ __ | |_| |
  / _` |/ _ | '_ \| |/ _ \| | | | '_ ` _ \ / _ | '_ \| __| |
 | (_| |  __| |_) | | (_) | |_| | | | | | |  __| | | | |_|_|
  \__,_|\___| .__/|_|\___/ \__, |_| |_| |_|\___|_| |_|\__(_)
            | |             __/ |
            |_|            |___/
EOF
printf "\n\n"
}

startBanner () {
# https://patorjk.com/software/taag
cat << "EOF"
   _____                 _     _____           _____
  / ____|               | |   |  __ \    /\   / ____|
 | |  __ _ __ __ _ _ __ | |__ | |__) |  /  \ | |  __
 | | |_ | '__/ _` | '_ \| '_ \|  _  /  / /\ \| | |_ |
 | |__| | | | (_| | |_) | | | | | \ \ / ____ | |__| |
  \_____|_|  \__,_| .__/|_| |_|_|  \_/_/_   \_\_____|
     /\           | | | |              | |
    /  \   ___ ___|_|_| | ___ _ __ __ _| |_ ___  _ __
   / /\ \ / __/ __/ _ | |/ _ | '__/ _` | __/ _ \| '__|
  / ____ | (_| (_|  __| |  __| | | (_| | || (_) | |
 /_/    \_\___\___\___|_|\___|_|  \__,_|\__\___/|_|
EOF
printf "\n\n"
}

exitIfCommandFailed () {
    local res=$1
    local msg=$2
    if [ 0 -ne $res ]; then
        errorBanner
        printf "$msg\n"
        exit 1
    fi
}

exitIfValueEmpty () {
    local value=$1
    local msg=$2
    # check if the value is empty or "null" (jq returns "null" when a value is not found)
    if [ -z "$value" ] || [[ "$value" == "null" ]]; then
        errorBanner
        printf "$msg\n"
        exit 1
    fi
}

exitIfThresholdExceeded () {
    local value=$1
    local threshold=$2
    local msg=$3
    # throw an error if input value exceeds threshold
    if [ $value -ge $threshold ]; then
        errorBanner
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
        # NOTE: older acceptable versions of jq report a version
        # number without the patch number. if patch version is
        # not present, set it to 0
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
        if [ -z "$paramValue" ] || [ "$paramValue" == "null" ]; then
            echo "Parameter $param is required, exiting..."
            exit 1
        fi
    done
}

populateRequiredParams () {
    local paramsFile=$1
    printf "Checking required parameters... "
    checkRequiredParams $paramsFile
    # The jq command below sets environment variable based on the key-value
    # pairs in a JSON-formatted file
    eval $(jq -r 'to_entries | .[] | "export \(.key)=\(.value)"' $paramsFile)
    printf "Done.\n"
}

populateOptionalParams () {
    # Optional environment variables may be set in the parameters file.
    # Otherwise using the default values below is recommended.
    local paramsFile=$1
    echo "Checking optional parameters..."
    if [ -z "$APIM_TIER" ]; then
        APIM_TIER="Developer"
        printf "\tsetting APIM_TIER=$APIM_TIER\n"
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
    if [ -z "$CLOUD_NAME" ]; then
        CLOUD_NAME="AzurePublicCloud"
        printf "\tsetting CLOUD_NAME=$CLOUD_NAME\n"
    fi
    if [ ! -z "$RESOURCE_BASE_NAME" ]; then
        printf "\tsetting RESOURCE_BASE_NAME=$RESOURCE_BASE_NAME\n"
    fi
    if [ -z "$COGNITIVE_SERVICES_AUDIENCE" ]; then
        COGNITIVE_SERVICES_AUDIENCE="https://cognitiveservices.azure.com/.default"
        printf "\tsetting COGNITIVE_SERVICES_AUDIENCE=$COGNITIVE_SERVICES_AUDIENCE\n"
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
    az group show -n $rg -o json > /dev/null 2>&1
    if [ $? -ne 0 ]; then
        printf "No.\n"
        printf "Creating resource group... "
        az group create -l $location -n $rg > /dev/null 2>&1
        printf "Done.\n"
    else
        printf "Yes.\n"
    fi
}

getAksCredentials () {
    local rg=$1
    local aks=$2
    printf "Getting AKS credentials... "
    az aks get-credentials -g $rg -n $aks --overwrite-existing > /dev/null 2>&1
    exitIfCommandFailed $? "Error getting AKS credentials, exiting..."
    kubelogin convert-kubeconfig -l azurecli
    exitIfCommandFailed $? "Error logging into AKS, exiting..."
    # get principal/object id of the signed in user
    local principalId=$(az ad signed-in-user show --output json | jq -r .id)
    exitIfValueEmpty $principalId "Principal ID of deployer not found"
    # assign "Azure Kubernetes Service RBAC Admin" role to deployer
    local scope=$(az aks show --resource-group $rg --name $aks --query "id" -o tsv)
    exitIfValueEmpty "$scope" "Unable to get AKS scope, exiting..."
    az role assignment create --role "Azure Kubernetes Service RBAC Cluster Admin" --assignee-object-id $principalId --scope $scope
    exitIfCommandFailed $? "Error assigning 'Azure Kubernetes Service RBAC Cluster Admin' role to deployer, exiting..."
    kubectl config set-context $aks --namespace=$aksNamespace
    printf "Done\n"
}

checkForApimSoftDelete () {
    printf "Checking if APIM was soft-deleted... "
    # This is an optional step to check if an APIM instance previously existed in the
    # resource group and is in a soft-deleted state. If so, purge it before deploying
    # a new APIM instance to prevent conflicts with the new deployment.
    local RESULTS=$(az apim deletedservice list -o json --query "[?contains(serviceId, 'resourceGroups/$RESOURCE_GROUP/')].{name:name, location:location}")
    exitIfCommandFailed $? "Error checking for soft-deleted APIM instances, exiting..."
    local apimName=$(jq -r .[0].name <<< $RESULTS)
    local location=$(jq -r .[0].location <<< $RESULTS)
    # jq returns "null" if a value is not found
    if [ -z "$apimName" ] || [[ "$apimName" == "null" ]] || [ -z "$location" ] || [[ "$location" == "null" ]]; then
        printf "Done.\n"
        return 0
    fi
    if [ ! -z "$apimName" ] && [ ! -z "$location" ]; then
        printf "\nAPIM instance found in soft-deleted state. Purging...\n"
        az apim deletedservice purge -n $apimName --location "$location" > /dev/null
    fi
    printf "Done.\n"
}

deployAzureResources () {
    echo "Deploying Azure resources..."
    # get principal/object id of the signed in user
    local deployerPrincipalId=$(az ad signed-in-user show --output json | jq -r .id)
    exitIfValueEmpty $deployerPrincipalId "Principal ID of deployer not found"
    local datetime="`date +%Y-%m-%d_%H-%M-%S`"
    local deployName="graphrag-deploy-$datetime"
    echo "Deployment name: $deployName"
    local AZURE_DEPLOY_RESULTS=$(az deployment group create --name "$deployName" \
        --no-prompt \
        --resource-group $RESOURCE_GROUP \
        --template-file ./main.bicep \
        --parameters "resourceBaseName=$RESOURCE_BASE_NAME" \
        --parameters "resourceGroup=$RESOURCE_GROUP" \
        --parameters "apimName=$APIM_NAME" \
        --parameters "apimTier=$APIM_TIER" \
        --parameters "apiPublisherName=$PUBLISHER_NAME" \
        --parameters "apiPublisherEmail=$PUBLISHER_EMAIL" \
        --parameters "enablePrivateEndpoints=$ENABLE_PRIVATE_ENDPOINTS" \
        --parameters "acrName=$CONTAINER_REGISTRY_NAME" \
        --parameters "deployerPrincipalId=$deployerPrincipalId" \
        --output json)
    # errors in deployment may not be caught by exitIfCommandFailed function so we also check the output for errors
    exitIfCommandFailed $? "Error deploying Azure resources..."
    exitIfValueEmpty "$AZURE_DEPLOY_RESULTS" "Error deploying Azure resources..."
    AZURE_OUTPUTS=$(jq -r .properties.outputs <<< $AZURE_DEPLOY_RESULTS)
    exitIfCommandFailed $? "Error parsing outputs from Azure deployment..."
    exitIfValueEmpty "$AZURE_OUTPUTS" "Error parsing outputs from Azure deployment..."
    assignAOAIRoleToManagedIdentity
}

validateSKUs() {
    # Run SKU validation functions unless skip flag is set
    local location=$1
    local validate_skus=$2
    if [ $validate_skus = true ]; then
        checkSKUAvailability $location
        checkSKUQuotas $location
    fi
}

checkSKUAvailability() {
    # Function to validate that the required SKUs are not restricted for the given region
    printf "Checking cloud region for VM sku availability... "
    local location=$1
    local sku_checklist=("standard_d4s_v5" "standard_d8s_v5" "standard_e8s_v5")
    for sku in ${sku_checklist[@]}; do
        local sku_check_result=$(
            az vm list-skus --location $location --size $sku --output json
        )
        local sku_validation_listing=$(jq -r .[0].name <<< $sku_check_result)
        exitIfValueEmpty $sku_validation_listing "SKU $sku is restricted for location $location under the current subscription."
    done
    printf "Done.\n"
}

checkSKUQuotas() {
    # Function to validation that the SKU quotas would not be exceeded during deployment
    printf "Checking Location for SKU Quota Usage... "
    local location=$1
    local vm_usage_report=$(
        az vm list-usage --location $location -o json
    )

    # Check quota for Standard DSv5 Family vCPUs
    local dsv5_usage_report=$(jq -c '.[] | select(.localName | contains("Standard DSv5 Family vCPUs"))' <<< $vm_usage_report)
    local dsv5_limit=$(jq -r .limit <<< $dsv5_usage_report)
    local dsv5_currVal=$(jq -r .currentValue <<< $dsv5_usage_report)
    local dsv5_reqVal=$(expr $dsv5_currVal + 12)
    exitIfThresholdExceeded $dsv5_reqVal $dsv5_limit "Not enough Standard DSv5 Family vCPU quota for deployment. At least 12 vCPU is required."

    # Check quota for Standard ESv5 Family vCPUs
    local esv5_usage_report=$(jq -c '.[] | select(.localName | contains("Standard ESv5 Family vCPUs"))' <<< $vm_usage_report)
    local esv5_limit=$(jq -r .limit <<< $esv5_usage_report)
    local esv5_currVal=$(jq -r .currentValue <<< $esv5_usage_report)
    local esv5_reqVal=$(expr $esv5_currVal + 8)
    exitIfThresholdExceeded $esv5_reqVal $esv5_limit "Not enough Standard ESv5 Family vCPU quota for deployment. At least 8 vCPU is required."
    printf "Done.\n"
}

assignAOAIRoleToManagedIdentity() {
    printf "Assigning 'Cognitive Services OpenAI Contributor' role to managed identity... "
    local servicePrincipalId=$(jq -r .azure_workload_identity_principal_id.value <<< $AZURE_OUTPUTS)
    exitIfValueEmpty "$servicePrincipalId" "Unable to parse service principal id from azure outputs, exiting..."
    local scope=$(az cognitiveservices account list --query "[?contains(properties.endpoint, '$GRAPHRAG_API_BASE')] | [0].id" -o tsv)
    az role assignment create --only-show-errors \
        --role "Cognitive Services OpenAI Contributor" \
        --assignee "$servicePrincipalId" \
        --scope "$scope" > /dev/null 2>&1
    exitIfCommandFailed $? "Error assigning role to service principal, exiting..."
    printf "Done.\n"
}

installGraphRAGHelmChart () {
    echo "Deploying graphrag helm chart... "
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

    local graphragHostname=$(jq -r .azure_app_hostname.value <<< $AZURE_OUTPUTS)
    exitIfValueEmpty "$graphragHostname" "Unable to parse graphrag hostname from deployment outputs, exiting..."

    local storageAccountBlobUrl=$(jq -r .azure_storage_account_blob_url.value <<< $AZURE_OUTPUTS)
    exitIfValueEmpty "$storageAccountBlobUrl" "Unable to parse storage account blob url from deployment outputs, exiting..."

    local containerRegistryName=$(jq -r .azure_acr_login_server.value <<< $AZURE_OUTPUTS)
    exitIfValueEmpty "$containerRegistryName" "Unable to parse container registry url from deployment outputs, exiting..."

    local graphragImageName=$(sed -rn "s/([^:]+).*/\1/p" <<< "$GRAPHRAG_IMAGE")
    local graphragImageVersion=$(sed -rn "s/[^:]+:(.*)/\1/p" <<< "$GRAPHRAG_IMAGE")
    exitIfValueEmpty "$graphragImageName" "Unable to parse graphrag image name, exiting..."
    exitIfValueEmpty "$graphragImageVersion" "Unable to parse graphrag image version, exiting..."

    reset_x=true
    if ! [ -o xtrace ]; then
        set -x
    else
        reset_x=false
    fi

    helm upgrade -i graphrag ./helm/graphrag -f ./helm/graphrag/values.yaml \
        --namespace $aksNamespace --create-namespace \
        --set "serviceAccount.name=$serviceAccountName" \
        --set "serviceAccount.annotations.azure\.workload\.identity/client-id=$workloadId" \
        --set "master.image.repository=$containerRegistryName/$graphragImageName" \
        --set "master.image.tag=$graphragImageVersion" \
        --set "ingress.host=$graphragHostname" \
        --set "graphragConfig.APPLICATIONINSIGHTS_CONNECTION_STRING=$appInsightsConnectionString" \
        --set "graphragConfig.AI_SEARCH_URL=https://$aiSearchName.$AISEARCH_ENDPOINT_SUFFIX" \
        --set "graphragConfig.AI_SEARCH_AUDIENCE=$AISEARCH_AUDIENCE" \
        --set "graphragConfig.COSMOS_URI_ENDPOINT=$cosmosEndpoint" \
        --set "graphragConfig.GRAPHRAG_API_BASE=$GRAPHRAG_API_BASE" \
        --set "graphragConfig.GRAPHRAG_API_VERSION=$GRAPHRAG_API_VERSION" \
        --set "graphragConfig.COGNITIVE_SERVICES_AUDIENCE=$COGNITIVE_SERVICES_AUDIENCE" \
        --set "graphragConfig.GRAPHRAG_LLM_MODEL=$GRAPHRAG_LLM_MODEL" \
        --set "graphragConfig.GRAPHRAG_LLM_DEPLOYMENT_NAME=$GRAPHRAG_LLM_DEPLOYMENT_NAME" \
        --set "graphragConfig.GRAPHRAG_EMBEDDING_MODEL=$GRAPHRAG_EMBEDDING_MODEL" \
        --set "graphragConfig.GRAPHRAG_EMBEDDING_DEPLOYMENT_NAME=$GRAPHRAG_EMBEDDING_DEPLOYMENT_NAME" \
        --set "graphragConfig.STORAGE_ACCOUNT_BLOB_URL=$storageAccountBlobUrl"

    local helmResult=$?
    "$reset_x" && set +x
    exitIfCommandFailed $helmResult "Error deploying helm chart, exiting..."
}

waitForExternalIp () {
    local -i maxTries=14
    local available="false"
    printf "Checking for GraphRAG external IP"
    for ((i=0;i < $maxTries; i++)); do
        TMP_GRAPHRAG_SERVICE_IP=$(kubectl get ingress --namespace graphrag graphrag -o json | jq -r .status.loadBalancer.ingress[0].ip)
        # jq returns "null" if a value is not found
        if [[ "$TMP_GRAPHRAG_SERVICE_IP" != "null" ]]; then
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

waitForGraphragBackend () {
    local backendSwaggerUrl=$1
    local -i maxTries=20
    local available="false"
    printf "Checking for GraphRAG API availability..."
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
        exitIfValueEmpty "" "GraphRAG API unavailable, exiting..."
    fi
}

deployDnsRecord () {
    waitForExternalIp
    exitIfValueEmpty "$GRAPHRAG_SERVICE_IP" "Unable to get GraphRAG external IP."
    local dnsZoneName=$(jq -r .azure_dns_zone_name.value <<< $AZURE_OUTPUTS)
    exitIfValueEmpty "$dnsZoneName" "Error parsing DNS zone name from azure outputs, exiting..."
    az deployment group create --only-show-errors --no-prompt \
        --name graphrag-dns \
        --resource-group $RESOURCE_GROUP \
        --template-file core/vnet/private-dns-zone-a-record.bicep \
        --parameters "name=graphrag" \
        --parameters "dnsZoneName=$dnsZoneName" \
        --parameters "ipv4Address=$GRAPHRAG_SERVICE_IP" > /dev/null
    exitIfCommandFailed $? "Error creating GraphRAG DNS record, exiting..."
}

deployGraphragAPI () {
    echo "Registering GraphRAG API with APIM..."
    local apimGatewayUrl=$(jq -r .azure_apim_gateway_url.value <<< $AZURE_OUTPUTS)
    exitIfValueEmpty "$apimGatewayUrl" "Unable to parse APIM gateway url from Azure outputs, exiting..."
    local apimName=$(jq -r .azure_apim_name.value <<< $AZURE_OUTPUTS)
    exitIfValueEmpty "$apimName" "Error parsing apim name from azure outputs, exiting..."
    local backendSwaggerUrl="$apimGatewayUrl/manpage/openapi.json"
    local graphragUrl=$(jq -r .azure_app_url.value <<< $AZURE_OUTPUTS)
    exitIfValueEmpty "$graphragUrl" "Error parsing GraphRAG URL from azure outputs, exiting..."

    waitForGraphragBackend $backendSwaggerUrl

    # download the openapi spec from the backend and load it into APIM
    az rest --only-show-errors --method get --url $backendSwaggerUrl -o json > core/apim/graphrag-openapi.json
    exitIfCommandFailed $? "Error downloading graphrag openapi spec, exiting..."
    az deployment group create --only-show-errors --no-prompt \
        --name upload-graphrag-api \
        --resource-group $RESOURCE_GROUP \
        --template-file core/apim/apim.graphrag-servicedef.bicep \
        --parameters "backendUrl=$graphragUrl" \
        --parameters "name=GraphRAG" \
        --parameters "apimname=$apimName" > /dev/null
    exitIfCommandFailed $? "Error registering graphrag API, exiting..."
    # cleanup
    rm core/apim/graphrag-openapi.json
}

grantDevAccessToAzureResources() {
    # This function is used to grant the deployer of this script "developer" access
    # to GraphRAG Azure resources by assigning the necessary RBAC roles for
    # Azure Storage, AI Search, and CosmosDB to the signed-in user. This will grant
    # the deployer access to data in the storage account, cosmos db, and AI search services
    # from the Azure portal.
    echo "Granting deployer developer access to Azure resources..."

    # get subscription id of the active subscription
    local subscriptionId=$(az account show --output json | jq -r .id)
    exitIfValueEmpty $subscriptionId "Subscription ID not found"

    # get principal/object id of the signed in user
    local principalId=$(az ad signed-in-user show --output json | jq -r .id)
    exitIfValueEmpty $principalId "Principal ID of deployer not found"

    # assign storage account roles
    local storageAccountName=$(az storage account list --resource-group $RESOURCE_GROUP --output json | jq -r .[0].name)
    exitIfValueEmpty $storageAccountName "Storage account not found"
    az role assignment create \
        --role "Storage Blob Data Contributor" \
        --assignee $principalId \
        --scope "/subscriptions/$subscriptionId/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.Storage/storageAccounts/$storageAccountName" > /dev/null

    # assign cosmos db role
    local cosmosDbName=$(az cosmosdb list --resource-group $RESOURCE_GROUP -o json | jq -r .[0].name)
    exitIfValueEmpty $cosmosDbName "CosmosDB account not found"
    az cosmosdb sql role assignment create \
        --account-name $cosmosDbName \
        --resource-group $RESOURCE_GROUP \
        --scope "/" \
        --principal-id $principalId \
        --role-definition-id /subscriptions/$subscriptionId/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.DocumentDB/databaseAccounts/graphrag/sqlRoleDefinitions/00000000-0000-0000-0000-000000000002 > /dev/null

    # assign AI search roles
    local searchServiceName=$(az search service list --resource-group $RESOURCE_GROUP -o json | jq -r .[0].name)
    exitIfValueEmpty $searchServiceName "AI Search service not found"
    az role assignment create \
        --role "Contributor" \
        --assignee $principalId \
        --scope "/subscriptions/$subscriptionId/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.Search/searchServices/$searchServiceName" > /dev/null
    az role assignment create \
        --role "Search Index Data Contributor" \
        --assignee $principalId \
        --scope "/subscriptions/$subscriptionId/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.Search/searchServices/$searchServiceName" > /dev/null
    az role assignment create \
        --role "Search Index Data Reader" \
        --assignee $principalId \
        --scope "/subscriptions/$subscriptionId/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.Search/searchServices/$searchServiceName" > /dev/null
}

deployDockerImageToACR() {
    local containerRegistry=$(jq -r .azure_acr_login_server.value <<< $AZURE_OUTPUTS)
    exitIfValueEmpty "$containerRegistry" "Unable to parse container registry from azure deployment outputs, exiting..."
    echo "Deploying docker image '${GRAPHRAG_IMAGE}' to container registry '${containerRegistry}'..."
    local scriptDir="$( cd -- "$( dirname -- "${BASH_SOURCE[0]:-$0}"; )" &> /dev/null && pwd 2> /dev/null; )";
    az acr build --only-show-errors \
        --registry $containerRegistry \
        --file $scriptDir/../docker/Dockerfile-backend \
        --image $GRAPHRAG_IMAGE \
        $scriptDir/../
    exitIfCommandFailed $? "Error deploying docker image, exiting..."
}

################################################################################
# Help menu                                                                    #
################################################################################
usage() {
   echo
   echo "Usage: bash $0 [-h|d|g|s] -p <deploy.parameters.json>"
   echo "Description: Deployment script for the GraphRAG Solution Accelerator."
   echo "options:"
   echo "  -h     Print this help menu."
   echo "  -d     Disable private endpoint usage."
   echo "  -g     Developer mode. Grants deployer of this script access to Azure Storage, AI Search, and CosmosDB. Will disable private endpoints (-d) and enable debug mode."
   echo "  -s     Skip validation of SKU availability and quota for a faster deployment"
   echo "  -p     A JSON file containing the deployment parameters (deploy.parameters.json)."
   echo
}
# print usage if no arguments are supplied
[ $# -eq 0 ] && usage && exit 0
# parse arguments
ENABLE_PRIVATE_ENDPOINTS=true
VALIDATE_SKUS_FLAG=true
GRANT_DEV_ACCESS=0 # false
PARAMS_FILE=""
while getopts ":dgsp:h" option; do
    case "${option}" in
        d)
            ENABLE_PRIVATE_ENDPOINTS=false
            ;;
        g)
            ENABLE_PRIVATE_ENDPOINTS=false
            GRANT_DEV_ACCESS=1 # true
            ;;
        s)
            VALIDATE_SKUS_FLAG=false
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
startBanner

checkRequiredTools
populateParams $PARAMS_FILE

# Check SKU availability and quotas
validateSKUs $LOCATION $VALIDATE_SKUS_FLAG

# Create resource group
createResourceGroupIfNotExists $LOCATION $RESOURCE_GROUP

# Deploy Azure resources
checkForApimSoftDelete
deployAzureResources

# Deploy the graphrag backend docker image to ACR
deployDockerImageToACR

# Retrieve AKS credentials and install GraphRAG helm chart
AKS_NAME=$(jq -r .azure_aks_name.value <<< $AZURE_OUTPUTS)
getAksCredentials $RESOURCE_GROUP $AKS_NAME
installGraphRAGHelmChart

# Import and setup GraphRAG API in APIM
deployDnsRecord
deployGraphragAPI

if [ $GRANT_DEV_ACCESS -eq 1 ]; then
    grantDevAccessToAzureResources
fi

successBanner
