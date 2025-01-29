# Web App
This application is a FastAPI app that implements a REST API wrapper around the graphrag library.

## Package Layout
The code has the following structure:
```shell
backend
├── README.md
├── graphrag_app     # contains the main application files
│   ├── __init__.py
│   ├── api          # endpoint definitions
│   ├── logger       # custom loggers designed for graphrag use
│   ├── main.py      # initializes the FastAPI application
│   ├── typing
│   └── utils        # utility/helper functions
├── manifests        # k8s manifest files
├── poetry.lock
├── pyproject.toml
├── pytest.ini
├── scripts          # miscellaneous scripts that get executed in k8s
└── tests            # pytests (integration tests + unit tests)
```
