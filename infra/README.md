# Managed App Instructions

This guide walks through the process to convert the graphrag solution accelerator into a managed app.

### Prerequisites
1. Create an ACR and push the relevant docker image to the registry.
1. This managed app uses a storage account to deploy. Please take note of the storage account name and SAS key for later.
1. When publishing the managed app , enable anonymous access on the blob storage container where the app code will be accessed.

### Steps to build Managed App

### 1. Auto format the bicep code

As a precaution, start by auto-formating and linting the bicep code to detect any mistakes early-on.

```bash
cd <repo_root_directory>/infra
find . -type f -name "*.bicep" -exec az bicep format --file {} \;
find . -type f -name "*.bicep" -exec az bicep lint --file {} \;
```

### 2. Convert bicep -> ARM
```bash
az bicep build --file main.bicep --outfile managed-app/mainTemplate.json
```

### 3. Create & test the Azure portal interface

Use the [Azure Portal Sandbox](https://portal.azure.com/#blade/Microsoft_Azure_CreateUIDef/SandboxBlade) to test and make any UI changes that are defined in [createUiDefinition.json](createUiDefinition.json). To make additional changes to the Azure portal experience, start by reading some [documentation](https://learn.microsoft.com/en-us/azure/azure-resource-manager/managed-applications/create-uidefinition-overview) and copying the contents of `createUiDefinition.json` into the sandbox environment.

### 4. Create the deployment package

The name of the final two files (`mainTemplate.json` and `createUiDefinition.json`) should not be modified. The file names are case-sensitive and Azure expects these files as part of a managed app. The files must be packaged up as a zip file (where the json files are located at the root directory).

```bash
cd <repo_root_directory>/infra/managed-app
 tar -a -c -f managed-app.zip createUiDefinition.json mainTemplate.json openapi.json artifacts 
 ```

This zip file can then be uploaded to an Azure Storage location when setting up a [Service Catalog Managed Application Definition](https://ms.portal.azure.com/#view/Microsoft_Azure_Marketplace/GalleryItemDetailsBladeNopdl/id/Microsoft.ApplianceDefinition/selectionMode~/false/resourceGroupId//resourceGroupLocation//dontDiscardJourney~/false/selectedMenuId/home/launchingContext~/%7B%22galleryItemId%22%3A%22Microsoft.ApplianceDefinition%22%2C%22source%22%3A%5B%22GalleryFeaturedMenuItemPart%22%2C%22VirtualizedTileDetails%22%5D%2C%22menuItemId%22%3A%22home%22%2C%22subMenuItemId%22%3A%22Search%20results%22%2C%22telemetryId%22%3A%2220409084-39a1-4800-bbce-d0b26a6f46a4%22%7D/searchTelemetryId/d7d20e05-ca16-47f7-bed5-9c7b8d2fa641).

### 5. Create the Service Catalog Managed App Definition

In the Azure Portal, go to Marketplace and create a `Service Catalog Managed App Definition`. You will be asked to provide a uri link to the uploaded `managed-app.zip` file as part of the creation process.

### 6. Deploy the managed app

There are two deployment options to consider when deploying a managed app. As a Marketplace App or as a one-click button:

* Marketplace App

    1. In the Azure Portal, find and click on the managed app definition resource that was created in the previous step.
    2. A button option `Deploy from definition` will be available.
    3. Click on it and proceed through the same setup experience (defined by the `createUiDefinitions.json` file) that a consumer would experience when installing the managed app.
    4. Follow-on work is needed to [publish the app](https://learn.microsoft.com/en-us/partner-center/marketplace-offers/plan-azure-application-offer) as an official app in the Azure Marketplace

* 1-click Deployment Button
If `mainTemplate.json` is hosted somewhere remotely, a button can be created that will deploy the app when clicked like the example below.

    [![Deploy to Azure](https://aka.ms/deploytoazurebutton)](https://portal.azure.com/#create/Microsoft.Template/uri/https%3A%2F%2Fraw.githubusercontent.com%2FAzure-Samples%2Fgraphrag-accelerator%2Frefs%2Fheads%2Fharjit-managed-app%2Finfra%2FmainTemplate.json)
