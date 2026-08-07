# wtfutil.strutil

Encoding/decoding, hashing, RSA/DES, string utilities, UTF-7, ghost bits.

```python
from wtfutil.strutil import base64encode, str_md5, url_encode
```

## Symbol index

### Type conversion

| Symbol | Description |
|--------|-------------|
| `tobytes(s, encoding='UTF-8')` | Convert to `bytes` |
| `tostr(value, encoding='UTF-8')` | Convert to `str` |
| `tobool(s)` | Parse boolean |

### String manipulation

`removesuffix`, `removeprefix`, `get_middle_text`, `splitlines`, `normalize_spaces`, `align_text`, `match1`, `string_to_bash_variable`

`rand_case` requires at least one case-sensitive character and otherwise raises `ValueError`; `string_to_bash_variable` always returns a non-empty valid name (`"_"` for an empty result).

### URL / Base64

`url_encode_all`, `url_encode`, `url_decode`, `qp_encode_all`, `uuencode`, `base64encode`, `base64decode`, `base64_urlencode`, `base64_urldecode`, `urlsafe_base64encode`, `urlsafe_base64decode`, `base64pickle`

`base64unpickle` was removed because Python pickle cannot safely deserialize untrusted data through the previous attempted opcode restriction. Applications that intentionally deserialize trusted pickle data must implement that policy explicitly outside wtfutil.

### Crypto

`rsa_encrypt(data, public_key, block_size=None)`, `rsa_decrypt`, `des_encrypt`, `des_decrypt`

### Hash

`str_md5`, `str_sha1`, `str_sha256`

### Misc encoding

`rand_base(length, letters=...)`, `rand_case(s)`, `format_bytes`, `extract_dict(text, sep, sep2='=')`, `utf8_overlong_encoding`, `utf7_encode`, `unicode_digit_hex_escape`, `unicode_digit_hex_encode`, `ghost_bits_byte`, `ghost_bits_encode`, `ghost_bits_decode_to_bytes`, `ghost_bits_decode`

## Examples

```python
from wtfutil.strutil import base64encode, get_middle_text, rand_base, str_md5, url_encode

str_md5("hello")
url_encode("a=1&b=2")
base64encode("data")

html = '<input name="token" value="abc123">'
get_middle_text(html, 'name="token" value="', '"')
# default charset: lowercase letters + digits (a-z0-9); pass `letters=` to customize
token = rand_base(32)
```
