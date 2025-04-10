# sound_player.py
import pygame
import os
import traceback

# --- Pygame 初始化 ---
PYGAME_AVAILABLE = False # 标记 Pygame 是否可用
try:
    # 尝试初始化 Pygame 的音频混合器模块
    pygame.mixer.init()
    PYGAME_AVAILABLE = True # 初始化成功，标记为可用
    print("Pygame mixer 初始化成功 (sound_player)。")
except ImportError:
    # 如果导入 Pygame 失败
    print("警告：未找到 Pygame 库 (sound_player)。声音播放功能将被禁用。")
    print("如果需要播放提示音，请安装 Pygame: pip install pygame")
except pygame.error as init_err:
    # 如果 Pygame 已安装但初始化 mixer 失败 (例如没有音频设备)
    print(f"警告：无法初始化 pygame mixer (sound_player): {init_err}。声音播放功能将被禁用。")

def play_sound(sound_path):
    """
    播放指定路径的声音文件。

    Args:
        sound_path (str): 声音文件的完整路径。
    """
    # 检查 Pygame 是否可用
    if not PYGAME_AVAILABLE:
        # print("[声音禁用] Pygame 不可用或 mixer 初始化失败。") # 避免过多日志
        return

    # 检查声音路径是否有效
    if not sound_path or not isinstance(sound_path, str):
        print(f"错误：无效的声音文件路径: {sound_path}")
        return
    if not os.path.exists(sound_path):
        print(f"错误：声音文件未找到: {sound_path}")
        return

    try:
        # 再次检查 mixer 是否已初始化 (防御性编程)
        if not pygame.mixer.get_init():
             print("警告：Pygame Mixer 未初始化，尝试重新初始化...")
             pygame.mixer.init()
             # 如果再次初始化失败，则放弃播放
             if not pygame.mixer.get_init():
                  print("错误：无法重新初始化 Pygame Mixer。无法播放声音。")
                  return

        print(f"尝试加载声音文件: {sound_path}")
        # 加载声音文件
        sound = pygame.mixer.Sound(sound_path)

        print(f"尝试播放声音: {sound_path}")
        # 播放声音
        sound.play()
        print(f"声音 '{os.path.basename(sound_path)}' 正在播放...")

    except pygame.error as e:
        # 捕获 Pygame 相关的错误 (例如文件格式不支持、设备问题)
        print(f"播放声音时出现 Pygame 错误 ({sound_path}): {e}")
        traceback.print_exc()
    except Exception as e:
        # 捕获其他意外错误
        print(f"播放声音时出现意外错误 ({sound_path}): {e}")
        traceback.print_exc()

# --- (可选) 停止所有声音的功能 ---
def stop_all_sounds():
    """停止当前所有正在播放的声音"""
    if PYGAME_AVAILABLE and pygame.mixer.get_init():
        try:
            pygame.mixer.stop()
            print("已停止所有播放中的声音。")
        except pygame.error as e:
            print(f"停止声音时出错: {e}")