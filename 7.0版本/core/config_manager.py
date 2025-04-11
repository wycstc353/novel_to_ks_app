# core/config_manager.py
import json
import os
import traceback
from pathlib import Path
from tkinter import messagebox, filedialog # 用于在某些错误时提示，以及文件对话框

# --- 常量定义 ---
# 配置文件的基础目录 (相对于脚本运行位置)
CONFIG_DIR = Path("configs")
# 定义各种配置文件的完整路径
LLM_CONFIG_FILE = CONFIG_DIR / "llm_global_config.json"
NAI_CONFIG_FILE = CONFIG_DIR / "nai_config.json"
SD_CONFIG_FILE = CONFIG_DIR / "sd_config.json"
GPTSOVITS_CONFIG_FILE = CONFIG_DIR / "gptsovits_config.json" # 新增 GPT-SoVITS 配置文件路径
# 注意：人物设定文件不由这里管理固定路径，而是用户选择

# --- 默认配置字典 ---
# 提供各种配置的默认值，当配置文件不存在或无效时使用
DEFAULT_LLM_GLOBAL_CONFIG = {
    "apiKey": "", # Google API Key
    "apiEndpoint": "https://generativelanguage.googleapis.com", # Google API 端点
    "modelName": "gemini-1.5-flash-latest", # 默认模型
    "temperature": 0.2, # 温度 (控制随机性)
    "maxOutputTokens": 8192, # 最大输出 Token 数
    "preInstruction": "", # 全局前置指令
    "postInstruction": "", # 全局后置指令
    "successSoundPath": "assets/success.wav", # 成功提示音路径
    "failureSoundPath": "assets/failure.wav", # 失败提示音路径
    "saveDebugInputs": False, # 是否保存 LLM 输入用于调试
    "enableStreaming": True, # 是否启用 LLM 流式传输
    "use_proxy": False, # 是否为 Google API 使用代理
    "proxy_address": "", # 代理地址
    "proxy_port": "" # 代理端口
}
DEFAULT_NAI_CONFIG = {
    "naiApiKey": "", # NovelAI API Key
    "naiImageSaveDir": "", # NAI 图片保存目录
    "naiModel": "nai-diffusion-3", # 默认 NAI 模型值
    "naiSampler": "k_euler", # 默认采样器
    "naiSteps": 28, # 默认步数
    "naiScale": 7.0, # 默认引导强度
    "naiSeed": -1, # 默认种子 (-1 随机)
    "naiUcPreset": 0, # 默认负面预设 (0: Heavy)
    "naiQualityToggle": True, # 默认开启质量标签
    "nai_use_proxy": False, # 是否为 NAI API 使用代理
    "nai_proxy_address": "", # NAI 代理地址
    "nai_proxy_port": "" # NAI 代理端口
}
DEFAULT_SD_CONFIG = {
    "sdWebUiUrl": "http://127.0.0.1:7860", # 默认 SD WebUI 地址
    "sdImageSaveDir": "", # SD 图片保存目录
    "sdSampler": "Euler a", # 默认采样器
    "sdSteps": 20, # 默认步数
    "sdCfgScale": 7.0, # 默认 CFG Scale
    "sdWidth": 512, # 默认宽度
    "sdHeight": 512, # 默认高度
    "sdSeed": -1, # 默认种子 (-1 随机)
    "sdRestoreFaces": False, # 默认不开启面部修复
    "sdTiling": False, # 默认不开启平铺
    "sdAdditionalPositivePrompt": "masterpiece, best quality", # 默认附加正向提示
    "sdAdditionalNegativePrompt": "lowres, bad anatomy, bad hands, text, error, missing fingers, extra digit, fewer digits, cropped, worst quality, low quality, normal quality, jpeg artifacts, signature, watermark, username, blurry" # 默认附加负向提示
}
# 新增 GPT-SoVITS 默认配置
DEFAULT_GPTSOVITS_CONFIG = {
    "apiUrl": "http://127.0.0.1:9880", # API 地址
    "audioSaveDir": "",             # 音频保存目录
    "audioPrefix": "cv_",           # 默认音频文件前缀
    # --- 默认生成参数 ---
    "how_to_cut": "不切",
    "top_k": 5,
    "top_p": 1.0,
    "temperature": 1.0,
    "ref_free": False,
    # --- 关键：人物语音映射 ---
    # 这个映射需要用户在 UI 中配置，这里只是示例结构
    "character_voice_map": {} # 默认为空字典
    # 示例:
    # "character_voice_map": {
    #     "远坂凛": {
    #         "refer_wav_path": "E:/GPT-SoVITS/output/slicer_opt/some_char/ref.wav",
    #         "prompt_text": "这是示例角色的参考文本",
    #         "prompt_language": "zh"
    #     }
    # }
}


# 将配置类型、文件路径和默认值关联起来
CONFIG_FILES = {
    "llm_global": {"path": LLM_CONFIG_FILE, "defaults": DEFAULT_LLM_GLOBAL_CONFIG},
    "nai": {"path": NAI_CONFIG_FILE, "defaults": DEFAULT_NAI_CONFIG},
    "sd": {"path": SD_CONFIG_FILE, "defaults": DEFAULT_SD_CONFIG},
    "gptsovits": {"path": GPTSOVITS_CONFIG_FILE, "defaults": DEFAULT_GPTSOVITS_CONFIG}, # 新增类型
}

# --- 辅助函数 ---
def _ensure_config_dir():
    """确保 configs 目录存在，如果不存在则尝试创建"""
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True) # parents=True 允许创建父目录，exist_ok=True 如果目录已存在则不报错
    except Exception as e:
        # 如果创建目录失败 (例如权限问题)，打印警告
        print(f"警告：无法创建或访问配置目录 '{CONFIG_DIR}': {e}")
        # 这里可以选择是否抛出异常或让程序继续 (当前选择继续)

# --- 主要配置加载/保存函数 ---
def load_config(config_type):
    """
    加载指定类型的配置。
    如果文件不存在或无效，返回默认配置。
    会对加载的数据进行类型检查和修正。
    """
    # 检查请求的配置类型是否已知
    if config_type not in CONFIG_FILES:
        print(f"错误：未知的配置类型 '{config_type}'")
        return {} # 返回空字典表示错误

    config_info = CONFIG_FILES[config_type]
    config_path = config_info["path"]
    # 创建默认配置的副本，避免修改原始默认值
    defaults = config_info["defaults"].copy()
    _ensure_config_dir() # 确保目录存在

    # 检查配置文件是否存在
    if not config_path.exists():
        print(f"配置文件 '{config_path}' 未找到，将使用默认值。")
        return defaults # 文件不存在，返回默认配置

    # --- 读取和解析配置文件 ---
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            loaded_data = json.load(f) # 从文件加载 JSON 数据

        # 合并默认配置和加载的数据
        # 加载的数据会覆盖默认值中同名的键
        final_config = {**defaults, **loaded_data}

        # --- 类型修正和校验 ---
        # 对特定配置类型中的字段进行类型检查和转换，增强鲁棒性
        if config_type == "llm_global":
            # Temperature (float)
            temp_val = final_config.get('temperature')
            if temp_val is not None:
                try: final_config['temperature'] = float(temp_val)
                except (ValueError, TypeError):
                    print(f"警告(LLM): 配置文件中的 temperature '{temp_val}' 无效，将使用默认值。")
                    final_config['temperature'] = defaults.get('temperature')
            else: final_config['temperature'] = defaults.get('temperature') # 如果键不存在，也用默认值

            # Max Tokens (int)
            max_tokens_val = final_config.get('maxOutputTokens')
            if max_tokens_val is not None:
                 try: final_config['maxOutputTokens'] = int(max_tokens_val)
                 except (ValueError, TypeError):
                     print(f"警告(LLM): 配置文件中的 maxOutputTokens '{max_tokens_val}' 无效，将使用默认值。")
                     final_config['maxOutputTokens'] = defaults.get('maxOutputTokens')
            else: final_config['maxOutputTokens'] = defaults.get('maxOutputTokens')

            # Booleans (确保是 bool 类型)
            for key in ['saveDebugInputs', 'enableStreaming', 'use_proxy']:
                if key in final_config and not isinstance(final_config[key], bool):
                    # 尝试将字符串 'true'/'false' (忽略大小写) 转为布尔值
                    final_config[key] = str(final_config.get(key)).lower() == 'true'

            # Proxy Port (确保是 string)
            final_config['proxy_port'] = str(final_config.get('proxy_port', defaults.get('proxy_port', '')))

        elif config_type == "nai":
            # NAI Steps (int)
            steps_val = final_config.get('naiSteps')
            if steps_val is not None:
                try: final_config['naiSteps'] = int(steps_val)
                except (ValueError, TypeError):
                    print(f"警告(NAI): 配置文件中的 naiSteps '{steps_val}' 无效，将使用默认值。")
                    final_config['naiSteps'] = defaults.get('naiSteps')
            else: final_config['naiSteps'] = defaults.get('naiSteps')

            # NAI Scale (float)
            scale_val = final_config.get('naiScale')
            if scale_val is not None:
                try: final_config['naiScale'] = float(scale_val)
                except (ValueError, TypeError):
                    print(f"警告(NAI): 配置文件中的 naiScale '{scale_val}' 无效，将使用默认值。")
                    final_config['naiScale'] = defaults.get('naiScale')
            else: final_config['naiScale'] = defaults.get('naiScale')

            # NAI Seed (int)
            seed_val = final_config.get('naiSeed')
            if seed_val is not None:
                try: final_config['naiSeed'] = int(seed_val)
                except (ValueError, TypeError):
                    print(f"警告(NAI): 配置文件中的 naiSeed '{seed_val}' 无效，将使用默认值。")
                    final_config['naiSeed'] = defaults.get('naiSeed')
            else: final_config['naiSeed'] = defaults.get('naiSeed')

            # NAI UC Preset (int)
            uc_preset_val = final_config.get('naiUcPreset')
            if uc_preset_val is not None:
                try: final_config['naiUcPreset'] = int(uc_preset_val)
                except (ValueError, TypeError):
                    print(f"警告(NAI): 配置文件中的 naiUcPreset '{uc_preset_val}' 无效，将使用默认值。")
                    final_config['naiUcPreset'] = defaults.get('naiUcPreset')
            else: final_config['naiUcPreset'] = defaults.get('naiUcPreset')

            # Booleans
            for key in ['naiQualityToggle', 'nai_use_proxy']:
                 if key in final_config and not isinstance(final_config[key], bool):
                     final_config[key] = str(final_config.get(key)).lower() == 'true'

            # NAI Proxy Port (string)
            final_config['nai_proxy_port'] = str(final_config.get('nai_proxy_port', defaults.get('nai_proxy_port', '')))

        elif config_type == "sd":
            # SD Steps (int)
            steps_val = final_config.get('sdSteps')
            if steps_val is not None:
                try: final_config['sdSteps'] = int(steps_val)
                except (ValueError, TypeError):
                    print(f"警告(SD): 配置文件中的 sdSteps '{steps_val}' 无效，将使用默认值。")
                    final_config['sdSteps'] = defaults.get('sdSteps')
            else: final_config['sdSteps'] = defaults.get('sdSteps')

            # SD CFG Scale (float)
            cfg_val = final_config.get('sdCfgScale')
            if cfg_val is not None:
                try: final_config['sdCfgScale'] = float(cfg_val)
                except (ValueError, TypeError):
                    print(f"警告(SD): 配置文件中的 sdCfgScale '{cfg_val}' 无效，将使用默认值。")
                    final_config['sdCfgScale'] = defaults.get('sdCfgScale')
            else: final_config['sdCfgScale'] = defaults.get('sdCfgScale')

            # SD Width (int)
            width_val = final_config.get('sdWidth')
            if width_val is not None:
                try: final_config['sdWidth'] = int(width_val)
                except (ValueError, TypeError):
                    print(f"警告(SD): 配置文件中的 sdWidth '{width_val}' 无效，将使用默认值。")
                    final_config['sdWidth'] = defaults.get('sdWidth')
            else: final_config['sdWidth'] = defaults.get('sdWidth')

            # SD Height (int)
            height_val = final_config.get('sdHeight')
            if height_val is not None:
                try: final_config['sdHeight'] = int(height_val)
                except (ValueError, TypeError):
                    print(f"警告(SD): 配置文件中的 sdHeight '{height_val}' 无效，将使用默认值。")
                    final_config['sdHeight'] = defaults.get('sdHeight')
            else: final_config['sdHeight'] = defaults.get('sdHeight')

            # SD Seed (int)
            seed_val = final_config.get('sdSeed')
            if seed_val is not None:
                try: final_config['sdSeed'] = int(seed_val)
                except (ValueError, TypeError):
                    print(f"警告(SD): 配置文件中的 sdSeed '{seed_val}' 无效，将使用默认值。")
                    final_config['sdSeed'] = defaults.get('sdSeed')
            else: final_config['sdSeed'] = defaults.get('sdSeed')

            # Booleans
            for key in ['sdRestoreFaces', 'sdTiling']:
                 if key in final_config and not isinstance(final_config[key], bool):
                     final_config[key] = str(final_config.get(key)).lower() == 'true'

            # SD WebUI URL (string, remove trailing slash)
            if 'sdWebUiUrl' in final_config and final_config.get('sdWebUiUrl'):
                final_config['sdWebUiUrl'] = str(final_config['sdWebUiUrl']).rstrip('/')

        # 新增：GPT-SoVITS 配置校验
        elif config_type == "gptsovits":
            # Top K (int)
            top_k_val = final_config.get('top_k')
            if top_k_val is not None:
                try: final_config['top_k'] = int(top_k_val)
                except (ValueError, TypeError):
                    print(f"警告(GPT-SoVITS): 配置文件中的 top_k '{top_k_val}' 无效，将使用默认值。")
                    final_config['top_k'] = defaults.get('top_k')
            else: final_config['top_k'] = defaults.get('top_k')

            # Top P (float)
            top_p_val = final_config.get('top_p')
            if top_p_val is not None:
                try: final_config['top_p'] = float(top_p_val)
                except (ValueError, TypeError):
                    print(f"警告(GPT-SoVITS): 配置文件中的 top_p '{top_p_val}' 无效，将使用默认值。")
                    final_config['top_p'] = defaults.get('top_p')
            else: final_config['top_p'] = defaults.get('top_p')

            # Temperature (float)
            temp_val = final_config.get('temperature')
            if temp_val is not None:
                try: final_config['temperature'] = float(temp_val)
                except (ValueError, TypeError):
                    print(f"警告(GPT-SoVITS): 配置文件中的 temperature '{temp_val}' 无效，将使用默认值。")
                    final_config['temperature'] = defaults.get('temperature')
            else: final_config['temperature'] = defaults.get('temperature')

            # Ref Free (bool)
            if 'ref_free' in final_config and not isinstance(final_config['ref_free'], bool):
                final_config['ref_free'] = str(final_config.get('ref_free')).lower() == 'true'

            # Character Voice Map (dict) - 确保是字典，且内部结构基本正确
            if 'character_voice_map' not in final_config or not isinstance(final_config['character_voice_map'], dict):
                print(f"警告(GPT-SoVITS): 配置文件中的 character_voice_map 无效或缺失，将使用空字典。")
                final_config['character_voice_map'] = {}
            else:
                # 简单检查内部结构
                valid_map = {}
                for name, voice_data in final_config['character_voice_map'].items():
                    if isinstance(voice_data, dict) and \
                       'refer_wav_path' in voice_data and \
                       'prompt_text' in voice_data and \
                       'prompt_language' in voice_data:
                        valid_map[name] = voice_data
                    else:
                        print(f"警告(GPT-SoVITS): 人物 '{name}' 的语音映射数据格式不完整，已忽略。")
                final_config['character_voice_map'] = valid_map # 使用校验后的映射

            # API URL (string, remove trailing slash)
            if 'apiUrl' in final_config and final_config.get('apiUrl'):
                final_config['apiUrl'] = str(final_config['apiUrl']).rstrip('/')


        print(f"配置 '{config_type}' 已从 '{config_path}' 加载并校验。")
        return final_config # 返回最终的配置字典

    except json.JSONDecodeError as e:
        # 如果 JSON 文件格式错误
        print(f"错误：解析配置文件 '{config_path}' 失败: {e}。文件可能已损坏。将使用默认值。")
        traceback.print_exc()
        # 显示错误给用户可能更好
        messagebox.showerror("配置加载错误", f"配置文件 '{config_path.name}' 格式错误或已损坏。\n错误: {e}\n\n将使用默认设置。", parent=None) # parent=None 可能在启动时使用
        return defaults
    except Exception as e:
        # 捕获其他可能的读取或处理错误
        print(f"错误：加载配置文件 '{config_path}' 时发生意外错误: {e}。将使用默认值。")
        traceback.print_exc()
        messagebox.showerror("配置加载错误", f"加载配置文件 '{config_path.name}' 时发生错误。\n错误: {e}\n\n将使用默认设置。", parent=None)
        return defaults

def save_config(config_type, data):
    """
    保存指定类型的配置数据到对应的 JSON 文件。

    Args:
        config_type (str): 配置类型 (如 "llm_global", "nai", "sd", "gptsovits")。
        data (dict): 要保存的配置数据字典。

    Returns:
        bool: 保存成功返回 True，失败返回 False。
    """
    if config_type not in CONFIG_FILES:
        print(f"错误：尝试保存未知的配置类型 '{config_type}'")
        return False

    config_path = CONFIG_FILES[config_type]["path"]
    _ensure_config_dir() # 确保目录存在
    data_to_save = data # 要保存的数据

    try:
        # 以写入模式打开文件 (w)，使用 utf-8 编码
        # indent=4 使 JSON 文件格式化，易于阅读
        # ensure_ascii=False 保证中文等非 ASCII 字符正确写入
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(data_to_save, f, ensure_ascii=False, indent=4)
        print(f"配置 '{config_type}' 已成功保存到 '{config_path}'。")
        return True # 保存成功
    except TypeError as e:
        # 如果 data 中包含无法序列化为 JSON 的类型
        print(f"错误：保存配置 '{config_type}' 到 '{config_path}' 时发生数据类型错误 (无法序列化为 JSON): {e}。")
        traceback.print_exc()
        messagebox.showerror("保存错误", f"保存配置 '{config_type}' 时遇到无法处理的数据类型。\n错误: {e}", parent=None)
        return False # 保存失败
    except Exception as e:
        # 捕获其他可能的写入错误 (如权限问题)
        print(f"错误：保存配置 '{config_type}' 到 '{config_path}' 时发生意外错误: {e}。")
        traceback.print_exc()
        messagebox.showerror("保存错误", f"保存配置文件 '{config_path.name}' 时发生错误。\n错误: {e}", parent=None)
        return False # 保存失败

# --- 加载/保存 Character Profiles (人物设定) ---
# 这些函数处理用户选择的文件，而不是固定的配置文件

def load_character_profiles_from_file(parent_window):
    """
    打开文件对话框让用户选择 JSON 文件加载人物设定。

    Args:
        parent_window: 调用此函数的父窗口 (用于显示消息框)。

    Returns:
        tuple or None: 加载成功返回 (profiles_dict, filepath)，失败或取消返回 None。
    """
    try:
        # 打开文件选择对话框，限制文件类型为 .json
        filepath = filedialog.askopenfilename(
            title="加载人物设定文件",
            filetypes=[("JSON 文件", "*.json"), ("所有文件", "*.*")],
            parent=parent_window # 使对话框显示在父窗口之上
        )
        # 如果用户取消选择，filepath 为空字符串或 None
        if not filepath:
            print("用户取消加载人物设定文件。")
            return None

        # --- 读取和解析选定的文件 ---
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                profiles = json.load(f)

            # 校验加载的数据是否为字典 (JSON 对象)
            if not isinstance(profiles, dict):
                messagebox.showerror("加载错误", "选择的文件内容不是有效的 JSON 对象 (字典)。\n请确保文件格式正确。", parent=parent_window)
                print(f"错误：文件 '{filepath}' 内容不是字典。")
                return None

            print(f"人物设定已从 '{filepath}' 加载。")
            return profiles, filepath # 返回加载的字典和文件路径

        except json.JSONDecodeError as e:
            messagebox.showerror("加载错误", f"解析文件 '{os.path.basename(filepath)}' 时出错。\n文件格式可能无效。\n错误: {e}", parent=parent_window)
            print(f"错误：解析 JSON 文件 '{filepath}' 失败: {e}")
            return None
        except Exception as e:
            messagebox.showerror("加载错误", f"读取文件 '{os.path.basename(filepath)}' 时发生错误。\n错误: {e}", parent=parent_window)
            print(f"错误：读取文件 '{filepath}' 时出错: {e}")
            traceback.print_exc()
            return None

    except Exception as e:
        # 捕获 filedialog 可能的错误
        print(f"错误：打开文件对话框时出错: {e}")
        traceback.print_exc()
        messagebox.showerror("错误", f"无法打开文件选择对话框。\n错误: {e}", parent=parent_window)
        return None

def save_character_profiles_to_file(profiles, parent_window):
    """
    打开文件对话框让用户选择位置保存当前的人物设定。

    Args:
        profiles (dict): 要保存的人物设定字典。
        parent_window: 调用此函数的父窗口。

    Returns:
        bool: 保存成功返回 True，失败或取消返回 False。
    """
    # 检查是否有数据需要保存
    if not profiles:
        print("警告：没有人物设定数据可以保存。")
        # messagebox.showwarning("无数据", "没有人物设定可以保存。", parent=parent_window) # ProfilesTab 内部已检查
        return False

    try:
        # 打开文件保存对话框
        filepath = filedialog.asksaveasfilename(
            title="保存人物设定到文件",
            defaultextension=".json", # 默认文件扩展名
            filetypes=[("JSON 文件", "*.json"), ("所有文件", "*.*")],
            initialfile="character_profiles.json", # 默认文件名
            parent=parent_window
        )
        # 如果用户取消保存，filepath 为空字符串或 None
        if not filepath:
            print("用户取消保存人物设定文件。")
            return False

        # --- 写入数据到选定的文件 ---
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(profiles, f, ensure_ascii=False, indent=4) # 格式化写入
            print(f"人物设定已成功保存到 '{filepath}'。")
            return True # 保存成功

        except TypeError as e:
            messagebox.showerror("保存错误", f"保存人物设定时遇到无法处理的数据类型。\n错误: {e}", parent=parent_window)
            print(f"错误：序列化人物设定到 JSON 时出错: {e}")
            traceback.print_exc()
            return False
        except Exception as e:
            messagebox.showerror("保存错误", f"写入文件 '{os.path.basename(filepath)}' 时发生错误。\n错误: {e}", parent=parent_window)
            print(f"错误：写入文件 '{filepath}' 时出错: {e}")
            traceback.print_exc()
            return False

    except Exception as e:
        # 捕获 filedialog 可能的错误
        print(f"错误：打开文件保存对话框时出错: {e}")
        traceback.print_exc()
        messagebox.showerror("错误", f"无法打开文件保存对话框。\n错误: {e}", parent=parent_window)
        return False

# --- 加载 NAI 模型列表 ---
def load_nai_models(default_path="assets/nai_models.json"):
    """
    从指定路径加载 NAI 模型列表 JSON 文件。

    Args:
        default_path (str): NAI 模型列表文件的路径。

    Returns:
        list: 包含模型信息的字典列表，如果加载失败则返回空列表。
              每个字典应包含 'name' (显示名称) 和 'value' (API 使用的值)。
    """
    model_path = Path(default_path) # 创建 Path 对象

    # 检查文件是否存在
    if not model_path.exists():
        print(f"警告: NAI 模型列表文件 '{model_path}' 未找到。将无法选择 NAI 模型。")
        # 可以考虑在这里显示一个更明显的警告给用户
        # messagebox.showwarning("文件缺失", f"NAI 模型定义文件 ({model_path}) 未找到。\n将无法在 NAI 设置中选择模型。", parent=None)
        return [] # 返回空列表

    try:
        with open(model_path, 'r', encoding='utf-8') as f:
            models = json.load(f) # 加载 JSON 数据

        # 校验加载的数据格式是否正确
        # 应该是一个列表 (list)
        if not isinstance(models, list):
            print(f"错误: NAI 模型文件 '{model_path}' 的顶层结构不是一个列表。")
            return []
        # 列表中的每个元素都应该是字典 (dict)
        if not all(isinstance(m, dict) for m in models):
            print(f"错误: NAI 模型文件 '{model_path}' 中包含非字典类型的元素。")
            return []
        # 每个字典都应该包含 'name' 和 'value' 键
        if not all('name' in m and 'value' in m for m in models):
            print(f"错误: NAI 模型文件 '{model_path}' 中的某些模型缺少 'name' 或 'value' 键。")
            return []

        print(f"NAI 模型列表已从 '{model_path}' 加载 ({len(models)} 个模型)。")
        return models # 返回加载并校验后的模型列表

    except json.JSONDecodeError as e:
        print(f"错误: 解析 NAI 模型文件 '{model_path}' 失败: {e}。文件格式可能无效。")
        return []
    except Exception as e:
        print(f"错误: 加载 NAI 模型文件 '{model_path}' 时发生意外错误: {e}")
        traceback.print_exc()
        return []