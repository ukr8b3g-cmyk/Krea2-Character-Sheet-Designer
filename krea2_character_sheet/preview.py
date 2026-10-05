"""Bounded same-server preview adapter. No image/model execution or upload."""
from __future__ import annotations
from .compiler import STATE_MAX_BYTES, StateValidationError, compile_state, decode_json
from .node import runtime_max_resolution

PREVIEW_PATH = "/krea2_character_sheet_designer/preview"
HTTP_MAX_BYTES = 3 * STATE_MAX_BYTES


def compile_preview_request(body: bytes, *, max_resolution: int, layout_reference: bool = False, builtin_layout: bool = False) -> dict:
    if len(body) > HTTP_MAX_BYTES:
        raise StateValidationError(f"Preview request exceeds the {HTTP_MAX_BYTES}-byte limit.", "request_too_large")
    try:
        text = body.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise StateValidationError("Preview request must be valid UTF-8.", "invalid_utf8") from exc
    envelope = decode_json(text, byte_limit=HTTP_MAX_BYTES)
    if type(envelope) is not dict or set(envelope) != {"state_json"}:
        raise StateValidationError("Preview request must be an object containing only state_json.", "invalid_request")
    return compile_state(envelope["state_json"], max_resolution=max_resolution, layout_reference=layout_reference, builtin_layout=builtin_layout)


async def preview(request, *, layout_reference=False, builtin_layout=False):
    from aiohttp import web  # Supplied by ComfyUI, not a pure-compiler dependency.

    def error(code, message, status):
        return web.json_response({"error": {"code": code, "message": message}}, status=status)

    if request.content_length is not None and request.content_length > HTTP_MAX_BYTES:
        return error("request_too_large", f"Preview request exceeds the {HTTP_MAX_BYTES}-byte limit.", 413)
    if request.content_type != "application/json":
        return error("invalid_content_type", "Content-Type must be application/json.", 415)
    body = bytearray()
    async for chunk in request.content.iter_chunked(4096):
        body.extend(chunk)
        if len(body) > HTTP_MAX_BYTES:
            return error("request_too_large", f"Preview request exceeds the {HTTP_MAX_BYTES}-byte limit.", 413)
    try:
        result = compile_preview_request(bytes(body), max_resolution=runtime_max_resolution(), layout_reference=layout_reference, builtin_layout=builtin_layout)
    except StateValidationError as exc:
        return error(exc.code, str(exc), 413 if exc.code in ("state_too_large", "request_too_large") else 400)
    except Exception as exc:
        # Do not return exception text or user prompts in a public HTTP response.
        import logging
        logging.getLogger(__name__).error("Krea2 sheet preview failed (%s)", type(exc).__name__)
        return error("internal_error", "Preview compilation failed; check the server setup. The saved state is unchanged.", 500)
    return web.json_response(result)


async def layout_preview(request):
    return await preview(request, layout_reference=True)


async def builtin_layout_preview(request):
    return await preview(request, layout_reference=True, builtin_layout=True)


def register_routes() -> bool:
    try:
        from server import PromptServer
    except ModuleNotFoundError as exc:
        if exc.name == "server":
            return False
        raise
    instance = getattr(PromptServer, "instance", None)
    if instance is None:
        return False
    flag = "_krea2_character_sheet_designer_route_registered"
    if getattr(instance, flag, False):
        return True
    instance.routes.post(PREVIEW_PATH)(preview)
    instance.routes.post("/krea2_character_sheet_designer/layout-reference/preview")(layout_preview)
    instance.routes.post("/krea2_character_sheet_designer/layout-image/preview")(builtin_layout_preview)
    setattr(instance, flag, True)
    return True
