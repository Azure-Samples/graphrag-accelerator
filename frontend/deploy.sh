#!/bin/bash

set -eux

function load_env_variables() {
    set -a
    source .env
    set +a
}

function checkRequiredParams () {
    requiredParams=(
    LOCATION
    RESOURCE_GROUP
    SUBSCRIPTION_ID
    AAD_CLIENT_ID
    AAD_OBJECT_ID
    AAD_TENANT_ID
    )
    local paramsFile=$1
    for param in "${requiredParams[@]}"; do
        local paramValue=$(jq -r .$param < $paramsFile)
        if [ "null" == "$paramValue" ] || [ -z "$paramValue" ]; then
            echo "Parameter $param is required, exiting..."
            exit 1
        fi
    done
}

function populateRequiredParams () {
    local paramsFile=$1
    printf "Checking required parameters... "
    checkRequiredParams $paramsFile
    # The jq command below sets environment variables based on the key-value pairs in a JSON-formatted file
    eval $(jq -r 'to_entries | .[] | "export \(.key)=\(.value)"' $paramsFile)
    printf "Done.\n"
}

function set_variables() {
    SUBSCRIPTION_ID=${SUBSCRIPTION_ID:-""}
    RESOURCE_GROUP=${RESOURCE_GROUP:-""}
    LOCATION=${LOCATION:-""}
    AAD_CLIENT_ID=${AAD_CLIENT_ID:-""}
    AAD_OBJECT_ID=${AAD_OBJECT_ID:-""}
    AAD_TENANT_ID=${AAD_TENANT_ID:-""}
    AAD_TOKEN_ISSUER_URL=${AAD_TOKEN_ISSUER_URL:-"https://login.microsoftonline.com/$AAD_TENANT_ID/v2.0"}
    IMAGE_NAME=${IMAGE_NAME:-"graphrag:frontend"}
    REGISTRY_NAME=${REGISTRY_NAME:-"${RESOURCE_GROUP}reg"}
    APP_SERVICE_PLAN=${APP_SERVICE_PLAN:-"${RESOURCE_GROUP}-asp"}
    WEB_APP=${WEB_APP:-"${RESOURCE_GROUP}-playground"}
    WEB_APP_IDENTITY=${WEB_APP_IDENTITY:-"${WEB_APP}-identity"}
    #BACKEND_RESOURCE_GROUP=${BACKEND_RESOURCE_GROUP:-""} # needed for backend outbound vnet integration
}
function create_resource_group {
    az account set --subscription $SUBSCRIPTION_ID
    az group create --name $RESOURCE_GROUP --location $LOCATION
}

function create_acr() {
    az acr create --resource-group $RESOURCE_GROUP \
    --name $REGISTRY_NAME \
    --sku Basic \
    --admin-enabled true
}


function build_and_push_image() {
    local SCRIPT_DIR="$( cd -- "$( dirname -- "${BASH_SOURCE[0]:-$0}"; )" &> /dev/null && pwd 2> /dev/null; )";
    az acr build --registry $REGISTRY_NAME -f $SCRIPT_DIR/../docker/Dockerfile-frontend --image $IMAGE_NAME $SCRIPT_DIR/../
}

function create_app_service_plan() {
    az appservice plan create --name $APP_SERVICE_PLAN \
        --resource-group $RESOURCE_GROUP \
        --sku B3 \
        --is-linux
}

function create_web_app() {
    az webapp create --resource-group $RESOURCE_GROUP \
        --plan $APP_SERVICE_PLAN \
        --name $WEB_APP \
        --deployment-container-image-name $REGISTRY_NAME.azurecr.io/$IMAGE_NAME
}

function create_web_app_identity() {
    IDENTITY_RESULT=$(az identity create --resource-group $RESOURCE_GROUP --name $WEB_APP_IDENTITY --output json)
    WEBAPP_IDENTITY_ID=$(jq -r .id <<< $IDENTITY_RESULT)
    WEBAPP_IDENTITY_OBJECT_ID=$(jq -r .principalId <<< $IDENTITY_RESULT)
    WEBAPP_IDENTITY_CLIENT_ID=$(jq -r .clientId <<< $IDENTITY_RESULT)
    az webapp identity assign --name $WEB_APP \
        --resource-group $RESOURCE_GROUP \
        --identities $WEBAPP_IDENTITY_ID
}

function configure_registry_credentials() {
    ACR_ID=$(az acr show --name $REGISTRY_NAME --resource-group $RESOURCE_GROUP --query id --output tsv)
    az role assignment create --assignee $WEBAPP_IDENTITY_CLIENT_ID \
        --role AcrPull \
        --scope $ACR_ID
    az webapp config container set --name $WEB_APP \
        --resource-group $RESOURCE_GROUP \
        --container-image-name $REGISTRY_NAME.azurecr.io/$IMAGE_NAME
}

function configure_app_settings() {
    APP_SETTINGS=""
    while IFS='=' read -r name value
    do
        value="${value%\"}"   # Remove opening quote
        value="${value#\"}"   # Remove closing quote
        APP_SETTINGS="$APP_SETTINGS $name=$value"
    done < .env
    echo $APP_SETTINGS
    az webapp config appsettings set --name $WEB_APP \
        --resource-group $RESOURCE_GROUP \
        --settings $APP_SETTINGS
}

function create_federated_identity_credentials() {
    EXISTING_CREDENTIAL_SUBJECTS=$(az rest --method GET --uri "https://graph.microsoft.com/beta/applications/$AAD_OBJECT_ID/federatedIdentityCredentials" -o json | jq -r '.value[].subject')
    if [[ "$EXISTING_CREDENTIAL_SUBJECTS" == *"$WEBAPP_IDENTITY_OBJECT_ID"* ]]; then
        echo "Federated identity credential already exists for the subject: $WEBAPP_IDENTITY_OBJECT_ID"
    else
        az webapp auth update \
            --name $WEB_APP \
            --resource-group $RESOURCE_GROUP \
            --enabled true \
            --action LoginWithAzureActiveDirectory \
            --aad-client-id $AAD_CLIENT_ID \
            --aad-token-issuer-url $AAD_TOKEN_ISSUER_URL
        az rest --method POST \
            --uri "https://graph.microsoft.com/beta/applications/$AAD_OBJECT_ID/federatedIdentityCredentials" \
            --body "{'name': '$WEB_APP', 'issuer': '$AAD_TOKEN_ISSUER_URL', 'subject': '$WEBAPP_IDENTITY_OBJECT_ID', 'audiences': [ 'api://AzureADTokenExchange' ]}"
    fi
}

function configure_auth_settings() {
    az webapp config appsettings set --resource-group $RESOURCE_GROUP \
        --name $WEB_APP \
        --slot-settings OVERRIDE_USE_MI_FIC_ASSERTION_CLIENTID=$WEBAPP_IDENTITY_CLIENT_ID \
        --verbose
    az webapp config appsettings list --resource-group $RESOURCE_GROUP \
        --name $WEB_APP

    authSettings=$(az rest --method GET --url "/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.Web/sites/$WEB_APP/config/authsettingsV2/list?api-version=2020-12-01")
    echo $authSettings > auth.json
    jq '.properties.identityProviders.azureActiveDirectory.registration.clientSecretSettingName = "OVERRIDE_USE_MI_FIC_ASSERTION_CLIENTID"' auth.json > tmp.json && mv tmp.json auth.json
    az rest --method PUT \
        --url "/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.Web/sites/$WEB_APP/config/authsettingsV2?api-version=2020-12-01" \
        --body @auth.json \
        --headers "Content-Type=application/json"
    rm auth.json
}

function enable_https() {
    az webapp update --name $WEB_APP \
        --resource-group $RESOURCE_GROUP \
        --set httpsOnly=true
}

function update_appreg_redirect_uris() {
    WEB_APP_URL=$(az webapp show --name $WEB_APP --resource-group $RESOURCE_GROUP --query defaultHostName --output tsv)
    NEW_REDIRECT_URI=https://$WEB_APP_URL/.auth/login/aad/callback
    # Fetch the current list of web redirect URIs
    CURRENT_URIS=$(az ad app show --id $AAD_CLIENT_ID --query "web.redirectUris" --output tsv)
    if ! echo "${CURRENT_URIS}" | grep -q "${NEW_REDIRECT_URI}"; then
        az ad app update --id $AAD_CLIENT_ID --web-redirect-uris ${CURRENT_URIS[@]} "$NEW_REDIRECT_URI"
    fi
}

function restart_web_app() {
    az webapp restart --name $WEB_APP --resource-group $RESOURCE_GROUP
}

## The following function adds outbound vnet integration on the webapp so that the frontend container can access resources in the AKS cluster directly.
## This will create a new subnet named "frontend" in the backend resource group's vnet if it does not exist.
## This may not be needed in simplified backend architecture but useful for folks using a prior version of the accelerator that had a different network architecture.
# function add_vnet_integration() {
#     VNET_NAME=$(az network vnet list --resource-group $BACKEND_RESOURCE_GROUP --query "[0].name" --output tsv)
#     VNET_ID=$(az network vnet list --resource-group $BACKEND_RESOURCE_GROUP --query "[0].id" --output tsv)
#     SUBNET_NAMES=$(az network vnet subnet list --resource-group $BACKEND_RESOURCE_GROUP --vnet-name $VNET_NAME --query "[].name" --output tsv)
#     SUBNET_NAME="frontend"
#     if [[ $SUBNET_NAMES == *$SUBNET_NAME* ]]; then
#         echo "Subnet with name $SUBNET_NAME already exists"
#     else
#         echo "Subnet with name $SUBNET_NAME does not exist, creating one now."
#         az network vnet subnet create --resource-group $BACKEND_RESOURCE_GROUP --vnet-name $VNET_NAME --name $SUBNET_NAME --address-prefixes 10.0.10.0/24
#     fi
#     az webapp vnet-integration add --name $WEB_APP --resource-group $RESOURCE_GROUP --vnet $VNET_ID --subnet $SUBNET_NAME
# }

function usage() {
   echo
   echo "Usage: bash $0 [-h] -p <frontend_deploy.parameters.json>"
   echo "Description: Deployment script for the Frontend App for GraphRAG Solution Accelerator."
   echo "options:"
   echo "  -h     Print this help menu."
   echo "  -p     A JSON file containing the deployment parameters (frontend_deploy.parameters.json)."
   echo
}

function main() {
    load_env_variables
    populateRequiredParams $PARAMS_FILE
    set_variables
    create_resource_group
    create_acr
    build_and_push_image
    create_app_service_plan
    create_web_app
    create_web_app_identity
    configure_registry_credentials
    configure_app_settings
    create_federated_identity_credentials
    configure_auth_settings
    enable_https
    # add_vnet_integration
    update_appreg_redirect_uris
    restart_web_app
    echo "Graphrag Frontend Web app deployed at https://$WEB_APP_URL"
}

# print usage if no arguments are supplied
[ $# -eq 0 ] && usage && exit 0
PARAMS_FILE=""
while getopts ":p:h" option; do
    case "${option}" in
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

main
