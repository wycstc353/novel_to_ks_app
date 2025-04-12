# ui/sd_config_tab.py
import customtkinter as ctk
from tkinter import StringVar, IntVar, DoubleVar, BooleanVar, filedialog # 导入标准库 filedialog
import traceback # 导入 traceback 以便在 trigger 中打印错误

class SDConfigTab(ctk.CTkFrame):
    """SD WebUI API 设置的 UI 标签页"""
    def __init__(self, master, config_manager, app_instance):
        super().__init__(master, fg_color="transparent")
        self.config_manager = config_manager
        self.app = app_instance # 主应用实例，用于访问 workflow_tab
        # 定义 SD 采样器列表 (常用的)
        self.sd_samplers = [
            "Euler a", "Euler", "LMS", "Heun", "DPM2", "DPM2 a",
            "DPM++ 2S a", "DPM++ 2M", "DPM++ SDE", "DPM++ 2M SDE", "DPM fast",
            "DPM adaptive", "LMS Karras", "DPM2 Karras", "DPM2 a Karras",
            "DPM++ 2S a Karras", "DPM++ 2M Karras", "DPM++ SDE Karras",
            "DPM++ 2M SDE Karras", "DDIM", "PLMS", "UniPC"
            # 可以根据需要添加更多采样器
        ]
        self.build_ui()
        self.load_initial_config()

    def build_ui(self):
        """构建 SD 配置界面的 UI 元素"""
        # 配置主框架的网格列权重，让第二列 (输入框) 可以扩展
        self.grid_columnconfigure(1, weight=1)

        # --- SD WebUI URL & 保存目录 ---
        row = 0
        url_label = ctk.CTkLabel(self, text="WebUI API 地址:")
        url_label.grid(row=row, column=0, padx=10, pady=5, sticky="w")
        self.url_var = StringVar()
        url_entry = ctk.CTkEntry(self, textvariable=self.url_var, placeholder_text="例如: http://127.0.0.1:7860")
        url_entry.grid(row=row, column=1, padx=10, pady=5, sticky="ew")
        # --- 新增绑定 ---
        url_entry.bind("<FocusOut>", self.trigger_workflow_button_update) # 绑定失去焦点事件

        row += 1
        save_dir_label = ctk.CTkLabel(self, text="图片保存目录:")
        save_dir_label.grid(row=row, column=0, padx=10, pady=5, sticky="w")
        self.save_dir_var = StringVar()
        dir_entry = ctk.CTkEntry(self, textvariable=self.save_dir_var, placeholder_text="应用可访问的完整目录路径")
        dir_entry.grid(row=row, column=1, padx=(10, 0), pady=5, sticky="ew")
        # --- 新增绑定 ---
        dir_entry.bind("<FocusOut>", self.trigger_workflow_button_update) # 绑定失去焦点事件
        # 浏览按钮放在第三列
        browse_button = ctk.CTkButton(self, text="浏览...", width=60, command=self.browse_save_directory)
        browse_button.grid(row=row, column=2, padx=(5, 10), pady=5, sticky="w")


        # --- SD 生成参数 (使用网格布局) ---
        row += 1
        param_frame = ctk.CTkFrame(self, fg_color="transparent")
        # 让参数框架跨越所有列
        param_frame.grid(row=row, column=0, columnspan=3, sticky="ew", padx=5, pady=(15, 5))
        # 配置参数框架内部的列权重，使其均匀分布
        param_frame.grid_columnconfigure((0, 1, 2, 3), weight=1, uniform="group_sd")

        col = 0
        row_param = 0
        # 采样器 (Sampler)
        sampler_label = ctk.CTkLabel(param_frame, text="采样器:")
        sampler_label.grid(row=row_param, column=col, padx=5, pady=5, sticky="w")
        self.sampler_var = StringVar(value="Euler a") # 默认值
        sampler_combo = ctk.CTkComboBox(param_frame, values=self.sd_samplers, variable=self.sampler_var)
        sampler_combo.grid(row=row_param+1, column=col, padx=5, pady=5, sticky="ew")

        col += 1
        # 步数 (Steps)
        steps_label = ctk.CTkLabel(param_frame, text="步数:")
        steps_label.grid(row=row_param, column=col, padx=5, pady=5, sticky="w")
        self.steps_var = IntVar(value=20) # 默认值
        steps_entry = ctk.CTkEntry(param_frame, textvariable=self.steps_var)
        steps_entry.grid(row=row_param+1, column=col, padx=5, pady=5, sticky="ew")

        col += 1
        # CFG Scale
        cfg_label = ctk.CTkLabel(param_frame, text="CFG Scale:")
        cfg_label.grid(row=row_param, column=col, padx=5, pady=5, sticky="w")
        self.cfg_scale_var = DoubleVar(value=7.0) # 默认值
        cfg_entry = ctk.CTkEntry(param_frame, textvariable=self.cfg_scale_var)
        cfg_entry.grid(row=row_param+1, column=col, padx=5, pady=5, sticky="ew")

        # 换到下一行参数
        col = 0
        row_param += 2
        # 宽度 (Width)
        width_label = ctk.CTkLabel(param_frame, text="宽度:")
        width_label.grid(row=row_param, column=col, padx=5, pady=5, sticky="w")
        self.width_var = IntVar(value=512) # 默认值
        width_entry = ctk.CTkEntry(param_frame, textvariable=self.width_var)
        width_entry.grid(row=row_param+1, column=col, padx=5, pady=5, sticky="ew")

        col += 1
        # 高度 (Height)
        height_label = ctk.CTkLabel(param_frame, text="高度:")
        height_label.grid(row=row_param, column=col, padx=5, pady=5, sticky="w")
        self.height_var = IntVar(value=512) # 默认值
        height_entry = ctk.CTkEntry(param_frame, textvariable=self.height_var)
        height_entry.grid(row=row_param+1, column=col, padx=5, pady=5, sticky="ew")

        col += 1
        # 种子 (Seed)
        seed_label = ctk.CTkLabel(param_frame, text="种子 (-1随机):")
        seed_label.grid(row=row_param, column=col, padx=5, pady=5, sticky="w")
        self.seed_var = IntVar(value=-1) # 默认值 -1 表示随机
        seed_entry = ctk.CTkEntry(param_frame, textvariable=self.seed_var)
        seed_entry.grid(row=row_param+1, column=col, padx=5, pady=5, sticky="ew")

        # 换到下一行参数 (布尔选项)
        col = 0
        row_param += 2
        # 面部修复 (Restore Faces)
        self.restore_faces_var = BooleanVar(value=False) # 默认关闭
        restore_check = ctk.CTkCheckBox(param_frame, text="面部修复", variable=self.restore_faces_var)
        restore_check.grid(row=row_param, column=col, padx=5, pady=10, sticky="w")

        col += 1
        # 平铺/无缝 (Tiling)
        self.tiling_var = BooleanVar(value=False) # 默认关闭
        tiling_check = ctk.CTkCheckBox(param_frame, text="平铺/无缝", variable=self.tiling_var)
        tiling_check.grid(row=row_param, column=col, padx=5, pady=10, sticky="w")

        # --- 全局附加提示词 ---
        row += 1 # 基于主框架的行
        add_pos_label = ctk.CTkLabel(self, text="全局附加正向提示:")
        add_pos_label.grid(row=row, column=0, padx=10, pady=(15, 5), sticky="nw") # 使用 nw 对齐
        self.add_pos_textbox = ctk.CTkTextbox(self, height=60, wrap="word") # 自动换行
        self.add_pos_textbox.grid(row=row, column=1, columnspan=2, padx=10, pady=(15, 5), sticky="ew") # 跨越输入框和按钮列

        row += 1
        add_neg_label = ctk.CTkLabel(self, text="全局附加负向提示:")
        add_neg_label.grid(row=row, column=0, padx=10, pady=5, sticky="nw")
        self.add_neg_textbox = ctk.CTkTextbox(self, height=60, wrap="word")
        self.add_neg_textbox.grid(row=row, column=1, columnspan=2, padx=10, pady=5, sticky="ew")


    def browse_save_directory(self):
        """打开目录选择对话框，让用户选择 SD 图片保存目录"""
        # 使用 tkinter 的 filedialog
        directory = filedialog.askdirectory(title="选择 SD 图片保存目录", parent=self) # parent=self 使对话框显示在应用窗口之上
        if directory:
            # 如果用户选择了目录，则更新输入框变量
            self.save_dir_var.set(directory)
            print(f"SD 图片保存目录已设置为: {directory}")
            # --- 新增：选择目录后也触发更新 ---
            self.trigger_workflow_button_update()
        else:
            print("用户取消选择目录。")

    def load_initial_config(self):
        """从配置文件加载初始 SD 配置并更新 UI 元素"""
        print("正在加载 SD 配置到 UI...")
        # 从 config_manager 加载 'sd' 类型的配置
        config = self.config_manager.load_config("sd")

        # 将加载的配置值设置到对应的 UI 变量
        self.url_var.set(config.get("sdWebUiUrl", "")) # WebUI 地址
        self.save_dir_var.set(config.get("sdImageSaveDir", "")) # 保存目录
        self.sampler_var.set(config.get("sdSampler", "Euler a")) # 采样器
        self.steps_var.set(int(config.get("sdSteps", 20))) # 步数 (确保是整数)
        self.cfg_scale_var.set(float(config.get("sdCfgScale", 7.0))) # CFG Scale (确保是浮点数)
        self.width_var.set(int(config.get("sdWidth", 512))) # 宽度
        self.height_var.set(int(config.get("sdHeight", 512))) # 高度
        self.seed_var.set(int(config.get("sdSeed", -1))) # 种子
        self.restore_faces_var.set(bool(config.get("sdRestoreFaces", False))) # 面部修复 (确保是布尔值)
        self.tiling_var.set(bool(config.get("sdTiling", False))) # 平铺 (确保是布尔值)

        # 加载附加提示词到文本框
        # 先清空文本框
        self.add_pos_textbox.delete("1.0", "end")
        # 插入加载的值
        self.add_pos_textbox.insert("1.0", config.get("sdAdditionalPositivePrompt", ""))

        self.add_neg_textbox.delete("1.0", "end")
        self.add_neg_textbox.insert("1.0", config.get("sdAdditionalNegativePrompt", ""))

        print("SD 配置加载完成。")


    def get_config_data(self):
        """从 UI 元素收集当前的 SD 配置数据"""
        print("正在从 UI 收集 SD 配置数据...")
        # --- 输入校验 ---
        # 对数字输入进行校验，如果无效则使用默认值
        try:
            steps = int(self.steps_var.get())
            if steps <= 0: raise ValueError("步数必须大于0")
        except (ValueError, TypeError):
            print(f"警告: 无效的步数输入 '{self.steps_var.get()}'，将使用默认值 20。")
            steps = 20
            self.steps_var.set(steps) # 更新 UI 显示为默认值

        try:
            cfg = float(self.cfg_scale_var.get())
            # 可以添加范围检查，例如 if not 0.0 <= cfg <= 30.0: raise ValueError(...)
        except (ValueError, TypeError):
            print(f"警告: 无效的 CFG Scale 输入 '{self.cfg_scale_var.get()}'，将使用默认值 7.0。")
            cfg = 7.0
            self.cfg_scale_var.set(cfg)

        try:
            width = int(self.width_var.get())
            # SD 通常要求宽高是 8 的倍数，可以添加检查
            if width <= 0 or width % 8 != 0: raise ValueError("宽度必须是大于0的8的倍数")
        except (ValueError, TypeError):
            print(f"警告: 无效的宽度输入 '{self.width_var.get()}'，将使用默认值 512。")
            width = 512
            self.width_var.set(width)

        try:
            height = int(self.height_var.get())
            if height <= 0 or height % 8 != 0: raise ValueError("高度必须是大于0的8的倍数")
        except (ValueError, TypeError):
            print(f"警告: 无效的高度输入 '{self.height_var.get()}'，将使用默认值 512。")
            height = 512
            self.height_var.set(height)

        try:
            seed = int(self.seed_var.get())
        except (ValueError, TypeError):
            print(f"警告: 无效的种子输入 '{self.seed_var.get()}'，将使用默认值 -1。")
            seed = -1
            self.seed_var.set(seed)

        # 获取附加提示词文本
        add_pos = self.add_pos_textbox.get("1.0", "end-1c").strip() # 获取从头到尾的文本，去除末尾换行符和首尾空格
        add_neg = self.add_neg_textbox.get("1.0", "end-1c").strip()

        # 组合配置字典
        config_data = {
            "sdWebUiUrl": self.url_var.get().rstrip('/'), # 获取 URL 并移除末尾斜杠
            "sdImageSaveDir": self.save_dir_var.get(), # 保存目录
            "sdSampler": self.sampler_var.get(), # 采样器
            "sdSteps": steps, # 校验后的步数
            "sdCfgScale": cfg, # 校验后的 CFG Scale
            "sdWidth": width, # 校验后的宽度
            "sdHeight": height, # 校验后的高度
            "sdSeed": seed, # 校验后的种子
            "sdRestoreFaces": self.restore_faces_var.get(), # 面部修复 (布尔值)
            "sdTiling": self.tiling_var.get(), # 平铺 (布尔值)
            "sdAdditionalPositivePrompt": add_pos, # 附加正向提示
            "sdAdditionalNegativePrompt": add_neg # 附加负向提示
        }
        print("SD 配置数据收集完成。")
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