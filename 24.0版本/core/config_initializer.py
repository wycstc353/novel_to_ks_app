# core/config_initializer.py
import logging
from pathlib import Path
# 导入 config_manager 来访问配置定义和保存函数
from . import config_manager

# 获取当前模块的 logger 实例
logger = logging.getLogger(__name__)

def ensure_all_configs_exist():
    """
    检查所有在 config_manager 中定义的配置文件是否存在。
    如果某个配置文件不存在，则使用其默认配置创建该文件。
    """
    logger.info("开始检查并确保所有配置文件存在...")
    created_count = 0
    checked_count = 0

    try:
        # 确保 configs 目录存在
        config_manager._ensure_config_dir()

        # 遍历在 config_manager 中定义的所有配置文件类型
        for config_type, config_info in config_manager.CONFIG_FILES.items():
            checked_count += 1
            config_path = config_info.get("path")
            defaults = config_info.get("defaults")

            # 检查路径和默认值是否有效
            if not isinstance(config_path, Path) or defaults is None:
                logger.warning(f"跳过无效的配置定义: {config_type}")
                continue

            # 检查配置文件是否存在
            if not config_path.exists():
                logger.info(f"配置文件 '{config_path}' 不存在，将使用默认值创建...")
                # 调用 config_manager 中的保存函数来创建文件并写入默认值
                if config_manager.save_config(config_type, defaults):
                    logger.info(f"成功创建默认配置文件: {config_path}")
                    created_count += 1
                else:
                    # save_config 内部会记录详细错误，这里只记录创建失败
                    logger.error(f"创建默认配置文件 '{config_path}' 失败。")
            else:
                # 文件已存在，无需操作
                logger.debug(f"配置文件 '{config_path}' 已存在。")

        logger.info(f"配置文件检查完成。共检查 {checked_count} 种配置，新创建 {created_count} 个文件。")

    except Exception as e:
        # 捕获遍历或检查过程中的意外错误
        logger.exception(f"检查或创建配置文件时发生意外错误: {e}")