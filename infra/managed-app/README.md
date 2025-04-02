# Managed App Instructions

This guide walks through the process to convert the graphrag solution accelerator into a managed app.

### Prerequisites
1. Create an ACR
1. Push both the graphrag backend docker image and the graphrag helm chart to the registry.
    ```shell
    # push docker image
    az acr login --name <registry>.azurecr.io
    cd <repo_root>
    az acr build --registry <registry>acurecr.io -f docker/Dockerfile-backend --image graphrag:latest .
    # push helm chart
    cd <repo_root>/infra/helm
    helm package graphrag
    helm push graphrag-<version>.tgz oci://<registry>.azurecr.io/helm
    ```
1. A managed app [requires a storage account to deploy](https://learn.microsoft.com/en-us/azure/azure-resource-manager/managed-applications/publish-service-catalog-bring-your-own-storage?tabs=azure-powershell) an Azure Managed App Definition. Create a storage account and take note of the name and SAS key for later.
1. Enable anonymous access on the blob container that will host the managed app deployment package (a zip file).
1. The Azure built-in service principle `Managed Applications on Behalf Application` **MUST** be granted the role of `Contributor` and `Role Based Access Control Administrator` on any Azure subscription where the app will be deployed.

### Steps to build a Managed App

### 1. Auto format the bicep code (optional)

As a precaution, auto-format and lint the bicep code to detect any mistakes early-on.

```bash
cd <repo_root_directory>/infra
find . -type f -name "*.bicep" -exec az bicep format --file {} \;
find . -type f -name "*.bicep" -exec az bicep lint --file {} \;
```

### 2. Create & test the Azure portal interface

Use the [Azure Portal Sandbox](https://portal.azure.com/#blade/Microsoft_Azure_CreateUIDef/SandboxBlade) to test and make UI changes defined in [createUiDefinition.json](createUiDefinition.json). To make additional changes to the Azure portal experience, check out the [documentation](https://learn.microsoft.com/en-us/azure/azure-resource-manager/managed-applications/create-uidefinition-overview) and copy the contents of `createUiDefinition.json` into the sandbox environment.

### 3. Prepare the deployment package

A *deployment package* is a zip file comprised of several files. This will include an ARM template and other files from the previous steps, along with additional code relevant to the deployment (i.e. artifacts)

The names of certain files (`mainTemplate.json` and `createUiDefinition.json`) should not be modified and are case-sensitive. Azure expects these files to be included in the final managed app deployment package.

A local copy of the backend docker image needs to be built in order to retrieve a copy of the openapi json spec associated with GraphRAG's REST API. This api spec file will become part of the final deployment package.
```shell
cd <repo_root_directory>
docker build -t graphrag:latest -f docker/Dockerfile-backend .
docker run -d -p 8080:80 graphrag:latest
```

Now create the deployment package:
```bash
cd <repo_root_directory>/infra

# get the openapi specification file
curl --fail-with-body -o core/apim/openapi.json http://localhost:8080/manpage/openapi.json

# compile bicep -> ARM
az bicep build --file main.bicep --outfile managed-app/mainTemplate.json

# zip up all files
cd managed-app
tar -a -cf managed-app-deployment-pkg.zip scripts createUiDefinition.json mainTemplate.json viewDefinition.json
```

The final deployment package should have the following file structure:
```bash
managed-app-deployment-pkg.zip
├── scripts
│   └── install-graphrag.sh
├── createUiDefinition.json
├── mainTemplate.json
└── viewDefinition.json
```

Upload the zip file to an Azure Storage location in preparation for the next step.

### 4. Create a Service Catalog Managed App Definition

Click [here](https://ms.portal.azure.com/#view/Microsoft_Azure_Marketplace/GalleryItemDetailsBladeNopdl/id/Microsoft.ApplianceDefinition/selectionMode~/false/resourceGroupId//resourceGroupLocation//dontDiscardJourney~/false/selectedMenuId/home/launchingContext~/%7B%22galleryItemId%22%3A%22Microsoft.ApplianceDefinition%22%2C%22source%22%3A%5B%22GalleryFeaturedMenuItemPart%22%2C%22VirtualizedTileDetails%22%5D%2C%22menuItemId%22%3A%22home%22%2C%22subMenuItemId%22%3A%22Search%20results%22%2C%22telemetryId%22%3A%2220409084-39a1-4800-bbce-d0b26a6f46a4%22%7D/searchTelemetryId/d7d20e05-ca16-47f7-bed5-9c7b8d2fa641) or from within the Azure Portal, go to Marketplace and create a `Service Catalog Managed App Definition`. You will be asked to provide a uri link to the uploaded `managed-app-deployment-pkg.zip` file during the creation process.

### 5. Deploy the managed app

There are two deployment options to consider when deploying a managed app. As an app in the Marketplace or as a one-click button:

* Marketplace App

    1. In the Azure Portal, find and click on the managed app definition resource created in the previous step.
    2. A button option `Deploy from definition` will be available.
    3. Click on it and proceed through the same setup experience (defined by the `createUiDefinitions.json` file) that a consumer would experience when installing the managed app.
    4. Additional work is needed to [publish the app](https://learn.microsoft.com/en-us/partner-center/marketplace-offers/plan-azure-application-offer) as an official app in the Azure Marketplace

* 1-click Deployment Button
If `mainTemplate.json` is hosted somewhere publicly (i.e. on Github), a deployment button can be created that deploys the app when clicked, like the the example below.

    [![Deploy to Azure](https://aka.ms/deploytoazurebutton)](https://portal.azure.com/#create/Microsoft.Template/uri/https%3A%2F%2Fraw.githubusercontent.com%2FAzure-Samples%2Fgraphrag-accelerator%2Frefs%2Fheads%2Fmain%2Finfra%2Fmanaged-app%2FmainTemplate.json)
