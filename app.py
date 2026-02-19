import streamlit as st
import requests
import fal_client
import asyncio
import os
import itertools
import base64
from PIL import Image
from io import BytesIO
from datetime import datetime
from zipfile import ZipFile

# =========================
# Page Config & Custom CSS
# =========================
st.set_page_config(
    page_title="吳振畫室",
    page_icon="🎨",
    layout="wide"
)

st.markdown("""
<style>
    .main-title {
        font-size: 3rem;
        font-weight: bold;
        text-align: center;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 2rem;
    }
    .sub-title {
        text-align: center;
        color: #888;
        margin-bottom: 2rem;
    }
    .model-card {
        background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
        border-radius: 15px;
        padding: 1rem;
        margin: 0.5rem 0;
    }
    .image-result-card {
        border: 2px solid #667eea;
        border-radius: 15px;
        padding: 1rem;
        margin: 1rem 0;
        background: #fafafa;
    }
    .stButton>button {
        border-radius: 10px;
        font-weight: bold;
    }
    .download-btn {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
    }
</style>
""", unsafe_allow_html=True)

st.markdown('<p class="main-title">🎨 吳振二號畫室</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">Flux + Nano Banana Pro + MiniMax</p>', unsafe_allow_html=True)

# =========================
# Session State Initialization
# =========================
if 'generated_images' not in st.session_state:
    st.session_state.generated_images = []
if 'generated_prompts' not in st.session_state:
    st.session_state.generated_prompts = []
if 'prompt' not in st.session_state:
    st.session_state.prompt = ""

# =========================
# MiniMax Prompt Tuning
# =========================
def tune_prompt_with_minimax(prompt):
    minimax_api_key = os.getenv("MINIMAX_API_KEY")
    if not minimax_api_key:
        raise ValueError("MINIMAX_API_KEY environment variable is not set")
    
    url = "https://api.minimax.chat/v1/text/chatcompletion_v2"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {minimax_api_key}"
    }
    payload = {
        "model": "abab6.5-chat",
        "messages": [
            {
                "role": "system",
                "content": "You are a professional prompt engineer. Improve the user's image prompt for AI image generation. Keep the improved prompt concise and descriptive."
            },
            {
                "role": "user",
                "content": f"""Improve this image generation prompt. Return in this format exactly:
PROMPT: <optimized prompt>
EXPLANATION: <what you improved>
SUGGESTIONS: <optional suggestions>

Original prompt: {prompt}
"""
            }
        ],
        "temperature": 0.7,
        "top_p": 0.95
    }
    
    response = requests.post(url, json=payload, headers=headers)
    if response.status_code != 200:
        raise ValueError(f"MiniMax HTTP Error {response.status_code}: {response.text}")
    
    result = response.json()
    if "base_resp" in result and result["base_resp"].get("status_code") != 0:
        raise ValueError(f"MiniMax API Error: {result['base_resp']}")
    
    if "choices" not in result or not result["choices"]:
        raise ValueError(f"Unexpected MiniMax response: {result}")
    
    return result["choices"][0]["message"]["content"].strip()


# =========================
# Image to Base64
# =========================
def image_to_base64_url(img_file):
    """Convert uploaded image to base64 data URL"""
    img_file.seek(0)
    img_data = img_file.read()
    b64 = base64.b64encode(img_data).decode()
    return f"data:image/png;base64,{b64}"


def image_to_fal_url(img_file):
    """Upload image and return fal-compatible URL or base64"""
    # fal accepts base64 data URLs directly
    return image_to_base64_url(img_file)


# =========================
# fal Image Generation
# =========================
async def generate_image_with_fal(
    prompt, 
    model, 
    image_size, 
    num_inference_steps, 
    guidance_scale, 
    num_images, 
    safety_tolerance,
    reference_images=None
):
    fal_api_key = os.getenv("FAL_KEY")
    if not fal_api_key:
        raise ValueError("FAL_KEY environment variable is not set")
    
    os.environ["FAL_KEY"] = fal_api_key
    
    arguments = {
        "prompt": prompt,
        "image_size": image_size,
        "num_inference_steps": num_inference_steps,
        "guidance_scale": guidance_scale,
        "num_images": num_images,
        "safety_tolerance": safety_tolerance
    }
    
    # Add reference images for editing models
    if reference_images and len(reference_images) > 0:
        if "nano-banana-pro/edit" in model:
            # Nano Banana Pro Edit - accepts image_url parameter
            arguments["image_url"] = image_to_fal_url(reference_images[0])
            if len(reference_images) > 1:
                # For multiple images, some models support image_urls array
                arguments["image_urls"] = [image_to_fal_url(img) for img in reference_images]
        elif "flux" in model.lower():
            # Flux models may support image-to-image
            arguments["image_url"] = image_to_fal_url(reference_images[0])
        else:
            # Default: add first image
            arguments["image_url"] = image_to_fal_url(reference_images[0])
    
    handler = await fal_client.submit_async(model, arguments=arguments)
    result = await handler.get()
    return result


# =========================
# Spinner Messages
# =========================
def cycle_spinner_messages():
    messages = [
        "🎨 Mixing colors...",
        "✨ Sprinkling creativity dust...",
        "🖌️ Applying artistic strokes...",
        "🌈 Infusing vibrant hues...",
        "🔍 Refining details...",
        "🖼️ Framing the masterpiece...",
        "🎭 Adding artistic flair...",
        "🌟 Bringing vision to life...",
    ]
    return itertools.cycle(messages)


async def run_with_spinner(coroutine, placeholder, cycle):
    task = asyncio.create_task(coroutine)
    while not task.done():
        placeholder.text(next(cycle))
        await asyncio.sleep(2)
    return await task


# =========================
# Download Functions
# =========================
def get_image_bytes(url):
    """Download image and return bytes"""
    response = requests.get(url, timeout=60)
    response.raise_for_status()
    return response.content


def create_download_button(image_bytes, filename, label="📥 下载图片"):
    """Create a download button for an image"""
    st.download_button(
        label=label,
        data=image_bytes,
        file_name=filename,
        mime="image/png",
        use_container_width=True
    )


# =========================
# Main App Layout
# =========================
def main():
    # Check API keys
    if not os.getenv("FAL_KEY"):
        st.error("❌ FAL_KEY not set. Please set the FAL_KEY environment variable.")
        st.info("Get your API key at: https://fal.ai/")
        return
    
    # =========================
    # Sidebar - Settings
    # =========================
    with st.sidebar:
        st.header("⚙️ 模型設置")
        
        # Model selection
        model_options = {
            "🌟 Flux 2 Pro": "fal-ai/flux-2-pro",
            "🍌 Nano Banana Pro Edit": "fal-ai/nano-banana-pro/edit",
            "⚡ Flux Pro v1.1 Ultra": "fal-ai/flux-pro/v1.1-ultra",
            "🖼️ Imagen4 Preview": "fal-ai/imagen4/preview",
            "🎨 HiDream I1 Full": "fal-ai/hidream-i1-full",
        }
        
        selected_model_display = st.selectbox(
            "選擇模型",
            list(model_options.keys())
        )
        selected_model = model_options[selected_model_display]
        
        # Model info
        if "nano-banana" in selected_model:
            st.info("🍌 Nano Banana 支持圖片編輯，請上傳參考圖")
        elif "flux" in selected_model:
            st.info("🌟 Flux 高質量生成")
        
        st.divider()
        
        # =========================
        # Reference Images Upload
        # =========================
        st.header("📷 參考圖像")
        
        ref_images = None
        if "nano-banana-pro/edit" in selected_model or st.checkbox("啟用參考圖上傳"):
            ref_images = st.file_uploader(
                "上傳參考圖（支持多張）",
                type=["png", "jpg", "jpeg", "webp"],
                accept_multiple_files=True,
                help="上傳一張或多張參考圖片"
            )
            
            if ref_images:
                st.write(f"已選擇 {len(ref_images)} 張圖片")
                # Display thumbnails
                cols = st.columns(min(3, len(ref_images)))
                for idx, ref_file in enumerate(ref_images[:3]):
                    with cols[idx % 3]:
                        try:
                            img = Image.open(ref_file)
                            st.image(img, width=80)
                        except Exception as e:
                            st.error(f"加載失敗: {e}")
        
        st.divider()
        
        # =========================
        # Generation Settings
        # =========================
        st.header("🎛️ 生成設置")
        
        image_size_options = {
            "方形 HD (1024×1024)": "square_hd",
            "方形 (1024×1024)": "square",
            "豎屏 4:3 (896×1152)": "portrait_4_3",
            "豎屏 16:9 (768×1024)": "portrait_16_9",
            "橫屏 4:3 (1152×896)": "landscape_4_3",
            "橫屏 16:9 (1024×768)": "landscape_16_9",
        }
        
        image_size_display = st.selectbox(
            "圖片尺寸",
            list(image_size_options.keys())
        )
        image_size = image_size_options[image_size_display]
        
        steps = st.slider("推理步數", 1, 50, 28)
        num_images = st.slider("生成數量", 1, 4, 1)
        
        with st.expander("進階設置"):
            guidance = st.slider("引導強度", 1.0, 20.0, 3.5, 0.1)
            safety = st.selectbox("安全等級", ["1", "2", "3", "4"], index=1)
        
        st.divider()
        
        # =========================
        # MiniMax Prompt Tuning
        # =========================
        st.header("🤖 提示詞優化")
        
        use_minimax = st.checkbox("使用 MiniMax 優化提示詞")
        
        if use_minimax:
            if not os.getenv("MINIMAX_API_KEY"):
                st.warning("MINIMAX_API_KEY 未設置")
        
        # Clear history
        st.divider()
        if st.button("🗑️ 清除歷史記錄"):
            st.session_state.generated_images = []
            st.session_state.generated_prompts = []
            st.success("✅ 已清除")
    
    # =========================
    # Main Content Area
    # =========================
    
    # Prompt input
    st.subheader("✍️ 輸入提示詞")
    prompt = st.text_area(
        "描述你想要生成的圖像",
        value=st.session_state.prompt,
        height=120,
        placeholder="例如: 一只可愛的橘貓坐在窗台上，陽光透過窗戶灑在它身上，溫馨的家庭氛圍..."
    )
    st.session_state.prompt = prompt
    
    # MiniMax tuning
    if use_minimax and st.button("🔧 優化提示詞", type="secondary"):
        if not prompt:
            st.warning("請先輸入提示詞")
        else:
            with st.spinner("正在優化提示詞..."):
                try:
                    tuned = tune_prompt_with_minimax(prompt)
                    optimized = ""
                    explanation = ""
                    suggestions = ""
                    
                    for line in tuned.splitlines():
                        if line.startswith("PROMPT:"):
                            optimized = line.replace("PROMPT:", "").strip()
                        elif line.startswith("EXPLANATION:"):
                            explanation = line.replace("EXPLANATION:", "").strip()
                        elif line.startswith("SUGGESTIONS:"):
                            suggestions = line.replace("SUGGESTIONS:", "").strip()
                    
                    if optimized:
                        st.session_state.prompt = optimized
                        st.success("✅ 提示詞已優化")
                        st.info(f"**優化後**: {optimized}")
                        if explanation:
                            st.caption(f"說明: {explanation}")
                        st.rerun()
                except Exception as e:
                    st.error(f"優化失敗: {e}")
    
    st.divider()
    
    # =========================
    # Generate Button
    # =========================
    col_gen1, col_gen2, col_gen3 = st.columns([1, 2, 1])
    with col_gen2:
        generate_btn = st.button("🎨 生成圖像", type="primary", use_container_width=True)
    
    if generate_btn:
        if not prompt:
            st.warning("請輸入提示詞")
        elif "nano-banana-pro/edit" in selected_model and not ref_images:
            st.warning("Nano Banana Pro Edit 需要上傳參考圖片")
        else:
            try:
                spinner = st.empty()
                cycle = cycle_spinner_messages()
                
                async def task():
                    return await generate_image_with_fal(
                        prompt,
                        selected_model,
                        image_size,
                        steps,
                        guidance,
                        num_images,
                        safety,
                        ref_images
                    )
                
                result = asyncio.run(run_with_spinner(task(), spinner, cycle))
                spinner.empty()
                
                if "images" not in result or not result["images"]:
                    raise ValueError(f"Invalid fal response: {result}")
                
                # Save to session state
                for img_data in result["images"]:
                    st.session_state.generated_images.append(img_data["url"])
                    st.session_state.generated_prompts.append(prompt)
                
                st.success(f"✅ 成功生成 {len(result['images'])} 張圖片")
                
                # Display seed and info
                col_info1, col_info2 = st.columns(2)
                with col_info1:
                    st.caption(f"種子: {result.get('seed', 'N/A')}")
                with col_info2:
                    st.caption(f"NSFW: {result.get('has_nsfw_concepts', 'N/A')}")
                
            except Exception as e:
                st.error(f"生成錯誤: {e}")
    
    # =========================
    # Display Generated Images
    # =========================
    if st.session_state.generated_images:
        st.divider()
        st.header("🖼️ 生成的圖像")
        st.caption(f"共 {len(st.session_state.generated_images)} 張")
        
        # Display in grid
        cols_per_row = 2
        for i in range(0, len(st.session_state.generated_images), cols_per_row):
            cols = st.columns(cols_per_row)
            for j, col in enumerate(cols):
                idx = i + j
                if idx < len(st.session_state.generated_images):
                    img_url = st.session_state.generated_images[idx]
                    img_prompt = st.session_state.generated_prompts[idx] if idx < len(st.session_state.generated_prompts) else ""
                    
                    with col:
                        with st.container(border=True):
                            try:
                                # Get image bytes
                                img_bytes = get_image_bytes(img_url)
                                img = Image.open(BytesIO(img_bytes))
                                st.image(img, use_column_width=True)
                                
                                # Download button
                                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                                create_download_button(
                                    img_bytes,
                                    f"ai_image_{idx + 1}_{timestamp}.png",
                                    f"📥 下載圖片 {idx + 1}"
                                )
                                
                                # Show prompt
                                with st.expander("📝 提示詞"):
                                    st.caption(img_prompt)
                            
                            except Exception as e:
                                st.error(f"加載失敗: {e}")
        
        # Batch download
        if len(st.session_state.generated_images) > 1:
            st.divider()
            st.subheader("📦 批量下載")
            
            if st.button("📥 下載所有圖片 (ZIP)"):
                with st.spinner("正在打包..."):
                    zip_buffer = BytesIO()
                    with ZipFile(zip_buffer, 'w') as zip_file:
                        for idx, img_url in enumerate(st.session_state.generated_images):
                            try:
                                img_bytes = get_image_bytes(img_url)
                                zip_file.writestr(f"ai_image_{idx + 1}.png", img_bytes)
                            except Exception as e:
                                st.warning(f"圖片 {idx + 1} 下載失敗: {e}")
                    
                    zip_buffer.seek(0)
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    st.download_button(
                        label="✅ 點擊下載 ZIP",
                        data=zip_buffer,
                        file_name=f"ai_images_{timestamp}.zip",
                        mime="application/zip",
                        use_container_width=True
                    )
    
    # =========================
    # Footer
    # =========================
    st.divider()
    with st.expander("📖 使用說明"):
        st.markdown("""
        ### 🎯 功能介紹
        
        | 模型 | 特點 | 參考圖 |
        |------|------|--------|
        | 🌟 Flux 2 Pro | 最高質量生成 | ❌ |
        | 🍌 Nano Banana Pro Edit | 圖片編輯 | ✅ 支持多張 |
        | ⚡ Flux Pro v1.1 Ultra | 高速高質量 | ❌ |
        | 🖼️ Imagen4 | Google 圖像模型 | ❌ |
        | 🎨 HiDream | 高質量藝術風格 | ❌ |
        
        ### 📝 使用步驟
        1. **選擇模型** - 左側選擇適合的模型
        2. **上傳參考圖** - Nano Banana Edit 需要參考圖
        3. **輸入提示詞** - 描述你想生成的圖像
        4. **優化提示詞** - 可選使用 MiniMax 優化
        5. **生成圖像** - 點擊按鈕開始
        6. **下載圖片** - 單張或批量下載
        
        ### ⚠️ 注意事項
        - Nano Banana Pro Edit 需要上傳參考圖片
        """)


if __name__ == "__main__":
    main()
