from aiodal.web import paginator
from aiodal import dal

from typing import Any
import dataclasses
import pytest


pytestmark = pytest.mark.anyio

from sqlalchemy.exc import NoResultFound, IntegrityError


async def test_default_paginator():
    # NOTE pydantic or whatever validator should assure offset/limit
    # ints are correct and match the logic in the request url

    offset = 0
    limit = 100
    current_len = 100
    total_count = 200
    url = f"https://mysite.com/v1/book/"
    x = paginator._default_paginator(url, offset, limit, current_len, total_count, None)
    assert x == "https://mysite.com/v1/book/?offset=100&limit=100"

    offset = 0
    limit = 100
    current_len = 100
    total_count = 200
    url = f"https://mysite.com/v1/book/?some_param=42"
    x = paginator._default_paginator(
        url, offset, limit, current_len, total_count, "/v1"
    )
    assert x == "/v1/book/?some_param=42&offset=100&limit=100"

    offset = 0
    limit = 100
    current_len = 100
    total_count = 200
    url = f"https://mysite.com/v1/book/?offset={offset}&limit={limit}"
    x = paginator._default_paginator(
        url, offset, limit, current_len, total_count, "/v1"
    )
    assert x == "/v1/book/?offset=100&limit=100"

    offset = 100
    limit = 100
    current_len = 100
    total_count = 200
    url = f"https://mysite.com/v1/book/?offset={offset}&limit={limit}"
    x = paginator._default_paginator(
        url, offset, limit, current_len, total_count, "/v1"
    )
    assert x is None

    offset = 100
    limit = 100
    current_len = 0
    total_count = 0
    url = f"https://mysite.com/v1/book/?offset={offset}&limit={limit}"
    x = paginator._default_paginator(
        url, offset, limit, current_len, total_count, "/v1"
    )
    assert x is None

    offset = 50
    limit = 100
    current_len = 50
    total_count = 200
    url = f"https://mysite.com/v1/book/?offset={offset}&limit={limit}"
    x = paginator._default_paginator(
        url, offset, limit, current_len, total_count, "/v1"
    )
    assert x == "/v1/book/?offset=150&limit=100"
