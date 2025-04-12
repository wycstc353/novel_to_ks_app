# ui/nai_config_tab.py
import customtkinter as ctk
from tkinter import StringVar, IntVar, DoubleVar, BooleanVar, messagebox, filedialog # 添加 messagebox 和 filedialog
import os
import traceback # 导入 traceback 以便在 trigger 中打印错误

class NAIConfigTab(ctk.CTkFrame):
    """NAI API 设置（包括代理）的 UI 标签页"""
    def __init__(self, master, config_manager, app_instance):
        super().__init__(master, fg_color="transparent")
        self.config_manager = config_manager
        self.app = app_instance # 主应用实例
        # 加载 NAI 模型列表 (从 config_manager)
        self.nai_models = self.config_manager.load_nai_models()
        # 创建模型名称到值的映射 (用于保存配置)
        self._model_name_to_value = {m['name']: m['value'] for m in self.nai_models}
        # 创建模型值到名称的映射 (用于加载配置时显示名称)
        self._model_value_to_name = {m['value']: m['name'] for m in self.nai_models}
        # 负面预设 (UC Preset) 的值到名称的映射 (用于 UI 显示)
        self._uc_preset_map = {0: "Heavy", 1: "Light", 2: "Human Focus", 3: "None"}
        # 负面预设名称到值的映射 (用于保存配置)
        self._uc_preset_name_to_value = {v: k for k, v in self._uc_preset_map.items()}

        self.build_ui()
        self.load_initial_config()

    def build_ui(self):
        """构建 NAI 配置界面的 UI 元素"""
        # 配置主框架的网格列权重，让第二列 (输入框) 可以扩展
        self.grid_columnconfigure(1, weight=1)

        row = 0
        # --- NAI API Key ---
        api_key_label = ctk.CTkLabel(self, text="NAI API Key:")
        api_key_label.grid(row=row, column=0, padx=10, pady=5, sticky="w")
        self.api_key_var = StringVar()
        api_key_entry = ctk.CTkEntry(self, textvariable=self.api_key_var, show="*") # show="*" 隐藏输入内容
        api_key_entry.grid(row=row, column=1, columnspan=2, padx=10, pady=5, sticky="ew") # 跨越两列
        # --- 新增绑定 ---
        api_key_entry.bind("<FocusOut>", self.trigger_workflow_button_update) # 绑定失去焦点事件

        # --- 图片保存目录 ---
        row += 1
        save_dir_label = ctk.CTkLabel(self, text="图片保存目录:")
        save_dir_label.grid(row=row, column=0, padx=10, pady=5, sticky="w")
        self.save_dir_var = StringVar()
        dir_entry = ctk.CTkEntry(self, textvariable=self.save_dir_var, placeholder_text="应用可访问的完整目录路径")
        dir_entry.grid(row=row, column=1, padx=(10, 0), pady=5, sticky="ew") # 输入框在第二列
        # --- 新增绑定 ---
        dir_entry.bind("<FocusOut>", self.trigger_workflow_button_update) # 绑定失去焦点事件
        # 浏览按钮放在第三列
        browse_button = ctk.CTkButton(self, text="浏览...", width=60, command=self.browse_save_directory)
        browse_button.grid(row=row, column=2, padx=(5, 10), pady=5, sticky="w")

        # --- NAI 代理设置 ---
        row += 1
        # 创建一个 Frame 来包裹代理相关的控件，方便布局管理
        nai_proxy_frame = ctk.CTkFrame(self, fg_color="transparent")
        # 将代理 Frame 放置在主框架的网格中，跨越所有列
        nai_proxy_frame.grid(row=row, column=0, columnspan=3, padx=10, pady=(10, 0), sticky="ew")
        # 配置代理 Frame 内部的列权重，让地址输入框可以扩展
        nai_proxy_frame.grid_columnconfigure(2, weight=1)

        # 代理启用复选框
        self.nai_use_proxy_var = BooleanVar()
        nai_proxy_checkbox = ctk.CTkCheckBox(nai_proxy_frame, text="使用代理访问 NAI API?",
                                             variable=self.nai_use_proxy_var,
                                             command=self.toggle_nai_proxy_entries) # 点击时切换输入框状态
        nai_proxy_checkbox.grid(row=0, column=0, padx=(0, 20), pady=10, sticky="w")

        # 代理地址标签和输入框
        nai_proxy_addr_label = ctk.CTkLabel(nai_proxy_frame, text="地址:")
        nai_proxy_addr_label.grid(row=0, column=1, padx=(0, 5), pady=10, sticky="w")
        self.nai_proxy_address_var = StringVar()
        self.nai_proxy_address_entry = ctk.CTkEntry(nai_proxy_frame, textvariable=self.nai_proxy_address_var, placeholder_text="例如: 127.0.0.1")
        self.nai_proxy_address_entry.grid(row=0, column=2, padx=5, pady=10, sticky="ew")

        # 代理端口标签和输入框
        nai_proxy_port_label = ctk.CTkLabel(nai_proxy_frame, text="端口:")
        nai_proxy_port_label.grid(row=0, column=3, padx=(10, 5), pady=10, sticky="w")
        self.nai_proxy_port_var = StringVar()
        self.nai_proxy_port_entry = ctk.CTkEntry(nai_proxy_frame, textvariable=self.nai_proxy_port_var, placeholder_text="例如: 7890", width=80) # 固定宽度
        self.nai_proxy_port_entry.grid(row=0, column=4, padx=(0, 10), pady=10, sticky="w")


        # --- NAI 生成参数 (放到一个新的 Frame 中) ---
        row += 1 # 基于主框架的行号增加
        param_frame = ctk.CTkFrame(self, fg_color="transparent")
        # 将参数 Frame 放置在主框架的网格中，跨越所有列
        param_frame.grid(row=row, column=0, columnspan=3, sticky="ew", padx=5, pady=(5, 5))
        # 配置参数 Frame 内部列权重，使其均匀分布
        param_frame.grid_columnconfigure((0, 1, 2, 3), weight=1, uniform="group_nai")

        col = 0
        row_param = 0
        # 模型选择 (Model)
        model_label = ctk.CTkLabel(param_frame, text="模型:")
        model_label.grid(row=row_param, column=col, padx=5, pady=5, sticky="w")
        # 从加载的模型列表中获取模型名称作为选项
        model_options = [m['name'] for m in self.nai_models] if self.nai_models else ["未加载模型列表"]
        self.model_display_var = StringVar(value=model_options[0] if model_options else "") # 默认选中第一个
        self.model_combobox = ctk.CTkComboBox(param_frame, values=model_options, variable=self.model_display_var)
        self.model_combobox.grid(row=row_param+1, column=col, padx=5, pady=5, sticky="ew")
        # 如果模型列表加载失败，禁用下拉框
        if not self.nai_models:
            self.model_combobox.configure(state="disabled")

        col += 1
        # 采样器 (Sampler)
        sampler_label = ctk.CTkLabel(param_frame, text="采样器:")
        sampler_label.grid(row=row_param, column=col, padx=5, pady=5, sticky="w")
        self.sampler_var = StringVar(value="k_euler") # NAI 常用默认值
        sampler_options = ["k_euler", "k_euler_ancestral", "k_dpmpp_2s_ancestral", "k_dpmpp_2m", "k_dpmpp_sde", "ddim"] # NAI 支持的采样器
        sampler_combo = ctk.CTkComboBox(param_frame, values=sampler_options, variable=self.sampler_var)
        sampler_combo.grid(row=row_param+1, column=col, padx=5, pady=5, sticky="ew")

        col += 1
        # 步数 (Steps)
        steps_label = ctk.CTkLabel(param_frame, text="步数:")
        steps_label.grid(row=row_param, column=col, padx=5, pady=5, sticky="w")
        self.steps_var = IntVar(value=28) # NAI 常用默认值
        steps_entry = ctk.CTkEntry(param_frame, textvariable=self.steps_var)
        steps_entry.grid(row=row_param+1, column=col, padx=5, pady=5, sticky="ew")

        col += 1
        # 引导强度 (Scale / CFG Scale)
        scale_label = ctk.CTkLabel(param_frame, text="引导强度:")
        scale_label.grid(row=row_param, column=col, padx=5, pady=5, sticky="w")
        self.scale_var = DoubleVar(value=7.0) # 常用默认值
        scale_entry = ctk.CTkEntry(param_frame, textvariable=self.scale_var)
        scale_entry.grid(row=row_param+1, column=col, padx=5, pady=5, sticky="ew")

        # 换到下一行参数
        col = 0
        row_param += 2
        # 种子 (Seed)
        seed_label = ctk.CTkLabel(param_frame, text="种子 (-1随机):")
        seed_label.grid(row=row_param, column=col, padx=5, pady=5, sticky="w")
        self.seed_var = IntVar(value=-1) # 默认值 -1 表示随机
        seed_entry = ctk.CTkEntry(param_frame, textvariable=self.seed_var)
        seed_entry.grid(row=row_param+1, column=col, padx=5, pady=5, sticky="ew")

        col += 1
        # 负面预设 (UC Preset)
        uc_label = ctk.CTkLabel(param_frame, text="负面预设:")
        uc_label.grid(row=row_param, column=col, padx=5, pady=5, sticky="w")
        uc_preset_options = list(self._uc_preset_map.values()) # 获取预设名称列表
        self.uc_preset_display_var = StringVar(value=uc_preset_options[0] if uc_preset_options else "") # 默认选中第一个 ("Heavy")
        uc_combo = ctk.CTkComboBox(param_frame, values=uc_preset_options, variable=self.uc_preset_display_var)
        uc_combo.grid(row=row_param+1, column=col, padx=5, pady=5, sticky="ew")

        col += 1
        # 质量标签 (Quality Toggle)
        quality_label = ctk.CTkLabel(param_frame, text="质量标签:")
        quality_label.grid(row=row_param, column=col, padx=5, pady=5, sticky="w")
        self.quality_toggle_var = BooleanVar(value=True) # NAI 默认开启
        quality_check = ctk.CTkCheckBox(param_frame, text="", variable=self.quality_toggle_var) # 无文本的复选框
        quality_check.grid(row=row_param+1, column=col, padx=5, pady=5, sticky="w")

        # 初始化代理输入框状态
        self.toggle_nai_proxy_entries()

    def browse_save_directory(self):
        """打开目录选择对话框，让用户选择 NAI 图片保存目录"""
        directory = filedialog.askdirectory(title="选择 NAI 图片保存目录", parent=self)
        if directory:
            self.save_dir_var.set(directory)
            print(f"NAI 图片保存目录已设置为: {directory}")
            # --- 新增：选择目录后也触发更新 ---
            self.trigger_workflow_button_update()
        else:
            print("用户取消选择目录。")

    def toggle_nai_proxy_entries(self):
        """根据 NAI 代理复选框状态启用/禁用代理地址和端口输入框"""
        use_proxy = self.nai_use_proxy_var.get() # 获取复选框当前状态 (True/False)
        new_state = "normal" if use_proxy else "disabled" # 根据状态决定输入框应该是启用还是禁用

        # 检查代理地址输入框是否存在并更新状态
        if hasattr(self, 'nai_proxy_address_entry') and self.nai_proxy_address_entry.winfo_exists():
             self.nai_proxy_address_entry.configure(state=new_state)
             if not use_proxy: self.nai_proxy_address_var.set("") # 禁用时清空内容

        # 检查代理端口输入框是否存在并更新状态
        if hasattr(self, 'nai_proxy_port_entry') and self.nai_proxy_port_entry.winfo_exists():
             self.nai_proxy_port_entry.configure(state=new_state)
             if not use_proxy: self.nai_proxy_port_var.set("") # 禁用时清空内容

    def load_initial_config(self):
        """从配置文件加载初始 NAI 配置并更新 UI 元素"""
        print("正在加载 NAI 配置到 UI...")
        config = self.config_manager.load_config("nai")

        self.api_key_var.set(config.get("naiApiKey", ""))
        self.save_dir_var.set(config.get("naiImageSaveDir", ""))

        # 加载模型选择
        saved_model_value = config.get("naiModel", "") # 获取保存的模型值
        saved_model_name = self._model_value_to_name.get(saved_model_value) # 尝试通过值找到名称
        if saved_model_name and self.nai_models:
            # 如果找到了对应的名称且模型列表已加载，则设置 UI 显示该名称
            self.model_display_var.set(saved_model_name)
        elif self.nai_models:
            # 如果没找到或保存的值无效，但模型列表存在，则默认选中第一个
            self.model_display_var.set(self.nai_models[0]['name'])
        else:
            # 如果模型列表加载失败
            self.model_display_var.set("未加载模型列表")
            if hasattr(self, 'model_combobox'): self.model_combobox.configure(state="disabled")

        # 加载其他参数
        self.sampler_var.set(config.get("naiSampler", "k_euler"))
        self.steps_var.set(int(config.get("naiSteps", 28)))
        self.scale_var.set(float(config.get("naiScale", 7.0)))
        self.seed_var.set(int(config.get("naiSeed", -1)))

        # 加载负面预设
        uc_preset_value = config.get("naiUcPreset", 0) # 获取保存的值
        uc_preset_name = self._uc_preset_map.get(uc_preset_value, "Heavy") # 通过值找到名称，找不到则用默认 "Heavy"
        self.uc_preset_display_var.set(uc_preset_name) # 设置 UI 显示名称

        self.quality_toggle_var.set(bool(config.get("naiQualityToggle", True)))

        # 加载 NAI 代理设置
        self.nai_use_proxy_var.set(bool(config.get("nai_use_proxy", False)))
        self.nai_proxy_address_var.set(config.get("nai_proxy_address", ""))
        self.nai_proxy_port_var.set(str(config.get("nai_proxy_port", ""))) # 端口加载为字符串

        # 根据加载的代理设置初始化输入框状态
        self.toggle_nai_proxy_entries()
        print("NAI 配置加载完成。")


    def get_config_data(self):
        """从 UI 元素收集当前的 NAI 配置数据"""
        print("正在从 UI 收集 NAI 配置数据...")
        # 获取模型值
        selected_model_name = self.model_display_var.get()
        model_value = self._model_name_to_value.get(selected_model_name, "") # 通过选中的名称找到对应的值
        if not model_value and self.nai_models:
             print(f"警告: 未找到模型名称 '{selected_model_name}' 对应的值，将使用第一个模型的值。")
             model_value = self.nai_models[0]['value'] # 如果找不到，默认用第一个模型的值

        # 获取负面预设值
        selected_uc_preset_name = self.uc_preset_display_var.get()
        uc_preset_value = self._uc_preset_name_to_value.get(selected_uc_preset_name, 0) # 通过选中的名称找到对应的值，找不到用0

        # --- 输入校验 ---
        try:
            steps = int(self.steps_var.get())
            if steps <= 0: raise ValueError("步数必须大于0")
        except (ValueError, TypeError):
            print(f"警告: 无效的步数输入 '{self.steps_var.get()}'，将使用默认值 28。")
            steps = 28
            self.steps_var.set(steps)

        try:
            scale = float(self.scale_var.get())
        except (ValueError, TypeError):
            print(f"警告: 无效的引导强度输入 '{self.scale_var.get()}'，将使用默认值 7.0。")
            scale = 7.0
            self.scale_var.set(scale)

        try:
            seed = int(self.seed_var.get())
        except (ValueError, TypeError):
            print(f"警告: 无效的种子输入 '{self.seed_var.get()}'，将使用默认值 -1。")
            seed = -1
            self.seed_var.set(seed)

        # 校验 NAI 代理端口
        nai_proxy_port_str = self.nai_proxy_port_var.get().strip()
        nai_proxy_port_validated = "" # 用于存储校验后的端口
        if self.nai_use_proxy_var.get() and nai_proxy_port_str: # 仅在启用代理且端口非空时校验
             try:
                  port_num = int(nai_proxy_port_str)
                  if 1 <= port_num <= 65535:
                      nai_proxy_port_validated = nai_proxy_port_str # 端口有效
                  else:
                      # 端口号无效
                      messagebox.showwarning("输入错误", f"NAI 代理端口号 '{nai_proxy_port_str}' 无效。\n端口号必须在 1 到 65535 之间。", parent=self)
                      print(f"错误: 无效的 NAI 代理端口号 '{nai_proxy_port_str}'。")
                      # self.nai_proxy_port_var.set("") # 清空无效输入
             except ValueError:
                  # 输入不是数字
                  messagebox.showwarning("输入错误", f"NAI 代理端口 '{nai_proxy_port_str}' 不是有效的数字。", parent=self)
                  print(f"错误: NAI 代理端口 '{nai_proxy_port_str}' 不是数字。")
                  # self.nai_proxy_port_var.set("") # 清空无效输入

        # 组合配置字典
        config_data = {
            "naiApiKey": self.api_key_var.get(),
            "naiImageSaveDir": self.save_dir_var.get(),
            "naiModel": model_value, # 保存模型的值
            "naiSampler": self.sampler_var.get(),
            "naiSteps": steps, # 校验后的步数
            "naiScale": scale, # 校验后的引导强度
            "naiSeed": seed, # 校验后的种子
            "naiUcPreset": uc_preset_value, # 保存负面预设的值
            "naiQualityToggle": self.quality_toggle_var.get(),
            # --- 返回 NAI 代理设置 ---
            "nai_use_proxy": self.nai_use_proxy_var.get(),
            "nai_proxy_address": self.nai_proxy_address_var.get().strip(),
            "nai_proxy_port": nai_proxy_port_validated # 返回校验后的端口 (可能为空字符串)
        }
        print("NAI 配置数据收集完成。")
        return config_data

    # --- 新增方法：触发 WorkflowTab 更新 ---
    def trigger_workflow_button_update(self, event=None):
        """通知 WorkflowTab 更新按钮状态"""
        try:
            # 确保主应用和 workflow_tab 实例存在且窗口有效
            if hasattr(self.app, 'workflow_tab') and self.app.workflow_tab and self.app.workflow_tab.winfo_exists():
                print(f"[{type(self).__name__}] 触发 WorkflowTab 按钮状态更新...")
                # 调用 WorkflowTab 的 update_button_states 方法
                self.app.workflow_tab.update_button_states()
            else:
                print(f"[{type(self).__name__}] 无法触发更新：WorkflowTab 不可用。")
        except Exception as e:
            print(f"错误: 在 trigger_workflow_button_update ({type(self).__name__}) 中发生异常: {e}")
            traceback.print_exc()