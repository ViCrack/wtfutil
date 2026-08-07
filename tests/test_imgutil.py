"""imgutil 图片校验、回退和会话生命周期回归测试。"""

from __future__ import annotations

import unittest
from unittest import mock

from requests import Response

from wtfutil import imgutil


def _build_response(
    content: bytes,
    *,
    status_code: int = 200,
    content_type: str | None = None,
) -> Response:
    response = Response()
    response.status_code = status_code
    response._content = content
    if content_type is not None:
        response.headers["Content-Type"] = content_type
    return response


class TestImageValidation(unittest.TestCase):
    def test_html_success_response_is_rejected(self) -> None:
        response = _build_response(
            b"<html>rate limited</html>" * 20,
            content_type="text/html",
        )

        with self.assertRaisesRegex(ValueError, "not an image"):
            imgutil._validate_image_bytes(response)

    def test_known_signature_is_accepted_without_content_type(self) -> None:
        image_bytes = b"\x89PNG\r\n\x1a\n" + b"x" * 300
        response = _build_response(image_bytes)

        self.assertEqual(imgutil._validate_image_bytes(response), image_bytes)

    def test_webp_signature_is_accepted(self) -> None:
        image_bytes = b"RIFF" + b"\x00" * 4 + b"WEBP" + b"x" * 300
        response = _build_response(image_bytes)

        self.assertEqual(imgutil._validate_image_bytes(response), image_bytes)

    def test_small_or_non_success_response_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "too small"):
            imgutil._validate_image_bytes(
                _build_response(b"\x89PNG\r\n\x1a\n", content_type="image/png")
            )
        with self.assertRaisesRegex(ValueError, "HTTP 503"):
            imgutil._validate_image_bytes(
                _build_response(b"x" * 300, status_code=503)
            )


class TestImageFetcherFallback(unittest.TestCase):
    def test_failed_fetcher_falls_back_to_next_provider(self) -> None:
        session = mock.Mock()

        def failing_fetcher(_session):
            raise RuntimeError("first failed")

        def successful_fetcher(received_session):
            self.assertIs(received_session, session)
            return b"image"

        result = imgutil.fetch_random_bytes(
            [failing_fetcher, successful_fetcher],
            session=session,
            shuffle=False,
        )

        self.assertEqual(result, b"image")
        session.close.assert_not_called()

    def test_all_failures_are_aggregated_and_owned_session_is_closed(self) -> None:
        session = mock.Mock()

        def first_fetcher(_session):
            raise RuntimeError("first failed")

        def second_fetcher(_session):
            raise ValueError("second failed")

        with (
            mock.patch.object(
                imgutil,
                "requests_session",
                return_value=session,
            ),
            self.assertRaises(imgutil.ImageFetchError) as raised,
        ):
            imgutil.fetch_random_bytes(
                [first_fetcher, second_fetcher],
                shuffle=False,
            )

        self.assertEqual(len(raised.exception.errors), 2)
        session.close.assert_called_once_with()

    def test_random_avatar_public_entrypoint_closes_owned_session(self) -> None:
        session = mock.Mock()
        provider = mock.Mock(return_value=b"avatar")

        with (
            mock.patch.object(
                imgutil,
                "_avatar_providers",
                return_value=[("test", provider)],
            ),
            mock.patch.object(
                imgutil,
                "requests_session",
                return_value=session,
            ) as requests_session_mock,
        ):
            result = imgutil.random_avatar_bytes(timeout=12)

        self.assertEqual(result, b"avatar")
        provider.assert_called_once_with(session)
        requests_session_mock.assert_called_once_with(timeout=12)
        session.close.assert_called_once_with()

    def test_random_avatar_external_session_is_not_closed(self) -> None:
        session = mock.Mock()
        provider = mock.Mock(return_value=b"avatar")

        with mock.patch.object(
            imgutil,
            "_avatar_providers",
            return_value=[("test", provider)],
        ):
            self.assertEqual(
                imgutil.random_avatar_bytes(session=session),
                b"avatar",
            )

        session.close.assert_not_called()

    def test_apihz_provider_requires_a_valid_image_url(self) -> None:
        session = mock.Mock()
        session.get.return_value.status_code = 200
        session.get.return_value.json.return_value = {"code": 200}
        with mock.patch.dict(
            imgutil.img_config,
            {"APIHZ_IMG_ID": "id", "APIHZ_IMG_KEY": "key"},
            clear=False,
        ):
            with self.assertRaisesRegex(ValueError, "missing msg"):
                imgutil._fetch_apihz(session)


if __name__ == "__main__":
    unittest.main()
