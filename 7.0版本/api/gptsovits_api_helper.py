# api/gptsovits_api_helper.py
"""
包含调用 GPT-SoVITS API 的辅助函数。
"""
import requests
import json
import traceback

def call_gptsovits_api(api_url, payload, output_filepath):
    """
    调用 GPT-SoVITS 的 /handle API 并将音频流保存到文件。

    Args:
        api_url (str): GPT-SoVITS API 的完整 URL (例如 "http://127.0.0.1:9880/handle")。
        payload (dict): 请求体 JSON 数据。
        output_filepath (str): 保存生成音频的完整文件路径。

    Returns:
        tuple: (success: bool, error_message: str or None)
               成功时 success 为 True，error_message 为 None。
               失败时 success 为 False，error_message 包含错误信息。
    """
    try:
        print(f"  [GPT-SoVITS API] 发送请求到: {api_url}")
        # 使用 stream=True 处理流式响应，设置超时
        response = requests.post(api_url, json=payload, stream=True, timeout=300) # 5分钟超时

        print(f"  [GPT-SoVITS API] 响应状态码: {response.status_code}")

        if response.status_code == 200:
            content_type = response.headers.get('content-type', '').lower()
            print(f"  [GPT-SoVITS API] 响应 Content-Type: {content_type}")

            if 'audio/wav' in content_type:
                try:
                    print(f"  [GPT-SoVITS API] 开始写入音频流到: {output_filepath}")
                    with open(output_filepath, 'wb') as f:
                        chunk_count = 0
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                                chunk_count += 1
                                # 简单的进度日志
                                # if chunk_count % 10 == 0:
                                #     print(f"    > 已写入 {chunk_count * 8 / 1024:.1f} KB...")
                    print(f"  [GPT-SoVITS API] 音频成功写入: {output_filepath}")
                    return True, None # 成功
                except Exception as write_e:
                    error_msg = f"写入音频文件 '{output_filepath}' 时出错: {write_e}"
                    print(f"  [GPT-SoVITS API] {error_msg}")
                    traceback.print_exc()
                    return False, error_msg
            else:
                # 如果返回的不是音频，尝试读取错误信息
                error_msg = f"服务器返回非预期的内容类型: {content_type}"
                try:
                    error_data = response.json()
                    error_msg += f" - 详情: {error_data}"
                except json.JSONDecodeError:
                    error_msg += f" - 原始响应: {response.text[:200]}..."
                print(f"  [GPT-SoVITS API] {error_msg}")
                return False, error_msg
        else:
            # 处理非 200 状态码
            error_msg = f"API 请求失败，状态码: {response.status_code}"
            try:
                error_data = response.json()
                error_msg += f" - 详情: {error_data}"
            except json.JSONDecodeError:
                error_msg += f" - 原始响应: {response.text[:500]}..."
            print(f"  [GPT-SoVITS API] {error_msg}")
            return False, error_msg

    except requests.exceptions.Timeout:
        error_msg = f"API 请求超时 (超过 300 秒)。"
        print(f"  [GPT-SoVITS API] {error_msg}")
        return False, error_msg
    except requests.exceptions.ConnectionError as conn_e:
        error_msg = f"无法连接到 API 地址 '{api_url}'. 请检查地址是否正确以及服务是否正在运行。错误: {conn_e}"
        print(f"  [GPT-SoVITS API] {error_msg}")
        return False, error_msg
    except requests.exceptions.RequestException as req_e:
        error_msg = f"API 请求时发生网络/HTTP 错误: {req_e}"
        print(f"  [GPT-SoVITS API] {error_msg}")
        return False, error_msg
    except Exception as e:
        error_msg = f"调用 GPT-SoVITS API 时发生未预期的严重错误: {e}"
        print(f"  [GPT-SoVITS API] {error_msg}")
        traceback.print_exc()
        return False, error_msg