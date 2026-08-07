# wtfutil.strutil

编码/解码、哈希、RSA/DES、字符串工具、UTF-7、ghost bits 等。

```python
from wtfutil.strutil import base64encode, str_md5, url_encode
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
| `string_to_bash_variable` | 转为非空合法 Bash 变量名；无有效字符时返回 `_` |

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
| `base64pickle` | pickle 序列化后编码为 Base64 |

`base64unpickle` 已移除：旧实现既无法正确处理现代 pickle 字节，也没有真正限制危险 opcode。pickle 不能用于不可信输入；确需反序列化可信数据时，应由应用自行实现并明确承担安全边界。

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
| `rand_base(length, letters=...)` | 随机字符串，默认字符集为小写字母+数字（`a-z0-9`，共 36 个），可用 `letters` 自定义 |
| `rand_case(s)` | 随机大小写混淆；无可变大小写字符时抛 `ValueError`，否则保证结果不同 |
| `format_bytes(n)` | 人类可读字节大小 |
| `extract_dict(text, sep, sep2='=')` | 按分隔符解析为 dict（`httpraw` 解析头用） |
| `utf8_overlong_encoding` | UTF-8 过长编码 |
| `utf7_encode` | UTF-7 |
| `unicode_digit_hex_escape` / `unicode_digit_hex_encode` | Unicode 数字十六进制变体 |
| `ghost_bits_byte` / `ghost_bits_encode` / `ghost_bits_decode_to_bytes` / `ghost_bits_decode` | Ghost bits 编解码 |

## 示例

```python
from wtfutil.strutil import base64encode, extract_dict, get_middle_text, rand_base, str_md5, url_encode

str_md5("hello")
url_encode("a=1&b=你好")
base64encode("data")

html = '<input name="token" value="abc123">'
get_middle_text(html, 'name="token" value="', '"')

headers = extract_dict("Host: example.com\nUser-Agent: test\n", "\n")
# 默认字符集为小写字母+数字 (a-z0-9)，可用 letters= 自定义
token = rand_base(32)
```
