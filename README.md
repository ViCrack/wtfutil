# wtfutil

<a href="https://pypi.python.org/pypi/wtfutil"><img src="https://img.shields.io/pypi/v/wtfutil.svg"></a>
<a href="https://pypi.python.org/pypi/wtfutil"><img src="https://img.shields.io/pypi/pyversions/wtfutil.svg"></a>

## Overview

**wtfutil** is a Python utility library for HTTP, files, strings & crypto, databases, Windows processes, notifications, translation, random images, and more.

**Author**: [vicrack](https://github.com/vicrack)

## Installation

```bash
pip install wtfutil
```

Requires Python 3.6+.

## Quick Start

```python
from wtfutil import util

req = util.requests_session(timeout=30)
print(req.get("https://example.com").status_code)

util.send("Alert", "Hello from wtfutil")
```

## Documentation

Full **usage examples** and **API reference** live in the readme repository:

| Language | File |
|----------|------|
| English | [`D:\Code\Python\wtfutil-readme\README.md`](D:\Code\Python\wtfutil-readme\README.md) |
| 中文 | [`D:\Code\Python\wtfutil-readme\README_zh.md`](D:\Code\Python\wtfutil-readme\README_zh.md) |

Modules: `httputil`, `fileutil`, `strutil`, `sqlutil`, `procutil`, `notifyutil`, `translateutil`, `imgutil`, `singleinstance`, and the aggregated `util` entry point.

Configuration: `wtfconfig.ini` (`[notify]`, `[img]`) or environment variables — see the docs above.

## Contributing

Issues and pull requests are welcome on [GitHub](https://github.com/vicrack).
