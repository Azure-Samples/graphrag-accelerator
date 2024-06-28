# Instructions

1. Create a dataset to use with GraphRAG. You may provide your own data or use the `get-wiki-articles.py` script to download a small set of wikipedia articles for demonstration purposes.

```shell
> python get-wiki-articles.py testdata
```
For a faster example with less data
```shell
> python get-wiki-articles.py --short-summary --num-articles 1 testdata
```

2. Follow instructions in the `1-Quickstart.ipynb` notebook to explore the GraphRAG API, by building an index of the data in `testdata` and executing queries.
