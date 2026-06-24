from __future__ import annotations

from typing import Any


import requests
from requests import Response, Session
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


DEFAULT_TIMEOUT = (10, 30)


def create_retry_session() -> Session:
    session = requests.Session()
    retry = Retry(
        total=3,
        connect=3,
        read=3,
        status=3,
        backoff_factor=1,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset(["GET", "POST", "PUT", "DELETE", "HEAD", "OPTIONS"]),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


def request_with_retry(method: str, url: str, **kwargs: Any) -> Response:
    session = create_retry_session()
    kwargs.setdefault("timeout", DEFAULT_TIMEOUT)
    return session.request(method=method, url=url, **kwargs)


def get_with_retry(url: str, **kwargs: Any) -> Response:
    return request_with_retry("GET", url, **kwargs)
