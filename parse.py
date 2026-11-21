import asyncio
import ipaddress
import socket
from typing import Annotated
from urllib.parse import urlsplit

import httpx
from bs4 import BeautifulSoup
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, HttpUrl

app = FastAPI()
MAX_RESPONSE_BYTES = 1_000_000


class SiteInfo(BaseModel):
    url: HttpUrl
    title: str | None
    description: str | None
    first_h1: str | None


async def validate_public_url(url: HttpUrl) -> None:
    try:
        parts = urlsplit(str(url))
        hostname = parts.hostname
        port = parts.port
    except ValueError as error:
        raise HTTPException(status_code=422, detail="Invalid URL") from error

    if (
        parts.scheme.lower() not in {"http", "https"}
        or not hostname
        or parts.username is not None
        or parts.password is not None
        or "%" in hostname
    ):
        raise HTTPException(
            status_code=422,
            detail="URL must be HTTP(S), without credentials or a scoped IP address",
        )

    expected_port = 443 if parts.scheme.lower() == "https" else 80
    if port is not None and port != expected_port:
        raise HTTPException(status_code=422, detail="Only standard HTTP(S) ports are allowed")

    port = port or expected_port
    try:
        addresses = {ipaddress.ip_address(hostname)}
    except ValueError:
        try:
            records = await asyncio.to_thread(
                socket.getaddrinfo, hostname, port, type=socket.SOCK_STREAM
            )
        except OSError as error:
            raise HTTPException(status_code=422, detail="Could not resolve URL hostname") from error
        addresses = {ipaddress.ip_address(record[4][0]) for record in records}

    if not addresses or any(not address.is_global for address in addresses):
        raise HTTPException(status_code=422, detail="URL must resolve only to public IP addresses")

@app.get("/parse", response_model=SiteInfo)
async def parse_site(url: Annotated[HttpUrl, Query(max_length=2048)]) -> SiteInfo:
    await validate_public_url(url)
    url_string = str(url)

    try:
        async with httpx.AsyncClient(
            timeout=10.0,
            follow_redirects=False,
            trust_env=False,
        ) as client:
            async with client.stream(
                "GET",
                url_string,
                headers={"User-Agent": "SiteInfoParser/1.0"},
            ) as response:
                if 300 <= response.status_code < 400:
                    raise HTTPException(
                        status_code=502,
                        detail="The site redirected; redirects are disabled",
                    )
                if response.status_code >= 400:
                    raise HTTPException(
                        status_code=502,
                        detail=f"The site returned HTTP {response.status_code}",
                    )

                content_type = response.headers.get("content-type", "").split(";", 1)[0].lower()
                if content_type and content_type not in {"text/html", "application/xhtml+xml"}:
                    raise HTTPException(status_code=502, detail="The site did not return HTML")

                content = bytearray()
                async for chunk in response.aiter_bytes():
                    content.extend(chunk)
                    if len(content) > MAX_RESPONSE_BYTES:
                        raise HTTPException(
                            status_code=502,
                            detail="The site's HTML exceeds the response size limit",
                        )
                encoding = response.encoding or "utf-8"
    except httpx.TimeoutException as error:
        raise HTTPException(status_code=504, detail="Timed out while fetching the site") from error
    except httpx.HTTPError as error:
        raise HTTPException(status_code=502, detail="Could not fetch the site") from error

    soup = BeautifulSoup(bytes(content).decode(encoding, errors="replace"), "html.parser")
    title = soup.find("title")
    description_tag = soup.find("meta", attrs={"name": "description"})
    heading = soup.find("h1")

    return SiteInfo(
        url=url,
        title=title.get_text(" ", strip=True) if title else None,
        description=description_tag.get("content") if description_tag else None,
        first_h1=heading.get_text(" ", strip=True) if heading else None,
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
