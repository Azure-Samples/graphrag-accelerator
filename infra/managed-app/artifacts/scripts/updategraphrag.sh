#!/bin/bash

# Install kubectl
set -e
az aks install-cli --only-show-errors
az login --identity

# Get AKS credentials
az aks get-credentials \
  --admin \
  --name $AKS_NAME  \
  --resource-group $RESOURCE_GROUP --only-show-errors

# Assign a value to aksNamespace
aksNamespace="graphrag"

# Install helm
curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 -o get_helm.sh -s
chmod 700 get_helm.sh
./get_helm.sh &>/dev/null

# Install graphrag helm chart
# helm repo update
# helm pull "oci://$ACR_SERVER/graphrag" --untar

helm upgrade -i graphrag ./graphrag -f ./graphrag/values.yaml \
    --namespace $aksNamespace --create-namespace \
    --set "serviceAccount.name=$AKS_SERVICE_ACCOUNT_NAME" \
    --set "serviceAccount.annotations.azure\.workload\.identity/client-id=$WORKLOAD_IDENTITY_CLIENT_ID" \
    --set "master.image.repository=$ACR_SERVER/$IMAGE_NAME" \
    --set "master.image.tag=$IMAGE_VERSION" \
    --set "ingress.host=$APP_HOSTNAME" \
    --set "graphragConfig.AI_SEARCH_URL=https://$AI_SEARCH_NAME.$AI_SEARCH_ENDPOINT_SUFFIX" \
    --set "graphragConfig.AI_SEARCH_AUDIENCE=$AI_SEARCH_AUDIENCE" \
    --set "graphragConfig.APPLICATIONINSIGHTS_CONNECTION_STRING=$APP_INSIGHTS_CONNECTION_STRING" \
    --set "graphragConfig.COGNITIVE_SERVICES_AUDIENCE=$COGNITIVE_SERVICES_AUDIENCE" \
    --set "graphragConfig.COSMOS_URI_ENDPOINT=$COSMOSDB_ENDPOINT" \
    --set "graphragConfig.GRAPHRAG_API_BASE=$OPENAI_ENDPOINT" \
    --set "graphragConfig.GRAPHRAG_API_VERSION=$AOAI_LLM_MODEL_API_VERSION" \
    --set "graphragConfig.GRAPHRAG_LLM_MODEL=$AOAI_LLM_MODEL"\
    --set "graphragConfig.GRAPHRAG_LLM_DEPLOYMENT_NAME=$AOAI_LLM_MODEL_DEPLOYMENT_NAME" \
    --set "graphragConfig.GRAPHRAG_EMBEDDING_MODEL=$AOAI_EMBEDDING_MODEL" \
    --set "graphragConfig.GRAPHRAG_EMBEDDING_DEPLOYMENT_NAME=$AOAI_EMBEDDING_MODEL_DEPLOYMENT_NAME" \
    --set "graphragConfig.STORAGE_ACCOUNT_BLOB_URL=$STORAGE_ACCOUNT_BLOB_URL"
