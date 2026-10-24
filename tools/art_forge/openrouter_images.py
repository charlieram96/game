"""Minimal client for the OpenRouter Image API (standard library only).

    POST https://openrouter.ai/api/v1/images   ->   {"data": [{"b64_json": ..., "media_type": ...}]}
    GET  https://openrouter.ai/api/v1/images/models   (public: models and the parameters each accepts)

The key comes from the OPENROUTER_API_KEY environment variable. It is sent
only in the Authorization header and is never printed, logged or written.

Every saved image gets a sidecar <image>.json with the request (prompt, model,
parameters, sha256 of each reference image), the reported usage and the time
taken, so each generated asset can be traced and regenerated. Requests are
cached by content hash: asking for the same thing again returns the files
already on disk unless `force` is set.
"""

from __future__ import annotations

import base64
import hashlib
import json
import mimetypes
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

API = "https://openrouter.ai/api/v1"
TIMEOUT_S = 600
RETRY_DELAYS_S = (2, 4, 8, 16)
RETRYABLE = {408, 429, 500, 502, 503, 504}
EXTENSIONS = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp", "image/svg+xml": ".svg"}


class ImageAPIError(RuntimeError):
    pass


def api_key() -> str:
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not key:
        raise ImageAPIError(
            "OPENROUTER_API_KEY is not set. Add it to this environment's secrets or "
            "variables (never to the repository) and start a new session."
        )
    return key


def list_models(cache: Path | None = None, max_age_s: float = 86400.0) -> list[dict]:
    """The image models and their supported parameters (no key needed)."""
    if cache is not None and cache.exists() and time.time() - cache.stat().st_mtime < max_age_s:
        return json.loads(cache.read_text())
    req = urllib.request.Request(API + "/images/models", headers={"User-Agent": "wildbound-art-forge"})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = json.loads(r.read())
    models = data.get("data", data) if isinstance(data, dict) else data
    if cache is not None:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(models, indent=1))
    return models


def find_model(model: str, models: list[dict]) -> dict:
    for m in models:
        if m.get("id") == model:
            return m
    raise ImageAPIError(f"unknown image model '{model}' (run `forge.py models` for the list)")


def max_batch(entry: dict) -> int:
    """How many images one request may ask for (`n`)."""
    spec = entry.get("supported_parameters", {}).get("n")
    return int(spec.get("max", 1)) if spec else 1


def check_params(entry: dict, params: dict, reference_count: int = 0) -> list[str]:
    """Problems with `params` for this model: unsupported keys, values outside its enums or ranges."""
    model = entry.get("id", "?")
    supported = entry.get("supported_parameters", {})
    problems: list[str] = []
    for name, value in params.items():
        if value is None or name in ("model", "prompt"):
            continue
        spec = supported.get(name)
        if spec is None:
            problems.append(f"{model} does not accept '{name}'")
        elif spec.get("type") == "enum" and value not in spec.get("values", []):
            problems.append(f"{model}: {name}={value!r} is not one of {spec.get('values')}")
        elif spec.get("type") == "range" and not (spec.get("min", value) <= value <= spec.get("max", value)):
            problems.append(f"{model}: {name}={value} is outside {spec.get('min')}..{spec.get('max')}")
    refs = supported.get("input_references")
    if reference_count and refs is None:
        problems.append(f"{model} does not accept reference images")
    elif refs is not None and not (refs.get("min", 0) <= reference_count <= refs.get("max", reference_count)):
        problems.append(f"{model} takes {refs.get('min', 0)}..{refs.get('max')} reference images, got {reference_count}")
    return problems


def data_url(path: Path) -> str:
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def _post(payload: dict) -> dict:
    body = json.dumps(payload).encode("utf-8")
    headers = {
        "Authorization": "Bearer " + api_key(),
        "Content-Type": "application/json",
        "User-Agent": "wildbound-art-forge",
        "X-Title": "Wildbound art_forge",
    }
    last: Exception | None = None
    for delay in (0,) + RETRY_DELAYS_S:
        if delay:
            time.sleep(delay)
        req = urllib.request.Request(API + "/images", data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", errors="replace")[:600]
            last = ImageAPIError(f"HTTP {e.code} from the Image API: {detail}")
            if e.code not in RETRYABLE:
                raise last from None
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            last = ImageAPIError(f"network error talking to the Image API: {e}")
    assert last is not None
    raise last


def _sniff_extension(raw: bytes, media_type: str | None) -> str:
    if media_type in EXTENSIONS:
        return EXTENSIONS[media_type]
    if raw.startswith(b"\x89PNG"):
        return ".png"
    if raw[:3] == b"\xff\xd8\xff":
        return ".jpg"
    if raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
        return ".webp"
    return ".png"


def generate(
    prompt: str,
    model: str,
    out_dir: Path,
    *,
    tag: str = "",
    n: int = 1,
    aspect_ratio: str | None = None,
    resolution: str | None = None,
    quality: str | None = None,
    background: str | None = None,
    seed: int | None = None,
    references: list[Path] | tuple[Path, ...] = (),
    models: list[dict] | None = None,
    dry_run: bool = False,
    force: bool = False,
) -> list[Path]:
    """One Image API request. Returns the saved image paths (cached files if already generated)."""
    refs = [Path(r) for r in references]
    params = {
        "model": model,
        "prompt": prompt,
        "n": n if n > 1 else None,
        "aspect_ratio": aspect_ratio,
        "resolution": resolution,
        "quality": quality,
        "background": background,
        "seed": seed,
    }
    if models is not None:
        problems = check_params(find_model(model, models), params, len(refs))
        if problems:
            raise ImageAPIError("; ".join(problems))
    payload = {k: v for k, v in params.items() if v is not None}
    ref_hashes = [hashlib.sha256(r.read_bytes()).hexdigest() for r in refs]
    request_id = hashlib.sha256(json.dumps({**payload, "refs": ref_hashes}, sort_keys=True).encode()).hexdigest()[:12]
    stem = f"{tag}_{model.split('/')[-1]}_{request_id}" if tag else f"{model.split('/')[-1]}_{request_id}"
    cached = sorted(p for p in out_dir.glob(stem + "_*") if p.suffix != ".json")
    if cached and not force:
        return cached
    if refs:
        payload["input_references"] = [{"type": "image_url", "image_url": {"url": data_url(r)}} for r in refs]
    if dry_run:
        shown = {k: v for k, v in payload.items() if k != "input_references"}
        if refs:
            shown["input_references"] = [str(r) for r in refs]
        print(json.dumps(shown, indent=1))
        return []
    out_dir.mkdir(parents=True, exist_ok=True)
    started = time.time()
    response = _post(payload)
    items = response.get("data") or []
    if not items:
        raise ImageAPIError(f"the Image API returned no images: {json.dumps(response)[:400]}")
    saved: list[Path] = []
    for i, item in enumerate(items):
        raw = base64.b64decode(item["b64_json"])
        path = out_dir / f"{stem}_{i}{_sniff_extension(raw, item.get('media_type'))}"
        path.write_bytes(raw)
        sidecar = {
            "model": model,
            "prompt": prompt,
            "params": {k: v for k, v in payload.items() if k not in ("model", "prompt", "input_references")},
            "references": [{"file": str(r), "sha256": h} for r, h in zip(refs, ref_hashes)],
            "usage": response.get("usage"),
            "seconds": round(time.time() - started, 1),
            "created": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "index": i,
        }
        path.with_suffix(".json").write_text(json.dumps(sidecar, indent=1))
        saved.append(path)
    return saved
