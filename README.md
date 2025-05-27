# wftutil

<a href="https://pypi.python.org/pypi/wtfutil"><img src="https://img.shields.io/pypi/v/wtfutil.svg"></a>
<a href="https://pypi.python.org/pypi/wtfutil"><img src="https://img.shields.io/pypi/pyversions/wtfutil.svg"></a>

=================================================================================================================

## ☤ Overview

WTF A Python utility

**wtfutil** is a versatile Python utility library designed to streamline common programming tasks. It provides a rich set of tools for HTTP requests, file operations, string manipulation, encryption/decryption, database interactions, notification services, and more. Built with developer convenience in mind, `wtfutil` includes optimizations such as enhanced requests handling for Windows HTTPS proxies, SSL verification bypass, and suppression of urllib3 warnings.

**Author** : [vicrack](https://github.com/vicrack)

**GitHub** : [https://github.com/vicrack](https://github.com/vicrack)

## ☤ Installation

Install `wtfutil` from [PyPI](https://pypi.org/project/wtfutil/) via pip:

```bash
pip install wtfutil
```

Ensure you have Python 3.6 or higher installed, as the library leverages modern Python features.

## ☤ Features

`wtfutil` is organized into several key modules, each addressing specific needs:

-   **HTTP Utilities (`httputil`)** : Enhanced requests sessions with proxy support, retries, timeouts, and raw HTTP request capabilities.
-   **File Utilities (`fileutil`)** : Simplified file I/O, hash computation, and JAR file analysis.
-   **String Utilities (`strutil`)** : Encoding/decoding, hashing, encryption, and text manipulation.
-   **Database Utilities (`sqlutil`)** : CRUD operations for SQLite and MySQL with thread-safe connections.
-   **Notification Utilities (`notifyutil`)** : Multi-channel notifications (e.g., Bark, DingTalk, Telegram).
-   **Translation Utilities (`translateutil`)** : Integration with Baidu Translate API.
-   **General Utilities**: Time measurement, unique data structures, and resource management.
-   more...

### Internal Optimizations

The library applies several optimizations to improve usability:

```python
urllib3.disable_warnings()          # Suppresses urllib3 warnings
remove_ssl_verify()                 # Disables SSL verification
patch_redirect()                    # Enhances redirect handling
patch_getproxies()                  # Fixes Windows proxy issues
```

## ☤ Usage Examples

Below are detailed examples demonstrating the core functionalities of wtfutil. Import the util module to access all features conveniently.

### ☤ HTTP Utilities

#### Creating an Optimized requests Session

```python
from wtfutil import util

# Basic session with timeout and retry
req1 = util.requests_session(timeout=30, max_retries=1)
response = req1.post('http://localhost:8080/xxx')

# Session with a base URL
req2 = util.requests_session(base_url='http://localhost:8080', timeout=30, max_retries=1)
response = req2.post('/xxx/update')  # Resolves to http://localhost:8080/xxx/update

req3 = util.requests_session()
response = req3.get('http://example.com')

```

#### Sending Raw HTTP Requests

```python
from wtfutil import util

response = util.httpraw('''
POST /upload HTTP/1.1
Host: example.com
User-Agent: wtfutil/1.0
Accept-Charset: utf-8
Content-Type: multipart/form-data; boundary=----WebKitFormBoundaryzxcxzcxz

------WebKitFormBoundaryzxcxzcxz
Content-Disposition: form-data; name="upload"; filename="f.jsp"

test
------WebKitFormBoundaryzxcxzcxz--
''')
print(response.status_code, response.text)
```

#### Checking Internal IPs and Wildcard DNS

```python
from wtfutil import util

# Check if an IP is private
print(util.is_private_ip('192.168.1.1'))  # True

# Check if a URL points to an internal IP
print(util.is_internal_url('http://10.0.0.1'))  # True

# Check for wildcard DNS
print(util.is_wildcard_dns('example.com'))  # Depends on DNS configuration
```

### ☤ File Utilities

#### File I/O Operations

```python
from wtfutil import util

# Read lines from a file
urls = util.read_lines('urls.txt')

# Read text or binary content
text = util.read_text('data.txt')
binary = util.read_bytes('image.jpg')

# Write content to a file
util.write_text('output.txt', 'Hello, World!')
util.write_lines('lines.txt', ['line1', 'line2'])
util.write_json('config.json', {'key': 'value'})
```

#### File Hashing

```python
from wtfutil import util

print(util.file_md5('/etc/hosts'))      # MD5 hash
print(util.file_sha1('/etc/hosts'))     # SHA1 hash
print(util.file_sha256('/etc/hosts'))   # SHA256 hash
```

#### JAR File Analysis

```python
from wtfutil import util

analyzer = util.JarAnalyzer('example.jar')
print(f"JDK Version: {analyzer.jdk_version}")
print(f"Is Spring Boot: {analyzer.is_spring_boot}")
print(f"Main Class: {analyzer.main_class}")
print(f"Recommended Executable: {analyzer.recommended_executable}")
```

### ☤ String Utilities

#### Encoding and Decoding

```python
from wtfutil import util

# Base64 operations
encoded = util.base64encode('Hello')
decoded = util.base64decode(encoded)

# URL-safe Base64
safe_encoded = util.urlsafe_base64encode('Hello')
safe_decoded = util.urlsafe_base64decode(safe_encoded)

# URL encoding
url_encoded = util.url_encode('Hello World')
all_encoded = util.url_encode_all('Hello')  # Encodes every character
q_all_encoded = util.q_encode_all('Hello')  # Encodes every character
```

#### String Hashing

```python
from wtfutil import util

print(util.str_md5('test'))      # MD5 hash of string
print(util.str_sha1('test'))     # SHA1 hash of string
print(util.str_sha256('test'))   # SHA256 hash of string
```

#### Encryption and Decryption

```python
from wtfutil import util

# RSA encryption
public_key = '...'  # Your RSA public key
private_key = '...' # Your RSA private key
encrypted = util.rsa_encrypt('Secret', public_key)
decrypted = util.rsa_decrypt(encrypted, private_key)

# DES encryption
key = '8bytekey'
encrypted = util.des_encrypt('Secret', key)
decrypted = util.des_decrypt(encrypted, key)
```

#### Text Manipulation

```python
from wtfutil import util

# Prefix/suffix removal
print(util.removesuffix('test123', '123'))  # 'test'
print(util.removeprefix('test123', 'test')) # '123'

# Random string generation
print(util.rand_base(10))  # e.g., 'abc123xyz9'
print(util.rand_case('hello'))  # e.g., 'HeLLo'

# Boolean conversion
print(util.str_to_bool('yes'))  # True
```

### ☤ Database Utilities

#### SQLite Operations

Perform database operations with minimal setup:

```python
from wtfutil import util

db = util.SQLite("test.db")
db.insert("users", {"id": 1, "name": "Alice"})
db.insert_many("users", [{"id": 2, "name": "Bob"}, {"id": 3, "name": "Charlie"}])
result = db.select_one("users", columns=["id", "name"], where_clause={"id": 1})
print(result)  # {'id': 1, 'name': 'Alice'}
print(db.record_exists("users", {"id": 1}))  # True
db.close()
```

#### MySQL Operations

Connect to MySQL with similar ease:

```python
from wtfutil import util

db = util.MYSQL(host="localhost", user="root", password="password", database="test_db")
db.insert("users", {"id": 1, "name": "Alice"})
db.update("users", {"name": "Alice Updated"}, where_clause={"id": 1})
result = db.select_by_id("users", 1)
print(result)  # {'id': 1, 'name': 'Alice Updated'}
db.close()
```

### ☤ Notification Utilities

#### Sending Notifications

```python
from wtfutil import util

# Configure via environment variables or wtfconfig.ini
util.send('Alert', 'Something happened!')
```

Supported channels include Bark, DingTalk, FeiShu, Telegram, SMTP, and more. Configuration is flexible via `wtfconfig.ini` or environment variables.

### ☤ Translation Utilities

#### Baidu Translate API

```python
from wtfutil import util

translator = util.BaiduTranslateApi(appid='your_appid', appkey='your_appkey')
result = translator.translate('你好', from_lang='zh', to_lang='en')  # 'Hello'
```

### ☤ Single Instance Utility

`wtfutil.singleinstance` provides a lightweight way to ensure that only one instance of a script runs at any given time. This is useful for preventing concurrent executions in environments like crontab or scheduled tasks.

It uses a lock file placed in the system's temporary directory, based on the full absolute path of the script (or a unique `flavor_id` if specified), to detect existing instances.

#### Example Usage with Context Manager

```python
from wtfutil import single_instance, SingleInstanceException

try:
    with single_instance(flavor_id=""):
        print("Running the only allowed instance...")
        # Your main logic goes here
except SingleInstanceException:
    print("Another instance is already running. Exiting.")
```

#### Example Usage with Decorator

```python
from wtfutil import single_instance, SingleInstanceException

@single_instance(flavor_id="job")
def run_task():
    print("This job runs exclusively.")

try:
    run_task()
except SingleInstanceException:
    print("Job is already running elsewhere.")

```

#### Parameters
* flavor_id: (optional) A custom identifier to distinguish between multiple singleton instances from the same script.
* SingleInstanceException: Exception raised when another instance is already active.


### ☤ General Utilities

#### Time Measurement

```python
from wtfutil import util

@util.measure_time
def slow_function():
    time.sleep(1)
slow_function()  # Prints execution time
```

#### Unique Items and Queues

```python
from wtfutil import util

# Unique list items
unique = util.unique_items([1, 2, 2, 3])  # [1, 2, 3]

# Unique queue
q = util.UniqueQueue()
q.put('item')
q.put('item')  # Ignored
print(q.qsize())  # 1
```

#### Resource Path Resolution

```python
from wtfutil import util

path = util.get_resource('config.txt')  # Resolves to absolute path
```



## ☤ Modular Imports in wtfutil

`wtfutil` is split into submodules like `httputil`, `fileutil`, and `sqlutil`, so you can import just what you need. For example:

* **HTTP utilities** : `from wtfutil import httputil`
* **File utilities** : `from wtfutil import fileutil`

This keeps your code light and clear. Alternatively, import `util` for everything: `from wtfutil import util`.

## ☤ Configuration

For notification services, configure settings in `wtfconfig.ini` or via environment variables. Example `wtfconfig.ini`:

### Using wtfconfig.ini

Place this file in your working directory:

```ini
[notify]
BARK_PUSH=https://api.day.app/your_key
TG_BOT_TOKEN=your_token
TG_USER_ID=your_id
```

### Using Environment Variables

Set variables in your shell:

```bash
export BARK_PUSH=https://api.day.app/your_bark_key
export TG_BOT_TOKEN=your_telegram_bot_token
export TG_USER_ID=your_telegram_user_id
```

### Priority

-   Environment variables take precedence over wtfconfig.ini.
-   If neither is provided, notifications may fail unless defaults are set.

## ☤ Contributing

Contributions are welcome! Please submit issues or pull requests via [GitHub](https://github.com/vicrack). Ensure code adheres to PEP 8 standards and includes tests where applicable.

## ☤ Acknowledgments

Thank you for exploring `wtfutil`! I hope it enhances your development workflow. Feedback and suggestions are appreciated via [GitHub Issues](https://github.com/vicrack).

**Author** : [vicrack](https://github.com/vicrack)

**GitHub** : [https://github.com/vicrack](https://github.com/vicrack)
