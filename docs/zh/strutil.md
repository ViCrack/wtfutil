# wtfutil.strutil

编码/解码、哈希、RSA/DES、字符串工具、UTF-7、ghost bits 等。

```python
from wtfutil import str_md5, base64encode, url_encode
```

## 符号索引（按类别）

### 类型转换

| 符号 | 说明 |
|------|------|
| `tobytes(s, encoding='UTF-8')` | 转为 `bytes` |
| `tostr(value, encoding='UTF-8')` | 转为 `str`；`None` 保持 `None` |
| `tobool(s)` | 解析布尔（`true`/`1`/`yes` 等） |

### 字符串处理

| 符号 | 说明 |
|------|------|
| `removesuffix` / `removeprefix` | 前后缀（兼容旧 Python） |
| `get_middle_text(text, start, end)` | 取中间片段 |
| `splitlines(s)` | 分行 |
| `normalize_spaces` | 空白归一化 |
| `align_text` | 对齐文本 |
| `match1(pattern, text)` | 正则第一个捕获组 |
| `string_to_bash_variable` | 转为 bash 变量名风格 |

### URL / Base64 / QP / uuencode

| 符号 | 说明 |
|------|------|
| `url_encode` / `url_decode` | 标准 URL 编码 |
| `url_encode_all` | 编码更多字符 |
| `qp_encode_all` | Quoted-Printable 风格 |
| `uuencode` | uuencode |
| `base64encode` / `base64decode` | Base64 |
| `base64_urlencode` / `base64_urldecode` | URL-safe Base64 |
| `urlsafe_base64encode` / `urlsafe_base64decode` | 同上（别名风格） |
| `base64pickle` / `base64unpickle` | pickle + Base64 |

### 加解密

| 符号 | 说明 |
|------|------|
| `rsa_encrypt(data, public_key, block_size=None)` | RSA 公钥加密（长数据分段） |
| `rsa_decrypt(data, private_key, block_size=None)` | RSA 私钥解密 |
| `des_encrypt(data, key)` / `des_decrypt(data, key)` | DES（`pycryptodome`） |

### 哈希

| 符号 | 说明 |
|------|------|
| `str_md5` / `str_sha1` / `str_sha256` | 字符串或 bytes → hex |

### 随机与特殊编码

| 符号 | 说明 |
|------|------|
| `rand_base(length, charset=...)` | 随机字符串 |
| `rand_case(s)` | 随机大小写 |
| `format_bytes(n)` | 人类可读字节大小 |
| `extract_dict(text, sep, sep2='=')` | 按分隔符解析为 dict（`httpraw` 解析头用） |
| `utf8_overlong_encoding` | UTF-8 过长编码 |
| `utf7_encode` | UTF-7 |
| `unicode_digit_hex_escape` / `unicode_digit_hex_encode` | Unicode 数字十六进制变体 |
| `ghost_bits_byte` / `ghost_bits_encode` / `ghost_bits_decode_to_bytes` / `ghost_bits_decode` | Ghost bits 编解码 |

## 示例

```python
from wtfutil import str_md5, base64encode, rsa_encrypt, extract_dict

str_md5("hello")
base64encode(b"data")

headers = extract_dict("Host: example.com\nUser-Agent: test\n", "\n")
```
