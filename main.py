import os
import time
import uuid
from collections import defaultdict, deque

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

EMAIL = os.getenv(
    "STUDENT_EMAIL",
    "25ds3000025@ds.study.iitm.ac.in",
)

ALLOWED_ORIGINS = [
    "https://app-kqugxj.example.com",
    "https://exam.sanand.workers.dev",
]

WINDOW_SECONDS = 10
MAX_REQUESTS = 10

app = FastAPI()
requests_by_client = defaultdict(deque)


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID")
        if not request_id:
            request_id = str(uuid.uuid4())

        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path != "/ping" or request.method != "GET":
            return await call_next(request)

        client_id = request.headers.get("X-Client-Id", "anonymous")
        now = time.monotonic()
        timestamps = requests_by_client[client_id]

        while timestamps and now - timestamps[0] >= WINDOW_SECONDS:
            timestamps.popleft()

        if len(timestamps) >= MAX_REQUESTS:
            request_id = getattr(request.state, "request_id", None)
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Rate limit exceeded",
                    "request_id": request_id,
                },
            )

        timestamps.append(now)
        return await call_next(request)


app.add_middleware(RateLimitMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "OPTIONS"],
    allow_headers=[
        "X-Request-ID",
        "X-Client-Id",
        "Content-Type",
    ],
)

app.add_middleware(RequestContextMiddleware)


@app.get("/ping")
async def ping(request: Request):
    return {
        "email": EMAIL,
        "request_id": request.state.request_id,
    }
