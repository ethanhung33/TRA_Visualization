## Taiwan Railway Diagram - Developing Repo

#### Usage

The website will be automatically built by github according to file `index.html`.

Data can be fetched by
```bash
python ../fetch.py {YYYY}/{MM}/{DD}
```
under `data/`. For example,
```bash
python ../fetch.py 2026/03/12
```

The existing files in `data/` and `fonts/` will be used in `index.html` and shouldn't be modified.
