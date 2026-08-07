"""strutil 常见编码、文本边界和密码学兼容测试。"""

from __future__ import annotations

import base64
import unittest
from unittest import mock

from Crypto.PublicKey import RSA

from wtfutil import strutil


class TestStringConversions(unittest.TestCase):
    def test_byte_and_boolean_conversions(self) -> None:
        self.assertEqual(strutil.tobytes("中文"), "中文".encode())
        self.assertEqual(strutil.tobytes(memoryview(b"data")), b"data")
        self.assertEqual(strutil.tostr(b"data"), "data")
        self.assertTrue(strutil.tobool("YES"))
        self.assertFalse(strutil.tobool("off"))
        with self.assertRaises(ValueError):
            strutil.tobool("maybe")

    def test_base64_and_url_encoding_round_trip(self) -> None:
        encoded = strutil.base64encode("中文 message")
        self.assertEqual(strutil.base64decode(encoded), "中文 message")
        url_encoded = strutil.url_encode("a b/中文")
        self.assertEqual(strutil.url_decode(url_encoded), "a b/中文")

    def test_middle_text_rejects_empty_delimiters(self) -> None:
        for start_delimiter, end_delimiter in (("", "]"), ("[", ""), ("", "")):
            with self.subTest(start=start_delimiter, end=end_delimiter), self.assertRaises(ValueError):
                strutil.get_middle_text("[value]", start_delimiter, end_delimiter)

    def test_bash_variable_uses_portable_ascii_identifier(self) -> None:
        self.assertEqual(strutil.string_to_bash_variable("中文"), "_")
        self.assertEqual(strutil.string_to_bash_variable("9-name"), "_9_name")


class TestEncodingBoundaries(unittest.TestCase):
    def test_utf7_rejects_non_positive_or_non_integer_segment_size(self) -> None:
        for invalid_size in (0, -1, 1.5, True):
            with self.subTest(invalid_size=invalid_size), self.assertRaises(ValueError):
                strutil.utf7_encode("abcdef", segment_size=invalid_size)

    def test_utf7_randomizes_each_segment(self) -> None:
        with mock.patch.object(strutil.random, "randint", side_effect=[1, 2, 1]) as randint:
            encoded = strutil.utf7_encode("abcd")

        self.assertEqual(randint.call_count, 3)
        self.assertEqual(encoded.count("-"), 3)

    def test_ghost_bits_round_trip_all_byte_values(self) -> None:
        original = bytes(range(256))
        encoded = strutil.ghost_bits_encode(original)
        self.assertEqual(strutil.ghost_bits_decode_to_bytes(encoded), original)


class TestLegacyCryptoCompatibility(unittest.TestCase):
    def test_des_round_trip(self) -> None:
        ciphertext = strutil.des_encrypt("中文 payload", "12345678")
        self.assertEqual(strutil.des_decrypt(ciphertext, "12345678"), "中文 payload")

    def test_rsa_round_trip_across_multiple_blocks(self) -> None:
        private_key = RSA.generate(1024)
        public_key_text = base64.b64encode(
            private_key.publickey().export_key(format="DER")
        ).decode("ascii")
        private_key_text = base64.b64encode(
            private_key.export_key(format="DER")
        ).decode("ascii")
        plaintext = "long-message-" * 20

        ciphertext = strutil.rsa_encrypt(plaintext, public_key_text)

        self.assertEqual(strutil.rsa_decrypt(ciphertext, private_key_text), plaintext)


if __name__ == "__main__":
    unittest.main()
