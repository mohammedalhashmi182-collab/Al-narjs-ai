---
name: gsk-image-generation
version: 1.0.0
description: Generate images using AI models. Supports text-to-image and image editing.
metadata:
  category: general
  requires:
    bins:
    - gsk
  cliHelp: gsk img --help
---

# gsk-image-generation

**PREREQUISITE:** Read `../gsk-shared/SKILL.md` for auth, global flags, and security rules.

Generate images using AI models. Supports text-to-image and image editing.

## Usage

```bash
gsk img [options]
```

**Aliases:** `img`

## Flags

| Flag | Required | Description |
|------|----------|-------------|
| `-m`, `--model` | No | If this parameter is omitted, nano-banana-2-flash-lite is used. Pick ONLY a model described below; never pick an undescribed model name unless the user explicitly asks for it by name. gpt-image-2: GPT Image 2 - Latest OpenAI image model. Superior text rendering, editing, and face preservation. Supports text-to-image and image editing with multi-image input. nano-banana-pro: [GEMINI NANO BANANA PRO] State of the Art (SOTA) for both generation and image editing. Multi-image fusion: Combine different images into one seamless new visual. Character & style consistency: Maintain the same subject or visual style across multiple generations. Conversational editing: Edit images with simple, natural language instructions. Perfect for creative use cases, marketing, training, advertising. Supports up to 14 images as reference input. Supports high resolution output up to 2K/4K. nano-banana-2: [GEMINI NANO BANANA 2] Gemini 3.1 Flash Image. Fast and efficient with advanced reasoning. Multi-image fusion with up to 14 reference images. Supports 0.5K/1K/2K/4K resolution. Google Search grounding for real-time data. Best for high-volume, speed-optimized workflows. fal-ai/bytedance/seedream/v5/lite: Bytedance Seedream v5 Lite model for text-to-image, image-to-image (single and multiple image editing) generation with native 2K resolution and excellent text layout.fal-ai/bytedance/seedream/v5/pro: Bytedance Seedream 5.0 Pro - flagship photorealistic model for text-to-image and multi-image editing (up to 10 reference images). High-density text/infographic layout, region-precise edits, native text in 14 languages, up to 2K output. xai/grok-imagine-image: xAI Grok Imagine Image 2.0 - top-ranked text-to-image and image editing (up to 3 reference images). Strong photorealism and prompt adherence, up to 2K output. qwen-image-3: Qwen Image 3 - Alibaba's latest image model for text-to-image and reference-image editing (1-3 reference images). Superior Chinese & English text rendering, precise prompt adherence, identity-preserving edits. Best for posters, bilingual typography, and instruction-based edits. fal-ai/flux-2-pro: Flux 2 Pro model - higher quality version of Flux 2 with professional-grade output. Enhanced realism, superior text generation, and advanced editing capabilities. Ideal for high-quality realistic images and complex editing tasks.fal-ai/z-image/turbo: Z-Image Turbo model optimized for speed without sacrificing quality. Supports both text-to-image and image-to-image modes. Perfect for quick iterations, bulk generation, style transfer, and cost-effective projects.bbox-segment: A model for extracting subjects from images based on bbox region.fal-bria-rmbg: A model specialized for remove background from image. Should prioritize this tool if the user wants to remove background from image. fal-ai/recraft-clarity-upscale: A model specialized for upscale image. fal-ai/image-editing/text-removal: A specialized model for removing text and watermarks from images. Automatically detects and removes text while preserving the background and other visual elements. Use when users want to clean images, remove watermarks, or eliminate text overlays. flux-pro/outpaint: A model specialized for expand image to a specific aspect ratio. nano-banana-2-flash-lite: [GEMINI NANO BANANA 2 FLASH LITE] Fast, lightweight Gemini image model for text-to-image and image editing with multi-image input. Native 1K output. Best for speed-sensitive, high-volume workflows.  (string, one of: gpt-image-2, nano-banana-pro, nano-banana-2, fal-ai/bytedance/seedream/v5/lite, fal-ai/bytedance/seedream/v5/pro, xai/grok-imagine-image, qwen-image-3, fal-ai/flux-2-pro, fal-ai/z-image/turbo, bbox-segment, fal-bria-rmbg, fal-ai/recraft-clarity-upscale, fal-ai/image-editing/text-removal, flux-pro/outpaint, nano-banana-2-flash-lite) |
| `<query>` (positional) | No | Detailed description of the image to generate. The prompt should be in English.However, any specific text that should appear within the image does not need to be translated.(e.g., 'A futuristic cityscape with flying cars and neon lights at night'). Omit when passing the prompt by `query_file` instead. (string) |
| `--query_file` | No | Optional. Repo-relative path to a UTF-8 text file containing the prompt, used verbatim in place of `query` (lets you pass a long prompt by path instead of inlining it). Requires `repo_id`. When set, `query` may be omitted. (string) |
| `--bbox` | No | BBox of the target object, for bbox segmentation modelFormat: [x1, y1, x2, y2], x1 and y1 are the top-left corner coordinates, x2 and y2 are the bottom-right corner coordinates. (array) |
| `-i`, `--image_urls` | No | The URLs of the images to use as a reference for the image generation or editing. Default is []. REQUIRED whenever the task edits, restyles, or must stay visually consistent with an existing image, person, product, or brand — pass the source/reference URL(s) on EVERY such call, including retries: omitting them regenerates from text and silently discards the user's actual image. (array) |
| `--repo_id` | No | Optional. Second Brain repo id (provided in the agent's system prompt). Required only when image_urls contains relative paths from a Second Brain project (e.g. 'assets/foo.png'). Absolute http(s) URLs and data: URLs do not need this parameter. (string) |
| `-r`, `--aspect_ratio` | No | The aspect ratio of the image to generate. Default 'auto'. When editing with image_urls (image-to-image), use 'auto' so the output keeps the reference image's aspect ratio — never switch between portrait and landscape unless the user explicitly asks. (string, one of: 1:1, 4:3, 16:9, 9:16, 3:4, 2:3, 3:2, auto) |
| `-s`, `--image_size` | No | Image size resolution. Default is auto. (string, one of: auto, 0.5k, 1k, 2k, 3k, 4k) |

## Local File Support

Parameters that accept URLs (`--image_urls`) also accept local file paths. The CLI automatically uploads local files before sending to the API.

## Output File

Use `-o <path>` / `--output-file <path>` to download the generated result directly to a local file.

## See Also

- [gsk-shared](../gsk-shared/SKILL.md) — Authentication and global flags
