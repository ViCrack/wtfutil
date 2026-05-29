# wtfutil.strutil

Encoding/decoding, hashing, RSA/DES, string utilities, UTF-7, ghost bits.

```python
from wtfutil import str_md5, base64encode, url_encode
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

### URL / Base64

`url_encode_all`, `url_encode`, `url_decode`, `qp_encode_all`, `uuencode`, `base64encode`, `base64decode`, `base64_urlencode`, `base64_urldecode`, `urlsafe_base64encode`, `urlsafe_base64decode`, `base64pickle`, `base64unpickle`

### Crypto

`rsa_encrypt(data, public_key, block_size=None)`, `rsa_decrypt`, `des_encrypt`, `des_decrypt`

### Hash

`str_md5`, `str_sha1`, `str_sha256`

### Misc encoding

`rand_base`, `rand_case`, `format_bytes`, `extract_dict(text, sep, sep2='=')`, `utf8_overlong_encoding`, `utf7_encode`, `unicode_digit_hex_escape`, `unicode_digit_hex_encode`, `ghost_bits_byte`, `ghost_bits_encode`, `ghost_bits_decode_to_bytes`, `ghost_bits_decode`

## Examples

```python
from wtfutil import str_md5, url_encode, base64encode, get_middle_text, rand_base

str_md5("hello")
url_encode("a=1&b=2")
base64encode("data")

html = '<input name="token" value="abc123">'
get_middle_text(html, 'name="token" value="', '"')
token = rand_base(32)
```
