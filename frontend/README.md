# Launch Instructions

Add the following variables to a `.env` file

* DEPLOYMENT_URL
* APIM_SUBSCRIPTION_KEY
* DEPLOYER_EMAIL (optional - will default to `deployer@email.com`)

The frontend is a streamlit app that can be run as a docker container:
```
# cd to the root directory of the repo
> docker build -t graphrag:frontend -f docker/Dockerfile-frontend .
> docker run --env-file <env_file> -p 8080:8080 graphrag:frontend
```

To access the app, visit `localhost:8080` in your browser
