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
    page_title="吳振畫室",
    page_icon="🎨",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Custom CSS – polished dark-mode-aware design
# ---------------------------------------------------------------------------
st.markdown(
    """
<style>
/* ---- Google Fonts ---- */
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;700;900&display=swap');

/* ---- Root variables ---- */
:root {
    --accent-1: #667eea;
    --accent-2: #764ba2;
    --accent-3: #f093fb;
    --card-radius: 16px;
    --transition: 0.25s ease;
}

/* ---- Page background gradient ---- */
section[data-testid="stAppViewContainer"] > .main {
    background: linear-gradient(160deg, #0f0c29 0%, #302b63 50%, #24243e 100%);
    min-height: 100vh;
}

/* ---- Sidebar ---- */
section[data-testid="stSidebar"] {
    background: rgba(255,255,255,0.04);
    backdrop-filter: blur(12px);
    border-right: 1px solid rgba(255,255,255,0.08);
}
section[data-testid="stSidebar"] * {
    color: rgba(255,255,255,0.88) !important;
}

/* ---- Title ---- */
.main-title {
    font-family: 'Noto Sans TC', sans-serif;
    font-size: clamp(1.8rem, 4vw, 3.2rem);
    font-weight: 900;
    text-align: center;
    background: linear-gradient(135deg, #f093fb 0%, #667eea 50%, #4facfe 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    margin-bottom: 0.3rem;
    letter-spacing: 0.08em;
    line-height: 1.2;
    text-shadow: none;
}
.sub-title {
    text-align: center;
    color: rgba(255,255,255,0.5) !important;
    font-size: 0.9rem;
    margin-bottom: 1.8rem;
    letter-spacing: 0.05em;
}

/* ---- Model badge ---- */
.model-badge {
    display: inline-block;
    background: linear-gradient(135deg, var(--accent-1), var(--accent-2));
    color: white !important;
    padding: 2px 10px;
    border-radius: 20px;
    font-size: 0.78rem;
    font-weight: 700;
    letter-spacing: 0.04em;
    margin-bottom: 4px;
}

/* ---- Feature tag ---- */
.feature-tag {
    display: inline-block;
    background: rgba(102,126,234,0.18);
    border: 1px solid rgba(102,126,234,0.4);
    color: #a5b4fc !important;
    padding: 1px 8px;
    border-radius: 12px;
    font-size: 0.72rem;
    margin: 2px;
}

/* ---- Image cards ---- */
.img-card {
    border-radius: var(--card-radius);
    overflow: hidden;
    transition: box-shadow var(--transition), transform var(--transition);
    background: rgba(255,255,255,0.05);
    border: 1px solid rgba(255,255,255,0.08);
}
.img-card:hover {
    box-shadow: 0 8px 32px rgba(102,126,234,0.45);
    transform: translateY(-2px);
}

/* ---- Primary button ---- */
div.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    border: none;
    border-radius: 12px;
    font-weight: 700;
    font-size: 1.05rem;
    letter-spacing: 0.04em;
    color: white !important;
    box-shadow: 0 4px 15px rgba(102,126,234,0.4);
    transition: all var(--transition);
    padding: 0.6rem 2rem;
}
div.stButton > button[kind="primary"]:hover {
    box-shadow: 0 6px 20px rgba(102,126,234,0.6);
    transform: translateY(-1px);
}

/* ---- Secondary button ---- */
div.stButton > button:not([kind="primary"]) {
    border-radius: 10px;
    font-weight: 600;
    border: 1px solid rgba(102,126,234,0.4);
    background: rgba(102,126,234,0.08);
    color: #a5b4fc !important;
    transition: all var(--transition);
}
div.stButton > button:not([kind="primary"]):hover {
    background: rgba(102,126,234,0.18);
    border-color: rgba(102,126,234,0.7);
}

/* ---- Text area ---- */
textarea {
    border-radius: 12px !important;
    border: 1px solid rgba(102,126,234,0.3) !important;
    background: rgba(255,255,255,0.04) !important;
    color: rgba(255,255,255,0.9) !important;
    font-size: 0.95rem !important;
    transition: border-color var(--transition), box-shadow var(--transition);
}
textarea:focus {
    border-color: var(--accent-1) !important;
    box-shadow: 0 0 0 3px rgba(102,126,234,0.2) !important;
}

/* ---- Selectbox ---- */
div[data-baseweb="select"] > div {
    border-radius: 10px !important;
    border: 1px solid rgba(102,126,234,0.3) !important;
    background: rgba(255,255,255,0.04) !important;
}

/* ---- Slider ---- */
div[data-testid="stSlider"] .stSlider > div > div > div {
    background: linear-gradient(90deg, var(--accent-1), var(--accent-2)) !important;
}

/* ---- Sidebar section headers ---- */
.sidebar-section {
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    color: rgba(165,180,252,0.7) !important;
    margin-top: 1.2rem;
    margin-bottom: 0.3rem;
    font-weight: 700;
}

/* ---- Divider ---- */
hr {
    border-color: rgba(255,255,255,0.08) !important;
    margin: 1.2rem 0 !important;
}

/* ---- Status box ---- */
div[data-testid="stStatusWidget"] {
    border-radius: 12px !important;
    background: rgba(102,126,234,0.1) !important;
    border: 1px solid rgba(102,126,234,0.25) !important;
}

/* ---- Gallery title ---- */
.gallery-title {
    font-size: 1.3rem;
    font-weight: 800;
    background: linear-gradient(135deg, #f093fb, #667eea);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    margin-bottom: 0.5rem;
}

/* ---- Metric cards ---- */
div[data-testid="stMetric"] {
    background: rgba(102,126,234,0.1);
    border: 1px solid rgba(102,126,234,0.2);
    border-radius: 10px;
    padding: 0.5rem 1rem;
}

/* ---- Expander ---- */
details summary {
    font-weight: 600;
    color: #a5b4fc !important;
}

/* ---- Nano Banana 2 special section ---- */
.nb2-info {
    background: linear-gradient(135deg, rgba(240,147,251,0.12) 0%, rgba(102,126,234,0.12) 100%);
    border: 1px solid rgba(240,147,251,0.25);
    border-radius: 12px;
    padding: 0.7rem 1rem;
    margin: 0.5rem 0;
    font-size: 0.85rem;
    color: rgba(255,255,255,0.8) !important;
}

/* ---- Toggle ---- */
div[data-testid="stToggle"] span {
    color: rgba(255,255,255,0.85) !important;
}

/* ---- Caption ---- */
div[data-testid="stCaptionContainer"] {
    color: rgba(255,255,255,0.5) !important;
    font-size: 0.78rem !important;
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
        "api_style": "flux",
    },
    "🍌 Nano Banana 2 Edit": {
        "endpoint": "fal-ai/nano-banana-2/edit",
        "supports_ref": True,
        "ref_required": True,
        "multi_ref": True,
        "max_refs": 14,
        "default_steps": 28,
        "default_guidance": 3.5,
        "description": "Gemini 3.1 Flash 圖像編輯，最多14張參考圖，支持Google搜索增強",
        "api_style": "nano_banana_2",
        "supports_web_search": True,
    },
    "🍌 Nano Banana Pro Edit": {
        "endpoint": "fal-ai/nano-banana-pro/edit",
        "supports_ref": True,
        "ref_required": True,
        "multi_ref": True,
        "max_refs": 8,
        "default_steps": 28,
        "default_guidance": 3.5,
        "description": "基於參考圖的編輯模型，需上傳圖片",
        "api_style": "flux",
    },
    "⚡ Flux Pro v1.1 Ultra": {
        "endpoint": "fal-ai/flux-pro/v1.1-ultra",
        "supports_ref": False,
        "default_steps": 25,
        "default_guidance": 4.0,
        "description": "高速高質量生成",
        "api_style": "flux",
    },
    "🖼️ Imagen4 Preview": {
        "endpoint": "fal-ai/imagen4/preview",
        "supports_ref": False,
        "default_steps": 30,
        "default_guidance": 7.0,
        "description": "Google Imagen 4 預覽版",
        "api_style": "flux",
    },
    "🎨 HiDream I1 Full": {
        "endpoint": "fal-ai/hidream-i1-full",
        "supports_ref": False,
        "default_steps": 30,
        "default_guidance": 5.0,
        "description": "高質量藝術風格",
        "api_style": "flux",
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
    img_file.seek(0)
    b64 = base64.b64encode(data).decode()
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
        result["optimized"] = text

    return result


# ---------------------------------------------------------------------------
# fal image generation (async core)
# ---------------------------------------------------------------------------

async def _generate_async(
    prompt: str,
    model_endpoint: str,
    api_style: str,
    image_size: str,
    steps: int,
    guidance: float,
    num_images: int,
    safety: str,
    ref_files: list | None = None,
    # Nano Banana 2 specific
    nb2_resolution: str = "1K",
    nb2_aspect_ratio: str = "auto",
    nb2_output_format: str = "png",
    nb2_enable_web_search: bool = False,
) -> dict:
    fal_key = os.getenv("FAL_KEY")
    if not fal_key:
        raise EnvironmentError("FAL_KEY environment variable is not set")
    os.environ["FAL_KEY"] = fal_key

    if api_style == "nano_banana_2":
        # Nano Banana 2 / edit uses a different parameter schema
        args: dict = {
            "prompt": prompt,
            "num_images": num_images,
            "resolution": nb2_resolution,
            "aspect_ratio": nb2_aspect_ratio,
            "output_format": nb2_output_format,
        }
        if nb2_enable_web_search:
            args["enable_google_search"] = True
        if ref_files:
            args["image_urls"] = [_file_to_base64_url(f) for f in ref_files]
    else:
        # Standard Flux / other models
        args = {
            "prompt": prompt,
            "image_size": image_size,
            "num_inference_steps": steps,
            "guidance_scale": guidance,
            "num_images": num_images,
            "safety_tolerance": safety,
        }
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
    api_style: str,
    image_size: str,
    steps: int,
    guidance: float,
    num_images: int,
    safety: str,
    ref_files: list | None = None,
    nb2_resolution: str = "1K",
    nb2_aspect_ratio: str = "auto",
    nb2_output_format: str = "png",
    nb2_enable_web_search: bool = False,
) -> dict:
    """Synchronous wrapper – runs the async generator in a worker thread."""

    def _run():
        return asyncio.run(
            _generate_async(
                prompt, model_endpoint, api_style, image_size, steps, guidance,
                num_images, safety, ref_files,
                nb2_resolution, nb2_aspect_ratio, nb2_output_format, nb2_enable_web_search,
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
        st.markdown(
            '<p class="main-title" style="font-size:1.5rem;margin-bottom:0.5rem">🎨 設置面板</p>',
            unsafe_allow_html=True,
        )

        # -- Model --
        st.markdown('<p class="sidebar-section">🤖 選擇模型</p>', unsafe_allow_html=True)
        model_name = st.selectbox(
            "選擇模型",
            list(MODEL_REGISTRY.keys()),
            label_visibility="collapsed",
        )
        meta = MODEL_REGISTRY[model_name]
        is_nb2 = meta.get("api_style") == "nano_banana_2"

        # Model info card
        desc_html = f'<div class="nb2-info">📋 {meta["description"]}'
        if is_nb2:
            desc_html += '<br><span class="feature-tag">🔍 Google搜索</span><span class="feature-tag">📸 最多14張參考圖</span><span class="feature-tag">🆕 Gemini 3.1 Flash</span>'
        desc_html += "</div>"
        st.markdown(desc_html, unsafe_allow_html=True)

        # -- Reference images --
        ref_files: list = []
        max_refs = meta.get("max_refs", 4)
        if meta.get("supports_ref") or st.checkbox("啟用參考圖上傳", value=False):
            st.markdown('<p class="sidebar-section">🖼️ 參考圖像</p>', unsafe_allow_html=True)
            if is_nb2:
                st.caption(f"支持最多 {max_refs} 張參考圖")
            ref_files = st.file_uploader(
                "上傳參考圖",
                type=["png", "jpg", "jpeg", "webp"],
                accept_multiple_files=True,
                label_visibility="collapsed",
            )
            if ref_files:
                # Enforce max limit
                if len(ref_files) > max_refs:
                    st.warning(f"⚠️ 最多支持 {max_refs} 張，已取前 {max_refs} 張")
                    ref_files = ref_files[:max_refs]
                thumb_cols = st.columns(min(3, len(ref_files)))
                for idx, f in enumerate(ref_files[:3]):
                    with thumb_cols[idx]:
                        try:
                            f.seek(0)
                            st.image(Image.open(f), width=72)
                            f.seek(0)
                        except Exception:
                            st.warning("⚠️")
                if len(ref_files) > 3:
                    st.caption(f"+ {len(ref_files) - 3} 張更多")

        # -- Nano Banana 2 specific controls --
        nb2_resolution = "1K"
        nb2_aspect_ratio = "auto"
        nb2_output_format = "png"
        nb2_enable_web_search = False

        if is_nb2:
            st.markdown('<p class="sidebar-section">📐 輸出設置</p>', unsafe_allow_html=True)
            nb2_resolution = st.select_slider(
                "解析度",
                options=["0.5K", "1K", "2K", "4K"],
                value="1K",
            )
            nb2_aspect_ratio = st.selectbox(
                "寬高比",
                ["auto", "1:1", "16:9", "9:16", "4:3", "3:4", "3:2", "2:3", "5:4", "4:5", "21:9"],
                label_visibility="visible",
            )
            nb2_output_format = st.radio(
                "輸出格式",
                ["png", "jpeg", "webp"],
                horizontal=True,
            )
            if meta.get("supports_web_search"):
                st.markdown('<p class="sidebar-section">🔍 搜索增強</p>', unsafe_allow_html=True)
                nb2_enable_web_search = st.toggle(
                    "啟用 Google 搜索增強",
                    value=False,
                    help="讓模型實時檢索網絡信息（每次請求額外 $0.015）",
                )

        # -- Size (for non-NB2 models) --
        image_size = "square_hd"
        if not is_nb2:
            st.markdown('<p class="sidebar-section">📐 畫布尺寸</p>', unsafe_allow_html=True)
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
        st.markdown('<p class="sidebar-section">⚙️ 生成參數</p>', unsafe_allow_html=True)
        if not is_nb2:
            steps = st.slider("推理步數", 1, 50, meta["default_steps"])
        else:
            steps = meta["default_steps"]  # Not used for NB2 but kept for API compat
        num_images = st.slider("生成數量", 1, 4, 1)

        guidance = meta["default_guidance"]
        safety = "2"
        if not is_nb2:
            with st.expander("進階設置"):
                guidance = st.slider("引導強度 (CFG)", 1.0, 20.0, meta["default_guidance"], 0.5)
                safety = st.selectbox("安全等級", ["1", "2", "3", "4"], index=1)

        # -- Prompt tuning toggle --
        st.markdown('<p class="sidebar-section">✨ AI 提示詞優化</p>', unsafe_allow_html=True)
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
            st.markdown('<p class="sidebar-section">📜 歷史提示詞</p>', unsafe_allow_html=True)
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
        "api_style": meta.get("api_style", "flux"),
        "meta": meta,
        "is_nb2": is_nb2,
        "ref_files": ref_files or [],
        "image_size": image_size,
        "steps": steps,
        "num_images": num_images,
        "guidance": guidance,
        "safety": safety,
        "use_minimax": use_minimax,
        "nb2_resolution": nb2_resolution,
        "nb2_aspect_ratio": nb2_aspect_ratio,
        "nb2_output_format": nb2_output_format,
        "nb2_enable_web_search": nb2_enable_web_search,
    }


# ---------------------------------------------------------------------------
# GALLERY
# ---------------------------------------------------------------------------

def render_gallery():
    images: list[GeneratedImage] = st.session_state.images
    if not images:
        return

    st.divider()
    st.markdown(
        f'<p class="gallery-title">🖼️ 圖庫  <span style="font-size:1rem;opacity:0.7">({len(images)} 張)</span></p>',
        unsafe_allow_html=True,
    )

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
    st.markdown(
        '<p class="main-title">🎨 吳振畫室（二號）</p>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<p class="sub-title">Flux 2 Pro · Nano Banana 2 · Nano Banana Pro · Imagen4 · HiDream — powered by fal.ai &nbsp;|&nbsp; 振視科技 tot@alexzhenwu.com</p>',
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
    # Show NB2 hint
    if cfg["is_nb2"]:
        st.markdown(
            '<div class="nb2-info">💡 <b>Nano Banana 2</b>：用自然語言描述你的編輯意圖，例如「把背景換成夜晚的城市」或「改成水彩畫風格」</div>',
            unsafe_allow_html=True,
        )

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

    # Show NB2 config summary
    if cfg["is_nb2"]:
        cols = st.columns(4)
        cols[0].metric("解析度", cfg["nb2_resolution"])
        cols[1].metric("寬高比", cfg["nb2_aspect_ratio"])
        cols[2].metric("格式", cfg["nb2_output_format"].upper())
        cols[3].metric("Google搜索", "開" if cfg["nb2_enable_web_search"] else "關")

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

        status_messages = [
            "🎨 調配顏料…",
            "✨ 灑下靈感粉塵…",
            "🖌️ 揮灑筆觸…",
            "🌈 注入色彩…",
            "🔍 雕琢細節…",
            "🖼️ 裱框中…",
        ]
        if cfg["is_nb2"]:
            status_messages = [
                "🧠 Gemini 理解圖像內容…",
                "✨ 分析編輯意圖…",
                "🎨 智能融合元素…",
                "🔍 細節精修…",
                "🖼️ 渲染輸出…",
                "✅ 即將完成…",
            ]

        with st.status("生成中…", expanded=True) as status:
            t0 = time.time()
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(
                    generate_images,
                    prompt,
                    cfg["model_endpoint"],
                    cfg["api_style"],
                    cfg["image_size"],
                    cfg["steps"],
                    cfg["guidance"],
                    cfg["num_images"],
                    cfg["safety"],
                    cfg["ref_files"] if cfg["ref_files"] else None,
                    cfg["nb2_resolution"],
                    cfg["nb2_aspect_ratio"],
                    cfg["nb2_output_format"],
                    cfg["nb2_enable_web_search"],
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

        if "images" not in result or not result["images"]:
            st.error("API 返回了空結果，請重試。")
            st.stop()

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

| 模型 | 特點 | 需要參考圖 | 費用/張 |
|------|------|:----------:|:-------:|
| 🌟 Flux 2 Pro | 最高質量通用生成 | ❌ | — |
| 🍌 Nano Banana 2 Edit | Gemini 3.1 Flash 圖像編輯，最多14張參考圖 | ✅ (最多14張) | ~$0.08 |
| 🍌 Nano Banana Pro Edit | 圖片編輯 / 風格遷移 | ✅ (多張) | — |
| ⚡ Flux Pro v1.1 Ultra | 高速高質量 | ❌ | — |
| 🖼️ Imagen4 Preview | Google 最新圖像模型 | ❌ | — |
| 🎨 HiDream I1 Full | 藝術風格 | ❌ | — |

### 🍌 Nano Banana 2 特色功能
- **多圖參考**：最多上傳 14 張參考圖，進行風格遷移、場景合成
- **自然語言編輯**：直接描述「把背景換成海邊」「改成油畫風格」
- **Google 搜索增強**：讓模型實時查詢網絡信息，獲得更準確結果
- **靈活輸出**：支持 0.5K/1K/2K/4K 解析度及多種寬高比

### 📝 快速上手
1. 在左側 **選擇模型** 和參數
2. 如使用 Nano Banana 模型，**上傳參考圖**
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
