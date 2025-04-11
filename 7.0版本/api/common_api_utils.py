# api/common_api_utils.py
"""
包含 API 助手模块可能共用的工具函数。
"""
import requests # _get_proxies 需要 requests

def _get_proxies(proxy_config):
    """
    根据传入的代理配置字典，返回适用于 requests 库的 proxies 字典。
    能自动识别 Google 和 NAI 的代理配置键。

    Args:
        proxy_config (dict or None): 包含代理设置的字典。
            Google: {"use_proxy": bool, "proxy_address": str, "proxy_port": str}
            NAI: {"nai_use_proxy": bool, "nai_proxy_address": str, "nai_proxy_port": str}

    Returns:
        dict or None: requests 库使用的 proxies 字典，或 None (如果不使用代理)。
    """
    proxies = None
    use_key = "use_proxy" # 默认 Google API 的 key
    addr_key = "proxy_address"
    port_key = "proxy_port"
    api_name = "Google" # 默认 API 名称

    # 检查是否是 NAI 的代理配置键存在
    if proxy_config and "nai_use_proxy" in proxy_config:
        use_key = "nai_use_proxy"
        addr_key = "nai_proxy_address"
        port_key = "nai_proxy_port"
        api_name = "NAI"

    # 检查是否启用代理，并且地址和端口有效
    if proxy_config and proxy_config.get(use_key) and proxy_config.get(addr_key) and proxy_config.get(port_key):
        addr = proxy_config[addr_key]
        port = proxy_config[port_key]
        # 确保地址和端口不为空字符串
        if addr and port:
            # 构建代理 URL (假设是 HTTP 代理)
            # 注意：如果代理需要认证，格式会更复杂 (http://user:pass@host:port)
            # 检查地址是否已包含协议头
            if not addr.startswith(('http://', 'https://', 'socks5://', 'socks4://')):
                 url = f"http://{addr}:{port}" # 默认使用 http
            else:
                 url = f"{addr}:{port}" # 如果已有协议头，直接拼接端口

            proxies = {"http": url, "https": url} # 同时为 http 和 https 设置代理
            print(f"[{api_name} API Helper] 使用代理: {url}")
        else:
            print(f"[{api_name} API Helper] 代理已启用但地址或端口为空，将不使用代理。")
    else:
        print(f"[{api_name} API Helper] 未配置或未启用代理。")
    return proxies