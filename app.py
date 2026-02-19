import streamlit as st
import requests
import fal_client
import asyncio
import os
import itertools
from PIL import Image
from io import BytesIO
from datetime import datetime


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
                "content": "You are a professional prompt engineer. Improve the user's image prompt."
            },
            {
                "role": "user",
                "content": f"""Improve this image generation prompt.

Return in this format exactly:

PROMPT: <optimized prompt>
EXPLANATION: <what you improved>
SUGGESTIONS: <optional suggestions>

Original prompt:
{prompt}
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

    # Handle MiniMax internal error format
    if "base_resp" in result and result["base_resp"].get("status_code") != 0:
        raise ValueError(f"MiniMax API Error: {result['base_resp']}")

    if "choices" not in result or not result["choices"]:
        raise ValueError(f"Unexpected MiniMax response: {result}")

    return result["choices"][0]["message"]["content"].strip()


# =========================
# fal Image Generation
# =========================
async def generate_image_with_fal(prompt, model, image_size,
                                  num_inference_steps, guidance_scale,
                                  num_images, safety_tolerance):

    fal_api_key = os.getenv("FAL_KEY")
    if not fal_api_key:
        raise ValueError("FAL_KEY environment variable is not set")

    os.environ["FAL_KEY"] = fal_api_key

    handler = await fal_client.submit_async(
        model,
        arguments={
            "prompt": prompt,
            "image_size": image_size,
            "num_inference_steps": num_inference_steps,
            "guidance_scale": guidance_scale,
            "num_images": num_images,
            "safety_tolerance": safety_tolerance
        }
    )

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
    ]
    return itertools.cycle(messages)


async def run_with_spinner(coroutine, placeholder, cycle):
    task = asyncio.create_task(coroutine)
    while not task.done():
        placeholder.text(next(cycle))
        await asyncio.sleep(2)
    return await task


# =========================
# Save Image + Markdown
# =========================
def save_image_and_markdown(url, prompt, result, model,
                            image_size, steps, guidance, safety):

    response = requests.get(url)
    if response.status_code != 200:
        raise IOError("Failed to download image")

    image = Image.open(BytesIO(response.content))

    timestamp = datetime.now().strftime("%Y-%m-%d-%H%M")
    safe_prompt = "".join(c for c in prompt if c.isalnum() or c in (' ', '-', '_'))[:50]

    folder = os.path.join(os.getcwd(), "images")
    os.makedirs(folder, exist_ok=True)

    image_path = os.path.join(folder, f"{timestamp}_{safe_prompt}.png")
    image.save(image_path)

    markdown_path = os.path.join(folder, f"{timestamp}_{safe_prompt}.md")

    markdown_content = f"""# Image Generation Results

## Prompt
{prompt}

## Details
- Date: {datetime.now()}
- Model: {model}
- Seed: {result.get('seed')}
- NSFW: {result.get('has_nsfw_concepts')}
- Size: {image_size}
- Steps: {steps}
- Guidance: {guidance}
- Safety: {safety}

## Image URL
{url}
"""

    with open(markdown_path, "w", encoding="utf-8") as f:
        f.write(markdown_content)

    return image_path, markdown_path


# =========================
# Main App
# =========================
def main():
    st.title("吳振二號畫室 · Flux + MiniMax")

    if not os.getenv("FAL_KEY"):
        st.error("FAL_KEY not set")
        return

    model_options = {
        "Flux 2": "fal-ai/flux-2",
        "Flux Pro v1.1": "fal-ai/flux-pro/v1.1-ultra",
        "Flux 2 pro": "fal-ai/flux-2-pro",
        "Imagen4": "fal-ai/imagen4/preview",
        "hidream-i1": "fal-ai/hidream-i1-full"
    }

    selected_model = st.selectbox("Select Model", list(model_options.keys()))

    image_size = st.selectbox("Image Size",
                              ["square_hd", "square", "portrait_4_3",
                               "portrait_16_9", "landscape_4_3",
                               "landscape_16_9"])

    steps = st.slider("Inference Steps", 1, 50, 28)

    with st.expander("Advanced Settings"):
        guidance = st.slider("Guidance Scale", 1.0, 20.0, 3.5, 0.1)
        safety = st.selectbox("Safety Tolerance", ["1", "2", "3", "4"])

    if "prompt" not in st.session_state:
        st.session_state.prompt = ""

    prompt = st.text_input("Enter Prompt", st.session_state.prompt)
    st.session_state.prompt = prompt

    # ---------------- MiniMax ----------------
    if st.checkbox("Use MiniMax Prompt Tuning"):
        if st.button("Tune Prompt"):
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

                if not optimized:
                    raise ValueError("MiniMax response malformed")

                st.session_state.prompt = optimized

                st.success("Prompt Tuned Successfully")
                st.write("Explanation:", explanation)
                st.write("Suggestions:", suggestions)

            except Exception as e:
                st.error(str(e))

    # ---------------- Image Generation ----------------
    if st.button("Generate Image"):

        if not prompt:
            st.warning("Please enter a prompt")
            return

        try:
            spinner = st.empty()
            cycle = cycle_spinner_messages()

            async def task():
                return await generate_image_with_fal(
                    prompt,
                    model_options[selected_model],
                    image_size,
                    steps,
                    guidance,
                    1,
                    safety
                )

            result = asyncio.run(run_with_spinner(task(), spinner, cycle))
            spinner.empty()

            if "images" not in result or not result["images"]:
                raise ValueError(f"Invalid fal response: {result}")

            image_url = result["images"][0]["url"]

            st.image(image_url, use_column_width=True)
            st.write("Seed:", result.get("seed"))
            st.write("NSFW:", result.get("has_nsfw_concepts"))

            img_path, md_path = save_image_and_markdown(
                image_url, prompt, result,
                selected_model, image_size,
                steps, guidance, safety
            )

            st.success(f"Saved: {img_path}")
            st.success(f"Saved: {md_path}")

        except Exception as e:
            st.error(f"Generation error: {e}")


if __name__ == "__main__":
    main()
