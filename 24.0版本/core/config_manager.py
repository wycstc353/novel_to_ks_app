# core/config_manager.py
import json
import os
import traceback
from pathlib import Path
from tkinter import messagebox, filedialog
import logging # 功能性备注: 导入日志模块

# 功能性备注: 获取当前模块的 logger 实例
logger = logging.getLogger(__name__)

# --- 常量定义 ---
CONFIG_DIR = Path("configs")
LLM_GLOBAL_CONFIG_FILE = CONFIG_DIR / "llm_global_config.json"
IMAGE_GLOBAL_CONFIG_FILE = CONFIG_DIR / "image_global_config.json"
IMAGE_GEN_SHARED_CONFIG_FILE = CONFIG_DIR / "image_gen_shared_config.json"
GOOGLE_CONFIG_FILE = CONFIG_DIR / "google_config.json"
OPENAI_CONFIG_FILE = CONFIG_DIR / "openai_config.json"
NAI_CONFIG_FILE = CONFIG_DIR / "nai_config.json"
SD_CONFIG_FILE = CONFIG_DIR / "sd_config.json"
COMFYUI_CONFIG_FILE = CONFIG_DIR / "comfyui_config.json"
GPTSOVITS_CONFIG_FILE = CONFIG_DIR / "gptsovits_config.json"


# --- 默认配置字典 (已更新, 添加颜色配置) ---
DEFAULT_LLM_GLOBAL_CONFIG = {
    "selected_provider": "Google",
    "temperature": 0.2, "maxOutputTokens": 8192, "topP": None, "topK": None,
    "preInstruction": "", "postInstruction": "",
    "successSoundPath": "assets/success.wav", "failureSoundPath": "assets/failure.wav",
    "saveDebugInputs": False, # LLM 调试开关
    "enableStreaming": True,
    "use_proxy": False, "proxy_address": "", "proxy_port": "",
    "enableSoundNotifications": True, "enableWinNotifications": True,
    # --- 功能性备注: 添加 UI 日志颜色默认值 ---
    "ui_log_color_debug": "#ADD8E6", # 浅蓝色
    "ui_log_color_info": "#3CB371",   # 中绿色
    "ui_log_color_warning": "orange",
    "ui_log_color_error": "#ff5f5f",
    "ui_log_color_critical": "#ff0000",
    # --- 功能性备注: 添加控制台日志颜色默认值 (使用 colorama 名称) ---
    "console_log_color_debug": "DIM", # 对应 colorama.Style.DIM
    "console_log_color_info": "GREEN", # 对应 colorama.Fore.GREEN
    "console_log_color_warning": "YELLOW",
    "console_log_color_error": "RED",
    "console_log_color_critical": "BRIGHT_RED", # 对应 colorama.Style.BRIGHT + colorama.Fore.RED
}
DEFAULT_IMAGE_GLOBAL_CONFIG = {
    "selected_image_provider": "SD WebUI"
}
DEFAULT_IMAGE_GEN_SHARED_CONFIG = {
    "imageSaveDir": "",
    "sampler": "Euler a",
    "scheduler": "karras",
    "steps": 20,
    "cfgScale": 7.0,
    "width": 512,
    "height": 512,
    "seed": -1,
    "sharedRandomSeed": False, # 功能性备注: 添加共享随机种子开关默认值
    "restoreFaces": False,
    "tiling": False,
    "denoisingStrength": 0.7,
    "clipSkip": 1,
    "maskBlur": 4,
    "additionalPositivePrompt": "masterpiece, best quality",
    "additionalNegativePrompt": "lowres, bad anatomy, bad hands, text, error, missing fingers, extra digit, fewer digits, cropped, worst quality, low quality, normal quality, jpeg artifacts, signature, watermark, username, blurry",
    "saveImageDebugInputs": False, # 图片生成调试开关 (SD/ComfyUI)
}
DEFAULT_GOOGLE_CONFIG = { "apiKey": "", "apiEndpoint": "https://generativelanguage.googleapis.com", "modelName": "gemini-1.5-flash-latest", }
DEFAULT_OPENAI_CONFIG = { "apiKey": "", "apiBaseUrl": "https://api.openai.com/v1", "modelName": "gpt-4o", "customHeaders": {} }
DEFAULT_NAI_CONFIG = {
    "naiApiKey": "", "naiImageSaveDir": "", "naiModel": "nai-diffusion-3", "naiSampler": "k_euler",
    "naiSteps": 28, "naiScale": 7.0, "naiSeed": -1,
    "naiRandomSeed": False, # 功能性备注: 添加 NAI 随机种子开关默认值
    "naiUcPreset": 0, "naiQualityToggle": True,
    "naiSmea": False, "naiSmeaDyn": False, "naiDynamicThresholding": False, "naiUncondScale": 1.0,
    "naiReferenceStrength": 0.6, "naiReferenceInfoExtracted": 0.7, "naiAddOriginalImage": True,
    "nai_use_proxy": False, "nai_proxy_address": "", "nai_proxy_port": "",
    "saveNaiDebugInputs": False, # NAI 调试开关
}
DEFAULT_SD_CONFIG = {
    "sdWebUiUrl": "http://127.0.0.1:7860",
    "sdOverrideModel": "", "sdOverrideVAE": "",
    "sdEnableHR": False, "sdHRScale": 2.0, "sdHRUpscaler": "Latent", "sdHRSteps": 0,
    "sdInpaintingFill": 1, "sdMaskMode": 0, "sdInpaintArea": 1, "sdResizeMode": 1
}
DEFAULT_COMFYUI_CONFIG = {
    "comfyapiUrl": "http://127.0.0.1:8188",
    "comfyWorkflowFile": "",
    "comfyCkptName": "", "comfyVaeName": "",
    "comfyLoraName": "", "comfyLoraStrengthModel": 0.7, "comfyLoraStrengthClip": 0.7,
    "comfyOutputNodeTitle": "SaveOutputImage",
    "comfyPositiveNodeTitle": "PositivePromptInput",
    "comfyNegativeNodeTitle": "NegativePromptInput",
    "comfySamplerNodeTitle": "MainSampler",
    "comfyLatentImageNodeTitle": "EmptyLatentImageNode",
    "comfyCheckpointNodeTitle": "LoadCheckpointNode",
    "comfyVAENodeTitle": "LoadVAENode",
    "comfyClipTextEncodeNodeTitle": "CLIPTextEncodeNode",
    "comfyLoraLoaderNodeTitle": "LoraLoaderNode",
    "comfyLoadImageNodeTitle": "LoadImageNode", # 用于图生图加载原图
    "comfyFaceDetailerNodeTitle": "OptionalFaceDetailer",
    "comfyTilingSamplerNodeTitle": "OptionalTilingSampler",
    # --- 新增开始 ---
    "comfyLoadMaskNodeTitle": "Load_Mask_Image", # 用于内/外绘加载蒙版图
    # --- 新增结束 ---
}
DEFAULT_GPTSOVITS_CONFIG = {
    "apiUrl": "http://127.0.0.1:9880", "model_name": "", "audioSaveDir": "", "audioPrefix": "cv_",
    "how_to_cut": "不切", "top_k": 5, "top_p": 1.0, "temperature": 1.0, "ref_free": False,
    "audio_dl_url": "", "batch_size": 1, "batch_threshold": 0.75, "split_bucket": True,
    "speed_facter": 1.0, "fragment_interval": 0.3, "parallel_infer": True,
    "repetition_penalty": 1.35, "seed": -1, "character_voice_map": {},
    "saveGsvDebugInputs": False, # GPT-SoVITS 调试开关
}


# 功能性备注: 配置类型映射 (已更新)
CONFIG_FILES = {
    "llm_global": {"path": LLM_GLOBAL_CONFIG_FILE, "defaults": DEFAULT_LLM_GLOBAL_CONFIG},
    "image_global": {"path": IMAGE_GLOBAL_CONFIG_FILE, "defaults": DEFAULT_IMAGE_GLOBAL_CONFIG},
    "image_gen_shared": {"path": IMAGE_GEN_SHARED_CONFIG_FILE, "defaults": DEFAULT_IMAGE_GEN_SHARED_CONFIG},
    "google": {"path": GOOGLE_CONFIG_FILE, "defaults": DEFAULT_GOOGLE_CONFIG},
    "openai": {"path": OPENAI_CONFIG_FILE, "defaults": DEFAULT_OPENAI_CONFIG},
    "nai": {"path": NAI_CONFIG_FILE, "defaults": DEFAULT_NAI_CONFIG},
    "sd": {"path": SD_CONFIG_FILE, "defaults": DEFAULT_SD_CONFIG},
    "comfyui": {"path": COMFYUI_CONFIG_FILE, "defaults": DEFAULT_COMFYUI_CONFIG},
    "gptsovits": {"path": GPTSOVITS_CONFIG_FILE, "defaults": DEFAULT_GPTSOVITS_CONFIG},
}

# --- 辅助函数 ---
def _ensure_config_dir():
    """确保 configs 目录存在"""
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        # 功能性备注: 记录无法创建或访问配置目录的警告
        logger.warning(f"警告：无法创建或访问配置目录 '{CONFIG_DIR}': {e}")

# --- 主要配置加载/保存函数 ---
def load_config(config_type):
    """加载指定类型的配置，若失败则返回默认配置"""
    if config_type not in CONFIG_FILES:
        # 功能性备注: 记录未知的配置类型错误
        logger.error(f"错误：未知的配置类型 '{config_type}'")
        return {}
    config_info = CONFIG_FILES[config_type]
    config_path = config_info["path"]
    defaults = config_info["defaults"].copy()
    _ensure_config_dir() # 确保目录存在
    if not config_path.exists():
        # 功能性备注: 记录配置文件未找到，将使用默认值
        logger.warning(f"配置文件 '{config_path}' 未找到，将使用默认值。")
        return defaults
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            loaded_data = json.load(f)
        # 功能性备注: 合并默认值和加载值，加载的值会覆盖默认值
        final_config = {**defaults, **loaded_data}

        # --- 功能性备注: 类型修正和校验 (已更新) ---
        # 功能性备注: 对不同配置类型进行特定的类型检查和修正
        if config_type == "llm_global":
            if final_config.get('selected_provider') not in ["Google", "OpenAI"]: final_config['selected_provider'] = defaults.get('selected_provider')
            try: final_config['temperature'] = float(final_config.get('temperature', defaults.get('temperature')))
            except: final_config['temperature'] = defaults.get('temperature')
            try: final_config['maxOutputTokens'] = int(final_config.get('maxOutputTokens', defaults.get('maxOutputTokens')))
            except: final_config['maxOutputTokens'] = defaults.get('maxOutputTokens')
            top_p_val = final_config.get('topP', defaults.get('topP')); final_config['topP'] = float(top_p_val) if top_p_val is not None else None
            top_k_val = final_config.get('topK', defaults.get('topK')); final_config['topK'] = int(top_k_val) if top_k_val is not None else None
            for key in ['saveDebugInputs', 'enableStreaming', 'use_proxy', 'enableSoundNotifications', 'enableWinNotifications']: final_config[key] = str(final_config.get(key, defaults.get(key))).lower() == 'true'
            final_config['proxy_port'] = str(final_config.get('proxy_port', defaults.get('proxy_port', '')))
            # 逻辑备注: 确保颜色配置是字符串
            color_keys = [k for k in defaults if k.startswith("ui_log_color_") or k.startswith("console_log_color_")]
            for key in color_keys:
                final_config[key] = str(final_config.get(key, defaults.get(key)))
        elif config_type == "image_global":
             if final_config.get('selected_image_provider') not in ["SD WebUI", "ComfyUI"]: final_config['selected_image_provider'] = defaults.get('selected_image_provider')
        elif config_type == "image_gen_shared":
            try: final_config['steps'] = int(final_config.get('steps', defaults.get('steps')))
            except: final_config['steps'] = defaults.get('steps')
            try: final_config['cfgScale'] = float(final_config.get('cfgScale', defaults.get('cfgScale')))
            except: final_config['cfgScale'] = defaults.get('cfgScale')
            try: final_config['width'] = int(final_config.get('width', defaults.get('width')))
            except: final_config['width'] = defaults.get('width')
            try: final_config['height'] = int(final_config.get('height', defaults.get('height')))
            except: final_config['height'] = defaults.get('height')
            try: final_config['seed'] = int(final_config.get('seed', defaults.get('seed')))
            except: final_config['seed'] = defaults.get('seed')
            # 功能性备注: 加载共享随机种子开关
            final_config['sharedRandomSeed'] = str(final_config.get('sharedRandomSeed', defaults.get('sharedRandomSeed'))).lower() == 'true'
            try: final_config['denoisingStrength'] = float(final_config.get('denoisingStrength', defaults.get('denoisingStrength')))
            except: final_config['denoisingStrength'] = defaults.get('denoisingStrength')
            try: final_config['clipSkip'] = int(final_config.get('clipSkip', defaults.get('clipSkip')))
            except: final_config['clipSkip'] = defaults.get('clipSkip')
            try: final_config['maskBlur'] = int(final_config.get('maskBlur', defaults.get('maskBlur')))
            except: final_config['maskBlur'] = defaults.get('maskBlur')
            for key in ['restoreFaces', 'tiling', 'saveImageDebugInputs']: final_config[key] = str(final_config.get(key, defaults.get(key))).lower() == 'true' # 添加 saveImageDebugInputs
            final_config['imageSaveDir'] = str(final_config.get('imageSaveDir', defaults.get('imageSaveDir', '')))
            final_config['sampler'] = str(final_config.get('sampler', defaults.get('sampler', '')))
            final_config['scheduler'] = str(final_config.get('scheduler', defaults.get('scheduler', '')))
            final_config['additionalPositivePrompt'] = str(final_config.get('additionalPositivePrompt', defaults.get('additionalPositivePrompt', '')))
            final_config['additionalNegativePrompt'] = str(final_config.get('additionalNegativePrompt', defaults.get('additionalNegativePrompt', '')))
        elif config_type == "google":
            if 'apiEndpoint' in final_config and final_config.get('apiEndpoint'): final_config['apiEndpoint'] = str(final_config['apiEndpoint']).rstrip('/')
        elif config_type == "openai":
            if 'apiBaseUrl' in final_config and final_config.get('apiBaseUrl'): final_config['apiBaseUrl'] = str(final_config['apiBaseUrl']).rstrip('/')
            if 'customHeaders' not in final_config or not isinstance(final_config['customHeaders'], dict): final_config['customHeaders'] = defaults.get('customHeaders', {})
        elif config_type == "nai":
            try: final_config['naiSteps'] = int(final_config.get('naiSteps', defaults.get('naiSteps')))
            except: final_config['naiSteps'] = defaults.get('naiSteps')
            try: final_config['naiScale'] = float(final_config.get('naiScale', defaults.get('naiScale')))
            except: final_config['naiScale'] = defaults.get('naiScale')
            try: final_config['naiSeed'] = int(final_config.get('naiSeed', defaults.get('naiSeed')))
            except: final_config['naiSeed'] = defaults.get('naiSeed')
            # 功能性备注: 加载 NAI 随机种子开关
            final_config['naiRandomSeed'] = str(final_config.get('naiRandomSeed', defaults.get('naiRandomSeed'))).lower() == 'true'
            try: final_config['naiUcPreset'] = int(final_config.get('naiUcPreset', defaults.get('naiUcPreset')))
            except: final_config['naiUcPreset'] = defaults.get('naiUcPreset')
            try: final_config['naiUncondScale'] = float(final_config.get('naiUncondScale', defaults.get('naiUncondScale')))
            except: final_config['naiUncondScale'] = defaults.get('naiUncondScale')
            try: final_config['naiReferenceStrength'] = float(final_config.get('naiReferenceStrength', defaults.get('naiReferenceStrength')))
            except: final_config['naiReferenceStrength'] = defaults.get('naiReferenceStrength')
            try: final_config['naiReferenceInfoExtracted'] = float(final_config.get('naiReferenceInfoExtracted', defaults.get('naiReferenceInfoExtracted')))
            except: final_config['naiReferenceInfoExtracted'] = defaults.get('naiReferenceInfoExtracted')
            for key in ['naiQualityToggle', 'nai_use_proxy', 'naiSmea', 'naiSmeaDyn', 'naiDynamicThresholding', 'naiAddOriginalImage', 'saveNaiDebugInputs']: # 添加 saveNaiDebugInputs
                 final_config[key] = str(final_config.get(key, defaults.get(key))).lower() == 'true'
            final_config['nai_proxy_port'] = str(final_config.get('nai_proxy_port', defaults.get('nai_proxy_port', '')))
        elif config_type == "sd":
            if 'sdWebUiUrl' in final_config and final_config.get('sdWebUiUrl'): final_config['sdWebUiUrl'] = str(final_config['sdWebUiUrl']).rstrip('/')
            final_config['sdOverrideModel'] = str(final_config.get('sdOverrideModel', defaults.get('sdOverrideModel', '')))
            final_config['sdOverrideVAE'] = str(final_config.get('sdOverrideVAE', defaults.get('sdOverrideVAE', '')))
            final_config['sdEnableHR'] = str(final_config.get('sdEnableHR', defaults.get('sdEnableHR', False))).lower() == 'true'
            try: final_config['sdHRScale'] = float(final_config.get('sdHRScale', defaults.get('sdHRScale')))
            except: final_config['sdHRScale'] = defaults.get('sdHRScale')
            final_config['sdHRUpscaler'] = str(final_config.get('sdHRUpscaler', defaults.get('sdHRUpscaler', '')))
            try: final_config['sdHRSteps'] = int(final_config.get('sdHRSteps', defaults.get('sdHRSteps')))
            except: final_config['sdHRSteps'] = defaults.get('sdHRSteps')
            try: final_config['sdInpaintingFill'] = int(final_config.get('sdInpaintingFill', defaults.get('sdInpaintingFill')))
            except: final_config['sdInpaintingFill'] = defaults.get('sdInpaintingFill')
            try: final_config['sdMaskMode'] = int(final_config.get('sdMaskMode', defaults.get('sdMaskMode')))
            except: final_config['sdMaskMode'] = defaults.get('sdMaskMode')
            try: final_config['sdInpaintArea'] = int(final_config.get('sdInpaintArea', defaults.get('sdInpaintArea')))
            except: final_config['sdInpaintArea'] = defaults.get('sdInpaintArea')
            try: final_config['sdResizeMode'] = int(final_config.get('sdResizeMode', defaults.get('sdResizeMode')))
            except: final_config['sdResizeMode'] = defaults.get('sdResizeMode')
        elif config_type == "comfyui":
            if 'comfyapiUrl' in final_config and final_config.get('comfyapiUrl'): final_config['comfyapiUrl'] = str(final_config['comfyapiUrl']).rstrip('/')
            final_config['comfyWorkflowFile'] = str(final_config.get('comfyWorkflowFile', defaults.get('comfyWorkflowFile', '')))
            final_config['comfyCkptName'] = str(final_config.get('comfyCkptName', defaults.get('comfyCkptName', '')))
            final_config['comfyVaeName'] = str(final_config.get('comfyVaeName', defaults.get('comfyVaeName', '')))
            final_config['comfyLoraName'] = str(final_config.get('comfyLoraName', defaults.get('comfyLoraName', '')))
            try: final_config['comfyLoraStrengthModel'] = float(final_config.get('comfyLoraStrengthModel', defaults.get('comfyLoraStrengthModel')))
            except: final_config['comfyLoraStrengthModel'] = defaults.get('comfyLoraStrengthModel')
            try: final_config['comfyLoraStrengthClip'] = float(final_config.get('comfyLoraStrengthClip', defaults.get('comfyLoraStrengthClip')))
            except: final_config['comfyLoraStrengthClip'] = defaults.get('comfyLoraStrengthClip')
            # 逻辑备注: 将新的 key 添加到 node_title_keys 列表中
            node_title_keys = [
                "comfyOutputNodeTitle", "comfyPositiveNodeTitle", "comfyNegativeNodeTitle",
                "comfySamplerNodeTitle", "comfyLatentImageNodeTitle", "comfyCheckpointNodeTitle",
                "comfyVAENodeTitle", "comfyClipTextEncodeNodeTitle", "comfyLoraLoaderNodeTitle",
                "comfyLoadImageNodeTitle", "comfyFaceDetailerNodeTitle", "comfyTilingSamplerNodeTitle",
                # --- 新增开始 ---
                "comfyLoadMaskNodeTitle",
                # --- 新增结束 ---
            ]
            for key in node_title_keys:
                 final_config[key] = str(final_config.get(key, defaults.get(key, "")))
        elif config_type == "gptsovits":
            final_config['model_name'] = str(final_config.get('model_name', defaults.get('model_name', '')))
            try: final_config['top_k'] = int(final_config.get('top_k', defaults.get('top_k')))
            except: final_config['top_k'] = defaults.get('top_k')
            try: final_config['top_p'] = float(final_config.get('top_p', defaults.get('top_p')))
            except: final_config['top_p'] = defaults.get('top_p')
            try: final_config['temperature'] = float(final_config.get('temperature', defaults.get('temperature')))
            except: final_config['temperature'] = defaults.get('temperature')
            final_config['ref_free'] = str(final_config.get('ref_free', defaults.get('ref_free', False))).lower() == 'true'
            final_config['audio_dl_url'] = str(final_config.get('audio_dl_url', defaults.get('audio_dl_url', '')))
            try: final_config['batch_size'] = int(final_config.get('batch_size', defaults.get('batch_size')))
            except: final_config['batch_size'] = defaults.get('batch_size')
            try: final_config['batch_threshold'] = float(final_config.get('batch_threshold', defaults.get('batch_threshold')))
            except: final_config['batch_threshold'] = defaults.get('batch_threshold')
            final_config['split_bucket'] = str(final_config.get('split_bucket', defaults.get('split_bucket', True))).lower() == 'true'
            try: final_config['speed_facter'] = float(final_config.get('speed_facter', defaults.get('speed_facter')))
            except: final_config['speed_facter'] = defaults.get('speed_facter')
            try: final_config['fragment_interval'] = float(final_config.get('fragment_interval', defaults.get('fragment_interval')))
            except: final_config['fragment_interval'] = defaults.get('fragment_interval')
            final_config['parallel_infer'] = str(final_config.get('parallel_infer', defaults.get('parallel_infer', True))).lower() == 'true'
            try: final_config['repetition_penalty'] = float(final_config.get('repetition_penalty', defaults.get('repetition_penalty')))
            except: final_config['repetition_penalty'] = defaults.get('repetition_penalty')
            try: final_config['seed'] = int(final_config.get('seed', defaults.get('seed')))
            except: final_config['seed'] = defaults.get('seed')
            final_config['saveGsvDebugInputs'] = str(final_config.get('saveGsvDebugInputs', defaults.get('saveGsvDebugInputs'))).lower() == 'true' # 添加 saveGsvDebugInputs
            if 'character_voice_map' not in final_config or not isinstance(final_config['character_voice_map'], dict): final_config['character_voice_map'] = {}
            else: valid_map = {name: data for name, data in final_config['character_voice_map'].items() if isinstance(data, dict)}; final_config['character_voice_map'] = valid_map
            if 'apiUrl' in final_config and final_config.get('apiUrl'): final_config['apiUrl'] = str(final_config['apiUrl']).rstrip('/')

        # 功能性备注: 记录加载和校验完成
        logger.info(f"配置 '{config_type}' 已从 '{config_path}' 加载并校验。")
        return final_config
    except json.JSONDecodeError as e:
        # 功能性备注: 记录 JSON 解析错误
        logger.error(f"错误：解析配置文件 '{config_path}' 失败: {e}。将使用默认值。")
        messagebox.showerror("配置加载错误", f"配置文件 '{config_path.name}' 格式错误或已损坏。\n错误: {e}\n\n将使用默认设置。", parent=None)
        return defaults
    except Exception as e:
        # 功能性备注: 记录其他加载错误
        logger.exception(f"错误：加载配置文件 '{config_path}' 时发生意外错误: {e}。将使用默认值。")
        messagebox.showerror("配置加载错误", f"加载配置文件 '{config_path.name}' 时发生错误。\n错误: {e}\n\n将使用默认设置。", parent=None)
        return defaults

def save_config(config_type, data):
    """保存配置数据到 JSON 文件"""
    if config_type not in CONFIG_FILES:
        # 功能性备注: 记录尝试保存未知配置类型的错误
        logger.error(f"错误：尝试保存未知的配置类型 '{config_type}'")
        return False
    config_path = CONFIG_FILES[config_type]["path"]
    _ensure_config_dir() # 确保目录存在
    data_to_save = data
    try:
        with open(config_path, 'w', encoding='utf-8') as f:
            # 功能性备注: 使用 ensure_ascii=False 保证中文等正确写入，indent=4 美化格式
            json.dump(data_to_save, f, ensure_ascii=False, indent=4)
        # 功能性备注: 记录保存成功
        logger.info(f"配置 '{config_type}' 已成功保存到 '{config_path}'。")
        return True
    except TypeError as e:
        # 功能性备注: 记录数据类型错误
        logger.exception(f"错误：保存配置 '{config_type}' 到 '{config_path}' 时发生数据类型错误: {e}。")
        messagebox.showerror("保存错误", f"保存配置 '{config_type}' 时遇到无法处理的数据类型。\n错误: {e}", parent=None)
        return False
    except Exception as e:
        # 功能性备注: 记录其他保存错误
        logger.exception(f"错误：保存配置 '{config_type}' 到 '{config_path}' 时发生意外错误: {e}。")
        messagebox.showerror("保存错误", f"保存配置文件 '{config_path.name}' 时发生错误。\n错误: {e}", parent=None)
        return False

# --- 加载/保存 Character Profiles ---
def load_character_profiles_from_file(parent_window):
    """加载人物设定 JSON 文件"""
    try:
        filepath = filedialog.askopenfilename(title="加载人物设定文件", filetypes=[("JSON 文件", "*.json"), ("所有文件", "*.*")], parent=parent_window)
        if not filepath: return None # 用户取消
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                profiles = json.load(f)
            if not isinstance(profiles, dict):
                # 功能性备注: 记录文件内容不是有效 JSON 对象的错误
                logger.error(f"加载错误：文件 '{filepath}' 内容不是有效的 JSON 对象 (字典)。")
                messagebox.showerror("加载错误", "选择的文件内容不是有效的 JSON 对象 (字典)。", parent=parent_window)
                return None
            # 功能性备注: 处理旧格式迁移和字段补充
            migrated_profiles = {}
            migration_needed = False
            for name_key, data in profiles.items():
                if isinstance(data, dict):
                    new_data = data.copy() # 使用副本操作
                    # 功能性备注: 处理旧格式迁移 (确保 display_name 和 replacement_name 存在)
                    if "display_name" not in new_data:
                         new_data["display_name"] = name_key
                         migration_needed = True
                    if "replacement_name" not in new_data:
                         new_data["replacement_name"] = ""
                         migration_needed = True # 也视为需要迁移
                    # 功能性备注: 确保 image_path 和 mask_path 存在
                    if "image_path" not in new_data:
                        new_data["image_path"] = ""
                        migration_needed = True
                    if "mask_path" not in new_data:
                        new_data["mask_path"] = ""
                        migration_needed = True
                    migrated_profiles[name_key] = new_data
                else:
                    # 功能性备注: 记录忽略无效数据格式的警告
                    logger.warning(f"警告：加载人物设定时，Key '{name_key}' 的值不是字典，已忽略。")

            if migration_needed:
                # 功能性备注: 提示用户格式已更新
                messagebox.showinfo("格式更新", "加载的人物设定文件格式已更新或补充了字段。", parent=parent_window)
            # 功能性备注: 记录加载成功
            logger.info(f"人物设定已从 '{filepath}' 加载并处理。")
            return migrated_profiles, filepath
        except json.JSONDecodeError as e:
            # 功能性备注: 记录 JSON 解析错误
            logger.error(f"加载错误：解析文件 '{os.path.basename(filepath)}' 时出错: {e}")
            messagebox.showerror("加载错误", f"解析文件 '{os.path.basename(filepath)}' 时出错: {e}", parent=parent_window)
            return None
        except Exception as e:
            # 功能性备注: 记录其他读取错误
            logger.exception(f"加载错误：读取文件 '{os.path.basename(filepath)}' 时发生错误: {e}")
            messagebox.showerror("加载错误", f"读取文件 '{os.path.basename(filepath)}' 时发生错误: {e}", parent=parent_window)
            return None
    except Exception as e:
        # 功能性备注: 记录打开文件对话框错误
        logger.exception(f"错误：打开文件对话框时出错: {e}")
        messagebox.showerror("错误", f"无法打开文件选择对话框: {e}", parent=parent_window)
        return None

def save_character_profiles_to_file(profiles, parent_window):
    """保存人物设定到 JSON 文件"""
    if not profiles: return False # 如果没有设定则不保存
    try:
        filepath = filedialog.asksaveasfilename(title="保存人物设定到文件", defaultextension=".json", filetypes=[("JSON 文件", "*.json"), ("所有文件", "*.*")], initialfile="character_profiles.json", parent=parent_window)
        if not filepath: return False # 用户取消
        try:
            # 功能性备注: 确保每个条目都有 image_path 和 mask_path
            profiles_to_save = {}
            for key, data in profiles.items():
                if isinstance(data, dict):
                    data_copy = data.copy()
                    if "image_path" not in data_copy:
                        data_copy["image_path"] = ""
                    if "mask_path" not in data_copy:
                        data_copy["mask_path"] = ""
                    profiles_to_save[key] = data_copy
                else:
                    profiles_to_save[key] = data # 保留非字典数据（虽然理论上不应出现）

            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(profiles_to_save, f, ensure_ascii=False, indent=4)
            # 功能性备注: 记录保存成功
            logger.info(f"人物设定已成功保存到 '{filepath}'。")
            return True
        except TypeError as e:
            # 功能性备注: 记录数据类型错误
            logger.exception(f"保存错误：保存人物设定时遇到无法处理的数据类型: {e}")
            messagebox.showerror("保存错误", f"保存人物设定时遇到无法处理的数据类型: {e}", parent=parent_window)
            return False
        except Exception as e:
            # 功能性备注: 记录其他写入错误
            logger.exception(f"保存错误：写入文件 '{os.path.basename(filepath)}' 时发生错误: {e}")
            messagebox.showerror("保存错误", f"写入文件 '{os.path.basename(filepath)}' 时发生错误: {e}", parent=parent_window)
            return False
    except Exception as e:
        # 功能性备注: 记录打开文件保存对话框错误
        logger.exception(f"错误：打开文件保存对话框时出错: {e}")
        messagebox.showerror("错误", f"无法打开文件保存对话框: {e}", parent=parent_window)
        return False

# --- 加载 NAI 模型列表 ---
def load_nai_models(default_path="assets/nai_models.json"):
    """加载 NAI 模型列表 JSON 文件"""
    model_path = Path(default_path)
    if not model_path.exists():
        # 功能性备注: 记录模型列表文件未找到的警告
        logger.warning(f"警告: NAI 模型列表文件 '{model_path}' 未找到。")
        return []
    try:
        with open(model_path, 'r', encoding='utf-8') as f:
            models = json.load(f)
        # 功能性备注: 校验加载的数据格式
        if not isinstance(models, list): raise TypeError("顶层结构不是列表")
        if not all(isinstance(m, dict) for m in models): raise TypeError("包含非字典元素")
        if not all('name' in m and 'value' in m for m in models): raise TypeError("缺少 'name' 或 'value' 键")
        # 功能性备注: 记录加载成功
        logger.info(f"NAI 模型列表已从 '{model_path}' 加载 ({len(models)} 个模型)。")
        return models
    except Exception as e:
        # 功能性备注: 记录加载或解析错误
        logger.exception(f"错误: 加载或解析 NAI 模型文件 '{model_path}' 失败: {e}")
        return []

# --- 更新 HELP_DATA ---
from core.help_data import HELP_DATA # 导入 HELP_DATA

# 功能性备注: 添加新的调试开关帮助信息
if "image_gen_shared" in HELP_DATA:
    HELP_DATA["image_gen_shared"]["saveImageDebugInputs"] = {
        "key": "saveImageDebugInputs", "name": "保存图片生成调试输入",
        "desc": "是否将 SD WebUI 或 ComfyUI API 的输入参数 (Payload) 保存到 debug_logs 目录以供调试。\n注意：可能会包含大量 Base64 编码的图片数据，占用较多空间。",
        "default": "False"
    }
if "nai" in HELP_DATA:
    HELP_DATA["nai"]["saveNaiDebugInputs"] = {
        "key": "saveNaiDebugInputs", "name": "保存 NAI 调试输入",
        "desc": "是否将 NAI API 的输入参数 (Payload) 保存到 debug_logs 目录以供调试。\n注意：会移除 API Key，但可能包含 Base64 图片数据。",
        "default": "False"
    }
if "gptsovits" in HELP_DATA:
    HELP_DATA["gptsovits"]["saveGsvDebugInputs"] = {
        "key": "saveGsvDebugInputs", "name": "保存 GPT-SoVITS 调试输入",
        "desc": "是否将 GPT-SoVITS API 的输入参数 (Payload) 保存到 debug_logs 目录以供调试。\n注意：会移除 Base64 音频数据。",
        "default": "False"
    }

# --- 功能性备注: 添加新的颜色配置帮助信息 ---
if "llm_global" in HELP_DATA:
    color_help_base = {
        "ui_log_color_debug": {"key": "ui_log_color_debug", "name": "UI日志颜色-Debug", "desc": "日志界面中 DEBUG 级别日志的显示颜色 (十六进制)。实时生效。", "default": "#ADD8E6"},
        "ui_log_color_info": {"key": "ui_log_color_info", "name": "UI日志颜色-Info", "desc": "日志界面中 INFO 级别日志的显示颜色 (十六进制)。实时生效。", "default": "#3CB371"},
        "ui_log_color_warning": {"key": "ui_log_color_warning", "name": "UI日志颜色-Warning", "desc": "日志界面中 WARNING 级别日志的显示颜色 (名称或十六进制)。实时生效。", "default": "orange"},
        "ui_log_color_error": {"key": "ui_log_color_error", "name": "UI日志颜色-Error", "desc": "日志界面中 ERROR 级别日志的显示颜色 (十六进制)。实时生效。", "default": "#ff5f5f"},
        "ui_log_color_critical": {"key": "ui_log_color_critical", "name": "UI日志颜色-Critical", "desc": "日志界面中 CRITICAL 级别日志的显示颜色 (十六进制)。实时生效。", "default": "#ff0000"},
        "console_log_color_debug": {"key": "console_log_color_debug", "name": "控制台颜色-Debug", "desc": "控制台中 DEBUG 级别日志的显示颜色 (Colorama 名称，如 DIM, CYAN)。下次启动生效。", "default": "DIM"},
        "console_log_color_info": {"key": "console_log_color_info", "name": "控制台颜色-Info", "desc": "控制台中 INFO 级别日志的显示颜色 (Colorama 名称，如 GREEN)。下次启动生效。", "default": "GREEN"},
        "console_log_color_warning": {"key": "console_log_color_warning", "name": "控制台颜色-Warning", "desc": "控制台中 WARNING 级别日志的显示颜色 (Colorama 名称，如 YELLOW)。下次启动生效。", "default": "YELLOW"},
        "console_log_color_error": {"key": "console_log_color_error", "name": "控制台颜色-Error", "desc": "控制台中 ERROR 级别日志的显示颜色 (Colorama 名称，如 RED)。下次启动生效。", "default": "RED"},
        "console_log_color_critical": {"key": "console_log_color_critical", "name": "控制台颜色-Critical", "desc": "控制台中 CRITICAL 级别日志的显示颜色 (Colorama 名称，如 BRIGHT_RED)。下次启动生效。", "default": "BRIGHT_RED"},
    }
    HELP_DATA["llm_global"].update(color_help_base)

# 功能性备注: 添加新的随机种子开关帮助信息
if "image_gen_shared" in HELP_DATA:
    HELP_DATA["image_gen_shared"]["sharedRandomSeed"] = {
        "key": "sharedRandomSeed", "name": "客户端随机种子",
        "desc": "勾选此项后，程序将在调用 API 时忽略上方输入的种子值，并在客户端生成一个随机的正整数种子发送给服务端。",
        "default": "False"
    }
if "nai" in HELP_DATA:
    HELP_DATA["nai"]["naiRandomSeed"] = {
        "key": "naiRandomSeed", "name": "客户端随机种子",
        "desc": "勾选此项后，程序将在调用 NAI API 时忽略上方输入的种子值，并在客户端生成一个随机的正整数种子发送给 NAI。",
        "default": "False"
    }

# --- 新增：添加 ComfyUI 加载蒙版节点标题的帮助信息 ---
if "comfyui" in HELP_DATA:
    HELP_DATA["comfyui"]["comfyLoadMaskNodeTitle"] = {
        "key": "comfyLoadMaskNodeTitle",
        "name": "加载蒙版节点标题 (内/外绘)",
        "desc": "工作流中用于加载内/外绘蒙版图像的 LoadImage 节点的标题。\n程序会设置其 'image' 输入（使用上传后的蒙版文件名）。\n重要：该蒙版文件必须位于 ComfyUI 服务器的 'input' 目录下。",
        "default": "Load_Mask_Image"
    }