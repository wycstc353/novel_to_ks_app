# api/gptsovits_api_helper.py
import requests
import json
import traceback
import base64
import os
import time
from pathlib import Path
import re
import copy # 需要 copy 来复制 payload

# 调试日志基础目录
DEBUG_LOG_DIR = Path("debug_logs") / "api_requests"

def call_gptsovits_api(api_endpoint_url, original_payload, output_filepath, save_debug_inputs=False, identifier=None):
    """
    调用 GPT-SoVITS 的推理 API (/infer_ref)，下载并保存音频。
    """
    print(f"  [GPT-SoVITS Helper] 准备调用 API: {api_endpoint_url}")
    print(f"  [GPT-SoVITS Helper] 原始 Payload (部分): "
          f"model_name='{original_payload.get('model_name', 'N/A')}', "
          f"ref_wav='{original_payload.get('refer_wav_path', 'N/A')}', "
          f"prompt='{original_payload.get('prompt_text', '')[:20]}...', "
          f"text='{original_payload.get('text', '')[:20]}...', "
          f"prompt_lang='{original_payload.get('prompt_language', 'N/A')}', "
          f"text_lang='{original_payload.get('text_language', 'N/A')}', "
          f"audio_dl_url='{original_payload.get('audio_dl_url', 'N/A')}'") # 增加打印 audio_dl_url

    # 读取并编码参考音频
    ref_audio_path = original_payload.get("refer_wav_path")
    ref_audio_b64 = ""
    if not ref_audio_path or not os.path.exists(ref_audio_path):
        error_msg = f"错误：参考音频文件路径无效或文件不存在: '{ref_audio_path}'"
        print(f"  [GPT-SoVITS Helper] {error_msg}")
        return False, error_msg
    try:
        with open(ref_audio_path, 'rb') as f: audio_data = f.read()
        ref_audio_b64 = base64.b64encode(audio_data).decode('utf-8')
        print(f"  [GPT-SoVITS Helper] 参考音频 '{os.path.basename(ref_audio_path)}' 读取并编码为 Base64 成功。")
    except Exception as e:
        error_msg = f"读取或编码参考音频 '{ref_audio_path}' 时出错: {e}"
        print(f"  [GPT-SoVITS Helper] {error_msg}"); traceback.print_exc()
        return False, error_msg

    # 构建最终发送给 API 的 Payload
    try:
        api_payload = {
            "app_key": "", # API Key (如果需要，应从配置获取)
            # --- 修正：从 original_payload 获取 audio_dl_url ---
            "audio_dl_url": original_payload.get("audio_dl_url", ""),
            # --- 修正结束 ---
            "model_name": original_payload.get("model_name", ""),
            "ref_audio_b64": ref_audio_b64,
            "text": original_payload.get("text", ""),
            "text_lang": original_payload.get("text_language", "中文"),
            "prompt_text": original_payload.get("prompt_text", ""),
            "prompt_text_lang": original_payload.get("prompt_language", "中文"),
            "top_k": int(original_payload.get("top_k", 10)),
            "top_p": float(original_payload.get("top_p", 1.0)),
            "temperature": float(original_payload.get("temperature", 1.0)),
            "text_split_method": original_payload.get("how_to_cut", "按标点符号切"),
            "batch_size": int(original_payload.get("batch_size", 1)),
            "batch_threshold": float(original_payload.get("batch_threshold", 0.75)),
            "split_bucket": bool(original_payload.get("split_bucket", True)),
            "speed_facter": float(original_payload.get("speed_facter", 1.0)),
            "fragment_interval": float(original_payload.get("fragment_interval", 0.3)),
            "media_type": original_payload.get("media_type", "wav"),
            "parallel_infer": bool(original_payload.get("parallel_infer", True)),
            "repetition_penalty": float(original_payload.get("repetition_penalty", 1.35)),
            "seed": int(original_payload.get("seed", -1)),
        }
        payload_to_print = {k: v for k, v in api_payload.items() if k != "ref_audio_b64"}
        # 再次打印确认最终发送的 payload 中的 audio_dl_url
        print(f"  [GPT-SoVITS Helper] 构建的最终 API Payload (发送给服务器): {payload_to_print}")

    except Exception as build_e:
        error_msg = f"构建 API 请求体时出错: {build_e}"
        print(f"  [GPT-SoVITS Helper] {error_msg}"); traceback.print_exc()
        return False, error_msg

    # 保存调试输入 (如果启用)
    if save_debug_inputs:
        try:
            api_type = "GPTSoVITS"; debug_save_dir = DEBUG_LOG_DIR / api_type.lower(); debug_save_dir.mkdir(parents=True, exist_ok=True)
            timestamp = time.strftime("%Y%m%d_%H%M%S"); safe_identifier = re.sub(r'[\\/*?:"<>|\s\.]+', '_', identifier or "payload"); filename = f"{timestamp}_{safe_identifier}.json"; filepath = debug_save_dir / filename
            payload_to_save = copy.deepcopy(api_payload)
            if "ref_audio_b64" in payload_to_save: payload_to_save["ref_audio_b64"] = "[Base64 Audio Data Removed]"
            with open(filepath, 'w', encoding='utf-8') as f: json.dump(payload_to_save, f, ensure_ascii=False, indent=4)
            print(f"  [Debug Save] GPT-SoVITS 请求 (无音频) 已保存到: {filepath}")
        except Exception as save_e: print(f"错误：保存 GPT-SoVITS 请求调试文件时出错: {save_e}"); traceback.print_exc()

    # 发送 POST 请求
    audio_url = None; response = None
    try:
        print(f"  [GPT-SoVITS Helper] 发送 POST 请求到: {api_endpoint_url}")
        response = requests.post(api_endpoint_url, json=api_payload, timeout=300)
        response.raise_for_status() # 检查 HTTP 错误状态码

        print(f"  [GPT-SoVITS Helper] POST 响应状态码: {response.status_code}")
        response_json = response.json()
        print(f"  [GPT-SoVITS Helper] 收到 JSON 响应: {response_json}")

        api_msg = response_json.get("msg", "未知 API 消息")
        is_error_msg = "错误" in api_msg or "error" in api_msg.lower() or "参数错误" in api_msg
        # 检查 API 是否返回错误或未提供 audio_url
        if is_error_msg or not response_json.get("audio_url"):
            error_msg = f"API 返回错误或未提供音频 URL: {api_msg}"
            print(f"  [GPT-SoVITS Helper] {error_msg}")
            return False, error_msg

        audio_url = response_json.get("audio_url")
        print(f"  [GPT-SoVITS Helper] 成功获取音频下载 URL: {audio_url}")

    except requests.exceptions.RequestException as req_e:
        error_msg = f"API POST 请求时发生网络/HTTP 错误: {req_e}"
        if response is not None: error_msg += f" (Status: {response.status_code})"
        print(f"  [GPT-SoVITS Helper] {error_msg}")
        return False, error_msg
    except json.JSONDecodeError:
        error_msg = f"无法解析 API 返回的 JSON 响应。状态码: {response.status_code if response else 'N/A'}."
        if response: error_msg += f" 响应内容: {response.text[:200]}..."
        print(f"  [GPT-SoVITS Helper] {error_msg}")
        return False, error_msg
    except Exception as e:
        error_msg = f"调用 GPT-SoVITS API (POST阶段) 时发生未预期的错误: {e}"
        print(f"  [GPT-SoVITS Helper] {error_msg}"); traceback.print_exc()
        return False, error_msg

    # 下载前的延时和重试逻辑
    if not audio_url: return False, "未能获取有效的音频下载 URL。"
    max_retries = 3; initial_delay = 5; retry_delay = 3
    print(f"  [GPT-SoVITS Helper] 等待 {initial_delay} 秒让服务器准备文件...")
    time.sleep(initial_delay)

    for attempt in range(max_retries):
        print(f"  [GPT-SoVITS Helper] 尝试下载音频 (第 {attempt + 1}/{max_retries} 次)... URL: {audio_url}")
        download_response = None
        try:
            download_response = requests.get(audio_url, stream=True, timeout=60)
            download_response.raise_for_status()
            print(f"  [GPT-SoVITS Helper] 音频下载响应状态码: {download_response.status_code}")
            content_type = download_response.headers.get('content-type', '').lower()
            print(f"  [GPT-SoVITS Helper] 音频下载 Content-Type: {content_type}")
            if not ('audio/' in content_type or 'application/octet-stream' in content_type):
                 error_msg = f"下载的链接返回非预期的内容类型: {content_type}"; print(f"  [GPT-SoVITS Helper] {error_msg}"); return False, error_msg
            print(f"  [GPT-SoVITS Helper] 开始写入音频流到: {output_filepath}")
            with open(output_filepath, 'wb') as f:
                chunk_count = 0
                for chunk in download_response.iter_content(chunk_size=8192):
                    if chunk: f.write(chunk); chunk_count += 1
            print(f"  [GPT-SoVITS Helper] 音频成功下载并写入: {output_filepath} ({chunk_count} chunks)")
            return True, None # 下载并保存成功
        except requests.exceptions.RequestException as req_e:
            error_msg = f"下载音频时发生网络/HTTP 错误 (尝试 {attempt + 1}/{max_retries}): {req_e}"
            if download_response is not None: error_msg += f" (Status: {download_response.status_code})"
            print(f"  [GPT-SoVITS Helper] {error_msg}")
            if attempt == max_retries - 1: return False, error_msg
            print(f"  [GPT-SoVITS Helper] 等待 {retry_delay} 秒后重试..."); time.sleep(retry_delay); continue
        except IOError as write_e: error_msg = f"写入音频文件 '{output_filepath}' 时出错: {write_e}"; print(f"  [GPT-SoVITS Helper] {error_msg}"); traceback.print_exc(); return False, error_msg
        except Exception as e: error_msg = f"下载或保存音频时发生未预期的错误: {e}"; print(f"  [GPT-SoVITS Helper] {error_msg}"); traceback.print_exc(); return False, error_msg
        finally:
            if download_response:
                try: download_response.close()
                except Exception as close_e: print(f"  [GPT-SoVITS Helper] 关闭下载响应流时出错: {close_e}")

    # 如果循环结束还没有成功返回
    return False, f"下载音频失败，已达到最大重试次数 ({max_retries})"