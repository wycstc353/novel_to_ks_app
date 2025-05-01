# api/comfyui_api_helper.py
import requests # 功能性备注: 导入 requests 库用于 HTTP 请求
import json # 功能性备注: 导入 json 库用于处理 JSON 数据
import time # 功能性备注: 导入 time 库用于延时和时间戳
import uuid # 功能性备注: 导入 uuid 库用于生成唯一 ID
import websocket # 功能性备注: 导入 websocket-client 库用于 WebSocket 通信
from urllib.parse import urlparse, urljoin # 功能性备注: 导入 URL 处理函数
import traceback # 功能性备注: 保留用于错误处理
import os # 功能性备注: 导入 os 库用于路径操作
import re # 功能性备注: 导入 re 库用于正则表达式
import copy # 功能性备注: 导入 copy 库用于深拷贝
from pathlib import Path # 功能性备注: 导入 Path 对象用于路径处理
import logging # 功能性备注: 导入日志模块

# 功能性备注: 获取当前模块的 logger 实例
logger = logging.getLogger(__name__)

# 功能性备注: 定义调试日志的基础目录
DEBUG_LOG_DIR = Path("debug_logs") / "api_requests"

def _save_debug_input(api_type, payload, identifier):
    """保存调试输入文件 (移除敏感信息)"""
    # 功能性备注: 此函数用于将 API 请求的 payload 保存到本地文件，以便调试，同时会移除潜在的敏感信息。
    try:
        # 功能性备注: 确保调试日志目录存在
        debug_save_dir = DEBUG_LOG_DIR / api_type.lower()
        debug_save_dir.mkdir(parents=True, exist_ok=True)
        # 功能性备注: 生成带时间戳和标识符的文件名
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        safe_identifier = re.sub(r'[\\/*?:"<>|\s\.]+', '_', identifier or "payload")
        filename = f"{timestamp}_{safe_identifier}.json"
        filepath = debug_save_dir / filename

        # 功能性备注: 复制 payload 以避免修改原始数据，并移除敏感信息
        payload_to_save = copy.deepcopy(payload)

        # 逻辑备注: 根据不同的操作类型移除不同的敏感信息
        if identifier == "upload" and "local_filepath" in payload_to_save:
            payload_to_save["local_filepath"] = "[Local Path Removed]" # 功能性备注: 移除上传文件的本地路径
        elif identifier == "prompt" and isinstance(payload_to_save.get("prompt"), dict):
            workflow_to_save = payload_to_save["prompt"]
            for node_id, node_data in workflow_to_save.items():
                # 功能性备注: 检查 LoadImage 节点并移除具体的服务器文件名（虽然不是特别敏感，但保持一致性）
                if isinstance(node_data, dict) and node_data.get("class_type") == "LoadImage":
                    if "inputs" in node_data and "image" in node_data["inputs"]:
                        if isinstance(node_data["inputs"]["image"], str):
                            node_data["inputs"]["image"] = "[Server Filename]"
                        else:
                            node_data["inputs"]["image"] = "[Non-string image value removed]"
                # 逻辑备注: 此处可以添加对其他可能包含敏感信息的节点的处理逻辑

        # 功能性备注: 将清理后的 payload 写入 JSON 文件
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(payload_to_save, f, ensure_ascii=False, indent=4)
        # 功能性备注: 记录调试文件保存成功的信息
        logger.info(f"  [Debug Save] {api_type.upper()} 请求已保存到: {filepath}")
    except Exception as save_e:
        # 功能性备注: 记录保存调试文件时发生的错误
        logger.error(f"错误：保存 {api_type.upper()} 请求调试文件时出错: {save_e}", exc_info=True)


def _find_node_id_by_title(workflow, title):
    """
    在工作流字典中根据节点标题查找节点 ID 和数据 (增强健壮性)。
    无论是否找到，都返回两个值 (node_id, node_data) 或 (None, None)。
    """
    # 功能性备注: 这是一个辅助函数，用于在 ComfyUI 工作流（字典格式）中通过用户指定的节点标题找到对应的节点 ID 和节点数据。
    # 逻辑备注: 检查输入标题和工作流数据的有效性
    if not title:
        return None, None
    if not workflow or not isinstance(workflow, dict):
        logger.warning(f"(_find_node_id_by_title): 工作流数据无效或为空 (类型: {type(workflow)})。") # 逻辑备注
        return None, None

    # 逻辑备注: 遍历工作流字典中的所有节点
    for node_id, node_data in workflow.items():
        # 逻辑备注: 增加更严格的检查，确保节点数据结构符合预期（包含 _meta 和 title）
        if isinstance(node_data, dict) and \
           "_meta" in node_data and \
           isinstance(node_data.get("_meta"), dict) and \
           "title" in node_data["_meta"] and \
           node_data["_meta"].get("title") == title:
            # 功能性备注: 找到了标题匹配的节点，返回其 ID 和数据
            return node_id, node_data

    # 逻辑备注: 如果循环结束仍未找到匹配的节点，记录警告并返回 None
    logger.warning(f"(_find_node_id_by_title): 未能在工作流中找到标题为 '{title}' 的节点。") # 逻辑备注
    return None, None

def _set_node_input(node_data, input_name, value):
    """安全地设置节点输入值"""
    # 功能性备注: 这是一个辅助函数，用于安全地修改 ComfyUI 工作流中某个节点的输入参数值。
    # 逻辑备注: 检查节点数据是否有效且包含 'inputs' 字典
    if isinstance(node_data, dict) and 'inputs' in node_data:
        # 逻辑备注: 如果传入的值是 None，表示希望使用 ComfyUI 的默认值，因此尝试从 inputs 中删除该项
        if value is None:
             if input_name in node_data['inputs']:
                 logger.info(f"    - 输入值 '{input_name}' 为 None，将从节点输入中移除（使用默认）。") # 功能性备注
                 del node_data['inputs'][input_name]
             else:
                 logger.info(f"    - 输入值 '{input_name}' 为 None 且节点无此输入，跳过。") # 功能性备注
             return True
        else:
            # 逻辑备注: 如果值不是 None，则直接设置或更新该输入项的值
            node_data['inputs'][input_name] = value
            return True
    # 逻辑备注: 如果节点数据无效或缺少 'inputs'，记录警告并返回失败
    logger.warning(f"    - 无法设置节点输入 '{input_name}'，节点数据无效或缺少 'inputs' 键。 Node Data: {str(node_data)[:100]}...") # 逻辑备注
    return False

def call_comfyui_api(comfyui_url, workflow_dict, expected_output_node_title="SaveOutputImage", client_id=None, save_debug=False):
    """
    调用 ComfyUI 的 /prompt API 提交工作流，并轮询或使用 WebSocket 获取结果。
    """
    # 功能性备注: 这是调用 ComfyUI API 的主要函数。它负责提交工作流、处理响应、通过 WebSocket 或 HTTP 轮询获取结果，并下载最终生成的图片。
    # --- 输入校验和 URL 准备 ---
    # 逻辑备注: 检查 ComfyUI URL 和工作流字典是否有效
    if not comfyui_url:
        return None, "错误: ComfyUI URL 不能为空。"
    if not workflow_dict or not isinstance(workflow_dict, dict):
        return None, "错误: 工作流字典无效或为空。"

    try:
        # 功能性备注: 解析并构建所需的 API 端点 URL 和 WebSocket URL
        parsed_url = urlparse(comfyui_url)
        scheme = parsed_url.scheme or "http"
        netloc = parsed_url.netloc or "127.0.0.1:8188" # 默认地址
        base_url = f"{scheme}://{netloc}"
        prompt_endpoint = urljoin(base_url, "/prompt") # 提交工作流的端点
        history_endpoint_base = urljoin(base_url, "/history/") # 获取历史记录的基础端点
        view_endpoint = urljoin(base_url, "/view") # 下载图片的端点
        # 功能性备注: 如果提供了 client_id，则构建 WebSocket URL，否则不使用 WebSocket
        ws_url = f"ws://{netloc}/ws?clientId={client_id}" if client_id else None
    except Exception as url_e:
        logger.error(f"处理 ComfyUI URL 时出错: {url_e}") # 功能性备注: 记录 URL 处理错误
        return None, f"处理 ComfyUI URL 时出错: {url_e}"

    # --- 初始化变量 ---
    prompt_id = None # 功能性备注: 存储提交工作流后返回的 Prompt ID
    image_data_list = [] # 功能性备注: 存储最终下载到的图片数据 (bytes)
    error_message = None # 功能性备注: 存储过程中发生的错误信息
    response = None # 功能性备注: 存储 HTTP 响应对象
    ws = None # 功能性备注: 存储 WebSocket 连接对象

    # --- 主逻辑包裹在 try...except 中以捕获意外错误 ---
    try:
        # --- 1. 准备并提交工作流 ---
        logger.info(f"准备提交工作流到: {prompt_endpoint}") # 功能性备注: 记录提交信息
        # 功能性备注: 构建提交给 /prompt API 的 payload
        payload = {"prompt": workflow_dict}
        if client_id:
            payload["client_id"] = client_id # 功能性备注: 如果有 client_id，添加到 payload

        # --- *** 新增的调试打印 *** ---
        logger.debug("--- [DEBUG] Workflow being sent to ComfyUI ---") # 功能性备注: 调试日志，标记工作流开始
        try:
            # 功能性备注: 尝试将工作流格式化为 JSON 打印，便于调试查看
            logger.debug(json.dumps(workflow_dict, indent=2, sort_keys=True, ensure_ascii=False))
        except TypeError as json_dump_error:
             # 逻辑备注: 如果工作流无法序列化为 JSON（理论上不应发生），则打印原始字典
             logger.warning(f"无法序列化为 JSON 进行调试打印: {json_dump_error}")
             logger.debug(workflow_dict)
        logger.debug("--- [DEBUG] End of Workflow ---") # 功能性备注: 调试日志，标记工作流结束
        # --- *** 调试打印结束 *** ---

        # 功能性备注: 如果启用了调试保存，则保存请求 payload
        if save_debug:
            _save_debug_input("comfyui", payload, "prompt")

        # 功能性备注: 发送 POST 请求提交工作流
        response = requests.post(prompt_endpoint, json=payload, timeout=30)
        response.raise_for_status() # 功能性备注: 检查 HTTP 错误 (4xx, 5xx)，如果出错则抛出异常
        result_json = response.json() # 功能性备注: 解析返回的 JSON 响应

        # 功能性备注: 检查提交结果，获取 prompt_id 或处理错误
        if 'prompt_id' in result_json:
            prompt_id = result_json['prompt_id']
            logger.info(f"工作流提交成功，Prompt ID: {prompt_id}") # 功能性备注: 记录成功信息
        elif 'error' in result_json:
            # 逻辑备注: 如果 API 返回明确的错误信息
            error_message = f"ComfyUI 提交错误: {result_json.get('message', '未知错误')}"
            if 'details' in result_json: error_message += f" 详情: {json.dumps(result_json['details'])}"
            if 'node_errors' in result_json: error_message += f" 节点错误: {json.dumps(result_json['node_errors'])}"
            logger.error(f"{error_message}") # 功能性备注: 记录错误
            return None, error_message
        else:
            # 逻辑备注: 如果响应中既没有 prompt_id 也没有 error
            error_message = "ComfyUI 提交失败，响应中未找到 prompt_id 或 error。"
            logger.error(f"{error_message} 响应: {response.text[:200]}...") # 功能性备注: 记录错误
            return None, error_message

        # --- 2. 获取结果 (优先 WebSocket，否则轮询) ---
        execution_finished = False # 功能性备注: 标记任务是否执行完成
        final_history = None # 功能性备注: 存储最终获取到的历史记录

        # 逻辑备注: 如果 WebSocket URL 有效，则尝试使用 WebSocket
        if ws_url:
            # --- 2a. 使用 WebSocket 获取结果 ---
            logger.info(f"尝试使用 WebSocket 连接: {ws_url}") # 功能性备注: 记录连接尝试
            try:
                # 功能性备注: 创建 WebSocket 连接，设置超时
                ws = websocket.create_connection(ws_url, timeout=10)
                logger.info(f"WebSocket 连接成功。等待 Prompt ID {prompt_id} 的结果...") # 功能性备注: 记录连接成功
                start_time = time.time()
                timeout_seconds = 600 # 功能性备注: 设置 WebSocket 等待超时时间 (10分钟)

                # 功能性备注: 循环接收 WebSocket 消息，直到任务完成或超时
                while time.time() - start_time < timeout_seconds:
                    message_str = None
                    message = None
                    try:
                        # 功能性备注: 设置接收超时，避免无限阻塞
                        ws.settimeout(10.0)
                        # 功能性备注: 接收数据
                        received_data = ws.recv()
                        if not received_data: continue # 功能性备注: 忽略空消息

                        # 功能性备注: 检查类型并解码 (如果需要)
                        if isinstance(received_data, bytes):
                            # 逻辑备注: 收到的是字节串，尝试解码
                          # logger.debug(f"收到原始 WebSocket 消息 (bytes): {received_data!r}") # 功能性备注: 记录原始字节
                            try:
                                message_str = received_data.decode('utf-8')
                            except UnicodeDecodeError:
                                logger.warning(f"WebSocket 消息解码失败 (非 UTF-8 或二进制数据?)，已跳过此消息。") # 功能性备注: 记录解码失败警告
                                continue # 功能性备注: 跳过无法解码的字节消息
                        elif isinstance(received_data, str):
                            # 逻辑备注: 收到的是字符串，直接使用
                            #logger.debug(f"收到原始 WebSocket 消息 (str): {received_data!r}") # 功能性备注: 记录原始字符串
                            message_str = received_data
                        else:
                            # 逻辑备注: 收到未知类型的数据
                            logger.warning(f"收到未知类型的 WebSocket 数据: {type(received_data)}，跳过。") # 功能性备注: 记录未知类型警告
                            continue

                        # 功能性备注: 如果成功获取到字符串，尝试解析 JSON
                        if message_str:
                            if message_str.strip() == '[DONE]': # 逻辑备注: 检查是否是结束标记
                                logger.info("WebSocket 收到 [DONE] 标记。") # 功能性备注: 记录收到 DONE
                                break # 功能性备注: 结束循环

                            try:
                                message = json.loads(message_str)
                            except json.JSONDecodeError as json_err:
                                logger.error(f"处理 ComfyUI WebSocket 消息时 JSON 解析错误: {json_err} - Raw Str: '{message_str[:100]}...'") # 功能性备注: 记录 JSON 解析错误
                                continue # 逻辑备注: 跳过无法解析的 JSON 消息
                        else:
                            # 逻辑备注: 如果 message_str 为 None 或空 (理论上不应发生)
                            continue

                        # 功能性备注: 处理解析后的 JSON 消息
                        if message:
                            msg_type = message.get('type')
                            data = message.get('data', {})
                            msg_prompt_id = data.get('prompt_id')

                            # 逻辑备注: 只处理与当前提交任务相关的消息
                            if msg_prompt_id == prompt_id:
                                if msg_type == 'executing':
                                    # 逻辑备注: 'executing' 消息中 node 为 None 表示执行完成
                                    if data.get('node') is None:
                                        logger.info(f"WebSocket: Prompt {prompt_id} 执行完成。") # 功能性备注: 记录完成
                                        execution_finished = True
                                        break # 功能性备注: 执行完毕，跳出 WebSocket 循环
                                    else:
                                        # 功能性备注: 记录正在执行的节点信息
                                        logger.info(f"WebSocket: 节点 {data.get('node')} 正在执行...")
                                elif msg_type == 'execution_error':
                                    # 逻辑备注: 如果收到执行错误消息
                                    node_id = data.get('node_id', 'N/A')
                                    node_type = data.get('node_type', 'N/A')
                                    err_msg = data.get('exception_message', '未知执行错误')
                                    error_message = f"ComfyUI 执行错误 (Node {node_id}, Type {node_type}): {err_msg}"
                                    logger.error(f"{error_message}") # 功能性备注: 记录错误
                                    execution_finished = True # 功能性备注: 认为执行因错误而结束
                                    break # 功能性备注: 出错，跳出 WebSocket 循环
                            elif msg_type == 'status':
                                # 功能性备注: 处理状态更新消息（例如队列剩余数量）
                                 if 'exec_info' in data:
                                     q_size = data['exec_info'].get('queue_remaining', '?')
                                     logger.info(f"WebSocket Status: 队列剩余 {q_size}") # 功能性备注: 记录队列状态

                    except websocket.WebSocketTimeoutException:
                        # 逻辑备注: 接收超时是正常的，继续等待下一条消息
                        continue
                    except websocket.WebSocketConnectionClosedException:
                        # 逻辑备注: WebSocket 连接意外关闭
                        error_message = "ComfyUI WebSocket 连接意外关闭。"
                        logger.error(f"{error_message}") # 功能性备注: 记录错误
                        execution_finished = True # 功能性备注: 无法再接收，认为结束
                        break # 功能性备注: 连接关闭，跳出 WebSocket 循环
                    except AttributeError as ae: # 逻辑备注: 捕获可能的其他 AttributeError
                        logger.error(f"处理 WebSocket 消息时发生 AttributeError: {ae}", exc_info=True) # 功能性备注: 记录错误
                        continue # 逻辑备注: 跳过此消息
                    except Exception as ws_proc_e:
                        # 逻辑备注: 捕获处理 WebSocket 消息时的其他未知错误
                        logger.exception(f"处理 WebSocket 消息时发生其他错误: {ws_proc_e}") # 功能性备注: 记录异常
                        continue # 逻辑备注: 跳过此消息

                # 逻辑备注: 检查是否是因为超时退出 WebSocket 循环
                if not execution_finished and not error_message:
                    error_message = f"ComfyUI WebSocket 等待超时 ({timeout_seconds}秒)，未收到完成信号。"
                    logger.error(f"{error_message}") # 功能性备注: 记录超时错误

            except websocket.WebSocketException as ws_connect_e:
                # 逻辑备注: 处理 WebSocket 连接或通信失败的情况
                logger.warning(f"WebSocket 连接或通信失败: {ws_connect_e}。将回退到 HTTP 轮询。") # 功能性备注: 记录警告
                ws_url = None # 功能性备注: 标记 WebSocket 不可用，以便后续进入轮询
            except Exception as ws_generic_e:
                # 逻辑备注: 处理 WebSocket 过程中的其他未知错误
                logger.exception(f"WebSocket 处理中发生其他错误: {ws_generic_e}。将回退到 HTTP 轮询。") # 功能性备注: 记录异常
                ws_url = None # 功能性备注: 标记 WebSocket 不可用
            finally:
                # 功能性备注: 确保关闭 WebSocket 连接
                if ws:
                    try:
                        ws.close()
                        logger.info("WebSocket 连接已关闭。") # 功能性备注: 记录关闭
                    except Exception as ws_close_e:
                        logger.warning(f"关闭 WebSocket 时出错: {ws_close_e}") # 功能性备注: 记录关闭错误

        # --- 2b. 如果 WebSocket 失败或未启用，并且之前没有错误，使用 HTTP 轮询获取结果 ---
        # 逻辑备注: 只有在任务未完成且没有发生错误时才进行轮询
        if not execution_finished and not error_message:
            logger.info(f"使用 HTTP 轮询获取 Prompt ID {prompt_id} 的结果...") # 功能性备注: 记录开始轮询
            history_endpoint = urljoin(history_endpoint_base, prompt_id) # 功能性备注: 构建获取特定历史的 URL
            polling_interval = 1 # 功能性备注: 轮询间隔（秒）
            timeout_seconds = 600 # 功能性备注: 轮询超时时间 (10分钟)
            start_time = time.time()

            # 功能性备注: 循环轮询，直到任务完成或超时
            while time.time() - start_time < timeout_seconds:
                history_response = None # 功能性备注: 初始化轮询响应对象
                try:
                    # 功能性备注: 发送 GET 请求获取历史记录
                    history_response = requests.get(history_endpoint, timeout=10)
                    history_response.raise_for_status() # 功能性备注: 检查 HTTP 错误
                    history_data = history_response.json() # 功能性备注: 解析 JSON 响应

                    # 逻辑备注: ComfyUI 的历史记录格式是 {prompt_id: {outputs: {...}, status: {...}} }
                    if prompt_id in history_data:
                        prompt_info = history_data[prompt_id]
                        status_info = prompt_info.get("status", {})
                        status_str = status_info.get("status_str", "unknown")
                        completed = status_info.get("completed", False)

                        # 逻辑备注: 检查任务是否已完成
                        if completed:
                            logger.info(f"轮询: Prompt {prompt_id} 执行完成 (Status: {status_str})。") # 功能性备注: 记录完成
                            final_history = prompt_info # 功能性备注: 保存完成的历史记录
                            execution_finished = True
                            break # 功能性备注: 完成，跳出轮询循环
                        else:
                             # 功能性备注: 记录当前状态和队列信息
                             q_size = status_info.get('exec_info', {}).get('queue_remaining', '?')
                             logger.info(f"轮询: Prompt {prompt_id} 状态: {status_str}, 队列: {q_size}。等待 {polling_interval} 秒...")
                    else:
                         # 逻辑备注: prompt_id 还没出现在历史里是正常的，继续等待
                         logger.info(f"轮询: 历史记录中暂未找到 Prompt ID {prompt_id}，继续等待...")

                except requests.exceptions.Timeout:
                    # 逻辑备注: 轮询超时是可接受的，继续下一次轮询
                    logger.debug(f"轮询: 获取历史记录超时，继续轮询...")
                except requests.exceptions.RequestException as poll_e:
                    # 逻辑备注: 处理轮询时的网络或 HTTP 错误
                    error_message = f"ComfyUI 轮询历史记录时网络/HTTP错误: {poll_e}"
                    logger.error(f"{error_message}") # 功能性备注: 记录错误
                    break # 功能性备注: 发生网络错误，终止等待
                except json.JSONDecodeError:
                    # 逻辑备注: 处理轮询响应 JSON 解析错误
                    error_message = f"ComfyUI 轮询错误：无法解析历史记录响应 JSON。Status: {history_response.status_code if history_response else 'N/A'}."
                    if history_response: error_message += f" Response: {history_response.text[:200]}..."
                    logger.error(f"{error_message}") # 功能性备注: 记录错误
                    break # 功能性备注: 无法解析响应，终止等待
                except Exception as poll_generic_e:
                    # 逻辑备注: 处理轮询时的其他未知错误
                    error_message = f"ComfyUI 轮询时发生意外错误: {poll_generic_e}"
                    logger.exception(error_message) # 功能性备注: 记录异常
                    break # 功能性备注: 发生未知错误，终止等待
                finally:
                    # 功能性备注: 确保关闭轮询的响应对象
                    if history_response:
                        try: history_response.close()
                        except Exception: pass

                # 功能性备注: 等待指定间隔后进行下一次轮询
                time.sleep(polling_interval)

            # 逻辑备注: 检查是否是因为轮询超时退出循环
            if not execution_finished and not error_message:
                error_message = f"ComfyUI 任务轮询超时 ({timeout_seconds}秒)。"
                logger.error(f"{error_message}") # 功能性备注: 记录超时错误

        # --- 3. 如果执行成功，尝试获取最终结果 ---
        # 逻辑备注: 只有在任务执行完成且没有发生错误时才进行
        if execution_finished and not error_message:
            # 逻辑备注: 如果是轮询成功，final_history 已经有值
            # 逻辑备注: 如果是 WebSocket 成功，需要重新发送 GET 请求获取一次最终的历史记录
            if not final_history:
                logger.info(f"WebSocket 完成后，获取最终历史记录: {history_endpoint_base}{prompt_id}") # 功能性备注: 记录获取最终历史
                final_hist_response = None # 功能性备注: 初始化最终历史响应对象
                try:
                    # 功能性备注: 发送 GET 请求获取最终历史
                    final_hist_response = requests.get(urljoin(history_endpoint_base, prompt_id), timeout=30)
                    final_hist_response.raise_for_status() # 功能性备注: 检查 HTTP 错误
                    history_data = final_hist_response.json() # 功能性备注: 解析 JSON
                    if prompt_id in history_data:
                        final_history = history_data[prompt_id] # 功能性备注: 保存最终历史
                    else:
                        # 逻辑备注: 这种情况比较少见，但可能发生（例如历史记录被清理）
                        error_message = "无法获取最终历史记录 (Prompt ID 未找到)。"
                        logger.error(f"{error_message}") # 功能性备注: 记录错误
                except Exception as final_hist_e:
                    # 逻辑备注: 处理获取最终历史时的错误
                    error_message = f"获取最终历史记录时出错: {final_hist_e}"
                    logger.error(f"{error_message}") # 功能性备注: 记录错误
                finally:
                    # 功能性备注: 确保关闭最终历史的响应对象
                    if final_hist_response:
                        try: final_hist_response.close()
                        except Exception: pass

            # --- 4. 解析最终历史记录，下载图片 ---
            # 逻辑备注: 只有在成功获取到最终历史记录且没有错误时才进行
            if final_history and 'outputs' in final_history and not error_message:
                outputs = final_history.get('outputs', {})
                # 功能性备注: 使用原始 workflow_dict 和预期的输出节点标题查找对应的节点 ID
                output_node_id, _ = _find_node_id_by_title(workflow_dict, expected_output_node_title)

                # 逻辑备注: 检查是否找到了输出节点并且其输出在历史记录中
                if output_node_id and output_node_id in outputs:
                    node_output = outputs[output_node_id]
                    # 逻辑备注: 检查输出节点是否有 'images' 列表
                    if 'images' in node_output and isinstance(node_output['images'], list):
                        logger.info(f"在节点 '{expected_output_node_title}' (ID: {output_node_id}) 找到 {len(node_output['images'])} 个输出图片信息。") # 功能性备注: 记录找到图片信息
                        images_to_download = node_output['images']
                        download_errors = [] # 功能性备注: 用于存储下载过程中发生的错误

                        # 功能性备注: 遍历每个图片信息并尝试下载
                        for img_info in images_to_download:
                            filename = img_info.get('filename')
                            subfolder = img_info.get('subfolder')
                            img_type = img_info.get('type', 'output') # 功能性备注: 获取图片类型（通常是 'output' 或 'temp'）

                            # 逻辑备注: 必须要有文件名才能下载
                            if filename:
                                logger.info(f"  > 准备下载图片: filename={filename}, subfolder={subfolder}, type={img_type}") # 功能性备注: 记录准备下载
                                img_download_error = None # 功能性备注: 初始化单张图片下载错误信息
                                img_response = None # 功能性备注: 初始化图片下载响应对象
                                try:
                                    # 功能性备注: 构建下载图片的请求参数
                                    view_params = {'filename': filename}
                                    if subfolder: view_params['subfolder'] = subfolder
                                    if img_type: view_params['type'] = img_type

                                    # 功能性备注: 发送 GET 请求下载图片
                                    img_response = requests.get(view_endpoint, params=view_params, timeout=60)
                                    img_response.raise_for_status() # 功能性备注: 检查下载请求的 HTTP 状态

                                    # 功能性备注: 检查返回内容的 Content-Type 是否是图片
                                    content_type = img_response.headers.get('content-type', '').lower()
                                    if 'image/' in content_type:
                                        # 功能性备注: 下载成功，将图片数据 (bytes) 添加到结果列表
                                        image_data_list.append(img_response.content)
                                        logger.info(f"    - 图片 '{filename}' 下载成功 ({len(img_response.content)} bytes)。") # 功能性备注: 记录下载成功
                                    else:
                                        # 逻辑备注: 如果 Content-Type 不是图片，则认为是下载错误
                                        img_download_error = f"下载链接 '{filename}' 返回非图片类型: {content_type}"
                                except requests.exceptions.RequestException as dl_e:
                                    # 逻辑备注: 处理下载时的网络或 HTTP 错误
                                    img_download_error = f"下载图片 '{filename}' 时网络/HTTP错误: {dl_e}"
                                except Exception as generic_dl_e:
                                     # 逻辑备注: 处理下载时的其他未知错误
                                     img_download_error = f"下载图片 '{filename}' 时发生意外错误: {generic_dl_e}"
                                finally:
                                     # 功能性备注: 确保关闭图片下载的响应对象
                                     if img_response:
                                         try: img_response.close()
                                         except Exception: pass

                                # 逻辑备注: 如果下载单张图片时出错，记录错误信息
                                if img_download_error:
                                    logger.error(f"    - {img_download_error}") # 功能性备注: 记录错误
                                    download_errors.append(img_download_error)
                            else:
                                # 逻辑备注: 如果图片信息中缺少文件名
                                logger.warning(f"  > 警告: 输出节点信息中缺少 'filename'。 Info: {img_info}") # 功能性备注: 记录警告
                                download_errors.append("输出节点信息缺少 'filename'")

                        # 功能性备注: 处理所有图片下载完成后的结果
                        if not image_data_list and download_errors:
                             # 逻辑备注: 如果一张图片都没下载成功
                             error_message = f"图片下载全部失败: {download_errors[0]}" # 只报告第一个错误
                        elif download_errors:
                             # 逻辑备注: 如果部分图片下载失败
                             logger.warning(f"警告: 部分图片下载失败 ({len(download_errors)} 个)。错误示例: {download_errors[0]}") # 功能性备注: 记录警告
                             # 逻辑备注: 即使部分失败，也认为整体可能算成功，返回已下载的图片。可以在调用处处理此警告。

                    else:
                         # 逻辑备注: 如果输出节点中没有 'images' 列表
                         error_message = f"在节点 '{expected_output_node_title}' 的输出中未找到 'images' 列表或列表无效。"
                         logger.error(f"{error_message} Node Output: {str(node_output)[:200]}...") # 功能性备注: 记录错误
                elif not error_message:
                     # 逻辑备注: 如果没有之前的错误，但找不到预期的输出节点
                     error_message = f"在历史记录输出中未找到预期节点 '{expected_output_node_title}' (尝试的 ID: {output_node_id})。"
                     logger.error(f"{error_message} Available outputs: {list(outputs.keys())}") # 功能性备注: 记录错误

            elif not error_message:
                # 逻辑备注: 如果任务完成但无法获取或解析最终历史记录
                error_message = "ComfyUI 任务完成但无法解析输出结果 (无法获取最终历史)。"
                logger.error(f"{error_message}") # 功能性备注: 记录错误

    # --- 统一处理 API 调用主 try 块的异常 ---
    except requests.exceptions.RequestException as post_e:
        # 功能性备注: 捕获提交工作流时的网络/HTTP错误
        status_code_info = f"Status: {response.status_code}" if response else "无响应"
        error_message = f"ComfyUI 提交工作流时网络/HTTP错误 ({status_code_info}): {post_e}"
        logger.error(f"{error_message}") # 功能性备注: 记录错误
    except json.JSONDecodeError as json_err:
        # 功能性备注: 捕获提交工作流响应的 JSON 解析错误
        status_code_info = f"Status: {response.status_code}" if response else "N/A"
        response_text = response.text[:200] + "..." if response else "无响应内容"
        error_message = f"ComfyUI 提交响应解析错误 (Status: {status_code_info}): {json_err}. Response: {response_text}"
        logger.error(f"{error_message}") # 功能性备注: 记录错误
    except Exception as e:
        # 功能性备注: 捕获其他所有未预料的错误
        error_message = f"调用 ComfyUI API 时发生未预期的严重错误: {e}"
        logger.exception(error_message) # 功能性备注: 记录异常

    finally:
        # 功能性备注: 确保关闭提交工作流的响应对象
        if response:
            try: response.close()
            except Exception: pass

    # --- 函数最终返回 ---
    # 逻辑备注: 如果 image_data_list 不为空，表示至少成功下载了一张图片，优先返回图片列表
    if image_data_list:
        # 逻辑备注: 如果过程中也记录了错误信息（例如部分下载失败），可以打印出来
        if error_message:
            logger.warning(f"函数返回时存在非致命错误/警告: {error_message}") # 功能性备注: 记录警告
        # 逻辑备注: 即使有警告，也返回成功获取的图片数据
        return image_data_list, None # 返回 (数据, 无错误)
    else:
        # 逻辑备注: 如果没有任何图片数据，说明整个过程失败了
        # 逻辑备注: 确保返回一个错误信息
        final_error = error_message or "ComfyUI 任务执行失败或未返回任何图片。"
        return None, final_error # 返回 (无数据, 错误信息)


def upload_image_to_comfyui(comfyui_url, local_filepath, overwrite=True, save_debug=False):
    """
    将本地图片上传到 ComfyUI 服务器的 /upload/image 端点。
    """
    # 功能性备注: 此函数负责将本地的图片文件上传到 ComfyUI 服务器，通常用于图生图或内绘的输入。
    # 逻辑备注: 检查输入 URL 和文件路径是否有效
    if not comfyui_url:
        return None, "错误: ComfyUI URL 不能为空。"
    if not local_filepath or not os.path.exists(local_filepath):
        return None, f"错误: 本地文件路径无效或文件不存在: '{local_filepath}'"

    # 功能性备注: 构建上传端点 URL
    try:
        parsed_url = urlparse(comfyui_url)
        scheme = parsed_url.scheme or "http"
        netloc = parsed_url.netloc or "127.0.0.1:8188"
        base_url = f"{scheme}://{netloc}"
        upload_endpoint = urljoin(base_url, "/upload/image")
    except Exception as url_e:
        logger.error(f"处理 ComfyUI URL 时出错: {url_e}") # 功能性备注: 记录错误
        return None, f"处理 ComfyUI URL 时出错: {url_e}"

    logger.info(f"准备上传图片: '{os.path.basename(local_filepath)}' 到 {upload_endpoint}") # 功能性备注: 记录上传信息
    response = None # 功能性备注: 初始化响应对象
    files = None # 功能性备注: 初始化文件对象

    try:
        # 功能性备注: 准备 multipart/form-data，包含图片文件和覆盖参数
        files = {'image': (os.path.basename(local_filepath), open(local_filepath, 'rb'))}
        data = {'overwrite': str(overwrite).lower()} # 功能性备注: 参数需要是字符串 'true' 或 'false'

        # 功能性备注: 如果启用了调试保存，则保存请求信息（不含文件内容）
        if save_debug:
            debug_payload = {"local_filepath": local_filepath, "overwrite": overwrite}
            _save_debug_input("comfyui", debug_payload, "upload")

        # 功能性备注: 发送 POST 请求进行上传
        response = requests.post(upload_endpoint, files=files, data=data, timeout=60) # 设置 60 秒超时
        response.raise_for_status() # 功能性备注: 检查 HTTP 错误

        logger.info(f"图片上传响应状态码: {response.status_code}") # 功能性备注: 记录响应码
        response_json = response.json() # 功能性备注: 解析 JSON 响应
        logger.info(f"图片上传响应 JSON: {response_json}") # 功能性备注: 记录响应内容

        # 功能性备注: 检查响应中是否包含服务器端的文件名 'name'
        if 'name' in response_json:
            server_filename = response_json['name']
            logger.info(f"图片上传成功，服务器文件名: '{server_filename}'") # 功能性备注: 记录成功
            return server_filename, None # 功能性备注: 返回服务器文件名和无错误
        else:
            # 逻辑备注: 如果响应成功但缺少 'name' 字段
            error_msg = "ComfyUI 图片上传错误: 响应成功但未找到 'name' 字段。"
            if 'error' in response_json: error_msg += f" 错误详情: {response_json['error']}"
            if 'message' in response_json: error_msg += f" 消息: {response_json['message']}"
            logger.error(error_msg) # 功能性备注: 记录错误
            return None, error_msg

    except requests.exceptions.RequestException as req_e:
        # 逻辑备注: 处理上传时的网络或 HTTP 错误
        error_msg = f"ComfyUI 图片上传网络/HTTP 错误: {req_e}"
        if response is not None: error_msg += f" (Status: {response.status_code})"
        logger.error(error_msg) # 功能性备注: 记录错误
        return None, error_msg
    except FileNotFoundError:
         # 逻辑备注: 处理本地文件未找到的错误
         error_msg = f"ComfyUI 图片上传错误: 本地文件未找到 '{local_filepath}'"
         logger.error(error_msg) # 功能性备注: 记录错误
         return None, error_msg
    except IOError as io_e:
        # 逻辑备注: 处理读取本地文件时的 IO 错误
        error_msg = f"ComfyUI 图片上传错误: 读取本地文件时出错 '{local_filepath}': {io_e}"
        logger.error(error_msg) # 功能性备注: 记录错误
        return None, error_msg
    except json.JSONDecodeError:
        # 逻辑备注: 处理服务器响应 JSON 解析错误
        error_msg = f"ComfyUI 图片上传错误: 无法解析服务器响应 JSON。Status: {response.status_code if response else 'N/A'}."
        if response: error_msg += f" Response: {response.text[:200]}..."
        logger.error(error_msg) # 功能性备注: 记录错误
        return None, error_msg
    except Exception as e:
        # 逻辑备注: 处理上传过程中的其他未知错误
        error_msg = f"ComfyUI 图片上传时发生未预期的严重错误: {e}"
        logger.exception(error_msg) # 功能性备注: 记录异常
        return None, error_msg
    finally:
        # 功能性备注: 确保文件句柄被关闭，释放资源
        if files and 'image' in files and hasattr(files['image'][1], 'close'):
            try:
                files['image'][1].close()
            except Exception as close_e:
                logger.warning(f"关闭上传文件句柄时出错: {close_e}") # 功能性备注: 记录关闭错误
