# core/help_data.py
"""
集中存储所有配置参数的帮助信息。
结构:
HELP_DATA = {
    "config_type": {
        "param_key": {
            "key": "internal_parameter_name",
            "name": "中文名",
            "desc": "参数作用描述。",
            "default": "默认值 (字符串表示)"
        },
        ...
    },
    ...
}
"""

# 注意：默认值应与 config_manager.py 中的 DEFAULT_* 配置保持一致
HELP_DATA = {
    # --- LLM 全局/共享配置 ---
    "llm_global": {
        "temperature": {
            "key": "temperature", "name": "Temperature",
            "desc": "控制生成文本的随机性。较低的值使输出更集中和确定，较高的值更多样和创造性。\n范围通常为 0.0 到 2.0 (具体取决于模型)。",
            "default": "0.2"
        },
        "maxOutputTokens": {
            "key": "maxOutputTokens", "name": "Max Tokens / Max Output Tokens",
            "desc": "限制模型单次响应生成的最大 Token 数量 (包括输入和输出的总和，或仅输出，取决于 API)。\nToken 大致对应单词或字符片段。",
            "default": "8192"
        },
        "topP": {
            "key": "topP", "name": "Top P (Nucleus Sampling)",
            "desc": "控制模型生成下一个词时考虑的概率总和阈值。例如 0.9 表示只考虑概率总和达到 90% 的最可能词汇。\n留空则不使用。",
            "default": "None"
        },
        "topK": {
            "key": "topK", "name": "Top K",
            "desc": "控制模型生成下一个词时只考虑概率最高的 K 个词汇。\n留空则不使用。",
            "default": "None"
        },
        "preInstruction": {
            "key": "preInstruction", "name": "全局前置指令",
            "desc": "在每次调用 LLM 时，添加到主要任务指令之前的通用指令或背景信息。",
            "default": ""
        },
        "postInstruction": {
            "key": "postInstruction", "name": "全局后置指令",
            "desc": "在每次调用 LLM 时，添加到主要任务指令之后的通用指令或格式要求。",
            "default": ""
        },
        "successSoundPath": {
            "key": "successSoundPath", "name": "成功提示音路径",
            "desc": "任务成功完成时播放的声音文件路径 (.wav 格式)。",
            "default": "assets/success.wav"
        },
        "failureSoundPath": {
            "key": "failureSoundPath", "name": "失败提示音路径",
            "desc": "任务失败时播放的声音文件路径 (.wav 格式)。",
            "default": "assets/failure.wav"
        },
        "saveDebugInputs": {
            "key": "saveDebugInputs", "name": "保存 LLM 调试输入",
            "desc": "是否将每次调用 LLM API 的输入参数 (Payload) 保存到 debug_logs 目录以供调试。",
            "default": "False"
        },
        "enableStreaming": {
            "key": "enableStreaming", "name": "启用 LLM 流式传输",
            "desc": "是否让 LLM 以流式方式逐步返回结果，提供更快的首字符响应时间。",
            "default": "True"
        },
        "use_proxy": {
            "key": "use_proxy", "name": "使用代理访问 LLM",
            "desc": "是否通过配置的 HTTP/HTTPS 代理服务器访问 Google 或 OpenAI API。",
            "default": "False"
        },
        "proxy_address": {
            "key": "proxy_address", "name": "LLM 代理地址",
            "desc": "代理服务器的 IP 地址或域名。",
            "default": ""
        },
        "proxy_port": {
            "key": "proxy_port", "name": "LLM 代理端口",
            "desc": "代理服务器的端口号。",
            "default": ""
        },
        # 功能性备注: 颜色配置帮助信息已在 config_manager.py 中添加
    },
    # --- Google 特定配置 ---
    "google": {
        "apiKey": {
            "key": "apiKey", "name": "Google API Key",
            "desc": "用于访问 Google Generative AI API 的密钥。",
            "default": ""
        },
        "apiEndpoint": {
            "key": "apiEndpoint", "name": "Google API Base URL",
            "desc": "Google Generative AI API 的基础接入点 URL。",
            "default": "https://generativelanguage.googleapis.com"
        },
        "modelName": {
            "key": "modelName", "name": "Google 模型名称 (手动)",
            "desc": "要使用的 Google 模型名称。如果手动输入，将覆盖从列表中的选择。",
            "default": "gemini-1.5-flash-latest"
        },
    },
    # --- OpenAI 特定配置 ---
    "openai": {
        "apiKey": {
            "key": "apiKey", "name": "OpenAI API Key",
            "desc": "用于访问 OpenAI API 或兼容反代 API 的密钥 (通常以 sk- 开头)。",
            "default": ""
        },
        "apiBaseUrl": {
            "key": "apiBaseUrl", "name": "OpenAI API Base URL",
            "desc": "OpenAI API 或兼容反代 API 的基础 URL。",
            "default": "https://api.openai.com/v1"
        },
        "modelName": {
            "key": "modelName", "name": "OpenAI 模型名称 (手动)",
            "desc": "要使用的 OpenAI 模型名称。如果手动输入，将覆盖从列表中的选择。",
            "default": "gpt-4o"
        },
        "customHeaders": {
            "key": "customHeaders", "name": "自定义 Headers (JSON)",
            "desc": "用于添加额外的 HTTP 请求头，例如用于反代认证。\n格式为 JSON 对象，如: {\"Authorization\": \"Bearer your_token\"} 或 {\"X-Api-Password\": \"pass\"}。",
            "default": "{}"
        },
    },
    # --- 图片生成共享配置 ---
    "image_gen_shared": {
        "imageSaveDir": {
            "key": "imageSaveDir", "name": "图片保存目录",
            "desc": "所有图片生成器 (SD WebUI, ComfyUI) 生成的图片默认保存到的目录。",
            "default": ""
        },
        "sampler": {
            "key": "sampler", "name": "采样器 (Sampler)",
            "desc": "选择用于图像生成的扩散算法（如 Euler a, DPM++ 2M Karras 等）。\nSD WebUI: 直接使用此名称。\nComfyUI: 工作流中的采样器节点需要能接受此名称。",
            "default": "Euler a"
        },
        "scheduler": {
            "key": "scheduler", "name": "调度器 (Scheduler)",
            "desc": "与采样器配合使用，影响步进方式（如 karras, simple, ddim_uniform）。\nSD WebUI: 通常与采样器绑定，此设置可能不直接生效。\nComfyUI: 用于 KSampler 节点的 'scheduler' 输入。",
            "default": "karras"
        },
        "steps": {
            "key": "steps", "name": "采样步数",
            "desc": "图像生成的迭代次数，步数越多通常细节越丰富，但耗时也越长。",
            "default": "20"
        },
        "cfgScale": {
            "key": "cfgScale", "name": "CFG Scale (提示词相关性)",
            "desc": "控制图像与提示词的符合程度，值越高越贴近提示词，但可能牺牲多样性。",
            "default": "7.0"
        },
        "width": {
            "key": "width", "name": "图像宽度",
            "desc": "生成图像的宽度（像素），通常需要是 8 的倍数。",
            "default": "512"
        },
        "height": {
            "key": "height", "name": "图像高度",
            "desc": "生成图像的高度（像素），通常需要是 8 的倍数。",
            "default": "512"
        },
        "seed": {
            "key": "seed", "name": "随机种子",
            "desc": "控制图像生成的随机性。-1 表示SD WebUI的随机种子，ComfyUI要0或者正整数。使用固定种子和相同参数理论上可复现图像。",
            "default": "-1"
        },
        # 功能性备注: 共享随机种子开关的帮助信息已在 config_manager.py 中添加
        "restoreFaces": {
            "key": "restoreFaces", "name": "面部修复",
            "desc": "是否尝试调用面部修复功能改善生成图像中的面部。\nSD WebUI: 直接调用内置功能。\nComfyUI: 需要工作流中有对应节点且程序配置了节点标题。",
            "default": "False"
        },
        "tiling": {
            "key": "tiling", "name": "平铺/无缝",
            "desc": "是否生成可无缝平铺的图像，适用于纹理创建。\nSD WebUI: 直接调用内置功能。\nComfyUI: 需要工作流中有对应节点或设置。",
            "default": "False"
        },
        "denoisingStrength": {
            "key": "denoisingStrength", "name": "重绘幅度 / Denoise",
            "desc": "用于图生图 (Image-to-Image) 或高清修复 (Hires. Fix) 时，控制对原始图像/低分辨率图像的重绘程度。\n范围 0.0 到 1.0。值越低越接近原图，值越高生成内容越多。\nComfyUI: 用于 KSampler 节点的 'denoise' 输入。\nSD WebUI: 用于 img2img 和 Hires. Fix 的 'denoising_strength'。",
            "default": "0.7"
        },
        "clipSkip": {
             "key": "clipSkip", "name": "CLIP Skip",
             "desc": "在处理提示词时跳过 CLIP 模型的最后几层。通常设置为 1 或 2 可以改善某些动漫模型的生成效果。\nSD WebUI: 通过 override_settings 设置。\nComfyUI: 用于 CLIPTextEncode 节点的 'stop_at_clip_layer' 输入 (值为负数, -1 表示跳过1层)。",
             "default": "1"
        },
        "maskBlur": {
            "key": "maskBlur", "name": "蒙版模糊 (Inpaint)",
            "desc": "用于局部重绘 (Inpainting) 时，控制蒙版边缘的模糊程度（像素），使重绘区域与原图过渡更自然。\nSD WebUI: 使用 'mask_blur' 参数。\nComfyUI: 可能需要 Mask Reroute 或类似节点。",
            "default": "4"
        },
        "additionalPositivePrompt": {
            "key": "additionalPositivePrompt", "name": "全局附加正向提示",
            "desc": "会自动添加到每个图片生成任务的正向提示词末尾的通用内容。",
            "default": "masterpiece, best quality"
        },
        "additionalNegativePrompt": {
            "key": "additionalNegativePrompt", "name": "全局附加负向提示",
            "desc": "会自动添加到每个图片生成任务的负向提示词末尾的通用内容。",
            "default": "lowres, bad anatomy, bad hands, text, error, missing fingers, extra digit, fewer digits, cropped, worst quality, low quality, normal quality, jpeg artifacts, signature, watermark, username, blurry"
        },
        # 功能性备注: 图片调试开关帮助信息已在 config_manager.py 中添加
    },
    # --- SD WebUI 独立配置 ---
    "sd": {
        "sdWebUiUrl": {
            "key": "sdWebUiUrl", "name": "SD WebUI API 地址",
            "desc": "Stable Diffusion WebUI (AUTOMATIC1111) 的 API 访问地址。",
            "default": "http://127.0.0.1:7860"
        },
        "sdOverrideModel": {
            "key": "sdOverrideModel", "name": "覆盖模型 (Checkpoint)",
            "desc": "在此处输入 Checkpoint 模型名称 (例如 'your_model.safetensors')。如果输入，将在调用 API 时通过 override_settings 覆盖 WebUI 的当前模型设置。",
            "default": ""
        },
        "sdOverrideVAE": {
            "key": "sdOverrideVAE", "name": "覆盖 VAE",
            "desc": "在此处输入 VAE 模型名称 (例如 'your_vae.safetensors' 或 'Automatic')。如果输入，将在调用 API 时通过 override_settings 覆盖 WebUI 的当前 VAE 设置。",
            "default": ""
        },
        "sdEnableHR": {
            "key": "sdEnableHR", "name": "启用高清修复 (Hires. Fix)",
            "desc": "是否在 SD WebUI 中启用高清修复流程。仅在文生图时有效。",
            "default": "False"
        },
        "sdHRScale": {
            "key": "sdHRScale", "name": "Hires. Fix 放大倍数",
            "desc": "高清修复流程中的图像放大倍数。",
            "default": "2.0"
        },
        "sdHRUpscaler": {
            "key": "sdHRUpscaler", "name": "Hires. Fix 放大算法",
            "desc": "高清修复流程中使用的放大算法名称 (需要 WebUI 支持)。例如：Latent, R-ESRGAN 4x+, SwinIR_4x 等。",
            "default": "Latent"
        },
        "sdHRSteps": {
            "key": "sdHRSteps", "name": "Hires. Fix 第二次步数",
            "desc": "高清修复流程中第二次采样使用的步数。0 表示与主采样步数相同。",
            "default": "0"
        },
        "sdInpaintingFill": {
            "key": "sdInpaintingFill", "name": "区域填充方式 (Inpaint)",
            "desc": "指定如何填充蒙版区域：\n0: fill (使用原图颜色填充)\n1: original (保留原图内容)\n2: latent noise (潜空间噪声)\n3: latent nothing (潜空间补零)",
            "default": "1"
        },
        "sdMaskMode": {
            "key": "sdMaskMode", "name": "蒙版模式 (Inpaint)",
            "desc": "指定重绘哪个区域：\n0: Inpaint masked (重绘蒙版内)\n1: Inpaint not masked (重绘蒙版外)",
            "default": "0"
        },
        "sdInpaintArea": {
            "key": "sdInpaintArea", "name": "重绘区域 (Inpaint)",
            "desc": "指定扩散作用的范围：\n0: Whole picture (在整张图上扩散)\n1: Only masked (仅在蒙版区域扩散)",
            "default": "1"
        },
         "sdResizeMode": {
            "key": "sdResizeMode", "name": "图像调整模式 (Img2Img)",
            "desc": "当输入图像尺寸与目标尺寸不符时如何处理：\n0: Just resize (直接拉伸)\n1: Crop and resize (裁剪后缩放)\n2: Resize and fill (缩放后填充)\n3: Just resize (latent upscale)",
            "default": "1"
        },
    },
    # --- ComfyUI 独立配置 ---
    "comfyui": {
        "comfyapiUrl": {
            "key": "comfyapiUrl", "name": "ComfyUI API 地址",
            "desc": "ComfyUI 服务器的 API 访问地址。",
            "default": "http://127.0.0.1:8188"
        },
        "comfyWorkflowFile": {
            "key": "comfyWorkflowFile", "name": "工作流文件 (.json)",
            "desc": "指向用于生成图片的基础 ComfyUI 工作流 JSON 文件路径。\n程序将基于此文件，并根据下方配置的参数和节点标题，尝试覆盖工作流中的设置。\n图生图/内绘功能需要加载适配的工作流文件，并将必要的图像/蒙版文件放置在 ComfyUI 的 'input' 目录中。",
            "default": ""
        },
        "comfyCkptName": {
             "key": "comfyCkptName", "name": "Checkpoint 模型名称",
             "desc": "要使用的 Checkpoint 模型文件名。如果填写，将覆盖工作流中对应节点（见下）的设置。",
             "default": ""
        },
        "comfyVaeName": {
             "key": "comfyVaeName", "name": "VAE 模型名称",
             "desc": "要使用的 VAE 模型文件名。如果填写，将覆盖工作流中对应节点（见下）的设置。",
             "default": ""
        },
        "comfyLoraName": {
            "key": "comfyLoraName", "name": "LoRA 1 名称",
            "desc": "(示例) 要加载的第一个 LoRA 文件名。如果填写，将覆盖工作流中对应 LoRA 加载节点（见下）的设置。需要工作流中有对应的节点。",
            "default": ""
        },
        "comfyLoraStrengthModel": {
            "key": "comfyLoraStrengthModel", "name": "LoRA 1 模型权重",
            "desc": "(示例) 第一个 LoRA 对主模型的影响强度。范围通常 0.0 - 1.0。",
            "default": "0.7"
        },
        "comfyLoraStrengthClip": {
            "key": "comfyLoraStrengthClip", "name": "LoRA 1 CLIP 权重",
            "desc": "(示例) 第一个 LoRA 对 CLIP 模型的影响强度。范围通常 0.0 - 1.0。",
            "default": "0.7"
        },
        "comfyPositiveNodeTitle": {
            "key": "comfyPositiveNodeTitle", "name": "正向提示节点标题",
            "desc": "工作流中用于接收正向提示词的节点的标题 (Title)。通常是 CLIPTextEncode 或类似节点。",
            "default": "PositivePromptInput"
        },
        "comfyNegativeNodeTitle": {
            "key": "comfyNegativeNodeTitle", "name": "负向提示节点标题",
            "desc": "工作流中用于接收负向提示词的节点的标题 (Title)。通常是 CLIPTextEncode 或类似节点。",
            "default": "NegativePromptInput"
        },
        "comfyOutputNodeTitle": {
            "key": "comfyOutputNodeTitle", "name": "保存图片节点标题",
            "desc": "工作流中用于保存最终图片的节点的标题 (Title)，程序将修改其文件名前缀。",
            "default": "SaveOutputImage"
        },
        "comfySamplerNodeTitle": {
            "key": "comfySamplerNodeTitle", "name": "采样器节点标题",
            "desc": "工作流中主要的 KSampler 或 KSamplerAdvanced 节点的标题 (Title)，用于注入种子、步数、CFG、采样器、调度器、Denoise 等共享参数。",
            "default": "MainSampler"
        },
        "comfyLatentImageNodeTitle": {
            "key": "comfyLatentImageNodeTitle", "name": "潜空间节点标题",
            "desc": "工作流中 EmptyLatentImage (文生图) 或 VAEEncode (图生图) 输出潜空间的节点的标题 (Title)，用于注入宽度、高度和批处理大小 (n_samples)。",
            "default": "EmptyLatentImageNode"
        },
        "comfyCheckpointNodeTitle": {
            "key": "comfyCheckpointNodeTitle", "name": "模型加载节点标题",
            "desc": "工作流中加载 Checkpoint 节点的标题 (例如 CheckpointLoaderSimple)。用于覆盖模型。",
            "default": "LoadCheckpointNode"
        },
        "comfyVAENodeTitle": {
            "key": "comfyVAENodeTitle", "name": "VAE 加载节点标题",
            "desc": "工作流中加载 VAE 节点的标题 (例如 VAELoader)。用于覆盖 VAE。",
            "default": "LoadVAENode"
        },
         "comfyClipTextEncodeNodeTitle": {
            "key": "comfyClipTextEncodeNodeTitle", "name": "CLIP 编码节点标题",
            "desc": "工作流中主要的 CLIPTextEncode 节点的标题。用于设置 CLIP Skip。注意：正向和负向提示节点也可能是 CLIPTextEncode，这里指用于应用 CLIP Skip 的那个（如果不同）。",
            "default": "CLIPTextEncodeNode"
        },
         "comfyLoraLoaderNodeTitle": {
            "key": "comfyLoraLoaderNodeTitle", "name": "LoRA 加载节点标题",
            "desc": "工作流中主要的 LoraLoader 节点的标题。用于设置 LoRA。",
            "default": "LoraLoaderNode"
        },
         "comfyLoadImageNodeTitle": {
            "key": "comfyLoadImageNodeTitle", "name": "加载图像节点标题 (图生图)",
            "desc": "工作流中用于加载图生图初始图像的 LoadImage 节点的标题。程序会设置其 'image' 输入（文件名）。\n重要：该图像文件必须位于 ComfyUI 服务器的 'input' 目录下。",
            "default": "LoadImageNode"
        },
        # 功能性备注: 加载蒙版节点标题的帮助信息已在 config_manager.py 中添加
        "comfyFaceDetailerNodeTitle": {
            "key": "comfyFaceDetailerNodeTitle", "name": "面部修复节点标题 (可选)",
            "desc": "(可选) 工作流中面部修复相关节点的标题 (如 FaceDetailer)。程序会根据共享设置尝试启用/禁用 (需要工作流支持)。",
            "default": "OptionalFaceDetailer"
        },
        "comfyTilingSamplerNodeTitle": {
            "key": "comfyTilingSamplerNodeTitle", "name": "Tiling 节点标题 (可选)",
            "desc": "(可选) 工作流中实现 Tiling 功能相关节点的标题。程序会根据共享设置尝试启用/禁用 (需要工作流支持)。",
            "default": "OptionalTilingSampler"
        },
    },
    # --- NAI 配置 ---
    "nai": {
        "naiApiKey": {
            "key": "naiApiKey", "name": "NAI API Key",
            "desc": "用于访问 NovelAI 图像生成 API 的密钥。",
            "default": ""
        },
        "naiImageSaveDir": {
            "key": "naiImageSaveDir", "name": "NAI 图片保存目录",
            "desc": "NAI 生成的图片保存到的目录。",
            "default": ""
        },
        "naiModel": {
            "key": "naiModel", "name": "NAI 模型",
            "desc": "选择要使用的 NovelAI 图像生成模型。",
            "default": "nai-diffusion-3"
        },
        "naiSampler": {
            "key": "naiSampler", "name": "NAI 采样器",
            "desc": "选择 NovelAI 使用的采样算法。",
            "default": "k_euler"
        },
        "naiSteps": {
            "key": "naiSteps", "name": "NAI 步数",
            "desc": "NovelAI 生成图像的迭代步数。",
            "default": "28"
        },
        "naiScale": {
            "key": "naiScale", "name": "NAI 引导强度 (Scale)",
            "desc": "控制 NovelAI 图像与提示词的符合程度。",
            "default": "7.0"
        },
        "naiSeed": {
            "key": "naiSeed", "name": "NAI 种子",
            "desc": "NovelAI 图像生成的随机种子，-1 表示随机。",
            "default": "-1"
        },
        # 功能性备注: NAI 随机种子开关的帮助信息已在 config_manager.py 中添加
        "naiUcPreset": {
            "key": "naiUcPreset", "name": "NAI 负面预设",
            "desc": "选择 NovelAI 的负面提示词预设强度。",
            "default": "0 (Heavy)"
        },
        "naiQualityToggle": {
            "key": "naiQualityToggle", "name": "NAI 质量标签",
            "desc": "是否自动为 NovelAI 添加提升质量的标签。",
            "default": "True"
        },
        "naiSmea": {
            "key": "naiSmea", "name": "启用 SMEA",
            "desc": "是否启用 NovelAI 的 SMEA 采样器增强。",
            "default": "False"
        },
        "naiSmeaDyn": {
            "key": "naiSmeaDyn", "name": "启用 SMEA DYN",
            "desc": "是否启用 NovelAI 的 SMEA DYN 采样器增强。",
            "default": "False"
        },
        "naiDynamicThresholding": {
            "key": "naiDynamicThresholding", "name": "启用动态阈值",
            "desc": "是否启用 NovelAI 的动态阈值功能。",
            "default": "False"
        },
        "naiUncondScale": {
             "key": "naiUncondScale", "name": "负面内容强度 (Scale)",
             "desc": "直接控制负面提示词的影响强度（API 中的 uncond_scale 参数），1.0 是默认值。此设置可能比预设更精细。",
             "default": "1.0"
        },
        "naiReferenceStrength": {
             "key": "naiReferenceStrength", "name": "参考强度 (Img2Img)",
             "desc": "用于 NAI 图生图时，控制输出与参考图的相似度。范围 0.0 - 1.0。值越低越相似。",
             "default": "0.6"
        },
        "naiReferenceInfoExtracted": {
            "key": "naiReferenceInfoExtracted", "name": "参考信息提取 (Img2Img)",
            "desc": "用于 NAI 图生图时，控制从参考图中提取多少信息（如颜色、构图）。范围 0.0 - 1.0。",
            "default": "0.7"
        },
        "naiAddOriginalImage": {
             "key": "naiAddOriginalImage", "name": "添加原图 (Variation)",
             "desc": "用于 NAI 图像变体时，是否在添加噪声前混合原图。",
             "default": "True"
        },
        "nai_use_proxy": {
            "key": "nai_use_proxy", "name": "使用代理访问 NAI",
            "desc": "是否通过配置的代理访问 NovelAI API。",
            "default": "False"
        },
        "nai_proxy_address": {
            "key": "nai_proxy_address", "name": "NAI 代理地址",
            "desc": "用于访问 NAI 的代理服务器地址。",
            "default": ""
        },
        "nai_proxy_port": {
            "key": "nai_proxy_port", "name": "NAI 代理端口",
            "desc": "用于访问 NAI 的代理服务器端口。",
            "default": ""
        },
        # 功能性备注: NAI 调试开关帮助信息已在 config_manager.py 中添加
    },
    # --- GPT-SoVITS 配置 ---
    "gptsovits": {
        "apiUrl": {
            "key": "apiUrl", "name": "GPT-SoVITS API 地址",
            "desc": "GPT-SoVITS 推理 API 的完整 URL (通常以 /infer_ref 结尾)。",
            "default": "http://127.0.0.1:9880"
        },
        "model_name": {
            "key": "model_name", "name": "TTS 模型名称",
            "desc": "在 GPT-SoVITS API 中指定的 TTS 模型名称。",
            "default": ""
        },
        "audioSaveDir": {
            "key": "audioSaveDir", "name": "音频保存目录",
            "desc": "生成的语音文件保存到的目录。",
            "default": ""
        },
        "audioPrefix": {
            "key": "audioPrefix", "name": "音频文件前缀",
            "desc": "添加到生成的语音文件名前缀。",
            "default": "cv_"
        },
        "how_to_cut": {
            "key": "how_to_cut", "name": "切分方式",
            "desc": "长文本的自动切分方法。",
            "default": "不切"
        },
        "top_k": {
            "key": "top_k", "name": "Top K",
            "desc": "控制声音生成的随机性，值越小越稳定。",
            "default": "5"
        },
        "top_p": {
            "key": "top_p", "name": "Top P",
            "desc": "控制声音生成的随机性，通常与 Top K 配合使用。",
            "default": "1.0"
        },
        "temperature": {
            "key": "temperature", "name": "Temperature",
            "desc": "控制声音生成的随机性，值越高越随机。",
            "default": "1.0"
        },
        "ref_free": {
            "key": "ref_free", "name": "无参考模式",
            "desc": "是否启用无参考音频的推理模式 (如果模型支持)。",
            "default": "False"
        },
        "audio_dl_url": {
            "key": "audio_dl_url", "name": "下载 URL 前缀 (可选)",
            "desc": "如果 API 返回的是相对路径，这里提供基础 URL 用于拼接下载链接。",
            "default": ""
        },
        "batch_size": {
            "key": "batch_size", "name": "批处理大小",
            "desc": "推理时的批处理大小。",
            "default": "1"
        },
        "batch_threshold": {
            "key": "batch_threshold", "name": "批处理阈值",
            "desc": "用于批处理切分的阈值。",
            "default": "0.75"
        },
        "split_bucket": {
            "key": "split_bucket", "name": "启用分桶",
            "desc": "是否启用分桶处理以优化长音频生成。",
            "default": "True"
        },
        "speed_facter": {
            "key": "speed_facter", "name": "语速因子",
            "desc": "调整生成语音的语速，大于 1 加快，小于 1 减慢。",
            "default": "1.0"
        },
        "fragment_interval": {
            "key": "fragment_interval", "name": "分片间隔",
            "desc": "并行推理时的分片间隔时间 (秒)。",
            "default": "0.3"
        },
        "parallel_infer": {
            "key": "parallel_infer", "name": "并行推理",
            "desc": "是否启用并行推理以加速。",
            "default": "True"
        },
        "repetition_penalty": {
            "key": "repetition_penalty", "name": "重复惩罚",
            "desc": "对重复内容的惩罚系数，大于 1 可减少重复。",
            "default": "1.35"
        },
        "seed": {
            "key": "seed", "name": "随机种子",
            "desc": "控制声音生成的随机性，-1 表示随机。",
            "default": "-1"
        },
        # 功能性备注: GPT-SoVITS 调试开关帮助信息已在 config_manager.py 中添加
    },
    # --- Workflow Tab UI 元素帮助 ---
    "workflow_tab_ui": {
         "manual_replace_placeholders": {
            "key": "manual_replace_placeholders_button",
            "name": "手动替换图片占位符按钮",
            "desc": "此按钮用于将 KAG 脚本中临时的 '[INSERT_IMAGE_HERE:名字]' 占位符，根据下方设置的“图片前缀”和占位符中的名字，转换为最终的、注释掉的 KAG '[image]' 标签 (例如 ';[image storage=\"前缀_名字_序号.png\"]')。\n\n主要作用：\n1. 预览将要生成的图片文件名。\n2. 为后续的“生成图片”步骤准备好包含文件名的脚本（图片生成功能会读取这些注释掉的标签）。\n\n建议在运行“生成图片”之前点击此按钮。",
            "default": "N/A"
        },
        "image_prefix": {
            "key": "image_prefix_var",
            "name": "图片前缀",
            "desc": "在手动或自动替换图片占位符时，添加到生成的文件名前缀。例如，设置为 'bg_'，占位符 '[INSERT_IMAGE_HERE:教室]' 会变成类似 ';[image storage=\"bg_教室_1.png\"]'。",
            "default": ""
        },
        "audio_prefix": {
            "key": "audio_prefix_var",
            "name": "音频前缀",
            "desc": "GPT-SoVITS 生成语音时，添加到最终保存的音频文件名前缀。",
            "default": "cv_"
        },
        "override_kag_temp": {
            "key": "override_kag_temp_var",
            "name": "覆盖KAG温度",
            "desc": "勾选此项，可以在下方输入框中指定一个温度值，该值将在“第三步：建议BGM并转KAG”时覆盖全局LLM设置中的温度，仅用于该步骤的LLM调用。",
            "default": "False"
        },
        "kag_temp": {
            "key": "kag_temp_var",
            "name": "KAG转换温度",
            "desc": "仅在勾选“覆盖KAG温度”时生效。指定用于步骤三（建议BGM并转KAG）的LLM温度值。",
            "default": "0.1"
        },
        "img_gen_scope": {
            "key": "img_gen_scope_var",
            "name": "图片生成范围",
            "desc": "选择图片生成的范围：\n- 所有: 处理 KAG 脚本中所有找到的、注释掉的图片任务。\n- 指定: 只处理下方输入框中指定的、逗号分隔的文件名对应的任务。",
            "default": "all"
        },
         "specific_images": {
            "key": "specific_images_var",
            "name": "指定图片文件名",
            "desc": "当范围选择“指定”时生效。输入要生成的图片文件名 (脚本中注释掉的 [image] 标签里的 storage 值)，多个文件名用英文逗号分隔。",
            "default": ""
        },
        "img_n_samples": {
            "key": "img_n_samples_var",
            "name": "图片生成数量",
            "desc": "为每个图片任务请求生成多少张图片。最终保存的文件名会自动添加序号 (例如 _1, _2)。",
            "default": "1"
        },
        "workflowEnableImg2Img": {
            "key": "workflowEnableImg2ImgCheckbox",
            "name": "启用图生图/内绘",
            "desc": "勾选此项以启用图生图 (Image-to-Image) 或局部重绘 (Inpainting) 功能。\n\n前提条件：\n1. 必须在“人物设定”标签页为目标人物配置有效的“参考图像”路径。\n2. (可选，用于内绘/外绘) 必须为目标人物配置有效的“蒙版图像”路径。\n\n如果只勾选此项但未配置有效参考图，或只配置了参考图但未勾选此项，程序将仍然执行文生图。\n\n效果依赖于“图片生成设置”中的相关参数（如重绘幅度、蒙版模糊、SD WebUI 内绘选项等）以及后端 API 的支持。",
            "default": "False"
        },
        "audio_gen_scope": {
            "key": "audio_gen_scope_var",
            "name": "语音生成范围",
            "desc": "选择语音生成的范围：\n- 所有: 处理 KAG 脚本中所有找到的、注释掉的语音任务 (@playse)。\n- 指定: 只处理下方输入框中指定的语音占位符对应的任务。",
            "default": "all"
        },
        "specific_speakers": {
            "key": "specific_speakers_var",
            "name": "指定语音占位符",
            "desc": "当范围选择“指定”时生效。输入要生成的语音占位符 (脚本中注释掉的 @playse 标签里的 storage 值，形如 PLACEHOLDER_名字_序号.wav)。",
            "default": ""
        },
    },
    # --- 人物设定 Tab UI 元素帮助 ---
    "profiles_tab_ui": {
        "reference_image": {
            "key": "reference_image_path",
            "name": "参考图像路径 (图生图)",
            "desc": "为该人物指定一个参考图像文件路径。如果设置了此路径，并且在“转换流程”标签页勾选了“启用图生图/内绘”，程序将尝试执行图生图 (Image-to-Image) 而不是文生图。\n注意：图生图功能需要 API 后端 (SD WebUI, ComfyUI, NAI) 支持，并且需要调整“图片生成设置”中的“重绘幅度 (Denoise)”参数。\nComfyUI：工作流文件需要适配图生图，且该图片需位于 ComfyUI 的 input 目录。",
            "default": ""
        },
        "mask_image": {
             "key": "mask_image_path",
             "name": "蒙版图像路径 (内/外绘, 可选)",
             "desc": "为该人物指定一个蒙版图像文件路径（通常是黑白图，白色区域表示要处理的部分）。如果同时设置了参考图像并启用了图生图，此蒙版将用于局部重绘 (Inpainting/Outpainting)。\n注意：需要后端 API 支持蒙版功能 (SD WebUI, NAI 支持较好, ComfyUI 需要特定工作流)。还需要在“图片生成设置”中配置相关内绘参数（如蒙版模糊、填充方式等）。",
             "default": ""
        },
    }
}

def get_help_data(config_type, param_key):
    """获取指定参数的帮助信息"""
    return HELP_DATA.get(config_type, {}).get(param_key)