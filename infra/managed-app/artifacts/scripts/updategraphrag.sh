#!/bin/bash
# Install kubectl
set -e
az aks install-cli --only-show-errors

az login --identity

# Get AKS credentials
az aks get-credentials \
  --admin \
  --name $AZURE_AKS_NAME  \
  --resource-group $AZURE_RESOURCE_GROUP --only-show-errors

# Check if the cluster is private or not

# Assign a value to aksNamespace
aksNamespace="graphrag"

# Install Helm
curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 -o get_helm.sh -s
chmod 700 get_helm.sh
./get_helm.sh &>/dev/null

# Add Helm repos
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx

# Update Helm repos
helm repo update

helm pull  oci://graphrag.azurecr.io/graphrag --untar

  
helm upgrade -i graphrag ./graphrag -f ./graphrag/values.yaml \
    --namespace $aksNamespace --create-namespace \
    --set "serviceAccount.name=$AZURE_AKS_SERVICE_ACCOUNT_NAME" \
    --set "serviceAccount.annotations.azure\.workload\.identity/client-id=$AZURE_WORKLOAD_IDENTITY_CLIENT_ID" \
    --set "master.image.repository=graphrag.azurecr.io/$IMAGE_NAME" \
    --set "master.image.tag=$IMAGE_VERSION" \
    --set "ingress.host=$AZURE_APP_HOSTNAME" \
    --set "graphragConfig.APPLICATIONINSIGHTS_CONNECTION_STRING=$APP_INSIGHTS_CONNECTION_STRING" \
    --set "graphragConfig.AI_SEARCH_URL=https://$AI_SEARCH_NAME.search.windows.net" \
    --set "graphragConfig.COSMOS_URI_ENDPOINT=$AZURE_COSMOSDB_ENDPOINT" \
    --set "graphragConfig.GRAPHRAG_API_BASE=$AZURE_OPENAI_ENDPOINT" \
    --set "graphragConfig.GRAPHRAG_API_VERSION=$AZURE_AOAI_LLM_MODEL_API_VERSION" \
    --set "graphragConfig.GRAPHRAG_LLM_MODEL=$AZURE_AOAI_LLM_MODEL"\
    --set "graphragConfig.GRAPHRAG_LLM_DEPLOYMENT_NAME=$AZURE_AOAI_LLM_MODEL_DEPLOYMENT_NAME" \
    --set "graphragConfig.GRAPHRAG_EMBEDDING_MODEL=$AZURE_AOAI_EMBEDDING_MODEL" \
    --set "graphragConfig.GRAPHRAG_EMBEDDING_DEPLOYMENT_NAME=$AZURE_AOAI_EMBEDDING_MODEL_DEPLOYMENT_NAME" \
    --set "graphragConfig.COGNITIVE_SERVICES_AUDIENCE=$COGNITIVE_SERVICES_AUDIENCE" \
    --set "graphragConfig.STORAGE_ACCOUNT_BLOB_URL=$AZURE_STORAGE_ACCOUNT_BLOB_URL"

  



