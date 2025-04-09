
# 小说转 KAG 脚本工具 (novel_to_ks_app)

通过谷歌 AI (Gemini) 等大型语言模型，将小说文本分步转换为 KiriKiri2 (krkr) 引擎适用的 KAG 脚本 (.ks) 文件，并可选地调用 NovelAI API 生成脚本中引用的图片。

---

## 功能简介

本工具是一个基于 Web 的应用程序，旨在帮助用户将原始的小说文本转换为适用于 KiriKiri2 引擎的 KAG 脚本（`.ks` 文件）格式。它通过调用外部的 大型语言模型 (LLM) API（目前主要测试 **Google Gemini**）分三步完成转换，并增加了调用 NovelAI API 生成图片的功能：

1.  **步骤一：格式化文本**：将原始小说文本进行预处理，自动识别说话人并在对话上方添加 `[名字]` 标记，识别内心独白并用 `*{{...}}*` 包裹。此步骤的输出结果可编辑，并可保存为 TXT 文件。
2.  **步骤二：添加 NAI 提示词**: 基于步骤一的结果和用户提供的人物基础设定（正面/负面提示词），调用 LLM **结合上下文**智能生成更具体的场景提示词，并将组合后的提示词以 `[NAI:...]` 标记插入到对应人物对话或动作之前。此步骤的输出结果可编辑，并可保存为 TXT 文件。
3.  **步骤三：转换为 KAG**: 将经过步骤二处理（包含 `[NAI:...]` 标记）的文本，转换为基本的 KAG 脚本，包含人物名称显示 (`[name]...[/name]`)、对话、旁白、心声和页面暂停 `[p]` 标签，同时将 `[NAI:...]` 标记转换为 KAG 注释和图片占位符。此步骤的结果**可编辑**，并可保存为 **UTF-16 LE 编码** 的 `.ks` 文件。
4.  **(可选) 生成图片**: 在生成 KAG 脚本后，可以点击按钮，调用 **NovelAI API** 批量生成脚本中包含的 NAI 提示对应的图片，并根据 KAG 中的文件名自动保存到服务器指定目录。成功生成图片后，脚本中对应的 NAI 注释会被移除。**（注意：此功能已实现，但因缺少 API Key 未经充分测试）**

**核心特性：**

*   **三步转换**：将文本处理任务分解，允许用户在中间步骤检查、编辑和保存。
*   **LLM 驱动**：利用 AI 能力自动进行格式化、提示词生成和 KAG 转换（目前主要测试 **Google Gemini**）。
*   **可选流式传输**：用户可以选择启用或禁用 LLM API 调用的流式传输，以平衡实时反馈和稳定性。
*   **集成 NovelAI 图片生成**：一键调用 NovelAI API 为 KAG 脚本中的提示词生成图片。**(未充分测试)**
*   **配置管理**：
    *   LLM API 参数（密钥、URL、模型、流式选项、声音路径等）可保存/加载到服务器端的 `config.json` 文件。
    *   NovelAI API 参数（密钥、保存目录、生成参数等）也保存在 `config.json`。
    *   人物基础设定可通过本地 `.json` 文件加载和保存。
    *   NovelAI 模型列表可通过本地 `.json` 文件加载，方便用户更新。
*   **用户反馈**：通过状态指示器、浏览器桌面通知和可选的声音提示告知用户处理进度和结果。
*   **结果保存与编辑**：
    *   步骤一、二、三的结果均**可编辑**。
    *   步骤一、二的结果可输入自定义文件名保存为 `.txt` 文件。
    *   步骤三的结果可输入自定义文件名保存为 `.ks` 文件（UTF-16 LE 编码）。
*   **灵活流程**：用户可以通过编辑中间步骤的文本框，从任意步骤开始。

## 环境准备

在开始之前，请确保你的计算机（将要运行此工具的服务器端）已安装以下软件：

*   **Python**: 版本 3.7 或更高。([Python 官网](https://www.python.org/)) 安装时建议勾选 "Add Python to PATH"。
*   **pip**: Python 包管理器，通常随 Python 安装。命令行运行 `pip --version` 检查。

## 安装与设置

1.  **获取文件**:
    *   确保拥有以下文件，并将它们放在同一个文件夹（目录）中：
        *   `app.py` (后端 Flask 服务器代码)
        *   `requirements.txt` (Python 依赖库列表)
        *   `templates/index.html` (前端界面代码，**必须放在 `templates` 子文件夹内**)
    *   目录结构应如下：
        ```
        your_project_folder/
        ├── app.py
        ├── requirements.txt
        └── templates/
            └── index.html
        ```

2.  **打开命令行**: 打开操作系统的命令行界面 (cmd, PowerShell, Terminal)。

3.  **进入项目目录**: 使用 `cd` 命令切换到项目文件夹。
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
    pip install -r requirements.txt
    ```
    *   等待 Flask, requests, pygame 安装完成。如果 `pygame` 安装失败或提示音频设备问题，声音提示功能将不可用，但程序主体仍可运行。

## 运行应用程序

1.  **启动服务器**: 确保在项目目录下且虚拟环境已激活，运行：
    ```bash
    python app.py
    ```

2.  **访问 Web 界面**:
    *   服务器启动后，命令行会显示运行地址，通常是 `http://127.0.0.1:5000/`。
    *   打开网页浏览器，访问该地址。

## 使用 Web 界面

Web 界面分为几个主要区域：

1.  **LLM API 与全局设置**:
    *   **LLM API Key**: 你的 Google Gemini API 密钥。**注意安全**。
    *   **LLM API Base URL**: API 的基础地址 (例如 `https://generativelanguage.googleapis.com`)。
    *   **LLM 模型名称**: 使用的模型名称 (例如 `gemini-1.5-flash-latest`)。**（目前主要测试 Gemini）**
    *   **Temperature/Max Tokens**: 控制 LLM 生成。
    *   **成功/失败提示音路径**: 服务器可访问的声音文件路径（可选）。
    *   **启用流式传输**: 勾选后，LLM 调用将逐步返回结果；取消勾选则一次性返回完整结果（可能较慢但更稳定）。
    *   **保存调试文件**: 勾选后，执行 LLM 步骤时会自动下载包含发送内容的 `.txt` 文件。
    *   **保存/加载 LLM 设置**: 保存或加载此区域的所有设置到 `config.json`。

2.  **NovelAI 图片生成设置**:
    *   **NovelAI API Key**: 你的 NovelAI API 密钥。**注意安全**。
    *   **图片保存目录**: **服务器上**用于保存生成图片的**绝对路径**（例如 `D:/nai_images` 或 `/home/user/nai_images`）。**请确保此目录存在且 Flask 服务器进程有写入权限！**
    *   **模型**:
        *   **加载模型**: 点击选择本地的 `.json` 模型配置文件（格式见下方说明）。
        *   **下拉框**: 显示从文件加载的模型列表供选择。
        *   **状态**: 显示加载的模型文件名。
    *   **采样器/步数/引导强度/种子/负面预设/质量标签**: NovelAI 的标准生成参数。
    *   **保存 NAI 设置**: 保存此区域的所有设置到 `config.json` (与 LLM 设置保存在同一个文件)。

3.  **人物设定 (用于生成 NAI 提示词)**:
    *   **加载设定文件 (.json)**: 点击选择本地的人物设定 `.json` 文件（格式：`{"人物A": {"positive": "...", "negative": "..."}, ...}`）。
    *   **保存当前设定到文件**: 将当前列表中的设定导出为 `character_profiles.json`。
    *   **列表区域**: 可直接编辑或通过按钮添加/删除人物设定。

4.  **转换流程 (三步式)**:
    *   **步骤一：转换小说格式**: 输入原文，点击按钮处理。输出结果**可编辑**。可保存为 TXT。
    *   **步骤二：添加 NAI 提示词**: 使用步骤一结果和人物设定，点击按钮处理。输出结果**可编辑**。可保存为 TXT。
    *   **步骤三：转 KAG 脚本**: 使用步骤二结果，点击按钮处理。输出结果（KAG 脚本）**可编辑**。可保存为 `.ks` 文件 (UTF-16 LE)。

5.  **最终输出与图片生成**:
    *   **KAG 脚本显示/编辑区域**: 显示步骤三生成的 KAG 脚本，**允许手动编辑**。
    *   **保存 KS**: 将当前文本框内容保存为 `.ks` 文件。
    *   **生成图片按钮**: 点击后，程序会解析当前 KAG 脚本中的 NAI 注释和图片标签，调用 NovelAI API 生成图片并保存到服务器指定目录。成功后会移除脚本中对应的注释。**(功能未充分测试)**
    *   **图片生成状态**: 显示图片生成过程的消息或结果。

## NovelAI 模型文件格式

用于加载 NovelAI 模型列表的 `.json` 文件应包含一个数组，每个数组元素是一个对象，格式如下：

```json
[
  {
    "name": "Anime V3 (推荐)", // 在下拉框中显示的名称
    "value": "nai-diffusion-3" // 调用 API 时使用的实际模型标识符
  },
  {
    "name": "Anime V2",
    "value": "nai-diffusion-2"
  }
  // ... 可以添加更多模型
]
```

## 常见工作流程

*   **完整流程**: 配置LLM API -> (可选)配置NAI API & 加载模型 -> 加载/创建人物设定 -> 粘贴原文 -> 步骤一 -> (编辑/保存) -> 步骤二 -> (编辑/保存) -> 步骤三 -> (编辑 KAG) -> 输入文件名 -> 保存KS -> (可选)点击生成图片。
*   **仅文本转换**: 配置LLM API -> 加载/创建人物设定 -> ... -> 保存KS。
*   **仅生成图片**: 配置NAI API & 加载模型 -> (将包含 NAI 注释和图片标签的 KAG 脚本粘贴到最终输出框) -> 点击生成图片。

## 重要提示与故障排除

*   **API Key 安全**: `config.json` 存储在服务器端，包含敏感信息，务必注意保密和访问权限。
*   **LLM 模型**: 目前主要使用和测试了 **Google Gemini** 系列模型。其他 LLM API 的兼容性未知。
*   **NovelAI 图片生成**: 此功能**未经充分测试**，因为开发过程中缺少有效的 API Key。使用时请自行承担风险，并注意 API 额度和可能的错误。
*   **图片保存目录**: 必须是**服务器上的绝对路径**，且 Flask 进程需要有**写入权限**。如果路径配置错误或无权限，图片生成会失败。
*   **文件编码**: 保存的 `.ks` 文件是 **UTF-16 LE (带 BOM)**。请使用支持此编码的编辑器（如 VS Code, Notepad++）打开和编辑。
*   **流式 vs 非流式**:
    *   **流式 (默认)**：实时看到结果，但可能因网络或 LLM 问题中断。超时 (`timeout=600`) 主要限制数据间歇。
    *   **非流式**: 等待完整结果，界面会“卡住”，但可能更稳定。超时 (`timeout=600`) 限制整个请求时长。如果处理时间过长，仍可能超时。
*   **NAI 图片生成超时**: 单张图片生成超时为 300 秒 (5 分钟)。如果脚本中图片过多，总处理时间可能超过浏览器默认超时。
*   **依赖/声音**: `pygame` 安装失败不影响核心文本处理功能，仅禁用声音提示。
*   **缓存**: 遇到界面问题时，尝试强制刷新浏览器 (`Ctrl+Shift+R`)。

## 停止应用程序

*   在运行 `python app.py` 的命令行窗口按下 `Ctrl + C`。

---

## 更新日志

*   **2025-04-09**:
    *   **新增 非流式传输选项**: 用户可在 LLM 设置中选择是否使用流式传输，以应对流式可能不稳定的情况。
    *   **新增 NovelAI 图片生成功能**: 添加调用 NovelAI API 为 KAG 脚本生成图片的功能，并自动移除成功图片的注释。**(注意：此功能未经充分测试)**
    *   **新增 NovelAI 配置界面**: 允许用户配置 NAI API Key、保存目录及生成参数。
    *   **新增 NAI 模型本地化**: NAI 模型列表不再硬编码，改为通过加载本地 `.json` 文件进行配置。
    *   **KAG 脚本可编辑**: 最终生成的 KAG 脚本输出框现在允许用户手动编辑。
    *   **Bug 修复**: 修正了之前版本中多处 Python 语法错误 (`try...except`) 和 JavaScript 元素 ID 不匹配的问题。
    *   **说明更新**: 明确指出 LLM 目前主要测试 Gemini，NAI 图片生成功能未经充分测试。
*   **2025-04-08**:
    *   **新增三步转换流程**: 格式化 -> 加提示 -> 转 KAG。
    *   **新增人物设定管理**: 加载/保存 `.json`，编辑、添加、删除人物基础提示。
    *   **新增文件保存选项**: 各步骤结果可保存为 TXT 或 KS (UTF-16LE)。
    *   **Prompt 优化**: 大幅改进 Prompt 以支持动态提示词和 NAI 标记。
    *   **界面调整与代码改进**。

```
