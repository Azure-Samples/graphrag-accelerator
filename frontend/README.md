# Launch Instructions

Add the following variables to a `.env` file

* APIM_SUBSCRIPTION_KEY
* DEPLOYMENT_URL
* AI_SEARCH_URL
* AI_SEARCH_KEY
* DEPLOYER_EMAIL

The frontend can run natively as a streamlit app:
```
> streamlit run app.py --server.port 8080
```
or as a docker container:
```
# cd to the root directory of the repo
> docker build -t graphrag:frontend -f docker/Dockerfile-frontend .
> docker run --env-file <env_file> -p 8080:8080 graphrag:frontend
```

To access the app, visit `localhost:8080` in your browser
