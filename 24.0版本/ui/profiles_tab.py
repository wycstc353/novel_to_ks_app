# ui/profiles_tab.py
import customtkinter as ctk
from tkinter import StringVar, messagebox, filedialog, Toplevel # 功能性备注: 导入 Toplevel 用于 LoRA 编辑器
import json # 功能性备注: 导入 json 用于处理文件加载/保存
import os # 功能性备注: 导入 os 用于路径操作
import traceback # 功能性备注: 保留用于错误处理（虽然 logger.exception 更好）
import logging # 功能性备注: 导入日志模块
# 功能性备注: 导入 UI 辅助函数
from .ui_helpers import create_help_button
# 功能性备注: 导入 tkinter BaseWidget 用于类型检查
from tkinter import BaseWidget

# 功能性备注: 获取当前模块的 logger 实例
logger = logging.getLogger(__name__)

class ProfilesTab(ctk.CTkFrame):
    """人物设定管理的 UI 标签页 (改为下拉选择+单项编辑模式，支持扩展提示词和 LoRA)""" # 功能性备注: 类定义，说明其功能和模式
    def __init__(self, master, config_manager, app_instance):
        # 功能性备注: 初始化父类 Frame
        super().__init__(master, fg_color="transparent")
        self.config_manager = config_manager
        self.app = app_instance
        self.character_profiles = {} # 功能性备注: 存储所有人物设定数据
        self.loaded_filepath = None # 功能性备注: 存储当前加载的文件路径
        self.lora_editor_window = None # 功能性备注: 用于跟踪 LoRA 编辑器窗口
        self.current_selected_profile_key = None # 功能性备注: 存储当前下拉框选中的人物 Key
        self.profile_selector_var = StringVar() # 功能性备注: 下拉选择框的变量

        # --- UI 构建 ---
        # 功能性备注: 配置网格，让编辑区域可扩展
        self.grid_rowconfigure(2, weight=1) # 让编辑区域行扩展
        self.grid_columnconfigure(0, weight=1) # 让列扩展

        # --- 固定部分：文件操作和选择器区域 ---
        # 功能性备注: 创建顶部框架，包含文件操作按钮和状态标签
        self.top_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.top_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        # 功能性备注: 文件操作按钮
        self.load_button = ctk.CTkButton(self.top_frame, text="加载设定文件 (.json)", command=self.load_profiles_from_file)
        self.load_button.pack(side="left", padx=5)
        self.save_button = ctk.CTkButton(self.top_frame, text="保存所有设定到文件", command=self.save_profiles_to_file, state="disabled") # 保存所有设定
        self.save_button.pack(side="left", padx=5)
        self.add_button = ctk.CTkButton(self.top_frame, text="添加人物", command=self.add_new_profile)
        self.add_button.pack(side="left", padx=5)
        self.remove_button = ctk.CTkButton(self.top_frame, text="删除当前人物", command=self.remove_profile, state="disabled", fg_color="#DB3E3E", hover_color="#B82E2E") # 删除当前人物按钮
        self.remove_button.pack(side="left", padx=5)
        self.file_status_label = ctk.CTkLabel(self.top_frame, text="尚未加载人物设定文件", text_color="gray", wraplength=300)
        self.file_status_label.pack(side="left", padx=10, fill="x", expand=True)

        # 功能性备注: 人物选择器和保存当前按钮框架
        self.selector_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.selector_frame.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="ew")
        self.selector_frame.grid_columnconfigure(1, weight=1) # 让选择器扩展
        profile_selector_label = ctk.CTkLabel(self.selector_frame, text="选择人物:")
        profile_selector_label.grid(row=0, column=0, padx=(0, 5), pady=5, sticky="w")
        self.profile_selector = ctk.CTkOptionMenu(self.selector_frame, variable=self.profile_selector_var, command=self._on_profile_selected, state="disabled", dynamic_resizing=False) # 下拉选择框
        self.profile_selector.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        self.save_current_profile_button = ctk.CTkButton(self.selector_frame, text="保存当前人物设定", command=self._save_current_profile, state="disabled") # 保存当前人物按钮
        self.save_current_profile_button.grid(row=0, column=2, padx=5, pady=5, sticky="e")

        # --- 滚动部分：单个任务编辑区域 ---
        # 功能性备注: 创建可滚动的编辑区域框架
        self.edit_scrollable_frame = ctk.CTkScrollableFrame(self, label_text="编辑当前人物设定")
        self.edit_scrollable_frame.grid(row=2, column=0, padx=10, pady=(0, 10), sticky="nsew")
        self.edit_scrollable_frame.grid_columnconfigure(1, weight=1) # 让输入框列扩展

        # 功能性备注: 在编辑区域内构建控件 (初始为空，由 _on_profile_selected 填充)
        self._build_edit_area(self.edit_scrollable_frame)

        logger.info("[ProfilesTab] 人物设定标签页 UI 构建完成 (下拉选择模式)。") # 功能性备注
        self._update_profile_selector() # 功能性备注: 初始更新下拉列表 (可能为空)

    def _build_edit_area(self, master_frame):
        """在指定的父框架（滚动编辑区域）内构建用于编辑单个任务的 UI 控件"""
        # 功能性备注: 此函数创建编辑区域的框架和控件，但不填充数据
        current_row = 0

        # --- 名称设置 ---
        # 功能性备注: 创建名称设置的子框架
        name_frame = ctk.CTkFrame(master_frame, fg_color="transparent")
        name_frame.grid(row=current_row, column=0, columnspan=2, pady=(0, 5), sticky="ew")
        name_frame.grid_columnconfigure(1, weight=1)
        name_frame.grid_columnconfigure(3, weight=1)
        # 功能性备注: 显示名称 (标签显示，不可编辑 Key)
        display_name_label_fixed = ctk.CTkLabel(name_frame, text="显示名称 (Key):")
        display_name_label_fixed.grid(row=0, column=0, padx=5, pady=2, sticky="w")
        self.display_name_label = ctk.CTkLabel(name_frame, text="- 未选择 -", anchor="w", font=ctk.CTkFont(weight="bold")) # 用于显示当前 Key
        self.display_name_label.grid(row=0, column=1, padx=5, pady=2, sticky="w")
        # 功能性备注: 替换名称输入框
        repl_name_label = ctk.CTkLabel(name_frame, text="替换名称:")
        repl_name_label.grid(row=0, column=2, padx=(10, 5), pady=2, sticky="w")
        self.repl_var = StringVar()
        self.repl_entry = ctk.CTkEntry(name_frame, textvariable=self.repl_var, placeholder_text="为空则使用显示名称")
        self.repl_entry.grid(row=0, column=3, padx=5, pady=2, sticky="ew")
        current_row += 1

        # --- 图像路径设置 ---
        # 功能性备注: 创建图像路径设置的子框架
        image_frame = ctk.CTkFrame(master_frame, fg_color="transparent")
        image_frame.grid(row=current_row, column=0, columnspan=2, pady=5, sticky="ew")
        image_frame.grid_columnconfigure(1, weight=1) # 参考图路径扩展
        image_frame.grid_columnconfigure(4, weight=1) # 蒙版图路径扩展
        # 功能性备注: 参考图像路径输入和浏览按钮
        img_path_label = ctk.CTkLabel(image_frame, text="参考图像 (图生图):")
        img_path_label.grid(row=0, column=0, padx=5, pady=2, sticky="w")
        self.img_path_var = StringVar()
        self.img_path_entry = ctk.CTkEntry(image_frame, textvariable=self.img_path_var, placeholder_text="为空则执行文生图")
        self.img_path_entry.grid(row=0, column=1, padx=5, pady=2, sticky="ew")
        img_browse_frame = ctk.CTkFrame(image_frame, fg_color="transparent")
        img_browse_frame.grid(row=0, column=2, padx=(5, 0), pady=2, sticky="w")
        self.img_browse_button = ctk.CTkButton(img_browse_frame, text="...", width=25, command=self.browse_reference_image) # 绑定新方法
        self.img_browse_button.pack(side="left")
        if help_btn := create_help_button(img_browse_frame, "profiles_tab_ui", "reference_image"): help_btn.pack(side="left", padx=(5, 0))
        # 功能性备注: 蒙版图像路径输入和浏览按钮
        mask_path_label = ctk.CTkLabel(image_frame, text="蒙版图像 (内/外绘):")
        mask_path_label.grid(row=0, column=3, padx=(10, 5), pady=2, sticky="w")
        self.mask_path_var = StringVar()
        self.mask_path_entry = ctk.CTkEntry(image_frame, textvariable=self.mask_path_var, placeholder_text="可选，用于内/外绘")
        self.mask_path_entry.grid(row=0, column=4, padx=5, pady=2, sticky="ew")
        mask_browse_frame = ctk.CTkFrame(image_frame, fg_color="transparent")
        mask_browse_frame.grid(row=0, column=5, padx=(5, 0), pady=2, sticky="w")
        self.mask_browse_button = ctk.CTkButton(mask_browse_frame, text="...", width=25, command=self.browse_mask_image) # 绑定新方法
        self.mask_browse_button.pack(side="left")
        if help_btn := create_help_button(mask_browse_frame, "profiles_tab_ui", "mask_image"): help_btn.pack(side="left", padx=(5, 0))
        current_row += 1

        # --- 提示词设置 (使用 Textbox) ---
        # 功能性备注: 创建提示词设置的子框架
        prompt_frame = ctk.CTkFrame(master_frame) # 加边框区分
        prompt_frame.grid(row=current_row, column=0, columnspan=2, pady=10, sticky="ew")
        prompt_frame.grid_columnconfigure((0, 1), weight=1) # 两列 Textbox 扩展
        # 功能性备注: NAI 提示词文本框
        nai_pos_label = ctk.CTkLabel(prompt_frame, text="NAI 正向提示:")
        nai_pos_label.grid(row=0, column=0, padx=10, pady=(5,0), sticky="nw")
        self.nai_pos_textbox = ctk.CTkTextbox(prompt_frame, height=80, wrap="word")
        self.nai_pos_textbox.grid(row=1, column=0, padx=10, pady=(0,5), sticky="ew")
        nai_neg_label = ctk.CTkLabel(prompt_frame, text="NAI 负向提示:")
        nai_neg_label.grid(row=2, column=0, padx=10, pady=(5,0), sticky="nw")
        self.nai_neg_textbox = ctk.CTkTextbox(prompt_frame, height=80, wrap="word")
        self.nai_neg_textbox.grid(row=3, column=0, padx=10, pady=(0,10), sticky="ew")
        # 功能性备注: SD/Comfy 提示词文本框
        sd_pos_label = ctk.CTkLabel(prompt_frame, text="SD/Comfy 正向提示:")
        sd_pos_label.grid(row=0, column=1, padx=10, pady=(5,0), sticky="nw")
        self.sd_pos_textbox = ctk.CTkTextbox(prompt_frame, height=80, wrap="word")
        self.sd_pos_textbox.grid(row=1, column=1, padx=10, pady=(0,5), sticky="ew")
        sd_neg_label = ctk.CTkLabel(prompt_frame, text="SD/Comfy 负向提示:")
        sd_neg_label.grid(row=2, column=1, padx=10, pady=(5,0), sticky="nw")
        self.sd_neg_textbox = ctk.CTkTextbox(prompt_frame, height=80, wrap="word")
        self.sd_neg_textbox.grid(row=3, column=1, padx=10, pady=(0,10), sticky="ew")
        current_row += 1

        # --- LoRA 设置 ---
        # 功能性备注: 创建 LoRA 设置的子框架
        lora_frame = ctk.CTkFrame(master_frame) # 加边框区分
        lora_frame.grid(row=current_row, column=0, columnspan=2, pady=10, sticky="ew")
        lora_label = ctk.CTkLabel(lora_frame, text="LoRA 配置:")
        lora_label.pack(side="left", padx=10, pady=5)
        self.lora_edit_button = ctk.CTkButton(lora_frame, text="编辑 LoRAs", command=self._open_lora_editor_for_current) # 绑定新方法
        self.lora_edit_button.pack(side="left", padx=5, pady=5)
        self.lora_count_label = ctk.CTkLabel(lora_frame, text="(0 个 LoRA)") # 显示 LoRA 数量
        self.lora_count_label.pack(side="left", padx=5, pady=5)
        current_row += 1

        # 功能性备注: 初始禁用所有编辑控件，直到选择了人物
        self._set_edit_area_state("disabled")

    def _set_edit_area_state(self, state):
        """启用或禁用编辑区域的所有输入控件"""
        # 功能性备注: 控制编辑区控件的可用性
        widgets_to_toggle = [
            self.repl_entry, self.img_path_entry, self.img_browse_button,
            self.mask_path_entry, self.mask_browse_button,
            self.nai_pos_textbox, self.nai_neg_textbox,
            self.sd_pos_textbox, self.sd_neg_textbox,
            self.lora_edit_button
        ]
        for widget in widgets_to_toggle:
            if widget and widget.winfo_exists():
                # 逻辑备注: Textbox 需要特殊处理 state
                if isinstance(widget, ctk.CTkTextbox):
                    widget.configure(state=state)
                else:
                    widget.configure(state=state)
        # 功能性备注: 同时控制保存当前人物按钮的状态
        if self.save_current_profile_button and self.save_current_profile_button.winfo_exists():
            self.save_current_profile_button.configure(state=state)
        # 功能性备注: 同时控制删除当前人物按钮的状态
        if self.remove_button and self.remove_button.winfo_exists():
            self.remove_button.configure(state=state)

    def _update_profile_selector(self):
        """更新下拉选择框中的人物列表"""
        # 功能性备注: 填充或更新人物选择下拉菜单
        profile_keys = sorted(self.character_profiles.keys())
        if profile_keys:
            self.profile_selector.configure(values=profile_keys, state="normal")
            # 逻辑备注: 如果当前选择的 key 不在新的列表里，或者从未选择过，则默认选第一个
            if self.current_selected_profile_key not in profile_keys:
                self.profile_selector_var.set(profile_keys[0])
                self._on_profile_selected(profile_keys[0]) # 功能性备注: 触发加载第一个的数据
            else:
                # 逻辑备注: 如果当前选择的还在，保持不变，确保变量也同步
                self.profile_selector_var.set(self.current_selected_profile_key)
                # 逻辑备注: 可能需要强制刷新显示（如果只是更新了数据但key没变）
                self._load_profile_data_to_ui(self.current_selected_profile_key)
        else:
            # 逻辑备注: 如果列表为空
            self.profile_selector.configure(values=["无可选择人物"], state="disabled")
            self.profile_selector_var.set("无可选择人物")
            self._clear_edit_area() # 功能性备注: 清空编辑区
            self._set_edit_area_state("disabled") # 功能性备注: 禁用编辑区
            self.current_selected_profile_key = None
        # 功能性备注: 更新保存所有按钮的状态
        self.save_button.configure(state="normal" if profile_keys else "disabled")

    def _clear_edit_area(self):
        """清空编辑区域的所有控件内容"""
        # 功能性备注: 重置编辑区内容为默认或空白
        self.display_name_label.configure(text="- 未选择 -")
        self.repl_var.set("")
        self.img_path_var.set("")
        self.mask_path_var.set("")
        # 功能性备注: 清空 Textbox
        textboxes = [self.nai_pos_textbox, self.nai_neg_textbox, self.sd_pos_textbox, self.sd_neg_textbox]
        for tb in textboxes:
            if tb and tb.winfo_exists():
                tb.configure(state="normal"); tb.delete("1.0", "end"); tb.configure(state="disabled")
        self.lora_count_label.configure(text="(0 个 LoRA)")

    def _load_profile_data_to_ui(self, profile_key):
        """将指定 profile_key 的数据加载到 UI 编辑控件中"""
        # 功能性备注: 将内存中的人物数据填充到界面控件
        if profile_key not in self.character_profiles:
            logger.error(f"错误：尝试加载不存在的人物 Key '{profile_key}' 的数据。") # 逻辑备注
            self._clear_edit_area()
            self._set_edit_area_state("disabled")
            return

        profile_data = self.character_profiles[profile_key]
        if not isinstance(profile_data, dict):
            logger.error(f"错误：人物 Key '{profile_key}' 的数据不是字典格式。") # 逻辑备注
            self._clear_edit_area()
            self._set_edit_area_state("disabled")
            return

        # 功能性备注: 填充数据
        self.display_name_label.configure(text=profile_data.get("display_name", profile_key))
        self.repl_var.set(profile_data.get("replacement_name", ""))
        self.img_path_var.set(profile_data.get("image_path", ""))
        self.mask_path_var.set(profile_data.get("mask_path", ""))

        # 功能性备注: 填充 Textbox (先启用，填充，再禁用)
        textboxes_map = {
            "nai_positive": self.nai_pos_textbox, "nai_negative": self.nai_neg_textbox,
            "sd_positive": self.sd_pos_textbox, "sd_negative": self.sd_neg_textbox
        }
        for key, tb in textboxes_map.items():
            if tb and tb.winfo_exists():
                tb.configure(state="normal")
                tb.delete("1.0", "end")
                tb.insert("1.0", profile_data.get(key, ""))
                tb.configure(state="disabled") # 逻辑备注: 加载后禁用，通过保存按钮保存

        # 功能性备注: 更新 LoRA 数量显示
        lora_list = profile_data.get("loras", [])
        lora_count = len(lora_list) if isinstance(lora_list, list) else 0
        self.lora_count_label.configure(text=f"({lora_count} 个 LoRA)")

        # 功能性备注: 启用编辑区域
        self._set_edit_area_state("normal")
        logger.info(f"[ProfilesTab] 已加载人物 '{profile_key}' 的数据到编辑区域。") # 功能性备注

    def _on_profile_selected(self, selected_key):
        """当用户从下拉菜单选择一个人物时调用"""
        # 功能性备注: 处理用户选择新人物的事件
        logger.info(f"[ProfilesTab] 用户选择了人物: '{selected_key}'") # 功能性备注
        # 逻辑备注: 检查选择的是否是有效 key (而不是提示文字)
        if selected_key in self.character_profiles:
            # 逻辑备注: 在加载新数据前，询问是否保存当前未保存的修改（如果需要）
            # (简化处理：暂时不检查是否有未保存修改，直接加载)
            self.current_selected_profile_key = selected_key
            self._load_profile_data_to_ui(selected_key)
        else:
            # 逻辑备注: 如果选择的是提示文字（例如 "无可选择人物"），则清空并禁用
            self._clear_edit_area()
            self._set_edit_area_state("disabled")
            self.current_selected_profile_key = None

    def _save_current_profile(self):
        """保存当前编辑区域的数据到内存中的对应人物"""
        # 功能性备注: 将界面上的修改保存回内存字典
        if self.current_selected_profile_key is None or self.current_selected_profile_key not in self.character_profiles:
            messagebox.showerror("错误", "没有选中有效的人物进行保存。", parent=self)
            logger.error("保存当前人物失败：没有选中有效的人物 Key。") # 逻辑备注
            return

        key_to_save = self.current_selected_profile_key
        logger.info(f"[ProfilesTab] 尝试保存人物 '{key_to_save}' 的设定...") # 功能性备注

        try:
            # 功能性备注: 从 UI 控件读取数据
            # 逻辑备注：display_name (Key) 不从 UI 读取，它是固定的
            replacement_name = self.repl_var.get().strip()
            image_path = self.img_path_var.get().strip()
            mask_path = self.mask_path_var.get().strip()
            # 功能性备注: 从 Textbox 读取提示词
            nai_positive = self.nai_pos_textbox.get("1.0", "end-1c").strip()
            nai_negative = self.nai_neg_textbox.get("1.0", "end-1c").strip()
            sd_positive = self.sd_pos_textbox.get("1.0", "end-1c").strip()
            sd_negative = self.sd_neg_textbox.get("1.0", "end-1c").strip()
            # 逻辑备注: LoRA 数据由 LoRA 编辑器直接修改内存，这里不需要读取

            # 功能性备注: 更新内存中的字典
            # 逻辑备注: 保留 display_name 和 loras 不变，只更新其他字段
            self.character_profiles[key_to_save].update({
                "replacement_name": replacement_name,
                "image_path": image_path,
                "mask_path": mask_path,
                "nai_positive": nai_positive,
                "nai_negative": nai_negative,
                "sd_positive": sd_positive,
                "sd_negative": sd_negative
            })

            # 功能性备注: 短暂改变按钮外观提示保存成功
            self.save_current_profile_button.configure(text="已保存!", fg_color="green")
            logger.info(f"[ProfilesTab] 人物 '{key_to_save}' 的设定已更新到内存。") # 功能性备注
            # 功能性备注: 延迟恢复按钮外观
            self.after(2000, lambda: self.save_current_profile_button.configure(text="保存当前人物设定", fg_color=ctk.ThemeManager.theme["CTkButton"]["fg_color"]))

        except Exception as e:
            logger.exception(f"保存人物 '{key_to_save}' 设定时发生错误: {e}") # 逻辑备注
            messagebox.showerror("保存错误", f"保存人物 '{key_to_save}' 设定时出错:\n{e}", parent=self)

    def browse_reference_image(self):
        """浏览选择参考图片文件 (用于当前选中人物)"""
        # 功能性备注: 为当前选中的人物选择参考图
        if self.current_selected_profile_key is None: return # 逻辑备注: 未选择人物则不执行
        filepath = filedialog.askopenfilename(
            title=f"为 '{self.current_selected_profile_key}' 选择参考图像",
            filetypes=[("图片文件", "*.png *.jpg *.jpeg *.bmp *.webp"), ("所有文件", "*.*")],
            parent=self
        )
        if filepath:
            self.img_path_var.set(filepath) # 功能性备注: 更新 UI 输入框
            # 逻辑备注：这里只更新了 UI，实际保存需要点击 "保存当前人物设定" 按钮
            logger.info(f"为 '{self.current_selected_profile_key}' 选择了参考图像: {filepath}") # 功能性备注
        else:
            logger.info(f"用户取消为 '{self.current_selected_profile_key}' 选择参考图像。") # 功能性备注

    def browse_mask_image(self):
        """浏览选择蒙版图片文件 (用于当前选中人物)"""
        # 功能性备注: 为当前选中的人物选择蒙版图
        if self.current_selected_profile_key is None: return # 逻辑备注: 未选择人物则不执行
        filepath = filedialog.askopenfilename(
            title=f"为 '{self.current_selected_profile_key}' 选择蒙版图像 (可选)",
            filetypes=[("图片文件", "*.png *.jpg *.jpeg *.bmp *.webp"), ("所有文件", "*.*")],
            parent=self
        )
        if filepath:
            self.mask_path_var.set(filepath) # 功能性备注: 更新 UI 输入框
            # 逻辑备注：这里只更新了 UI，实际保存需要点击 "保存当前人物设定" 按钮
            logger.info(f"为 '{self.current_selected_profile_key}' 选择了蒙版图像: {filepath}") # 功能性备注
        else:
            logger.info(f"用户取消为 '{self.current_selected_profile_key}' 选择蒙版图像。") # 功能性备注

    def update_profile_field(self, name_key, field_type, value):
        """(内部调用) 更新内存中指定人物的字段 (例如文件路径更新)"""
        # 功能性备注: 主要用于程序内部更新字段，如文件选择后
        # 逻辑备注: LoRA 字段由 LoRA 编辑器单独处理
        if field_type == "loras":
            logger.warning("警告: update_profile_field 不用于更新 loras 字段。") # 逻辑备注
            return

        logger.info(f"[ProfilesTab] 内部更新字段请求：Key='{name_key}', 字段='{field_type}', 新值='{str(value)[:50]}...'") # 功能性备注
        if name_key in self.character_profiles:
            # 功能性备注: 有效字段列表，包含新的提示词字段
            valid_fields = ["replacement_name", "image_path", "mask_path",
                            "nai_positive", "nai_negative", "sd_positive", "sd_negative"]
            if field_type in valid_fields:
                if isinstance(self.character_profiles[name_key], dict):
                    self.character_profiles[name_key][field_type] = value.strip() if isinstance(value, str) else value
                    logger.info(f"[ProfilesTab] 内存中 '{name_key}' 的 '{field_type}' 字段已通过内部调用更新。") # 功能性备注
                    # 逻辑备注: 如果更新的是当前选中的人物，也更新 UI 显示
                    if name_key == self.current_selected_profile_key:
                        if field_type == "image_path": self.img_path_var.set(value)
                        elif field_type == "mask_path": self.mask_path_var.set(value)
                        # 逻辑备注: 其他字段暂时不由内部调用更新，主要靠保存按钮
                else:
                    logger.error(f"错误：人物 '{name_key}' 在内存中的设定数据不是字典格式！无法更新字段 '{field_type}'。") # 逻辑备注
            else:
                logger.warning(f"警告: 尝试内部更新未知的字段类型 '{field_type}' 对于人物 '{name_key}'") # 逻辑备注
        else:
            logger.warning(f"警告: 尝试内部更新不存在的人物 Key '{name_key}' 的字段 '{field_type}'。") # 逻辑备注

    def remove_profile(self):
        """移除当前选中的人物设定"""
        # 功能性备注: 删除当前下拉框选中的人物
        key_to_remove = self.current_selected_profile_key
        logger.info(f"[ProfilesTab] 请求删除当前人物 Key: '{key_to_remove}'") # 功能性备注
        if key_to_remove is None or key_to_remove not in self.character_profiles:
            messagebox.showerror("错误", "请先选择一个要删除的人物。", parent=self)
            logger.error("删除失败：未选择有效人物。") # 逻辑备注
            return

        display_name = self.character_profiles[key_to_remove].get("display_name", key_to_remove)
        if messagebox.askyesno("确认删除", f"确定要删除人物 '{display_name}' (Key: {key_to_remove}) 吗？", parent=self):
            try:
                del self.character_profiles[key_to_remove]
                logger.info(f"[ProfilesTab] 人物 Key '{key_to_remove}' 已从内存字典中删除。") # 功能性备注
                self.current_selected_profile_key = None # 功能性备注: 清除当前选择
                self._update_profile_selector() # 功能性备注: 更新下拉列表并选择第一个（或清空）
            except Exception as e:
                logger.exception(f"错误：删除人物 Key '{key_to_remove}' 时发生意外错误: {e}") # 逻辑备注
                messagebox.showerror("删除错误", f"删除人物时出错:\n{e}", parent=self)
                self._update_profile_selector() # 逻辑备注: 即使出错也尝试刷新列表

    def add_new_profile(self):
        """添加新的人物设定"""
        # 功能性备注: 添加一个全新的人物条目
        logger.info("[ProfilesTab] 请求添加新人物...") # 功能性备注
        dialog = ctk.CTkInputDialog(text="请输入新人物的名称 (这将是显示名称和内部 Key):", title="添加人物")
        new_name_raw = dialog.get_input()
        if new_name_raw is not None:
            new_name = new_name_raw.strip()
            logger.info(f"[ProfilesTab] 用户输入名称: '{new_name}'") # 功能性备注
            if not new_name:
                messagebox.showerror("名称错误", "人物名称不能为空！", parent=self)
                logger.error("错误：用户尝试添加空名称。") # 逻辑备注
                return
            if new_name in self.character_profiles:
                messagebox.showerror("名称冲突", f"人物名称 (Key) '{new_name}' 已经存在！", parent=self)
                logger.error(f"错误：用户尝试添加已存在的 Key '{new_name}'。") # 逻辑备注
                return
            # 功能性备注: 添加到内存字典，包含新的提示词字段和 loras 列表
            self.character_profiles[new_name] = {
                "display_name": new_name, "replacement_name": "",
                "nai_positive": "", "nai_negative": "", "sd_positive": "", "sd_negative": "", # 功能性备注: 新的四个提示词字段
                "image_path": "", "mask_path": "", "loras": [] # 功能性备注: 添加空的 loras 列表
            }
            logger.info(f"[ProfilesTab] 新人物 '{new_name}' 已添加到内存字典。") # 功能性备注
            self.current_selected_profile_key = new_name # 功能性备注: 将新添加的设为当前选中
            self._update_profile_selector() # 功能性备注: 更新下拉列表并选中新人物
        else:
            logger.info("[ProfilesTab] 用户取消添加人物。") # 功能性备注

    def load_profiles_from_file(self):
        """加载人物设定文件"""
        # 功能性备注: 从 JSON 文件加载所有人物设定
        logger.info("[ProfilesTab] 请求加载人物设定文件...") # 功能性备注
        result = self.config_manager.load_character_profiles_from_file(parent_window=self)
        if result:
            profiles, filepath = result
            logger.info(f"[ProfilesTab] 文件加载成功，路径: {filepath}") # 功能性备注

            # --- 处理旧格式迁移和字段补充 ---
            # 功能性备注: 确保加载的数据包含所有必需字段，并处理旧的提示词格式
            migrated_profiles = {}
            migration_needed = False
            missing_fields_added = False
            for name_key, data in profiles.items():
                if isinstance(data, dict):
                    new_data = data.copy() # 功能性备注: 使用副本操作
                    # 逻辑备注: 1. 处理旧的 positive/negative (如果存在且新字段不存在)
                    is_old_prompt_format = ("positive" in new_data or "negative" in new_data) and \
                                           ("nai_positive" not in new_data and "sd_positive" not in new_data)
                    if is_old_prompt_format:
                        old_pos = new_data.get("positive", "")
                        old_neg = new_data.get("negative", "")
                        new_data["nai_positive"] = old_pos; new_data["sd_positive"] = old_pos
                        new_data["nai_negative"] = old_neg; new_data["sd_negative"] = old_neg
                        if "positive" in new_data: del new_data["positive"]
                        if "negative" in new_data: del new_data["negative"]
                        migration_needed = True
                        logger.info(f"  > 迁移旧格式提示词 for '{name_key}'") # 功能性备注
                    # 逻辑备注: 2. 确保所有必需字段存在 (包括新的提示词字段和 loras)
                    required_fields = ["display_name", "replacement_name", "image_path", "mask_path",
                                       "nai_positive", "nai_negative", "sd_positive", "sd_negative", "loras"]
                    for field in required_fields:
                        if field not in new_data:
                            if field == "display_name": new_data[field] = name_key
                            elif field == "loras": new_data[field] = []
                            else: new_data[field] = ""
                            missing_fields_added = True
                            logger.info(f"  > 为 '{name_key}' 添加缺失字段: '{field}'") # 功能性备注
                    # 逻辑备注: 确保 loras 是列表
                    if not isinstance(new_data.get("loras"), list):
                        logger.warning(f"警告: 人物 '{name_key}' 的 'loras' 字段不是列表，已重置为空列表。") # 逻辑备注
                        new_data["loras"] = []; missing_fields_added = True
                    migrated_profiles[name_key] = new_data
                else:
                    logger.warning(f"警告：加载人物设定时，Key '{name_key}' 的值不是字典，已忽略。") # 逻辑备注

            if migration_needed: messagebox.showinfo("格式迁移", "加载的人物设定文件是旧格式，已自动迁移提示词字段。", parent=self)
            elif missing_fields_added: messagebox.showinfo("字段补充", "加载的人物设定文件缺少部分字段，已自动补充。", parent=self)
            # --- 迁移和补充结束 ---

            self.character_profiles = migrated_profiles # 功能性备注: 更新内存数据
            self.loaded_filepath = filepath
            self.current_selected_profile_key = None # 功能性备注: 重置当前选择
            self._update_profile_selector() # 功能性备注: 更新 UI 下拉列表并选中第一个
            filename = os.path.basename(filepath)
            self.file_status_label.configure(text=f"当前设定: {filename}", text_color="green")
        else:
            logger.info("[ProfilesTab] 文件加载失败或用户取消。") # 功能性备注
            if self.loaded_filepath: filename = os.path.basename(self.loaded_filepath); self.file_status_label.configure(text=f"加载失败/取消 (仍使用: {filename})", text_color="orange")
            else: self.file_status_label.configure(text="加载失败或取消", text_color="orange")

    def save_profiles_to_file(self):
        """保存当前所有人物设定到文件"""
        # 功能性备注: 将内存中所有人物设定保存到 JSON 文件
        logger.info("[ProfilesTab] 请求保存所有人物设定文件...") # 功能性备注
        if not self.character_profiles:
            messagebox.showwarning("无设定", "当前没有人物设定数据可以保存。", parent=self)
            logger.warning("[ProfilesTab] 保存取消：内存中没有人物设定。") # 逻辑备注
            return
        invalid_keys = [key for key in self.character_profiles.keys() if not key or key.isspace()]
        if invalid_keys:
            messagebox.showerror("内部错误", f"发现无效的人物 Key：\n{', '.join(invalid_keys)}\n请修正后再保存。", parent=self)
            logger.error(f"[ProfilesTab] 保存取消：发现无效 Key: {invalid_keys}") # 逻辑备注
            return
        # 功能性备注: 确保所有条目都包含必需字段
        profiles_to_save = {}
        for key, data in self.character_profiles.items():
             if isinstance(data, dict):
                 data_copy = data.copy()
                 required_fields = ["display_name", "replacement_name", "image_path", "mask_path",
                                    "nai_positive", "nai_negative", "sd_positive", "sd_negative", "loras"] # 功能性备注: 包含新字段
                 for field in required_fields:
                     if field not in data_copy: data_copy[field] = [] if field == "loras" else ""
                 if not isinstance(data_copy.get("loras"), list): data_copy["loras"] = []
                 profiles_to_save[key] = data_copy
             else: profiles_to_save[key] = data

        logger.info(f"[ProfilesTab] 准备将以下数据保存到文件:", json.dumps(profiles_to_save, indent=2, ensure_ascii=False)) # 功能性备注
        success = self.config_manager.save_character_profiles_to_file(profiles=profiles_to_save, parent_window=self)
        if success:
            logger.info("[ProfilesTab] 文件保存成功。") # 功能性备注
            self.file_status_label.configure(text="当前设定已保存", text_color="green")
        else:
            logger.info("[ProfilesTab] 文件保存失败或用户取消。") # 功能性备注
            self.file_status_label.configure(text="保存失败或取消", text_color="orange")

    def get_profiles_for_step2(self):
        """返回供步骤二使用的 profiles 字典和 JSON 字符串"""
        # 功能性备注: 准备传递给步骤二的数据
        # 逻辑备注: *** 这是关键修改点 *** 现在需要返回包含所有四个提示词字段的 JSON
        logger.info("[ProfilesTab] 请求获取供步骤二使用的 Profiles 字典和 JSON...") # 功能性备注
        current_profiles = self.character_profiles
        logger.info("[ProfilesTab] 当前内存中的人物设定:", current_profiles) # 功能性备注
        if not current_profiles:
            logger.warning("[ProfilesTab] 获取数据：人物设定为空。") # 逻辑备注
            messagebox.showwarning("无设定", "当前没有人物设定数据。", parent=self)
            return None, None
        invalid_keys = [key for key in current_profiles.keys() if not key or key.isspace()]
        if invalid_keys:
            messagebox.showerror("名称错误", f"发现无效的人物 Key：\n{', '.join(invalid_keys)}\n请修正。", parent=self)
            logger.error("[ProfilesTab] 获取数据失败：发现无效 Key。") # 逻辑备注
            return None, None
        # 功能性备注: 生成 JSON 时包含所有四个提示词字段
        effective_profiles_for_json = {}
        for key, data in current_profiles.items():
            if isinstance(data, dict):
                display_name = data.get("display_name", key)
                # 逻辑备注: 将所有四个提示词字段都加入到 JSON 中
                effective_profiles_for_json[display_name] = {
                    "nai_positive": data.get("nai_positive", ""),
                    "nai_negative": data.get("nai_negative", ""),
                    "sd_positive": data.get("sd_positive", ""),
                    "sd_negative": data.get("sd_negative", "")
                    # 逻辑备注: 不再包含旧的 positive/negative
                }
            else: logger.warning(f"警告：人物 Key '{key}' 的数据格式无效，已在生成 JSON 时跳过。") # 逻辑备注
        try:
            json_string = json.dumps(effective_profiles_for_json, ensure_ascii=False, indent=2)
            logger.info("[ProfilesTab] 成功生成供步骤二使用的 JSON 字符串 (包含 NAI 和 SD/Comfy 提示词)。") # 功能性备注
            return current_profiles.copy(), json_string # 功能性备注: 返回完整字典和 JSON 字符串
        except Exception as e:
            logger.exception(f"错误：将人物设定转换为 JSON 字符串时出错: {e}") # 逻辑备注
            messagebox.showerror("内部错误", f"无法将人物设定转换为 JSON 格式:\n{e}", parent=self)
            return None, None

    # --- 获取/设置人物设定数据的方法，用于主程序保存/加载 ---
    def get_profiles_data(self):
        """返回当前的人物设定字典"""
        # 功能性备注: 提供内存中的人物设定数据给外部
        return self.character_profiles.copy()

    def set_profiles_data(self, profiles_dict):
        """设置人物设定字典并更新 UI"""
        # 功能性备注: 从外部加载人物设定数据并更新界面
        if isinstance(profiles_dict, dict):
            processed_dict = {}
            for key, data in profiles_dict.items():
                 if isinstance(data, dict):
                     data_copy = data.copy()
                     # 逻辑备注: 确保加载时包含所有必需字段
                     required_fields = ["display_name", "replacement_name", "image_path", "mask_path",
                                        "nai_positive", "nai_negative", "sd_positive", "sd_negative", "loras"]
                     for field in required_fields:
                         if field not in data_copy: data_copy[field] = [] if field == "loras" else ""
                     if not isinstance(data_copy.get("loras"), list): data_copy["loras"] = []
                     processed_dict[key] = data_copy
                 else: processed_dict[key] = data
            self.character_profiles = processed_dict
            self.current_selected_profile_key = None # 功能性备注: 重置选择
            self._update_profile_selector() # 功能性备注: 更新下拉列表并选中第一个
            logger.info("[ProfilesTab] 人物设定数据已从状态加载并处理。") # 功能性备注
        else:
            logger.error("错误：尝试加载的人物设定数据不是有效的字典。") # 逻辑备注
            self.character_profiles = {} # 功能性备注: 重置为空
            self._update_profile_selector() # 功能性备注: 更新下拉列表

    # --- LoRA 编辑器相关方法 ---
    def _open_lora_editor_for_current(self):
        """打开用于编辑当前选中人物 LoRA 的 Toplevel 窗口"""
        # 功能性备注: 打开 LoRA 编辑器
        if self.current_selected_profile_key is None:
            messagebox.showerror("错误", "请先选择一个人物。", parent=self)
            return
        self._open_lora_editor(self.current_selected_profile_key) # 功能性备注: 调用原来的方法，传入当前 key

    def _open_lora_editor(self, character_key):
        """打开用于编辑指定人物 LoRA 的 Toplevel 窗口 (内部实现)"""
        # 功能性备注: 创建和显示 LoRA 编辑窗口
        if self.lora_editor_window is not None and self.lora_editor_window.winfo_exists(): self.lora_editor_window.focus(); logger.warning("LoRA 编辑器已打开。"); return # 逻辑备注
        if character_key not in self.character_profiles: logger.error(f"错误：无法打开 LoRA 编辑器，人物 Key '{character_key}' 不存在。"); return # 逻辑备注

        profile_data = self.character_profiles[character_key]; display_name = profile_data.get("display_name", character_key)
        self.lora_editor_window = ctk.CTkToplevel(self); self.lora_editor_window.title(f"编辑 '{display_name}' 的 LoRAs"); self.lora_editor_window.geometry("600x400"); self.lora_editor_window.attributes("-topmost", True); self.lora_editor_window.protocol("WM_DELETE_WINDOW", self._close_lora_editor)
        self.lora_editor_window.grid_rowconfigure(1, weight=1); self.lora_editor_window.grid_columnconfigure(0, weight=1)
        top_label = ctk.CTkLabel(self.lora_editor_window, text=f"管理 '{display_name}' 的 LoRA 配置", font=ctk.CTkFont(weight="bold")); top_label.grid(row=0, column=0, padx=10, pady=10, sticky="w")
        lora_scroll_frame = ctk.CTkScrollableFrame(self.lora_editor_window, label_text="LoRA 列表"); lora_scroll_frame.grid(row=1, column=0, padx=10, pady=5, sticky="nsew"); lora_scroll_frame.grid_columnconfigure(0, weight=1); lora_scroll_frame.grid_columnconfigure(1, weight=0); lora_scroll_frame.grid_columnconfigure(2, weight=0); lora_scroll_frame.grid_columnconfigure(3, weight=0)
        self.lora_editor_widgets = [] # 功能性备注: 存储编辑器内每行 LoRA 的控件

        def render_lora_list_in_editor():
            # 功能性备注: 在 LoRA 编辑器内部渲染 LoRA 列表
            # 逻辑备注: 清理旧控件
            for widget_row in self.lora_editor_widgets:
                # *** FIX START ***
                # 逻辑修改: 只销毁实际的 widget，而不是 StringVar
                for key, widget_or_var in widget_row.items():
                    # 检查是否是界面控件 (继承自 BaseWidget) 并且存在
                    if isinstance(widget_or_var, BaseWidget) and widget_or_var.winfo_exists():
                        widget_or_var.destroy()
                # *** FIX END ***
            self.lora_editor_widgets.clear()
            # 逻辑备注: 确保从当前选中的 character_key 获取 loras
            current_loras = self.character_profiles.get(character_key, {}).get("loras", [])
            if not isinstance(current_loras, list): current_loras = [] # 逻辑备注: 防御性编程
            # 功能性备注: 创建表头
            headers = ["LoRA 文件名", "模型权重", "CLIP 权重", "操作"]
            for col, text in enumerate(headers): header = ctk.CTkLabel(lora_scroll_frame, text=text, font=ctk.CTkFont(size=12, weight="bold")); header.grid(row=0, column=col, padx=5, pady=2, sticky="w")
            # 功能性备注: 遍历 LoRA 数据创建控件行
            for idx, lora_data in enumerate(current_loras):
                row_widgets = {}
                name_var = StringVar(value=lora_data.get("name", "")); name_entry = ctk.CTkEntry(lora_scroll_frame, textvariable=name_var, placeholder_text="lora_name.safetensors"); name_entry.grid(row=idx + 1, column=0, padx=5, pady=2, sticky="ew"); row_widgets["name_var"] = name_var; row_widgets["name_entry"] = name_entry
                model_w_var = StringVar(value=str(lora_data.get("model_weight", 1.0))); model_w_entry = ctk.CTkEntry(lora_scroll_frame, textvariable=model_w_var, width=60); model_w_entry.grid(row=idx + 1, column=1, padx=5, pady=2, sticky="w"); row_widgets["model_w_var"] = model_w_var; row_widgets["model_w_entry"] = model_w_entry
                clip_w_var = StringVar(value=str(lora_data.get("clip_weight", 1.0))); clip_w_entry = ctk.CTkEntry(lora_scroll_frame, textvariable=clip_w_var, width=60); clip_w_entry.grid(row=idx + 1, column=2, padx=5, pady=2, sticky="w"); row_widgets["clip_w_var"] = clip_w_var; row_widgets["clip_w_entry"] = clip_w_entry
                remove_button = ctk.CTkButton(lora_scroll_frame, text="删除", width=50, fg_color="#DB3E3E", hover_color="#B82E2E", command=lambda k=character_key, i=idx: self._remove_lora_from_editor(k, i, render_lora_list_in_editor)); remove_button.grid(row=idx + 1, column=3, padx=5, pady=2, sticky="e"); row_widgets["remove_button"] = remove_button
                self.lora_editor_widgets.append(row_widgets)

        # 功能性备注: 创建编辑器底部的按钮
        add_lora_button = ctk.CTkButton(self.lora_editor_window, text="添加 LoRA", command=lambda k=character_key: self._add_lora_to_editor(k, render_lora_list_in_editor)); add_lora_button.grid(row=2, column=0, padx=10, pady=5, sticky="w")
        bottom_button_frame = ctk.CTkFrame(self.lora_editor_window, fg_color="transparent"); bottom_button_frame.grid(row=3, column=0, padx=10, pady=10, sticky="e")
        save_button = ctk.CTkButton(bottom_button_frame, text="保存更改", command=lambda k=character_key: self._save_loras_from_editor(k)); save_button.pack(side="left", padx=5)
        cancel_button = ctk.CTkButton(bottom_button_frame, text="取消", command=self._close_lora_editor); cancel_button.pack(side="left", padx=5)
        # 功能性备注: 初始渲染 LoRA 列表
        render_lora_list_in_editor()

    def _add_lora_to_editor(self, character_key, render_callback):
        """在 LoRA 编辑器中添加一个新的空 LoRA 条目"""
        # 功能性备注: 为指定人物添加空 LoRA 数据
        if character_key in self.character_profiles and isinstance(self.character_profiles[character_key].get("loras"), list):
            self.character_profiles[character_key]["loras"].append({"name": "", "model_weight": 1.0, "clip_weight": 1.0})
            render_callback() # 功能性备注: 重新渲染列表
            logger.info(f"为 '{character_key}' 添加了一个新的空 LoRA 条目。") # 功能性备注
        else: logger.error(f"错误：无法为 '{character_key}' 添加 LoRA，人物数据或 loras 列表无效。") # 逻辑备注

    def _remove_lora_from_editor(self, character_key, index, render_callback):
        """从 LoRA 编辑器中移除指定索引的 LoRA 条目"""
        # 功能性备注: 从指定人物的 LoRA 列表中移除一项
        if character_key in self.character_profiles and isinstance(self.character_profiles[character_key].get("loras"), list):
            loras = self.character_profiles[character_key]["loras"]
            if 0 <= index < len(loras):
                removed_lora = loras.pop(index); render_callback(); logger.info(f"从 '{character_key}' 移除了 LoRA (索引 {index}): {removed_lora.get('name')}") # 功能性备注
            else: logger.warning(f"警告：尝试移除无效索引 {index} 的 LoRA (人物: {character_key})。") # 逻辑备注
        else: logger.error(f"错误：无法移除 LoRA，人物 '{character_key}' 数据或 loras 列表无效。") # 逻辑备注

    def _save_loras_from_editor(self, character_key):
        """从 LoRA 编辑器的控件中读取数据并保存到内存"""
        # 功能性备注: 将 LoRA 编辑器中的修改保存回内存
        if character_key not in self.character_profiles: logger.error(f"错误：无法保存 LoRAs，人物 Key '{character_key}' 不存在。"); return # 逻辑备注
        new_loras_list = []; validation_passed = True
        # 功能性备注: 遍历编辑器中的每一行 LoRA 控件
        for idx, row_widgets in enumerate(self.lora_editor_widgets):
            name = row_widgets["name_var"].get().strip(); model_w_str = row_widgets["model_w_var"].get().strip(); clip_w_str = row_widgets["clip_w_var"].get().strip()
            # 逻辑备注: 验证输入
            if not name: messagebox.showerror("输入错误", f"第 {idx+1} 行的 LoRA 名称不能为空！", parent=self.lora_editor_window); validation_passed = False; break
            try: model_w = float(model_w_str); clip_w = float(clip_w_str); new_loras_list.append({"name": name, "model_weight": model_w, "clip_weight": clip_w})
            except ValueError: messagebox.showerror("输入错误", f"第 {idx+1} 行的 LoRA 权重必须是数字！", parent=self.lora_editor_window); validation_passed = False; break
        # 逻辑备注: 如果验证通过，则更新内存数据
        if validation_passed:
            self.character_profiles[character_key]["loras"] = new_loras_list
            logger.info(f"已保存 '{character_key}' 的 LoRA 配置 ({len(new_loras_list)} 个)。") # 功能性备注
            self._close_lora_editor() # 功能性备注: 保存成功后关闭编辑器
            # 功能性备注: 更新主界面 LoRA 数量显示
            self._load_profile_data_to_ui(character_key)

    def _close_lora_editor(self):
        """关闭 LoRA 编辑器窗口"""
        # 功能性备注: 关闭 LoRA 编辑器窗口并清理引用
        if self.lora_editor_window is not None and self.lora_editor_window.winfo_exists(): self.lora_editor_window.destroy()
        self.lora_editor_window = None
        logger.info("LoRA 编辑器已关闭。") # 功能性备注
