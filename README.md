
# 小说转 KAG 脚本工具 (模块化版)

通过谷歌 AI (Gemini) 等大型语言模型，将小说文本分步转换为 KiriKiri2 (krkr) 引擎适用的 KAG 脚本 (.ks) 文件，并可选地调用 NovelAI API、Stable Diffusion WebUI API 生成图片，或调用 GPT-SoVITS API 生成语音。

---

## 功能简介

本工具是一个基于 Python 和 CustomTkinter 的**桌面应用程序**，旨在帮助用户将原始的小说文本转换为适用于 KiriKiri2 引擎的 KAG 脚本（`.ks` 文件）格式。它通过调用外部的大型语言模型 (LLM) API（目前主要测试 **Google Gemini**）分多步完成转换，并增加了调用多种 AI API 生成图片和语音的功能：

1.  **步骤一：格式化文本**：将原始小说文本进行预处理，自动识别说话人并在对话上方添加 `[名字]` 标记，识别内心独白并用 `*{{...}}*` 包裹。此步骤的输出结果可编辑。
2.  **步骤二：添加图像提示词**: 基于步骤一的结果和用户提供的人物基础设定（正面/负面提示词），调用 LLM **结合上下文**智能生成更具体的场景提示词，并将组合后的提示词以 `[NAI:...]` 标记（兼容 NAI 和 SD）插入到对应人物对话或动作之前。此步骤的输出结果可编辑。
3.  **步骤三：建议 BGM 并转 KAG**:
    *   调用 LLM 分析文本，在合适的场景切换或情绪变化处添加 BGM 推荐注释。
    *   将经过处理（包含提示词和 BGM 建议标记）的文本，转换为基本的 KAG 脚本，包含人物名称显示 (`[name]...[/name]`)、对话、旁白、心声、页面暂停 `[p]` 标签。
    *   同时，将 `[NAI:...]` 标记转换为 KAG 注释（包含提示词）和**图片占位符** `[INSERT_IMAGE_HERE:名字]`。
    *   自动在对话行和**心声行**上方插入**注释掉的语音占位符** `; @playse storage="PLACEHOLDER_名字_序号.wav" ...`，并由 Python 代码确保序号正确递增。
    *   此步骤的结果（KAG 脚本）**可编辑**。
4.  **(可选) 替换图片占位符**: 手动或自动将 `[INSERT_IMAGE_HERE:名字]` 占位符替换为实际的**注释掉的** `[image storage="..."]` 标签，文件名包含用户定义的前缀和序号。
5.  **(可选) 生成图片 (NAI/SD)**: 在生成 KAG 脚本并替换占位符后，可以点击按钮：
    *   调用 **NovelAI API** 或 **Stable Diffusion WebUI API** 批量生成脚本中 NAI/SD 提示对应的图片。
    *   图片根据 KAG 中的文件名自动保存到用户指定的目录。
    *   成功生成图片后，脚本中对应的 `[image]` 标签的注释会被**自动取消**。
    *   **测试状态：已初步测试，基本可用，但可能存在边缘情况或配置问题。**
6.  **(可选) 生成语音 (GPT-SoVITS)**: 在生成 KAG 脚本后，可以点击按钮：
    *   调用 **GPT-SoVITS API** 批量生成脚本中注释掉的 `@playse` 标签对应的语音。
    *   语音根据 KAG 中的文件名（包含正确序号）自动保存到用户指定的目录。
    *   成功生成语音后，脚本中对应的 `@playse` 标签的注释会被**自动取消**。
    *   **测试状态：已初步测试 (使用 AI Hobbyist 交流社区的整合包 API)，基本可用，但可能存在边缘情况或配置问题。**

**核心特性：**

*   **多步转换**：将文本处理任务分解，允许用户在中间步骤检查、编辑。
*   **LLM 驱动**：利用 AI 能力自动进行格式化、提示词生成、BGM 建议和 KAG 转换（目前主要测试 **Google Gemini**）。
*   **可选流式传输**：用户可以选择启用或禁用 LLM API 调用的流式传输 (Google API)。
*   **集成多种 AI 生成**: 支持 NAI/SD 图片生成和 GPT-SoVITS 语音生成（**注意：均已初步测试，但建议谨慎使用**）。
*   **模块化结构**: 代码被组织到 `api`, `core`, `tasks`, `ui` 子目录中，更易维护。
*   **配置管理**：
    *   LLM、NAI、SD、GPT-SoVITS 的 API 参数及全局设置分别保存/加载到 `configs/` 目录下的 `.json` 文件。
    *   人物基础设定可通过本地 `.json` 文件加载和保存。
    *   NovelAI 模型列表可通过本地 `.json` 文件加载。
*   **用户反馈**：通过状态标签、可选的声音提示和 Windows 桌面通知（如果安装了 `win10toast`）告知用户处理进度和结果。
*   **结果编辑与保存**：
    *   所有文本处理步骤的结果均**可编辑**。
    *   最终的 KAG 脚本可保存为 **UTF-16 LE (带 BOM)** 编码的 `.ks` 文件。
*   **灵活流程**：用户可以通过编辑中间步骤的文本框，从任意步骤开始或修改。
*   **UI 可滚动**: 所有标签页内容均可通过垂直滚动条查看，适应不同屏幕尺寸和内容长度。
*   **高级参数配置**:
    *   可配置 Google API 的 Top P 和 Top K 采样参数。
    *   可单独覆盖 KAG 转换步骤使用的 LLM 温度。
    *   可配置是否启用声音提示和 Windows 系统通知。

## 环境准备

在开始之前，请确保你的计算机已安装以下软件：

*   **Python**: 版本 3.7 或更高。([Python 官网](https://www.python.org/)) 安装时建议勾选 "Add Python to PATH"。
*   **pip**: Python 包管理器，通常随 Python 安装。命令行运行 `pip --version` 检查。

## 安装与设置

1.  **获取文件**:
    *   确保拥有所有项目文件，包括 `main_app.py` 以及 `api/`, `core/`, `tasks/`, `ui/`, `configs/`, `assets/` 等目录及其内容。
    *   基本目录结构应如下（省略部分文件）：
        ```
        你的项目根目录/
        ├── main_app.py
        ├── api/
        │   ├── __init__.py
        │   └── ... (api helpers)
        ├── core/
        │   ├── __init__.py
        │   └── ... (config_manager, utils, etc.)
        ├── tasks/
        │   ├── __init__.py
        │   └── ... (task logic)
        ├── ui/
        │   ├── __init__.py
        │   └── ... (tab classes)
        ├── configs/
        └── assets/
        ```

2.  **打开命令行**: 打开操作系统的命令行界面 (cmd, PowerShell, Terminal)。

3.  **进入项目根目录**: 使用 `cd` 命令切换到包含 `main_app.py` 的文件夹。
    ```bash
    cd path/to/your_project_folder
    ```

4.  **创建虚拟环境 (推荐)**:
    ```bash
    python -m venv venv
    ```

5.  **激活虚拟环境**:
    *   Windows: `venv\Scripts\activate`
    *   macOS / Linux: `source venv/bin/activate`
    *   成功后提示符前通常显示 `(venv)`。

6.  **安装依赖库**: 在**激活的虚拟环境**中运行：
    ```bash
    pip install customtkinter requests pygame win10toast
    ```
    *   `customtkinter`: UI 框架。
    *   `requests`: 用于进行 API 调用。
    *   `pygame` (可选): 用于播放提示音。如果安装失败或提示音频设备问题，声音提示功能将不可用。
    *   `win10toast` (可选, 仅 Windows): 用于显示桌面通知。如果不需要或非 Windows 系统，可以不安装。

## 运行应用程序

1.  **启动程序**: 确保在项目根目录下且虚拟环境已激活，运行：
    ```bash
    python main_app.py
    ```

2.  **应用程序窗口**: 程序将启动一个桌面应用程序窗口。

## 使用应用程序界面

应用程序包含多个标签页：

1.  **LLM 与全局设置**:
    *   配置 Google Gemini API（密钥、URL、模型、Temperature、**Top P、Top K** 等）。
    *   配置全局指令、提示音路径、流式传输选项、Google API 代理等。
    *   **保存/加载设置** 保存或加载此标签页的配置到 `configs/llm_global_config.json`。

2.  **NAI 设置**:
    *   配置 NovelAI API（密钥、图片保存目录、模型、采样器、生成参数、NAI API 代理等）。
    *   加载本地的 NAI 模型 `.json` 文件。
    *   **保存/加载设置** 保存或加载此标签页的配置到 `configs/nai_config.json`。
    *   **测试状态：已初步测试。**

3.  **SD WebUI 设置**:
    *   配置 Stable Diffusion WebUI API（URL、图片保存目录、采样器、生成参数、全局附加提示词等）。
    *   **保存/加载设置** 保存或加载此标签页的配置到 `configs/sd_config.json`。
    *   **测试状态：已初步测试。**

4.  **GPT-SoVITS 设置**:
    *   配置 GPT-SoVITS API（URL、音频保存目录、音频前缀、**下载 URL 前缀**、默认生成参数等）。
    *   管理**人物语音映射**（将 KAG 脚本中的人物名称映射到参考语音文件路径、参考文本和语言）。
    *   **保存/加载设置** 保存或加载此标签页的配置到 `configs/gptsovits_config.json`。
    *   **测试状态：已初步测试 (使用 AI Hobbyist 交流社区的整合包 API)。**

5.  **人物设定**:
    *   用于管理生成图像提示词时使用的人物基础设定（Positive/Negative Prompts）。
    *   可通过本地 `.json` 文件加载/保存。
    *   可在界面中直接添加、编辑、删除人物设定。

6.  **转换流程**:
    *   **步骤一：转换小说格式**: 输入原文 -> 点击按钮 -> 输出格式化文本。
    *   **步骤二：添加提示词**: 使用步骤一结果和人物设定 -> 点击按钮 -> 输出含提示词标记的文本。
    *   **步骤三：建议BGM并转KAG**: 使用步骤二结果 -> 点击按钮 -> 输出包含 BGM 建议、带序号语音占位符和图片占位符的 KAG 脚本。**可在此处覆盖 KAG 转换的温度**。
    *   **KAG 脚本编辑区**: 显示步骤三结果，**允许手动编辑**。
    *   **图片/语音生成选项**: 配置生成范围（所有/指定）和数量（图片）。
    *   **手动替换图片占位符**: 点击将 `[INSERT_IMAGE_HERE:...]` 替换为注释掉的 `[image storage="..."]`。
    *   **生成图片 (NAI/SD)**: 点击调用相应 API 生成图片，成功后取消对应 `[image]` 注释。
    *   **生成语音 (GPT-SoVITS)**: 点击调用 API 生成语音，成功后取消对应 `@playse` 注释。
    *   **保存 KAG 脚本 (.ks)**: 点击将当前 KAG 脚本编辑区内容保存为 `.ks` 文件 (UTF-16 LE 编码)。

7.  **顶部栏**:
    *   **保存/加载所有设置**: 一键保存或加载所有配置标签页的设置（不包括人物设定列表）。
    *   **通知开关**: 控制是否启用声音提示和 Windows 系统通知。
    *   **外观**: 切换亮色/暗色/系统模式。

## NovelAI 模型文件格式

(与之前版本相同)

```json
[
  {
    "name": "Anime V3 (推荐)",
    "value": "nai-diffusion-3"
  },
  {
    "name": "Anime V2",
    "value": "nai-diffusion-2"
  }
]
```

## 常见工作流程

*   **完整流程 (包括图片和语音)**: 配置 LLM (含 Top P/K) -> 配置 NAI/SD -> 配置 GPT-SoVITS (含下载 URL 前缀) -> 加载/创建人物设定 -> 加载/创建语音映射 -> 配置通知开关 -> 粘贴原文 -> 步骤一 -> 步骤二 -> (可选)配置 KAG 温度覆盖 -> 步骤三 -> (编辑 KAG) -> 手动替换图片占位符 -> (可选)生成图片 (NAI/SD) -> (可选)生成语音 (GPT-SoVITS) -> 保存 KS。
*   **仅文本转换**: 配置 LLM -> 加载/创建人物设定 -> ... -> 保存 KS。
*   **仅生成图片/语音**: 配置相应 API -> 将包含正确注释标签和文件名的 KAG 脚本粘贴到最终输出框 -> 配置生成选项 -> 点击生成按钮。

## 重要提示与故障排除

*   **API Key 安全**: 配置文件存储在本地 `configs/` 目录，请注意保密。
*   **测试状态**:
    *   **Google Gemini API (LLM)**：是主要测试和使用的 API。
    *   **NovelAI API / SD WebUI API / GPT-SoVITS API**：集成代码已添加，并经过**初步测试**。建议在使用前仔细检查配置，并注意 API 额度、服务器状态及可能的错误。
*   **文件/目录路径**:
    *   图片/音频**保存目录**必须是应用程序可访问的**绝对或相对路径**。确保程序有**写入权限**。
    *   GPT-SoVITS 的**参考语音路径** (`refer_wav_path`) 需要是 **GPT-SoVITS 服务器能够访问的路径**。
*   **GPT-SoVITS 下载 URL 前缀**: 如果你的 GPT-SoVITS API 服务器运行在 `0.0.0.0` 或 Docker 等导致自动生成的下载 URL 无效的情况下，请务必在此配置项中填入**客户端可以访问**的正确基础 URL（例如 `http://你的服务器IP:端口号`）。
*   **文件编码**: 保存的 `.ks` 文件是 **UTF-16 LE (带 BOM)**。请使用支持此编码的编辑器（如 VS Code, Notepad++）打开和编辑。
*   **流式 vs 非流式 (Google API)**:
    *   **流式 (默认)**：实时反馈，可能因网络或 API 问题中断。
    *   **非流式**: 等待完整结果，界面会暂时无响应，但可能更稳定。
*   **图片/语音生成**: 这些过程可能耗时较长，请耐心等待。如果生成失败，请检查：
    *   API 配置是否正确（URL、Key、路径、模型名称等）。
    *   对应的 API 服务是否正在运行。
    *   网络连接是否正常。
    *   保存目录是否有写入权限。
    *   (GPT-SoVITS) 参考语音路径是否有效，人物映射是否正确，随机模式文件夹内容是否配对。
    *   控制台输出的错误信息。
*   **依赖/声音/通知**: `pygame` 或 `win10toast` 安装失败不影响核心文本处理功能，仅禁用相应功能。
*   **界面卡顿**: 长时间运行或处理大量文本时，UI 可能会有卡顿，尤其是在非流式模式下等待 LLM 响应时。

## 停止应用程序

*   关闭应用程序窗口，或在运行 `python main_app.py` 的命令行窗口按下 `Ctrl + C`。

---

## 更新日志

*   **2025-04-14**:
    *   **UI 改进**: 为所有标签页添加主滚动条，解决内容过多无法查看的问题。
    *   **LLM 参数**: 在 LLM 设置中添加 Top P 和 Top K 参数配置。
    *   **KAG 温度覆盖**: 在 Workflow 标签页添加选项，允许为 KAG 转换步骤单独设置 LLM 温度。
    *   **通知开关**: 在顶部栏添加复选框，控制是否启用声音和 Windows 系统通知。
    *   **语音占位符**: 修正 KAG 转换逻辑，确保 `@playse` 占位符中的文件名包含正确的、针对每个角色的递增序号。
    *   **GPT-SoVITS 随机模式**: 修正 Bug，确保随机选择的参考音频和参考文本正确配对。
    *   **GPT-SoVITS 下载 URL**: 修正 API 调用逻辑，确保客户端配置的 `audio_dl_url` 能够正确覆盖服务器返回的 URL。
    *   **测试状态更新**: 对 SD/GPT-SoVITS 的 API 集成进行了初步测试。
*   **2025-04-11**:
    *   **代码结构模块化**: 将 `.py` 文件移动到 `api`, `core`, `tasks`, `ui` 子目录。
    *   **新增 Stable Diffusion 支持**: 添加 SD WebUI API 配置和生成功能。
    *   **新增 GPT-SoVITS 支持**: 添加 GPT-SoVITS API 配置（含映射）和生成功能。
    *   **KAG 脚本改进**: 自动生成 `@playse` 占位符，增加后处理逻辑，生成成功后自动取消注释。
    *   **UI 调整**: 增加 SD、GPT-SoVITS 配置标签页；Workflow 标签页增加生成选项和按钮。
    *   **新增 KAG 保存按钮**。
    *   **README 更新**。
    *   **修复**: 修正 `.ks` 文件保存编码。
*   **2025-04-09**:
    *   新增 非流式传输选项 (Google API)。
    *   新增 NovelAI 图片生成功能。
    *   新增 NovelAI 配置界面及模型加载。
    *   KAG 脚本输出框可编辑。
    *   修复 Bug。
*   **2025-04-08**:
    *   初始版本，包含三步文本转换流程和人物设定管理。
