# Day in the Life — Site Manager Edition

A standalone first-person office demo. It uses three preselected questions against the live Trilobyte API and speaks English through the browser's speech synthesizer. No Trilobyte application files are imported or changed.

```sh
python3 server.py
# http://127.0.0.1:8102
```

The local server listens on `127.0.0.1:8102` and proxies only `/api/ask` and the selected floor-plan image to `TRILOBYTE_API` (default `http://127.0.0.1:8090`). Click **Start shift**, use **E** or click the monitor, ask Trilobyte, and tell the worker the answer.
