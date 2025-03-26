# Overview

This helm chart was created to install graphrag into a kubernetes cluster.

## Developer Notes
If making updates to the helm chart, you can validate changes to the helm chart locally by using the following `helm` command example:

```shell
helm template test ./graphrag \
    --namespace graphrag \
    --set "master.image.repository=registry.azurecr.io/graphrag" \
    --set "master.image.tag=latest"
```
