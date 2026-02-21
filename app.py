import streamlit as st
import requests
import fal_client
import asyncio
import os
import base64
import logging
import time
import concurrent.futures
from PIL import Image
from io import BytesIO
from datetime import datetime
from zipfile import ZipFile
from dataclasses import dataclass, field
from typing import Optional

# ---------------------------------------------------------------------------
# Setup logging
# ---------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Page Config & Theme  (must be the first Streamlit command)
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="吳振畫室 振視科技 tot@alexzhenwu.com",
    page_icon="🎨",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Custom CSS – dark-mode-aware
# ---------------------------------------------------------------------------
st.markdown(
    """
<style>
/* ---- Title ---- */
.main-title {
    font-size: clamp(2rem, 5vw, 4rem);
    font-weight: 900;
    text-align: center;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin-bottom: 0.25rem;
    letter-spacing: 0.1em;
}
.sub-title {
    text-align: center;
    opacity: 0.6;
    font-size: 0.95rem;
    margin-bottom: 1.5rem;
}

/* ---- Cards ---- */
.img-card {
    border-radius: 12px;
    overflow: hidden;
    transition: box-shadow 0.3s ease;
}
.img-card:hover {
    box-shadow: 0 4px 20px rgba(102, 126, 234, 0.35);
}

/* ---- Buttons ---- */
div.stButton > button {
    border-radius: 10px;
    font-weight: 600;
}

/* ---- Sidebar section headers ---- */
.sidebar-section {
    font-size: 0.8rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    opacity: 0.55;
    margin-top: 1rem;
}
</style>
""",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class GeneratedImage:
    """Stores metadata for every generated image."""
    url: str
    prompt: str
    model: str
    timestamp: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    seed: Optional[int] = None
    nsfw: Optional[bool] = None


# ---------------------------------------------------------------------------
# Model Registry — single source of truth
# ---------------------------------------------------------------------------

MODEL_REGISTRY: dict[str, dict] = {
    "🌟 Flux 2 Pro": {
        "endpoint": "fal-ai/flux-2-pro",
        "supports_ref": False,
        "default_steps": 28,
        "default_guidance": 3.5,
        "description": "最高質量通用生成",
    },
    "🍌 Nano Banana Pro Edit": {
        "endpoint": "fal-ai/nano-banana-pro/edit",
        "supports_ref": True,
        "ref_required": True,
        "multi_ref": True,
        "default_steps": 28,
        "default_guidance": 3.5,
        "description": "基於參考圖的編輯模型，需上傳圖片",
    },
    "⚡ Flux Pro v1.1 Ultra": {
        "endpoint": "fal-ai/flux-pro/v1.1-ultra",
        "supports_ref": False,
        "default_steps": 25,
        "default_guidance": 4.0,
        "description": "高速高質量生成",
    },
    "🖼️ Imagen4 Preview": {
        "endpoint": "fal-ai/imagen4/preview",
        "supports_ref": False,
        "default_steps": 30,
        "default_guidance": 7.0,
        "description": "Google Imagen 4 預覽版",
    },
    "🎨 HiDream I1 Full": {
        "endpoint": "fal-ai/hidream-i1-full",
        "supports_ref": False,
        "default_steps": 30,
        "default_guidance": 5.0,
        "description": "高質量藝術風格",
    },
}

# ---------------------------------------------------------------------------
# Session State Helpers
# ---------------------------------------------------------------------------

def _init_state():
    defaults = {
        "images": [],           # list[GeneratedImage]
        "prompt": "",
        "optimized_prompt": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


_init_state()

# ---------------------------------------------------------------------------
# Utility: image encoding
# ---------------------------------------------------------------------------

def _file_to_base64_url(img_file) -> str:
    """Return a data-URI from an UploadedFile (resets seek position)."""
    img_file.seek(0)
    data = img_file.read()
    img_file.seek(0)  # reset so later reads still work
    b64 = base64.b64encode(data).decode()
    # Detect mime
    mime = "image/png"
    name = getattr(img_file, "name", "")
    if name.lower().endswith((".jpg", ".jpeg")):
        mime = "image/jpeg"
    elif name.lower().endswith(".webp"):
        mime = "image/webp"
    return f"data:{mime};base64,{b64}"


# ---------------------------------------------------------------------------
# MiniMax prompt tuning
# ---------------------------------------------------------------------------

def tune_prompt_with_minimax(prompt: str) -> dict[str, str]:
    """Return dict with keys: optimized, explanation, suggestions."""
    api_key = os.getenv("MINIMAX_API_KEY")
    if not api_key:
        raise EnvironmentError("MINIMAX_API_KEY environment variable is not set")

    url = "https://api.minimax.chat/v1/text/chatcompletion_v2"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    payload = {
        "model": "abab6.5-chat",
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a professional prompt engineer for AI image generation. "
                    "Improve the user's prompt to be vivid, specific, and effective. "
                    "Keep it concise (under 200 words)."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Improve this image generation prompt. "
                    "Return in this EXACT format (one item per line):\n"
                    "PROMPT: <optimized prompt>\n"
                    "EXPLANATION: <what you improved>\n"
                    "SUGGESTIONS: <optional extra tips>\n\n"
                    f"Original prompt: {prompt}"
                ),
            },
        ],
        "temperature": 0.7,
        "top_p": 0.95,
    }

    resp = requests.post(url, json=payload, headers=headers, timeout=30)
    resp.raise_for_status()
    body = resp.json()

    if body.get("base_resp", {}).get("status_code", 0) != 0:
        raise RuntimeError(f"MiniMax API error: {body['base_resp']}")

    text = body["choices"][0]["message"]["content"].strip()

    result = {"optimized": "", "explanation": "", "suggestions": ""}
    for line in text.splitlines():
        if line.upper().startswith("PROMPT:"):
            result["optimized"] = line.split(":", 1)[1].strip()
        elif line.upper().startswith("EXPLANATION:"):
            result["explanation"] = line.split(":", 1)[1].strip()
        elif line.upper().startswith("SUGGESTIONS:"):
            result["suggestions"] = line.split(":", 1)[1].strip()

    if not result["optimized"]:
        # Fallback: use entire response as the optimized prompt
        result["optimized"] = text

    return result


# ---------------------------------------------------------------------------
# fal image generation (async core)
# ---------------------------------------------------------------------------

async def _generate_async(
    prompt: str,
    model_endpoint: str,
    image_size: str,
    steps: int,
    guidance: float,
    num_images: int,
    safety: str,
    ref_files: list | None = None,
) -> dict:
    fal_key = os.getenv("FAL_KEY")
    if not fal_key:
        raise EnvironmentError("FAL_KEY environment variable is not set")
    os.environ["FAL_KEY"] = fal_key

    args: dict = {
        "prompt": prompt,
        "image_size": image_size,
        "num_inference_steps": steps,
        "guidance_scale": guidance,
        "num_images": num_images,
        "safety_tolerance": safety,
    }

    # Attach reference images when applicable
    if ref_files:
        if "nano-banana-pro/edit" in model_endpoint:
            args["image_urls"] = [_file_to_base64_url(f) for f in ref_files]
        else:
            args["image_url"] = _file_to_base64_url(ref_files[0])

    handler = await fal_client.submit_async(model_endpoint, arguments=args)
    return await handler.get()


def generate_images(
    prompt: str,
    model_endpoint: str,
    image_size: str,
    steps: int,
    guidance: float,
    num_images: int,
    safety: str,
    ref_files: list | None = None,
) -> dict:
    """Synchronous wrapper – runs the async generator in a worker thread."""

    def _run():
        return asyncio.run(
            _generate_async(
                prompt, model_endpoint, image_size, steps, guidance, num_images, safety, ref_files
            )
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(_run)
        return future.result()


# ---------------------------------------------------------------------------
# Download helpers
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner=False, ttl=600)
def fetch_image_bytes(url: str) -> bytes:
    """Download image bytes with caching (10 min TTL)."""
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    return resp.content


def build_zip(images: list[GeneratedImage]) -> bytes:
    buf = BytesIO()
    with ZipFile(buf, "w") as zf:
        for i, img in enumerate(images, 1):
            try:
                data = fetch_image_bytes(img.url)
                zf.writestr(f"image_{i}.png", data)
            except Exception as exc:
                logger.warning("Failed to fetch image %d: %s", i, exc)
    buf.seek(0)
    return buf.read()


# ---------------------------------------------------------------------------
# SIDEBAR
# ---------------------------------------------------------------------------

def render_sidebar() -> dict:
    """Render the sidebar and return a dict of all user settings."""
    with st.sidebar:
        st.markdown('<p class="main-title" style="font-size:1.6rem">🎨 設置</p>', unsafe_allow_html=True)

        # -- Model --
        st.markdown('<p class="sidebar-section">模型</p>', unsafe_allow_html=True)
        model_name = st.selectbox(
            "選擇模型",
            list(MODEL_REGISTRY.keys()),
            label_visibility="collapsed",
        )
        meta = MODEL_REGISTRY[model_name]
        st.caption(meta["description"])

        # -- Reference images --
        ref_files: list = []
        if meta.get("supports_ref") or st.checkbox("啟用參考圖上傳", value=False):
            st.markdown('<p class="sidebar-section">參考圖像</p>', unsafe_allow_html=True)
            ref_files = st.file_uploader(
                "上傳參考圖",
                type=["png", "jpg", "jpeg", "webp"],
                accept_multiple_files=True,
                label_visibility="collapsed",
            )
            if ref_files:
                thumb_cols = st.columns(min(3, len(ref_files)))
                for idx, f in enumerate(ref_files[:3]):
                    with thumb_cols[idx]:
                        try:
                            f.seek(0)
                            st.image(Image.open(f), width=75)
                            f.seek(0)
                        except Exception:
                            st.warning("⚠️")

        # -- Size --
        st.markdown('<p class="sidebar-section">畫布</p>', unsafe_allow_html=True)
        SIZE_MAP = {
            "方形 HD (1024×1024)": "square_hd",
            "方形 (512×512)": "square",
            "豎屏 4:3": "portrait_4_3",
            "豎屏 16:9": "portrait_16_9",
            "橫屏 4:3": "landscape_4_3",
            "橫屏 16:9": "landscape_16_9",
        }
        size_label = st.selectbox("圖片尺寸", list(SIZE_MAP.keys()), label_visibility="collapsed")
        image_size = SIZE_MAP[size_label]

        # -- Generation params --
        st.markdown('<p class="sidebar-section">生成參數</p>', unsafe_allow_html=True)
        steps = st.slider("推理步數", 1, 50, meta["default_steps"])
        num_images = st.slider("生成數量", 1, 4, 1)

        with st.expander("進階設置"):
            guidance = st.slider("引導強度 (CFG)", 1.0, 20.0, meta["default_guidance"], 0.5)
            safety = st.selectbox("安全等級", ["1", "2", "3", "4"], index=1)

        # -- Prompt tuning toggle --
        st.markdown('<p class="sidebar-section">AI 提示詞優化</p>', unsafe_allow_html=True)
        use_minimax = st.toggle("使用 MiniMax 優化", value=False)
        if use_minimax and not os.getenv("MINIMAX_API_KEY"):
            st.warning("⚠️ `MINIMAX_API_KEY` 未設置")

        # -- History management --
        st.divider()
        if st.button("🗑️ 清除所有歷史", use_container_width=True):
            st.session_state.images = []
            st.session_state.prompt = ""
            st.session_state.optimized_prompt = None
            st.toast("✅ 歷史已清除")
            st.rerun()

        # -- Quick prompt history --
        past_prompts = list({img.prompt for img in st.session_state.images})
        if past_prompts:
            st.markdown('<p class="sidebar-section">歷史提示詞</p>', unsafe_allow_html=True)
            chosen = st.selectbox(
                "快速選擇", [""] + past_prompts[-10:],
                label_visibility="collapsed",
            )
            if chosen:
                st.session_state.prompt = chosen
                st.rerun()

    return {
        "model_name": model_name,
        "model_endpoint": meta["endpoint"],
        "meta": meta,
        "ref_files": ref_files or [],
        "image_size": image_size,
        "steps": steps,
        "num_images": num_images,
        "guidance": guidance,
        "safety": safety,
        "use_minimax": use_minimax,
    }


# ---------------------------------------------------------------------------
# GALLERY
# ---------------------------------------------------------------------------

def render_gallery():
    images: list[GeneratedImage] = st.session_state.images
    if not images:
        return

    st.divider()
    st.subheader(f"🖼️ 圖庫  ({len(images)} 張)")

    view = st.radio("檢視模式", ["網格", "單張"], horizontal=True, label_visibility="collapsed")

    if view == "網格":
        cols_per_row = 3 if len(images) >= 3 else len(images)
        for row_start in range(0, len(images), cols_per_row):
            cols = st.columns(cols_per_row, gap="medium")
            for j, col in enumerate(cols):
                idx = row_start + j
                if idx >= len(images):
                    break
                img_meta = images[idx]
                with col:
                    with st.container(border=True):
                        try:
                            data = fetch_image_bytes(img_meta.url)
                            st.image(Image.open(BytesIO(data)), use_container_width=True)
                            st.caption(f"{img_meta.model} · {img_meta.timestamp}")
                            st.download_button(
                                f"📥 下載 #{idx + 1}",
                                data=data,
                                file_name=f"wuzhen_{idx + 1}_{img_meta.timestamp.replace(' ', '_').replace(':', '')}.png",
                                mime="image/png",
                                use_container_width=True,
                                key=f"dl_{idx}",
                            )
                            with st.expander("📝 提示詞"):
                                st.code(img_meta.prompt, language=None)
                        except Exception as exc:
                            st.error(f"加載失敗: {exc}")
    else:
        # Single-image view with navigation
        idx = st.number_input(
            "選擇圖片", min_value=1, max_value=len(images), value=len(images), step=1
        ) - 1
        img_meta = images[idx]
        try:
            data = fetch_image_bytes(img_meta.url)
            st.image(Image.open(BytesIO(data)), use_container_width=True)
            c1, c2, c3 = st.columns(3)
            c1.metric("模型", img_meta.model.split()[-1])
            c2.metric("種子", img_meta.seed or "N/A")
            c3.metric("時間", img_meta.timestamp.split()[1] if " " in img_meta.timestamp else img_meta.timestamp)
            st.download_button(
                "📥 下載此圖",
                data=data,
                file_name=f"wuzhen_{idx + 1}.png",
                mime="image/png",
                use_container_width=True,
                key="dl_single",
            )
            with st.expander("📝 完整提示詞"):
                st.code(img_meta.prompt, language=None)
        except Exception as exc:
            st.error(f"加載失敗: {exc}")

    # Batch download
    if len(images) > 1:
        st.divider()
        if st.button("📦 打包下載全部 (ZIP)", use_container_width=True):
            with st.spinner("正在打包…"):
                zip_data = build_zip(images)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            st.download_button(
                "✅ 點擊保存 ZIP",
                data=zip_data,
                file_name=f"wuzhen_all_{ts}.zip",
                mime="application/zip",
                use_container_width=True,
                key="dl_zip",
            )


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main():
    # Title
    st.markdown('<p class="main-title">🎨 吳振二號畫室</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="sub-title">Flux · Nano Banana Pro · Imagen4 · HiDream — powered by fal.ai</p>',
        unsafe_allow_html=True,
    )

    # API key gate
    if not os.getenv("FAL_KEY"):
        st.error("❌ 缺少 `FAL_KEY` 環境變量。請到 https://fal.ai 獲取 API Key。")
        st.stop()

    # Sidebar
    cfg = render_sidebar()

    # ---- Prompt area ----
    st.subheader("✍️ 提示詞")
    prompt = st.text_area(
        "描述你想要生成的圖像",
        value=st.session_state.prompt,
        height=130,
        placeholder="例如：一隻橘貓懶洋洋地躺在午後的窗台上，金色陽光灑落，水彩風格…",
        label_visibility="collapsed",
    )
    st.session_state.prompt = prompt

    # ---- MiniMax optimisation ----
    if cfg["use_minimax"]:
        if st.button("🔧 AI 優化提示詞", type="secondary"):
            if not prompt.strip():
                st.warning("請先輸入提示詞")
            else:
                with st.spinner("MiniMax 正在優化…"):
                    try:
                        result = tune_prompt_with_minimax(prompt)
                        st.session_state.prompt = result["optimized"]
                        st.session_state.optimized_prompt = result
                        st.toast("✅ 提示詞已優化！")
                        st.rerun()
                    except Exception as exc:
                        st.error(f"優化失敗：{exc}")

        if st.session_state.optimized_prompt:
            r = st.session_state.optimized_prompt
            with st.expander("🔍 優化詳情", expanded=False):
                st.success(f"**優化後：** {r['optimized']}")
                if r.get("explanation"):
                    st.info(f"**說明：** {r['explanation']}")
                if r.get("suggestions"):
                    st.caption(f"💡 {r['suggestions']}")

    st.divider()

    # ---- Generate button ----
    _, col_btn, _ = st.columns([1, 2, 1])
    with col_btn:
        go = st.button("🎨 開始生成", type="primary", use_container_width=True)

    if go:
        if not prompt.strip():
            st.warning("請輸入提示詞 ✏️")
            st.stop()

        meta = cfg["meta"]
        if meta.get("ref_required") and not cfg["ref_files"]:
            st.warning(f"⚠️ {cfg['model_name']} 需要至少一張參考圖片，請在左側上傳。")
            st.stop()

        # --- Run generation with a status widget ---
        status_messages = [
            "🎨 調配顏料…",
            "✨ 灑下靈感粉塵…",
            "🖌️ 揮灑筆觸…",
            "🌈 注入色彩…",
            "🔍 雕琢細節…",
            "🖼️ 裱框中…",
        ]

        with st.status("生成中…", expanded=True) as status:
            t0 = time.time()
            # Start generation in background
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(
                    generate_images,
                    prompt,
                    cfg["model_endpoint"],
                    cfg["image_size"],
                    cfg["steps"],
                    cfg["guidance"],
                    cfg["num_images"],
                    cfg["safety"],
                    cfg["ref_files"] if cfg["ref_files"] else None,
                )

                msg_idx = 0
                while not future.done():
                    st.write(status_messages[msg_idx % len(status_messages)])
                    msg_idx += 1
                    time.sleep(1.5)

                try:
                    result = future.result()
                except Exception as exc:
                    status.update(label="❌ 生成失敗", state="error")
                    st.error(f"錯誤：{exc}")
                    logger.exception("Generation failed")
                    st.stop()

            elapsed = time.time() - t0
            status.update(label=f"✅ 生成完成 ({elapsed:.1f}s)", state="complete")

        # Validate result
        if "images" not in result or not result["images"]:
            st.error("API 返回了空結果，請重試。")
            st.stop()

        # Store results
        seed = result.get("seed")
        nsfw = result.get("has_nsfw_concepts")
        for img_data in result["images"]:
            st.session_state.images.append(
                GeneratedImage(
                    url=img_data["url"],
                    prompt=prompt,
                    model=cfg["model_name"],
                    seed=seed,
                    nsfw=nsfw,
                )
            )

        st.toast(f"🎉 成功生成 {len(result['images'])} 張圖片！")
        st.balloons()

    # ---- Gallery ----
    render_gallery()

    # ---- Footer / Help ----
    st.divider()
    with st.expander("📖 使用說明"):
        st.markdown(
            """
### 🎯 模型一覽

| 模型 | 特點 | 需要參考圖 |
|------|------|:----------:|
| 🌟 Flux 2 Pro | 最高質量通用生成 | ❌ |
| 🍌 Nano Banana Pro Edit | 圖片編輯 / 風格遷移 | ✅ (多張) |
| ⚡ Flux Pro v1.1 Ultra | 高速高質量 | ❌ |
| 🖼️ Imagen4 Preview | Google 最新圖像模型 | ❌ |
| 🎨 HiDream I1 Full | 藝術風格 | ❌ |

### 📝 快速上手
1. 在左側 **選擇模型** 和參數
2. 如使用 Nano Banana Edit，**上傳參考圖**
3. 輸入描述文字（提示詞）
4. 可選：開啟 **MiniMax 優化** 讓 AI 潤色提示詞
5. 點擊 **開始生成**
6. 在圖庫中 **預覽 / 下載**

### ⚙️ 環境變量
| 變量 | 用途 |
|------|------|
| `FAL_KEY` | fal.ai API 密鑰 (必需) |
| `MINIMAX_API_KEY` | MiniMax 提示詞優化 (可選) |
"""
        )


if __name__ == "__main__":
    main()
