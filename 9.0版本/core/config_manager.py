# core/config_manager.py
import json
import os
import traceback
from pathlib import Path
from tkinter import messagebox, filedialog

# --- 常量定义 ---
CONFIG_DIR = Path("configs")
LLM_CONFIG_FILE = CONFIG_DIR / "llm_global_config.json"
NAI_CONFIG_FILE = CONFIG_DIR / "nai_config.json"
SD_CONFIG_FILE = CONFIG_DIR / "sd_config.json"
GPTSOVITS_CONFIG_FILE = CONFIG_DIR / "gptsovits_config.json"

# --- 默认配置字典 ---
DEFAULT_LLM_GLOBAL_CONFIG = {
    "apiKey": "", "apiEndpoint": "https://generativelanguage.googleapis.com",
    "modelName": "gemini-1.5-flash-latest", "temperature": 0.2, "maxOutputTokens": 8192,
    "topP": None, "topK": None, # 新增：默认不设置 Top P/K
    "preInstruction": "", "postInstruction": "",
    "successSoundPath": "assets/success.wav", "failureSoundPath": "assets/failure.wav",
    "saveDebugInputs": False, "enableStreaming": True,
    "use_proxy": False, "proxy_address": "", "proxy_port": "",
    "enableSoundNotifications": True, "enableWinNotifications": True,
}
DEFAULT_NAI_CONFIG = {
    "naiApiKey": "", "naiImageSaveDir": "", "naiModel": "nai-diffusion-3",
    "naiSampler": "k_euler", "naiSteps": 28, "naiScale": 7.0, "naiSeed": -1,
    "naiUcPreset": 0, "naiQualityToggle": True,
    "nai_use_proxy": False, "nai_proxy_address": "", "nai_proxy_port": ""
}
DEFAULT_SD_CONFIG = {
    "sdWebUiUrl": "http://127.0.0.1:7860", "sdImageSaveDir": "", "sdSampler": "Euler a",
    "sdSteps": 20, "sdCfgScale": 7.0, "sdWidth": 512, "sdHeight": 512, "sdSeed": -1,
    "sdRestoreFaces": False, "sdTiling": False,
    "sdAdditionalPositivePrompt": "masterpiece, best quality",
    "sdAdditionalNegativePrompt": "lowres, bad anatomy, bad hands, text, error, missing fingers, extra digit, fewer digits, cropped, worst quality, low quality, normal quality, jpeg artifacts, signature, watermark, username, blurry"
}
DEFAULT_GPTSOVITS_CONFIG = {
    "apiUrl": "http://127.0.0.1:9880", "model_name": "", "audioSaveDir": "", "audioPrefix": "cv_",
    "how_to_cut": "不切", "top_k": 5, "top_p": 1.0, "temperature": 1.0, "ref_free": False,
    "audio_dl_url": "", "batch_size": 1, "batch_threshold": 0.75, "split_bucket": True,
    "speed_facter": 1.0, "fragment_interval": 0.3, "parallel_infer": True,
    "repetition_penalty": 1.35, "seed": -1, "character_voice_map": {}
}

# 配置类型映射
CONFIG_FILES = {
    "llm_global": {"path": LLM_CONFIG_FILE, "defaults": DEFAULT_LLM_GLOBAL_CONFIG},
    "nai": {"path": NAI_CONFIG_FILE, "defaults": DEFAULT_NAI_CONFIG},
    "sd": {"path": SD_CONFIG_FILE, "defaults": DEFAULT_SD_CONFIG},
    "gptsovits": {"path": GPTSOVITS_CONFIG_FILE, "defaults": DEFAULT_GPTSOVITS_CONFIG},
}

# --- 辅助函数 ---
def _ensure_config_dir():
    """确保 configs 目录存在"""
    try: CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    except Exception as e: print(f"警告：无法创建或访问配置目录 '{CONFIG_DIR}': {e}")

# --- 主要配置加载/保存函数 ---
def load_config(config_type):
    """加载指定类型的配置，若失败则返回默认配置"""
    if config_type not in CONFIG_FILES: print(f"错误：未知的配置类型 '{config_type}'"); return {}
    config_info = CONFIG_FILES[config_type]
    config_path = config_info["path"]
    defaults = config_info["defaults"].copy()
    _ensure_config_dir()
    if not config_path.exists(): print(f"配置文件 '{config_path}' 未找到，将使用默认值。"); return defaults
    try:
        with open(config_path, 'r', encoding='utf-8') as f: loaded_data = json.load(f)
        final_config = {**defaults, **loaded_data}

        # --- 类型修正和校验 ---
        if config_type == "llm_global":
            # 修正数字类型 (Temperature, Max Tokens)
            try: final_config['temperature'] = float(final_config.get('temperature', defaults.get('temperature')))
            except (ValueError, TypeError): final_config['temperature'] = defaults.get('temperature')
            try: final_config['maxOutputTokens'] = int(final_config.get('maxOutputTokens', defaults.get('maxOutputTokens')))
            except (ValueError, TypeError): final_config['maxOutputTokens'] = defaults.get('maxOutputTokens')
            # 修正 Top P (float or None)
            top_p_val = final_config.get('topP', defaults.get('topP'))
            if top_p_val is not None:
                try: final_config['topP'] = float(top_p_val); assert 0.0 <= final_config['topP'] <= 1.0
                except: final_config['topP'] = defaults.get('topP') # 无效则回退默认
            else: final_config['topP'] = None # 保持 None
            # 修正 Top K (int or None)
            top_k_val = final_config.get('topK', defaults.get('topK'))
            if top_k_val is not None:
                try: final_config['topK'] = int(top_k_val); assert final_config['topK'] >= 1
                except: final_config['topK'] = defaults.get('topK') # 无效则回退默认
            else: final_config['topK'] = None # 保持 None
            # 修正布尔类型
            for key in ['saveDebugInputs', 'enableStreaming', 'use_proxy', 'enableSoundNotifications', 'enableWinNotifications']:
                default_val = defaults.get(key, True if key.startswith('enable') else False)
                final_config[key] = str(final_config.get(key, default_val)).lower() == 'true'
            final_config['proxy_port'] = str(final_config.get('proxy_port', defaults.get('proxy_port', '')))
        elif config_type == "nai":
            try: final_config['naiSteps'] = int(final_config.get('naiSteps', defaults.get('naiSteps')))
            except (ValueError, TypeError): final_config['naiSteps'] = defaults.get('naiSteps')
            try: final_config['naiScale'] = float(final_config.get('naiScale', defaults.get('naiScale')))
            except (ValueError, TypeError): final_config['naiScale'] = defaults.get('naiScale')
            try: final_config['naiSeed'] = int(final_config.get('naiSeed', defaults.get('naiSeed')))
            except (ValueError, TypeError): final_config['naiSeed'] = defaults.get('naiSeed')
            try: final_config['naiUcPreset'] = int(final_config.get('naiUcPreset', defaults.get('naiUcPreset')))
            except (ValueError, TypeError): final_config['naiUcPreset'] = defaults.get('naiUcPreset')
            for key in ['naiQualityToggle', 'nai_use_proxy']: final_config[key] = str(final_config.get(key, defaults.get(key, False))).lower() == 'true'
            final_config['nai_proxy_port'] = str(final_config.get('nai_proxy_port', defaults.get('nai_proxy_port', '')))
        elif config_type == "sd":
            try: final_config['sdSteps'] = int(final_config.get('sdSteps', defaults.get('sdSteps')))
            except (ValueError, TypeError): final_config['sdSteps'] = defaults.get('sdSteps')
            try: final_config['sdCfgScale'] = float(final_config.get('sdCfgScale', defaults.get('sdCfgScale')))
            except (ValueError, TypeError): final_config['sdCfgScale'] = defaults.get('sdCfgScale')
            try: final_config['sdWidth'] = int(final_config.get('sdWidth', defaults.get('sdWidth')))
            except (ValueError, TypeError): final_config['sdWidth'] = defaults.get('sdWidth')
            try: final_config['sdHeight'] = int(final_config.get('sdHeight', defaults.get('sdHeight')))
            except (ValueError, TypeError): final_config['sdHeight'] = defaults.get('sdHeight')
            try: final_config['sdSeed'] = int(final_config.get('sdSeed', defaults.get('sdSeed')))
            except (ValueError, TypeError): final_config['sdSeed'] = defaults.get('sdSeed')
            for key in ['sdRestoreFaces', 'sdTiling']: final_config[key] = str(final_config.get(key, defaults.get(key, False))).lower() == 'true'
            if 'sdWebUiUrl' in final_config and final_config.get('sdWebUiUrl'): final_config['sdWebUiUrl'] = str(final_config['sdWebUiUrl']).rstrip('/')
        elif config_type == "gptsovits":
            final_config['model_name'] = str(final_config.get('model_name', defaults.get('model_name', '')))
            try: final_config['top_k'] = int(final_config.get('top_k', defaults.get('top_k')))
            except (ValueError, TypeError): final_config['top_k'] = defaults.get('top_k')
            try: final_config['top_p'] = float(final_config.get('top_p', defaults.get('top_p')))
            except (ValueError, TypeError): final_config['top_p'] = defaults.get('top_p')
            try: final_config['temperature'] = float(final_config.get('temperature', defaults.get('temperature')))
            except (ValueError, TypeError): final_config['temperature'] = defaults.get('temperature')
            final_config['ref_free'] = str(final_config.get('ref_free', defaults.get('ref_free', False))).lower() == 'true'
            final_config['audio_dl_url'] = str(final_config.get('audio_dl_url', defaults.get('audio_dl_url', '')))
            try: final_config['batch_size'] = int(final_config.get('batch_size', defaults.get('batch_size')))
            except (ValueError, TypeError): final_config['batch_size'] = defaults.get('batch_size')
            try: final_config['batch_threshold'] = float(final_config.get('batch_threshold', defaults.get('batch_threshold')))
            except (ValueError, TypeError): final_config['batch_threshold'] = defaults.get('batch_threshold')
            final_config['split_bucket'] = str(final_config.get('split_bucket', defaults.get('split_bucket', True))).lower() == 'true'
            try: final_config['speed_facter'] = float(final_config.get('speed_facter', defaults.get('speed_facter')))
            except (ValueError, TypeError): final_config['speed_facter'] = defaults.get('speed_facter')
            try: final_config['fragment_interval'] = float(final_config.get('fragment_interval', defaults.get('fragment_interval')))
            except (ValueError, TypeError): final_config['fragment_interval'] = defaults.get('fragment_interval')
            final_config['parallel_infer'] = str(final_config.get('parallel_infer', defaults.get('parallel_infer', True))).lower() == 'true'
            try: final_config['repetition_penalty'] = float(final_config.get('repetition_penalty', defaults.get('repetition_penalty')))
            except (ValueError, TypeError): final_config['repetition_penalty'] = defaults.get('repetition_penalty')
            try: final_config['seed'] = int(final_config.get('seed', defaults.get('seed')))
            except (ValueError, TypeError): final_config['seed'] = defaults.get('seed')
            if 'character_voice_map' not in final_config or not isinstance(final_config['character_voice_map'], dict): final_config['character_voice_map'] = {}
            else: valid_map = {name: data for name, data in final_config['character_voice_map'].items() if isinstance(data, dict)}; final_config['character_voice_map'] = valid_map
            if 'apiUrl' in final_config and final_config.get('apiUrl'): final_config['apiUrl'] = str(final_config['apiUrl']).rstrip('/')

        print(f"配置 '{config_type}' 已从 '{config_path}' 加载并校验。")
        return final_config
    except json.JSONDecodeError as e: print(f"错误：解析配置文件 '{config_path}' 失败: {e}。将使用默认值。"); traceback.print_exc(); messagebox.showerror("配置加载错误", f"配置文件 '{config_path.name}' 格式错误或已损坏。\n错误: {e}\n\n将使用默认设置。", parent=None); return defaults
    except Exception as e: print(f"错误：加载配置文件 '{config_path}' 时发生意外错误: {e}。将使用默认值。"); traceback.print_exc(); messagebox.showerror("配置加载错误", f"加载配置文件 '{config_path.name}' 时发生错误。\n错误: {e}\n\n将使用默认设置。", parent=None); return defaults

def save_config(config_type, data):
    """保存配置数据到 JSON 文件"""
    if config_type not in CONFIG_FILES: print(f"错误：尝试保存未知的配置类型 '{config_type}'"); return False
    config_path = CONFIG_FILES[config_type]["path"]; _ensure_config_dir(); data_to_save = data
    try:
        with open(config_path, 'w', encoding='utf-8') as f: json.dump(data_to_save, f, ensure_ascii=False, indent=4)
        print(f"配置 '{config_type}' 已成功保存到 '{config_path}'。"); return True
    except TypeError as e: print(f"错误：保存配置 '{config_type}' 到 '{config_path}' 时发生数据类型错误: {e}。"); traceback.print_exc(); messagebox.showerror("保存错误", f"保存配置 '{config_type}' 时遇到无法处理的数据类型。\n错误: {e}", parent=None); return False
    except Exception as e: print(f"错误：保存配置 '{config_type}' 到 '{config_path}' 时发生意外错误: {e}。"); traceback.print_exc(); messagebox.showerror("保存错误", f"保存配置文件 '{config_path.name}' 时发生错误。\n错误: {e}", parent=None); return False

# --- 加载/保存 Character Profiles ---
def load_character_profiles_from_file(parent_window):
    """加载人物设定 JSON 文件 (包含旧格式迁移)"""
    try:
        filepath = filedialog.askopenfilename(title="加载人物设定文件", filetypes=[("JSON 文件", "*.json"), ("所有文件", "*.*")], parent=parent_window)
        if not filepath: return None
        try:
            with open(filepath, 'r', encoding='utf-8') as f: profiles = json.load(f)
            if not isinstance(profiles, dict): messagebox.showerror("加载错误", "选择的文件内容不是有效的 JSON 对象 (字典)。", parent=parent_window); return None
            migrated_profiles = {}; migration_needed = False
            for name_key, data in profiles.items():
                if isinstance(data, dict):
                    if "display_name" not in data: migration_needed = True; migrated_profiles[name_key] = {"display_name": name_key, "replacement_name": "", "positive": data.get("positive", ""), "negative": data.get("negative", "")}
                    else:
                        if "replacement_name" not in data: data["replacement_name"] = ""
                        migrated_profiles[name_key] = data
                else: print(f"警告：加载人物设定时，Key '{name_key}' 的值不是字典，已忽略。")
            if migration_needed: messagebox.showinfo("格式迁移", "加载的人物设定文件是旧格式，已自动转换为新格式。", parent=parent_window)
            print(f"人物设定已从 '{filepath}' 加载并处理。"); return migrated_profiles, filepath
        except json.JSONDecodeError as e: messagebox.showerror("加载错误", f"解析文件 '{os.path.basename(filepath)}' 时出错: {e}", parent=parent_window); return None
        except Exception as e: messagebox.showerror("加载错误", f"读取文件 '{os.path.basename(filepath)}' 时发生错误: {e}", parent=parent_window); traceback.print_exc(); return None
    except Exception as e: print(f"错误：打开文件对话框时出错: {e}"); traceback.print_exc(); messagebox.showerror("错误", f"无法打开文件选择对话框: {e}", parent=parent_window); return None

def save_character_profiles_to_file(profiles, parent_window):
    """保存人物设定到 JSON 文件"""
    if not profiles: return False
    try:
        filepath = filedialog.asksaveasfilename(title="保存人物设定到文件", defaultextension=".json", filetypes=[("JSON 文件", "*.json"), ("所有文件", "*.*")], initialfile="character_profiles.json", parent=parent_window)
        if not filepath: return False
        try:
            with open(filepath, 'w', encoding='utf-8') as f: json.dump(profiles, f, ensure_ascii=False, indent=4)
            print(f"人物设定已成功保存到 '{filepath}'。"); return True
        except TypeError as e: messagebox.showerror("保存错误", f"保存人物设定时遇到无法处理的数据类型: {e}", parent=parent_window); traceback.print_exc(); return False
        except Exception as e: messagebox.showerror("保存错误", f"写入文件 '{os.path.basename(filepath)}' 时发生错误: {e}", parent=parent_window); traceback.print_exc(); return False
    except Exception as e: print(f"错误：打开文件保存对话框时出错: {e}"); traceback.print_exc(); messagebox.showerror("错误", f"无法打开文件保存对话框: {e}", parent=parent_window); return False

# --- 加载 NAI 模型列表 ---
def load_nai_models(default_path="assets/nai_models.json"):
    """加载 NAI 模型列表 JSON 文件"""
    model_path = Path(default_path)
    if not model_path.exists(): print(f"警告: NAI 模型列表文件 '{model_path}' 未找到。"); return []
    try:
        with open(model_path, 'r', encoding='utf-8') as f: models = json.load(f)
        if not isinstance(models, list): raise TypeError("顶层结构不是列表")
        if not all(isinstance(m, dict) for m in models): raise TypeError("包含非字典元素")
        if not all('name' in m and 'value' in m for m in models): raise TypeError("缺少 'name' 或 'value' 键")
        print(f"NAI 模型列表已从 '{model_path}' 加载 ({len(models)} 个模型)。"); return models
    except Exception as e: print(f"错误: 加载或解析 NAI 模型文件 '{model_path}' 失败: {e}"); traceback.print_exc(); return []