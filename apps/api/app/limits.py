from starlette.responses import JSONResponse

class RequestSizeLimit:
    """Bound total body bytes, including requests sent without Content-Length."""
    def __init__(self, app, max_bytes): self.app, self.max_bytes = app, max_bytes
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] not in {"POST","PUT","PATCH"}:
            return await self.app(scope, receive, send)
        chunks=[]; total=0
        while True:
            message=await receive()
            if message["type"]=="http.disconnect": return
            total+=len(message.get("body",b""))
            if total>self.max_bytes:
                return await JSONResponse({"detail":"Requisição grande demais."},status_code=413)(scope,receive,send)
            chunks.append(message.get("body",b""))
            if not message.get("more_body",False): break
        delivered=False
        async def bounded_receive():
            nonlocal delivered
            if not delivered:
                delivered=True
                return {"type":"http.request","body":b"".join(chunks),"more_body":False}
            return await receive()
        await self.app(scope,bounded_receive,send)
