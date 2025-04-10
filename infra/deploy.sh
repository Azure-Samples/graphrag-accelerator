#!/usr/bin/env bash
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

set -ux # uncomment this line to debug
# TODO: use https://www.shellcheck.net to lint this script and make recommended updates

aksNamespace="graphrag"

# Optional parameters with default values
AI_SEARCH_AUDIENCE="https://search.azure.com"
AI_SEARCH_TIER="standard"
AISEARCH_ENDPOINT_SUFFIX="search.windows.net"
APIM_NAME=""
APIM_TIER="Developer"
CLOUD_NAME="AzurePublicCloud"
GRAPHRAG_IMAGE="graphrag:backend"
PUBLISHER_EMAIL="publisher@microsoft.com"
PUBLISHER_NAME="publisher"
RESOURCE_BASE_NAME=""
COGNITIVE_SERVICES_AUDIENCE="https://cognitiveservices.azure.com/.default"
CONTAINER_REGISTRY_LOGIN_SERVER=""
GRAPHRAG_API_BASE=""
GRAPHRAG_API_VERSION="2023-03-15-preview"
GRAPHRAG_LLM_MODEL="gpt-4"
GRAPHRAG_LLM_MODEL_VERSION="turbo-2024-04-09"
GRAPHRAG_LLM_DEPLOYMENT_NAME="gpt-4"
GRAPHRAG_LLM_MODEL_QUOTA="80"
GRAPHRAG_EMBEDDING_MODEL="text-embedding-ada-002"
GRAPHRAG_EMBEDDING_MODEL_VERSION="2"
GRAPHRAG_EMBEDDING_DEPLOYMENT_NAME="text-embedding-ada-002"
GRAPHRAG_EMBEDDING_MODEL_QUOTA="300"
GRAPHRAG_LLM_MODEL_CONCURRENT_REQUEST="15"
GRAPHRAG_EMBEDDING_MODEL_CONCURRENT_REQUEST="15"

requiredParams=(
    LOCATION
    RESOURCE_GROUP
)
optionalParams=(
    AI_SEARCH_AUDIENCE
    AISEARCH_ENDPOINT_SUFFIX
    APIM_NAME
    APIM_TIER
    AI_SEARCH_TIER
    CLOUD_NAME
    GRAPHRAG_IMAGE
    PUBLISHER_EMAIL
    PUBLISHER_NAME
    RESOURCE_BASE_NAME
    COGNITIVE_SERVICES_AUDIENCE
    CONTAINER_REGISTRY_LOGIN_SERVER
    GRAPHRAG_API_BASE
    GRAPHRAG_API_VERSION
    GRAPHRAG_LLM_MODEL
    GRAPHRAG_LLM_MODEL_QUOTA
    GRAPHRAG_LLM_MODEL_VERSION
    GRAPHRAG_LLM_DEPLOYMENT_NAME
    GRAPHRAG_EMBEDDING_MODEL
    GRAPHRAG_EMBEDDING_MODEL_QUOTA
    GRAPHRAG_EMBEDDING_MODEL_VERSION
    GRAPHRAG_EMBEDDING_DEPLOYMENT_NAME
    GRAPHRAG_LLM_MODEL_CONCURRENT_REQUEST
    GRAPHRAG_EMBEDDING_MODEL_CONCURRENT_REQUEST
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
    local JQ_VERSION
    local major minor patch
    local YQ_VERSION
    local AZ_VERSION

    printf "Checking for required tools... "

    which sed > /dev/null
    exitIfCommandFailed $? "sed is required, exiting..."

    which kubectl > /dev/null
    exitIfCommandFailed $? "kubectl is required, exiting..."

    which kubelogin > /dev/null
    exitIfCommandFailed $? "kubelogin is required, exiting..."

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
    JQ_VERSION=$(jq --version | cut -d'-' -f2)
    IFS='.' read -r major minor patch <<< "$JQ_VERSION"
    if [ -z $patch ]; then
        # NOTE: older acceptable versions of jq report a version
        # number without the patch number. if patch version is
        # not present, set it to 0
        patch=0
        JQ_VERSION="$major.$minor.$patch"
    fi
    YQ_VERSION=$(yq --version | awk '{print substr($4,2)}')
    AZ_VERSION=$(az version -o json | jq -r '.["azure-cli"]')
    versionCheck "jq" $JQ_VERSION "1.6.0"
    versionCheck "yq" $YQ_VERSION "4.40.7"
    versionCheck "az cli" $AZ_VERSION "2.55.0"
    printf "Done.\n"
}

checkRequiredParams () {
    local paramsFile=$1
    local paramValue
    for param in "${requiredParams[@]}"; do
        paramValue=$(jq -r .$param < $paramsFile)
        if [ -z "$paramValue" ] || [ "$paramValue" == "null" ]; then
            echo "Parameter $param is required, exiting..."
            exit 1
        fi
    done
}

populateParams () {
    local paramsFile=$1
    printf "Checking required parameters... "
    checkRequiredParams $paramsFile
    printf "Done.\n"

    # The jq command below sets env variables based on the key-value pairs defined in a JSON-formatted parameters file.
    # This will override default values of previously defined env variables.
    eval $(jq -r 'to_entries | .[] | "export \(.key)=\(.value)"' $paramsFile)

    # print environment variables for end user
    echo "Setting environment variables..."
    for param in "${requiredParams[@]}"; do
        # skip empty variables
        if [ -z "${!param}" ]; then
            continue
        fi
        printf "\t$param = ${!param}\n"
    done
    for param in "${optionalParams[@]}"; do
        # skip empty variables
        if [ -z "${!param}" ]; then
            continue
        fi
        printf "\t$param = ${!param}\n"
    done
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
    local aks_name
    local principalId
    local scope

    printf "Getting AKS credentials... "
    aks_name=$(jq -r .azure_aks_name.value <<< $AZURE_DEPLOY_OUTPUTS)
    az aks get-credentials -g $rg -n $aks_name --overwrite-existing > /dev/null 2>&1
    exitIfCommandFailed $? "Error getting AKS credentials, exiting..."
    kubelogin convert-kubeconfig -l azurecli
    exitIfCommandFailed $? "Error logging into AKS, exiting..."
    # get principal/object id of the signed in user
    principalId=$(az ad signed-in-user show --output json | jq -r .id)
    exitIfValueEmpty $principalId "Principal ID of deployer not found"
    # assign "Azure Kubernetes Service RBAC Admin" role to deployer
    scope=$(az aks show --resource-group $rg --name $aks_name --query "id" -o tsv)
    exitIfValueEmpty "$scope" "Unable to get AKS scope, exiting..."
    az role assignment create --role "Azure Kubernetes Service RBAC Cluster Admin" --assignee-object-id $principalId --scope $scope
    exitIfCommandFailed $? "Error assigning 'Azure Kubernetes Service RBAC Cluster Admin' role to deployer, exiting..."
    kubectl config set-context $aks_name --namespace=$aksNamespace
    printf "Done\n"
}

checkForApimSoftDelete () {
    local apimName
    local location
    local deleted_service_list_results

    printf "Checking if APIM was soft-deleted... "
    # This is an optional step to check if an APIM instance previously existed in the
    # resource group and is in a soft-deleted state. If so, purge it before deploying
    # a new APIM instance to prevent conflicts with the new deployment.
    deleted_service_list_results=$(az apim deletedservice list -o json --query "[?contains(serviceId, 'resourceGroups/$RESOURCE_GROUP/')].{name:name, location:location}")
    exitIfCommandFailed $? "Error checking for soft-deleted APIM instances, exiting..."
    apimName=$(jq -r .[0].name <<< $deleted_service_list_results)
    location=$(jq -r .[0].location <<< $deleted_service_list_results)
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
    local deployAoai
    local existingAoaiId=""
    local deployAcr
    local graphragImageName
    local graphragImageVersion

    echo "Deploying Azure resources..."
    # deploy AOAI if the user did not provide links to an existing AOAI service
    deployAoai="true"
    if [ -n "$GRAPHRAG_API_BASE" ]; then
        deployAoai="false"
        existingAoaiId=$(az cognitiveservices account list --query "[?contains(properties.endpoint, '$GRAPHRAG_API_BASE')].id" -o tsv)
        exitIfValueEmpty "$existingAoaiId" "Unable to get AOAI resource id from GRAPHRAG_API_BASE, exiting..."
    fi
    deployAcr="true"
    if [ -n "$CONTAINER_REGISTRY_LOGIN_SERVER" ]; then
        deployAcr="false"
    fi
    graphragImageName=$(sed -rn "s/([^:]+).*/\1/p" <<< "$GRAPHRAG_IMAGE")
    graphragImageVersion=$(sed -rn "s/[^:]+:(.*)/\1/p" <<< "$GRAPHRAG_IMAGE")
    exitIfValueEmpty "$graphragImageName" "Unable to parse graphrag docker image name, exiting..."
    exitIfValueEmpty "$graphragImageVersion" "Unable to parse graphrag docker image version, exiting..."

    local datetime deployName AZURE_DEPLOY_RESULTS
    datetime="`date +%Y-%m-%d_%H-%M-%S`"
    deployName="graphrag-deploy-$datetime"
    echo "Deployment name: $deployName"
    AZURE_DEPLOY_RESULTS=$(az deployment group create --name "$deployName" \
        --no-prompt \
        --resource-group $RESOURCE_GROUP \
        --template-file ./main.bicep \
        --parameters "resourceBaseName=$RESOURCE_BASE_NAME" \
        --parameters "apimName=$APIM_NAME" \
        --parameters "apimTier=$APIM_TIER" \
        --parameters "aiSearchTier=$AI_SEARCH_TIER" \
        --parameters "apiPublisherEmail=$PUBLISHER_EMAIL" \
        --parameters "apiPublisherName=$PUBLISHER_NAME" \
        --parameters "enablePrivateEndpoints=$ENABLE_PRIVATE_ENDPOINTS" \
        --parameters "deployAcr=$deployAcr" \
        --parameters "existingAcrLoginServer=$CONTAINER_REGISTRY_LOGIN_SERVER" \
        --parameters "graphragImageName=$graphragImageName" \
        --parameters "graphragImageVersion=$graphragImageVersion" \
        --parameters "deployAoai=$deployAoai" \
        --parameters "existingAoaiId=$existingAoaiId" \
        --parameters "llmModelName=$GRAPHRAG_LLM_MODEL" \
        --parameters "llmModelDeploymentName=$GRAPHRAG_LLM_DEPLOYMENT_NAME" \
        --parameters "llmModelVersion=$GRAPHRAG_LLM_MODEL_VERSION" \
        --parameters "llmModelQuota=$GRAPHRAG_LLM_MODEL_QUOTA" \
        --parameters "embeddingModelName=$GRAPHRAG_EMBEDDING_MODEL" \
        --parameters "embeddingModelDeploymentName=$GRAPHRAG_EMBEDDING_DEPLOYMENT_NAME" \
        --parameters "embeddingModelVersion=$GRAPHRAG_EMBEDDING_MODEL_VERSION" \
        --parameters "embeddingModelQuota=$GRAPHRAG_EMBEDDING_MODEL_QUOTA" \
        --output json)
    # errors in deployment may not be caught by exitIfCommandFailed function so we also check the output for errors
    exitIfCommandFailed $? "Error deploying Azure resources..."
    exitIfValueEmpty "$AZURE_DEPLOY_RESULTS" "Error deploying Azure resources..."
    AZURE_DEPLOY_OUTPUTS=$(jq -r .properties.outputs <<< $AZURE_DEPLOY_RESULTS)
    exitIfCommandFailed $? "Error parsing outputs from Azure deployment..."
    exitIfValueEmpty "$AZURE_DEPLOY_OUTPUTS" "Error parsing outputs from Azure deployment..."

    # Must assign ACRPull role to aks if ACR was not part of the deployment (i.e. user chose to utilize an ACR resource external to this deployment)
    if [ -n "$CONTAINER_REGISTRY_LOGIN_SERVER" ]; then
        assignACRPullRoleToAKS $RESOURCE_GROUP $CONTAINER_REGISTRY_LOGIN_SERVER
    fi
}

assignACRPullRoleToAKS() {
    local rg=$1
    local registry=$2
    local aks_name kubelet_id acr_id

    echo "Assigning 'ACRPull' role to AKS..."
    aks_name=$(jq -r .azure_aks_name.value <<< $AZURE_DEPLOY_OUTPUTS)
    exitIfValueEmpty "$aks_name" "Unable to parse aks name from azure outputs, exiting..."
    kubelet_id=$(az aks show --resource-group $rg --name $aks_name --query identityProfile.kubeletidentity.objectId --output tsv)
    exitIfValueEmpty "$kubelet_id" "Unable to retrieve AKS kubelet id, exiting..."
    acr_id=$(az acr show --name $registry --query id -o tsv)
    exitIfValueEmpty "$acr_id" "Unable to retrieve ACR id, exiting..."
    az role assignment create --role "AcrPull" --assignee $kubelet_id --scope $acr_id
    exitIfCommandFailed $? "Error assigning ACRPull role to AKS, exiting..."
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
    local location=$1
    local sku_checklist
    local sku_check_result
    local sku_validation_listing

    sku_checklist=("standard_d4s_v5" "standard_d8s_v5" "standard_e8s_v5")
    printf "Checking cloud region for VM sku availability... "
    for sku in ${sku_checklist[@]}; do
        sku_check_result=$(
            az vm list-skus --location $location --size $sku --output json
        )
        sku_validation_listing=$(jq -r .[0].name <<< $sku_check_result)
        exitIfValueEmpty $sku_validation_listing "SKU $sku is restricted for location $location under the current subscription."
    done
    printf "Done.\n"
}

checkSKUQuotas() {
    local location=$1
    local vm_usage_report

    # Function to validation that the SKU quotas would not be exceeded during deployment
    printf "Checking Location for SKU Quota Usage... "
    vm_usage_report=$(
        az vm list-usage --location $location -o json
    )

    # Check quota for Standard DSv5 Family vCPUs
    local dsv5_usage_report dsv5_limit dsv5_currVal dsv5_reqVal
    dsv5_usage_report=$(jq -c '.[] | select(.localName | contains("Standard DSv5 Family vCPUs"))' <<< $vm_usage_report)
    dsv5_limit=$(jq -r .limit <<< $dsv5_usage_report)
    dsv5_currVal=$(jq -r .currentValue <<< $dsv5_usage_report)
    dsv5_reqVal=$(expr $dsv5_currVal + 12)
    exitIfThresholdExceeded $dsv5_reqVal $dsv5_limit "Not enough Standard DSv5 Family vCPU quota for deployment. At least 12 vCPU is required."

    # Check quota for Standard ESv5 Family vCPUs
    local esv5_usage_report esv5_limit esv5_currVal esv5_reqVal
    esv5_usage_report=$(jq -c '.[] | select(.localName | contains("Standard ESv5 Family vCPUs"))' <<< $vm_usage_report)
    esv5_limit=$(jq -r .limit <<< $esv5_usage_report)
    esv5_currVal=$(jq -r .currentValue <<< $esv5_usage_report)
    esv5_reqVal=$(expr $esv5_currVal + 8)
    exitIfThresholdExceeded $esv5_reqVal $esv5_limit "Not enough Standard ESv5 Family vCPU quota for deployment. At least 8 vCPU is required."
    printf "Done.\n"
}

installGraphRAGHelmChart () {
    local containerRegistryServer=""
    local graphragImageName graphragImageVersion
    local workloadId serviceAccountName appInsightsConnectionString aiSearchName cosmosEndpoint appHostname storageAccountBlobUrl
    local graphragApiBase graphragApiVersion graphragLlmModel graphragLlmModelDeployment graphragEmbeddingModel graphragEmbeddingModelDeployment

    echo "Deploying graphrag helm chart... "
    workloadId=$(jq -r .azure_workload_identity_client_id.value <<< $AZURE_DEPLOY_OUTPUTS)
    exitIfValueEmpty "$workloadId" "Unable to parse workload id from Azure outputs, exiting..."

    serviceAccountName=$(jq -r .azure_aks_service_account_name.value <<< $AZURE_DEPLOY_OUTPUTS)
    exitIfValueEmpty "$serviceAccountName" "Unable to parse service account name from Azure outputs, exiting..."

    appInsightsConnectionString=$(jq -r .azure_app_insights_connection_string.value <<< $AZURE_DEPLOY_OUTPUTS)
    exitIfValueEmpty "$appInsightsConnectionString" "Unable to parse app insights connection string from Azure outputs, exiting..."

    aiSearchName=$(jq -r .azure_ai_search_name.value <<< $AZURE_DEPLOY_OUTPUTS)
    exitIfValueEmpty "$aiSearchName" "Unable to parse AI search name from Azure outputs, exiting..."

    cosmosEndpoint=$(jq -r .azure_cosmosdb_endpoint.value <<< $AZURE_DEPLOY_OUTPUTS)
    exitIfValueEmpty "$cosmosEndpoint" "Unable to parse CosmosDB endpoint from Azure outputs, exiting..."

    appHostname=$(jq -r .azure_app_hostname.value <<< $AZURE_DEPLOY_OUTPUTS)
    exitIfValueEmpty "$appHostname" "Unable to parse graphrag hostname from deployment outputs, exiting..."

    storageAccountBlobUrl=$(jq -r .azure_storage_account_blob_url.value <<< $AZURE_DEPLOY_OUTPUTS)
    exitIfValueEmpty "$storageAccountBlobUrl" "Unable to parse storage account blob url from deployment outputs, exiting..."

    # retrieve container registry info either from the deployment or from user provided input
    if [ -n "$CONTAINER_REGISTRY_LOGIN_SERVER" ]; then
        containerRegistryServer="$CONTAINER_REGISTRY_LOGIN_SERVER"
    else
        containerRegistryServer=$(jq -r .azure_acr_login_server.value <<< $AZURE_DEPLOY_OUTPUTS)
    fi
    exitIfValueEmpty "$containerRegistryServer" "Unable to parse container registry url from deployment outputs, exiting..."
    graphragImageName=$(sed -rn "s/([^:]+).*/\1/p" <<< "$GRAPHRAG_IMAGE")
    graphragImageVersion=$(sed -rn "s/[^:]+:(.*)/\1/p" <<< "$GRAPHRAG_IMAGE")
    exitIfValueEmpty "$graphragImageName" "Unable to parse graphrag docker image name, exiting..."
    exitIfValueEmpty "$graphragImageVersion" "Unable to parse graphrag docker image version, exiting..."

    # retrieve AOAOI values either from the deployment or from user provided input
    if [ -n "$GRAPHRAG_API_BASE" ]; then
        graphragApiBase="$GRAPHRAG_API_BASE"
        graphragApiVersion="$GRAPHRAG_API_VERSION"
        graphragLlmModel="$GRAPHRAG_LLM_MODEL"
        graphragLlmModelDeployment="$GRAPHRAG_LLM_DEPLOYMENT_NAME"
        graphragEmbeddingModel="$GRAPHRAG_EMBEDDING_MODEL"
        graphragEmbeddingModelDeployment="$GRAPHRAG_EMBEDDING_DEPLOYMENT_NAME"
    else
        graphragApiBase=$(jq -r .azure_aoai_endpoint.value <<< $AZURE_DEPLOY_OUTPUTS)
        exitIfValueEmpty "$graphragApiBase" "Unable to parse AOAI endpoint from deployment outputs, exiting..."
        graphragApiVersion=$(jq -r .azure_aoai_llm_model_api_version.value <<< $AZURE_DEPLOY_OUTPUTS)
        exitIfValueEmpty "$graphragApiVersion" "Unable to parse AOAI model api version from deployment outputs, exiting..."
        graphragLlmModel=$(jq -r .azure_aoai_llm_model.value <<< $AZURE_DEPLOY_OUTPUTS)
        exitIfValueEmpty "$graphragLlmModel" "Unable to parse LLM model name from deployment outputs, exiting..."
        graphragLlmModelDeployment=$(jq -r .azure_aoai_llm_model_deployment_name.value <<< $AZURE_DEPLOY_OUTPUTS)
        exitIfValueEmpty "$graphragLlmModelDeployment" "Unable to parse LLM model deployment name from deployment outputs, exiting..."
        graphragEmbeddingModel=$(jq -r .azure_aoai_embedding_model.value <<< $AZURE_DEPLOY_OUTPUTS)
        exitIfValueEmpty "$graphragEmbeddingModel" "Unable to parse embedding model name from deployment outputs, exiting..."
        graphragEmbeddingModelDeployment=$(jq -r .azure_aoai_embedding_model_deployment_name.value <<< $AZURE_DEPLOY_OUTPUTS)
        exitIfValueEmpty "$graphragEmbeddingModelDeployment" "Unable to parse embedding model deployment name from deployment outputs, exiting..."
    fi

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
        --set "master.image.repository=$containerRegistryServer/$graphragImageName" \
        --set "master.image.tag=$graphragImageVersion" \
        --set "ingress.host=$appHostname" \
        --set "graphragConfig.AI_SEARCH_URL=https://$aiSearchName.$AISEARCH_ENDPOINT_SUFFIX" \
        --set "graphragConfig.AI_SEARCH_AUDIENCE=$AI_SEARCH_AUDIENCE" \
        --set "graphragConfig.APPLICATIONINSIGHTS_CONNECTION_STRING=$appInsightsConnectionString" \
        --set "graphragConfig.COGNITIVE_SERVICES_AUDIENCE=$COGNITIVE_SERVICES_AUDIENCE" \
        --set "graphragConfig.COSMOS_URI_ENDPOINT=$cosmosEndpoint" \
        --set "graphragConfig.GRAPHRAG_API_BASE=$graphragApiBase" \
        --set "graphragConfig.GRAPHRAG_API_VERSION=$graphragApiVersion" \
        --set "graphragConfig.GRAPHRAG_LLM_MODEL=$graphragLlmModel" \
        --set "graphragConfig.GRAPHRAG_LLM_DEPLOYMENT_NAME=$graphragLlmModelDeployment" \
        --set "graphragConfig.GRAPHRAG_EMBEDDING_MODEL=$graphragEmbeddingModel" \
        --set "graphragConfig.GRAPHRAG_EMBEDDING_DEPLOYMENT_NAME=$graphragEmbeddingModelDeployment" \
        --set "graphragConfig.STORAGE_ACCOUNT_BLOB_URL=$storageAccountBlobUrl" \
        --set "graphragConfig.GRAPHRAG_LLM_MODEL_CONCURRENT_REQUEST=\"$GRAPHRAG_LLM_MODEL_CONCURRENT_REQUEST\"" \
        --set "graphragConfig.GRAPHRAG_EMBEDDING_MODEL_CONCURRENT_REQUEST=\"$GRAPHRAG_EMBEDDING_MODEL_CONCURRENT_REQUEST\""
      

    local helmResult
    helmResult=$?
    "$reset_x" && set +x
    exitIfCommandFailed $helmResult "Error deploying helm chart, exiting..."
}

waitForExternalIp () {
    local -i maxTries=14
    local available="false"
    local TMP_GRAPHRAG_SERVICE_IP

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

    local dnsZoneName
    dnsZoneName=$(jq -r .azure_dns_zone_name.value <<< $AZURE_DEPLOY_OUTPUTS)
    exitIfValueEmpty "$dnsZoneName" "Error parsing DNS zone name from azure outputs, exiting..."
    az deployment group create --only-show-errors --no-prompt \
        --name graphrag-dns-deployment \
        --resource-group $RESOURCE_GROUP \
        --template-file core/vnet/private-dns-zone-a-record.bicep \
        --parameters "name=graphrag" \
        --parameters "dnsZoneName=$dnsZoneName" \
        --parameters "ipv4Address=$GRAPHRAG_SERVICE_IP" > /dev/null
    exitIfCommandFailed $? "Error creating GraphRAG DNS record, exiting..."
}

deployGraphragAPI () {
    local apimGatewayUrl apimName backendSwaggerUrl graphragUrl

    echo "Registering GraphRAG API with APIM..."
    apimGatewayUrl=$(jq -r .azure_apim_gateway_url.value <<< $AZURE_DEPLOY_OUTPUTS)
    exitIfValueEmpty "$apimGatewayUrl" "Unable to parse APIM gateway url from Azure outputs, exiting..."
    apimName=$(jq -r .azure_apim_name.value <<< $AZURE_DEPLOY_OUTPUTS)
    exitIfValueEmpty "$apimName" "Error parsing apim name from azure outputs, exiting..."
    backendSwaggerUrl="$apimGatewayUrl/manpage/openapi.json"
    graphragUrl=$(jq -r .azure_app_url.value <<< $AZURE_DEPLOY_OUTPUTS)
    exitIfValueEmpty "$graphragUrl" "Error parsing GraphRAG URL from azure outputs, exiting..."

    waitForGraphragBackend $backendSwaggerUrl

    # download the openapi spec from the backend and load it into APIM
    az rest --only-show-errors --method get --url $backendSwaggerUrl -o json > core/apim/openapi.json
    exitIfCommandFailed $? "Error downloading graphrag openapi spec, exiting..."
    az deployment group create --only-show-errors --no-prompt \
        --name upload-graphrag-api-to-apim \
        --resource-group $RESOURCE_GROUP \
        --template-file core/apim/apim.graphrag-api.bicep \
        --parameters "backendUrl=$graphragUrl" \
        --parameters "name=GraphRAG" \
        --parameters "apiManagementName=$apimName" > /dev/null
    exitIfCommandFailed $? "Error registering graphrag API, exiting..."
    # cleanup
    #rm core/apim/openapi.json
}

grantDevAccessToAzureResources() {
    # This function is used to grant the deployer of this script "developer" access
    # to GraphRAG Azure resources by assigning the necessary RBAC roles for
    # Azure Storage, AI Search, and CosmosDB to the signed-in user. This grants
    # the deployer access to data in the storage account, cosmos db, and AI search services
    # from the Azure portal.
    echo "Granting deployer developer access to Azure resources..."

    # get subscription id of the active subscription
    local subscriptionId
    subscriptionId=$(az account show --output json | jq -r .id)
    exitIfValueEmpty $subscriptionId "Subscription ID not found"

    # get principal/object id of the signed in user
    local principalId
    principalId=$(az ad signed-in-user show --output json | jq -r .id)
    exitIfValueEmpty $principalId "Principal ID of deployer not found"

    # assign storage account roles
    local storageAccountName
    storageAccountName=$(az storage account list --resource-group $RESOURCE_GROUP --output json | jq -r .[0].name)
    exitIfValueEmpty $storageAccountName "Storage account not found"
    az role assignment create \
        --role "Storage Blob Data Contributor" \
        --assignee $principalId \
        --scope "/subscriptions/$subscriptionId/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.Storage/storageAccounts/$storageAccountName" > /dev/null

    # assign cosmos db role
    local cosmosDbName
    cosmosDbName=$(az cosmosdb list --resource-group $RESOURCE_GROUP -o json | jq -r .[0].name)
    exitIfValueEmpty $cosmosDbName "CosmosDB account not found"
    az cosmosdb sql role assignment create \
        --account-name $cosmosDbName \
        --resource-group $RESOURCE_GROUP \
        --scope "/" \
        --principal-id $principalId \
        --role-definition-id /subscriptions/$subscriptionId/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.DocumentDB/databaseAccounts/graphrag/sqlRoleDefinitions/00000000-0000-0000-0000-000000000002 > /dev/null

    # assign AI search roles
    local searchServiceName
    searchServiceName=$(az search service list --resource-group $RESOURCE_GROUP -o json | jq -r .[0].name)
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

deployDockerImageToInternalACR() {
    local containerRegistry
    containerRegistry=$(jq -r .azure_acr_login_server.value <<< $AZURE_DEPLOY_OUTPUTS)
    exitIfValueEmpty "$containerRegistry" "Unable to parse container registry from azure deployment outputs, exiting..."
    echo "Deploying docker image '${GRAPHRAG_IMAGE}' to container registry '${containerRegistry}'..."

    local scriptDir
    scriptDir="$( cd -- "$( dirname -- "${BASH_SOURCE[0]:-$0}"; )" &> /dev/null && pwd 2> /dev/null; )";
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

# Deploy graphrag docker image to internal ACR if an external ACR was not provided
if [ -z "$CONTAINER_REGISTRY_LOGIN_SERVER" ]; then
    deployDockerImageToInternalACR
fi

# Retrieve AKS credentials and install GraphRAG helm chart
getAksCredentials $RESOURCE_GROUP
installGraphRAGHelmChart

# Import and setup GraphRAG API in APIM
deployDnsRecord
deployGraphragAPI

if [ $GRANT_DEV_ACCESS -eq 1 ]; then
    grantDevAccessToAzureResources
fi

successBanner
