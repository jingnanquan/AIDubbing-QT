# -*- coding: utf-8 -*-
import os
from pathlib import Path
import re
import time
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
import tkinter.ttk as ttk
import pandas as pd
import threading
import traceback
import concurrent.futures

# ==============================================================================
#                                 库导入区域 (已整合清理)
# ==============================================================================

# ... (库导入部分无变化，保持原样) ...
# 用于估算Token
try:
    import tiktoken

    HAS_TIKTOKEN = True
except ImportError:
    HAS_TIKTOKEN = False
    print("警告: 未安装 tiktoken，Token 计算将使用简单分词法，可能不准确。")

# 用于Vertex AI (Gemini)
try:
    from google.oauth2 import service_account
    import vertexai
    from vertexai.generative_models import GenerativeModel, Part
    import vertexai.preview.generative_models as generative_models

    HAS_VERTEX_AI = True
    print("Vertex AI SDK 已成功导入。")
except ImportError:
    print("错误: 未安装 google-cloud-aiplatform (Vertex AI SDK)。")
    print("请在您的环境中运行: pip install google-cloud-aiplatform")
    HAS_VERTEX_AI = False

# 用于Deepseek API
try:
    import requests

    HAS_REQUESTS = True
except ImportError:
    print("警告: 未安装 requests，Deepseek API 不可用。")
    HAS_REQUESTS = False

# 用于从视频提取音频
try:
    import ffmpeg

    HAS_FFMPEG = True
except ImportError:
    print("错误: 未安装 ffmpeg-python。从视频提取音频的功能将无法使用。")
    print("请在您的环境中运行: pip install ffmpeg-python")
    HAS_FFMPEG = False

# ==============================================================================
#                                   API 配置
# ==============================================================================

# Deepseek API Key
API_KEY_DEEPSEEK = "sk-a1d9e06313554068b87359f624eff10d"  # 请替换为您的Key

# Gemini (Vertex AI) 配置
VERTEX_JSON_CRED_FILENAME = "vertex_credentials.json"
VERTEX_PROJECT_ID = "gen-lang-client-0944558427"
VERTEX_LOCATION = "us-central1"

# ==============================================================================
#                                   全局变量
# ==============================================================================

global_gemini_client = None
global_token_count = 0
app_instance = None  # 用于在非GUI线程中更新UI


# ==============================================================================
#                                   核心功能函数
# ==============================================================================

# -------------------- 数据处理 --------------------
def read_project_info(info_folder_path):
    # ... (此函数无变化) ...
    role_info_str = ""
    plot_summary_str = ""
    role_file_found = False
    for filename in os.listdir(info_folder_path):
        if filename.lower().startswith("角色介绍-") and filename.lower().endswith(".xlsx"):
            try:
                excel_path = os.path.join(info_folder_path, filename)
                df_roles = pd.read_excel(excel_path)
                role_info_str = build_role_info_string(df_roles)
                app_instance.log_message(f"[信息] 已成功读取角色文件: {filename}")
                role_file_found = True
                break
            except Exception as e:
                app_instance.log_message(f"[错误] 读取角色文件 {filename} 失败: {e}")
    if not role_file_found:
        app_instance.log_message("[警告] 未在信息文件夹中找到 '角色介绍-*.xlsx' 文件。")
    plot_file_found = False
    for filename in os.listdir(info_folder_path):
        if filename.lower().startswith("剧情简介-") and filename.lower().endswith(".txt"):
            try:
                txt_path = os.path.join(info_folder_path, filename)
                with open(txt_path, 'r', encoding='utf-8') as f:
                    plot_summary_str = f.read()
                app_instance.log_message(f"[信息] 已成功读取剧情简介: {filename}")
                plot_file_found = True
                break
            except Exception as e:
                app_instance.log_message(f"[错误] 读取剧情简介 {filename} 失败: {e}")
    if not plot_file_found:
        app_instance.log_message("[警告] 未在信息文件夹中找到 '剧情简介-*.txt' 文件。")
    return role_info_str, plot_summary_str


def build_role_info_string(df_roles):
    # ... (此函数无变化) ...
    lines = []
    for _, row in df_roles.iterrows():
        desc = (
            f"原名：{row.get('原名', '')}；别称：{row.get('译名', '')}；"
            f"性别：{row.get('性别', '')}；年龄：{row.get('年龄', '')}；"
            f"性格：{row.get('性格', '')}；说话风格：{row.get('说话风格', '')}；"
            f"补充：{row.get('补充信息', '')}"
        )
        lines.append(desc)
    return "\n".join(lines)


def parse_srt(file_path):
    # ... (此函数无变化) ...
    try:
        with open(file_path, 'r', encoding='utf-8-sig') as f:
            content = f.read()
    except Exception:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    blocks = re.split(r'\n\s*\n', content.strip())
    entries = []
    for block in blocks:
        lines = block.strip().splitlines()
        if len(lines) >= 3:
            idx_line, time_line = lines[0].strip(), lines[1].strip()
            text_content = " ".join(lines[2:])
            if "-->" in time_line:
                entries.append({"index": idx_line, "time_range": time_line, "text": text_content})
    return entries


# -------------------- 音频提取 --------------------
def extract_audio_from_video(video_path, app_instance_ref, log_prefix=""):
    # ... (此函数无变化) ...
    if not HAS_FFMPEG:
        app_instance_ref.log_message(f"{log_prefix}[错误] 缺少 ffmpeg-python 库，无法从视频提取音频。")
        return None
    base_name = os.path.splitext(os.path.basename(video_path))[0]
    timestamp = int(time.time() * 1000)
    output_audio_path = os.path.join(os.path.dirname(video_path), f"{base_name}_{timestamp}_temp_audio.wav")
    app_instance_ref.log_message(f"{log_prefix}[音频] 正在从 {os.path.basename(video_path)} 提取...")
    try:
        (
            ffmpeg
            .input(video_path)
            .output(output_audio_path, acodec='pcm_s16le', ac=1, ar='16000')
            .overwrite_output()
            .run(quiet=True, capture_stdout=True, capture_stderr=True)
        )
        app_instance_ref.log_message(f"{log_prefix}[音频] 成功提取: {os.path.basename(output_audio_path)}")
        return output_audio_path
    except Exception as e:
        app_instance_ref.log_message(f"{log_prefix}[错误] 提取音频失败: {e}")
        traceback.print_exc()
        return None


# -------------------- Prompt 构造 --------------------
def build_prompt_for_chunk(srt_entries_chunk, role_info_str, plot_summary_str):
    # ... (此函数无变化) ...
    plot_section = f"【剧情简介】:\n{plot_summary_str}\n\n" if plot_summary_str else ""
    example = "示例格式：\n1\n00:00:16,320 --> 00:00:17,839\n萧尘宴：我包养你\n\n2\n00:00:17,839 --> 00:00:19,480\n萧尘宴：每个月给你十万\n\n"
    instruction = (
        "你是一名智能助手，能够根据给定的【剧情简介】和【角色信息】与【字幕】内容，为每句字幕匹配或推断说话人的角色。\n\n"
        f"{plot_section}"
        "如果台词明显符合某个已知角色（原名或别称），则写该角色名字；否则可标注为 '士兵甲' '随从甲' '路人甲' 等。\n\n"
        f"【角色信息】：\n{role_info_str}\n\n"
        f"以下是字幕格式示例（严格遵循）：\n{example}"
        "以下是本批字幕，请严格按照示例格式推断并输出：\n行号\n时间戳\n角色名：台词\n\n（每条后空行，禁止添加“角色：”前缀、注释或说明）\n"
    )
    srt_text = ""
    for item in srt_entries_chunk:
        srt_text += f"{item['index']}\n{item['time_range']}\n{item['text']}\n\n"
    return instruction + srt_text


# [修改] 恢复使用您指定的简洁版Prompt
def build_gemini_diarization_prompt(role_info_str, plot_summary_str, current_srt_content, prev_srt_content,
                                    next_srt_content):
    plot_section = f"【剧情简介】:\n{plot_summary_str}\n\n" if plot_summary_str else ""
    prev_srt_section = f"【参考字幕 - 上一集】:\n---\n{prev_srt_content.strip()}\n---\n\n" if prev_srt_content else ""
    next_srt_section = f"【参考字幕 - 下一集】:\n---\n{next_srt_content.strip()}\n---\n\n" if next_srt_content else ""

    # 在您的要求中，新增了要同时处理三个音频文件的点。
    # 我们需要在Prompt中体现出来，让模型知道它接收了多个音频。
    instruction = (
        "你是一位专业的音频后期处理专家，你的任务是对【当前待处理字幕】进行说话人识别（Speaker Diarization）。\n\n"
        "我为你提供了三集连续的【音频文件】（上一集、当前集、下一集）和三个对应的【SRT字幕文件文本】。\n\n"
        "你需要严格遵循以下步骤：\n"
        "1.  仔细聆听所有提供的【音频文件】，以建立对角色声音的跨集认知。\n"
        "2.  阅读【剧情简介】、【角色信息】以及所有提供的字幕上下文（上一集、当前、下一集），以全面理解剧情、角色关系和对话流。\n"
        "3.  你的核心任务是处理【当前待处理字幕】。对于其中的每一句台词，结合【声音特征】、【台词内容】以及【跨集剧情上下文】来判断说话人。\n"
        "4.  将你识别出的角色名添加到【当前待处理字幕】的台词前面。\n\n"
        f"{plot_section}"
        f"{prev_srt_section}"
        f"{next_srt_section}"
        "【角色信息】:\n"
        f"{role_info_str}\n\n"
        "【输出要求】:\n"
        "- 你的唯一输出必须是【处理后】的【当前待处理字幕】的完整SRT格式内容。\n"
        "- **不要**输出参考字幕（上一集或下一集）的任何内容。\n"
        "- 严格按照 “行号\\n时间戳\\n角色名: 台词\\n\\n” 的格式输出。\n"
        "- 如果一句台词不属于任何主要角色，可以标注为 '旁白'、'路人' 或其他合适的标签。\n"
        "- 不要添加任何多余的解释、引言、代码块标记（如 ```srt ... ```）或总结。\n\n"
        "以下是【当前待处理字幕】，这是你需要处理并输出的唯一部分：\n"
        "-------------------------------------\n"
        f"{current_srt_content}"
    )
    return instruction


# -------------------- 模型调用 --------------------
# [修改] 增加temperature参数
def safe_generate_content_gemini(prompt, audio_paths=None, max_retries=5, temperature=0.5, log_prefix=""):
    if not HAS_VERTEX_AI or not global_gemini_client:
        print(f"{log_prefix}[Gemini] 客户端未初始化，跳过调用。")
        return None

    for attempt in range(1, max_retries + 1):
        try:
            contents_to_send = []
            if audio_paths:
                # 日志只在第一次显示，避免重复刷屏
                if "候选" not in log_prefix:
                    app_instance.update_status(f"{log_prefix}正在准备 {len(audio_paths)} 个音频数据...")

                for audio_path in audio_paths:
                    if audio_path and os.path.exists(audio_path):
                        audio_file_bytes = Path(audio_path).read_bytes()
                        audio_part = Part.from_data(mime_type='audio/wav', data=audio_file_bytes)
                        contents_to_send.append(audio_part)

                if "候选" not in log_prefix:
                    app_instance.update_status(f"{log_prefix}数据准备完毕，向Gemini请求分析...")

            contents_to_send.append(Part.from_text(prompt))

            response = global_gemini_client.generate_content(
                contents_to_send,
                generation_config=generative_models.GenerationConfig(temperature=temperature, max_output_tokens=8192)
            )
            return response.text if hasattr(response, 'text') else str(response)

        except Exception as e:
            print(f"{log_prefix}[Gemini] 第{attempt}次失败: {e}")
            traceback.print_exc()
            time.sleep(5)
    return None


def safe_generate_content_deepseek(prompt, max_retries=5, log_prefix=""):
    # ... (此函数无变化) ...
    if not HAS_REQUESTS: return None
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.post("https://api.deepseek.com/v1/chat/completions",
                                 headers={"Authorization": f"Bearer {API_KEY_DEEPSEEK}",
                                          "Content-Type": "application/json"},
                                 json={"model": "deepseek-chat", "messages": [{"role": "user", "content": prompt}],
                                       "temperature": 0.5, "max_tokens": 4096},
                                 timeout=90)
            resp.raise_for_status()
            return resp.json()['choices'][0]['message']['content']
        except Exception as e:
            print(f"{log_prefix}[Deepseek] 第{attempt}次失败: {e}")
            time.sleep(5)
    return None


def safe_generate_content_wrapper(api_mode, prompt, audio_paths=None, temperature=0.5, log_prefix=""):
    if api_mode == "Gemini":
        return safe_generate_content_gemini(prompt, audio_paths=audio_paths, temperature=temperature,
                                            log_prefix=log_prefix)
    else:
        # ... (此函数无变化) ...
        if audio_paths and any(audio_paths):
            app_instance.log_message(f"{log_prefix}[警告] Deepseek API 不支持音频输入，已忽略音频文件。")
        return safe_generate_content_deepseek(prompt, log_prefix=log_prefix)


# [新增] 仲裁函数
def run_arbitrator_model(candidate_srts, original_srt, role_info_str, plot_summary_str, log_prefix=""):
    app_instance.log_message(f"[{log_prefix}][仲裁] 已获得 {len(candidate_srts)} 个候选结果，开始最终仲裁...")

    candidates_section = ""
    valid_candidates = [srt for srt in candidate_srts if srt and srt.strip()]

    if not valid_candidates:
        app_instance.log_message(f"[{log_prefix}][错误] 所有候选生成均失败，无法进行仲裁。")
        return None

    for i, srt_text in enumerate(valid_candidates):
        candidates_section += f"--- 候选版本 {i + 1} ---\n{filter_extras(srt_text)}\n\n"

    arbitrator_prompt = (
        "你是一位经验丰富的总编辑和剧本监制，你的任务是从多个由AI生成的带角色标注的SRT字幕草稿中，裁定出唯一一个最准确、最合理的最终版本。\n\n"
        "**任务背景**:\n"
        "我让多个AI助手根据同一份【原始SRT】、【音频】、【剧情简介】和【角色信息】各自生成了一份角色标注版本。由于AI的随机性，这些版本可能存在细微差异。你需要利用你的专业判断力，选出最佳答案。\n\n"
        "**决策流程**:\n"
        "1.  **通读所有候选版本**: 快速浏览下面提供的所有【候选版本】，了解它们之间的差异点。\n"
        "2.  **逐行对比，多数投票**: 针对【原始SRT】中的每一句台词，查看【候选版本】中分别标注了哪个角色。在大多数情况下，选择票数最高的那个角色标注。\n"
        "3.  **逻辑优先，修正错误**: 当出现分歧时（例如，票数接近），你必须运用【剧情简介】和【角色信息】进行逻辑推理，做出最终裁决。剧情的连贯性和角色的性格设定是最高判断准则。\n"
        "4.  **构建最终版本**: 基于你的裁决，生成一个全新的、完整的、从头到尾都最准确的SRT文件。\n\n"
        "**参考信息**:\n"
        f"【剧情简介】:\n{plot_summary_str}\n\n"
        f"【角色信息】:\n{role_info_str}\n\n"
        f"【原始SRT】 (这是你需要标注的原本):\n{original_srt}\n\n"
        "**以下是需要你进行仲裁的【候选版本】**:\n"
        f"{candidates_section}"
        "**输出要求**:\n"
        "- 你的唯一输出，必须是你裁定的【最终版本】的完整SRT内容。\n"
        "- 严格遵循SRT格式：“行号\\n时间戳\\n角色名: 台词\\n\\n”。\n"
        "- **不要**包含任何解释、分析、投票过程或代码块标记(```)。只输出最终的SRT文本。"
    )

    final_srt = safe_generate_content_wrapper(
        "Gemini",
        arbitrator_prompt,
        audio_paths=None,
        temperature=0.1,  # 仲裁过程需要确定性，使用低温
        log_prefix=f"{log_prefix}[仲裁]"
    )

    app_instance.log_message(f"[{log_prefix}][仲裁] 仲裁完成。")
    return final_srt


# -------------------- 辅助函数 --------------------
def filter_extras(text):
    # ... (此函数无变化) ...
    if not text: return ""
    lines = text.strip().splitlines()
    if lines and lines[0].strip().lower() in ("```srt", "```"): lines = lines[1:]
    if lines and lines[-1].strip() == "```": lines = lines[:-1]
    skip_keys = ["好的，我已经准备好了", "请提供台词", "角色：", "**", "Sure"]
    return "\n".join([l for l in lines if not any(k in l for k in skip_keys)]).strip()


def parse_model_output_as_srt(text):
    # ... (此函数无变化) ...
    blocks = re.split(r'\n\s*\n', text.strip())
    entries = []
    for block in blocks:
        lines = block.strip().splitlines()
        if len(lines) >= 3 and "-->" in lines[1] and lines[0].strip().isdigit():
            entries.append((lines[0].strip(), lines[1].strip(), "\n".join(lines[2:])))
    return entries


def produce_standard_srt(entries):
    # ... (此函数无变化) ...
    srt_blocks = []
    for srt_idx, time_range, sub_text in entries:
        block_text = f"{srt_idx}\n{time_range}\n{sub_text.strip() if sub_text else ''}"
        srt_blocks.append(block_text)
    return "\n\n".join(srt_blocks) + "\n\n" if srt_blocks else ""


def approximate_token_count(text, model="gpt-4"):
    # ... (此函数无变化) ...
    if HAS_TIKTOKEN:
        try:
            enc = tiktoken.encoding_for_model(model)
            return len(enc.encode(text))
        except Exception:
            return len(text.split())
    else:
        return len(text.split())


# ==============================================================================
#                                   GUI 主程序
# ==============================================================================

class SpeakerTaggerApp:
    def __init__(self, master):
        self.master = master
        master.title("SRT角色标注工具 v4.0 (自洽仲裁版)")
        # ... (GUI部分无变化) ...
        master.geometry("800x700")
        self.token_lock = threading.Lock()
        frm_mode = tk.Frame(master, padx=10, pady=5)
        frm_mode.pack(fill=tk.X)
        tk.Label(frm_mode, text="分析模式:", font=("", 10, "bold")).pack(side=tk.LEFT)
        self.mode_var = tk.StringVar(value="Audio-Enhanced")
        tk.Radiobutton(frm_mode, text="声纹增强 (文件夹)", variable=self.mode_var, value="Audio-Enhanced",
                       command=self.toggle_mode).pack(side=tk.LEFT, padx=5)
        tk.Radiobutton(frm_mode, text="纯文本 (单SRT文件)", variable=self.mode_var, value="Text-Only",
                       command=self.toggle_mode).pack(side=tk.LEFT, padx=5)
        frm_paths = tk.LabelFrame(master, text="输入路径", padx=10, pady=5)
        frm_paths.pack(fill=tk.X, padx=10)
        self.lbl_input = tk.Label(frm_paths, text="媒体文件夹:", width=15, anchor='w')
        self.lbl_input.grid(row=0, column=0, pady=2)
        self.entry_input = tk.Entry(frm_paths)
        self.entry_input.grid(row=0, column=1, sticky='ew', padx=5)
        self.btn_browse_input = tk.Button(frm_paths, text="浏览文件夹...", command=self.browse_input)
        self.btn_browse_input.grid(row=0, column=2)
        self.lbl_info = tk.Label(frm_paths, text="信息文件夹:", width=15, anchor='w')
        self.lbl_info.grid(row=1, column=0, pady=2)
        self.entry_info = tk.Entry(frm_paths)
        self.entry_info.grid(row=1, column=1, sticky='ew', padx=5)
        self.btn_browse_info = tk.Button(frm_paths, text="浏览文件夹...", command=self.select_info_folder)
        self.btn_browse_info.grid(row=1, column=2)
        frm_paths.grid_columnconfigure(1, weight=1)
        frm_params = tk.LabelFrame(master, text="参数配置", padx=10, pady=5)
        frm_params.pack(fill=tk.X, padx=10, pady=5)
        tk.Label(frm_params, text="API模式:", width=10, anchor='w').pack(side=tk.LEFT)
        self.combo_api = ttk.Combobox(frm_params, values=["Gemini", "Deepseek"], state="readonly", width=12)
        self.combo_api.set("Gemini")
        self.combo_api.pack(side=tk.LEFT, padx=5)
        tk.Label(frm_params, text="每块行数 (仅文本模式):").pack(side=tk.LEFT, padx=(10, 0))
        self.entry_chunk_size = tk.Entry(frm_params, width=8)
        self.entry_chunk_size.insert(0, "200")
        self.entry_chunk_size.pack(side=tk.LEFT, padx=5)
        self.btn_run = tk.Button(master, text="开始生成", command=self.start_process_thread, font=("", 12, "bold"))
        self.btn_run.pack(pady=10)
        self.txt_log = scrolledtext.ScrolledText(master, height=15)
        self.txt_log.pack(padx=10, pady=5, fill=tk.BOTH, expand=True)
        status_frame = tk.Frame(master, padx=10)
        status_frame.pack(fill=tk.X)
        self.lbl_status = tk.Label(status_frame, text="状态：待命", fg="blue", anchor='w')
        self.lbl_status.pack(side=tk.LEFT)
        self.lbl_token_usage = tk.Label(status_frame, text="累计已用 Token: 0", fg="red", anchor='e')
        self.lbl_token_usage.pack(side=tk.RIGHT)
        self.toggle_mode()

    # ... (GUI方法无变化) ...
    def toggle_mode(self):
        mode = self.mode_var.get()
        if mode == 'Text-Only':
            self.lbl_input.config(text="输入SRT文件:")
            self.btn_browse_input.config(text="浏览文件...")
            self.entry_chunk_size.config(state=tk.NORMAL)
            self.lbl_info.config(state=tk.NORMAL);
            self.entry_info.config(state=tk.NORMAL);
            self.btn_browse_info.config(state=tk.NORMAL)
        else:
            self.lbl_input.config(text="媒体文件夹:")
            self.btn_browse_input.config(text="浏览文件夹...")
            self.entry_chunk_size.config(state=tk.DISABLED)
            self.lbl_info.config(state=tk.NORMAL);
            self.entry_info.config(state=tk.NORMAL);
            self.btn_browse_info.config(state=tk.NORMAL)

    def browse_input(self):
        mode = self.mode_var.get()
        path = ""
        if mode == 'Text-Only':
            path = filedialog.askopenfilename(title="选择SRT文件", filetypes=[("SRT字幕文件", "*.srt")])
        else:
            path = filedialog.askdirectory(title="选择包含视频(.mp4)和字幕(.srt)的文件夹")
        if path: self.entry_input.delete(0, tk.END); self.entry_input.insert(0, path)

    def select_info_folder(self):
        path = filedialog.askdirectory(title="选择包含角色介绍和剧情简介的文件夹")
        if path: self.entry_info.delete(0, tk.END); self.entry_info.insert(0, path)

    def update_status(self, text):
        self.master.after(0, lambda: self.lbl_status.config(text=text))

    def update_token_count(self, count):
        self.master.after(0, lambda: self.lbl_token_usage.config(text=f"累计已用 Token: {count}"))

    def log_message(self, text):
        self.master.after(0, lambda: self.txt_log.insert(tk.END, text + "\n"))

    def show_info_on_main_thread(self, title, message):
        self.master.after(0, lambda: messagebox.showinfo(title, message))

    def show_error_on_main_thread(self, title, message):
        self.master.after(0, lambda: messagebox.showerror(title, message))

    def set_run_button_state(self, state):
        self.master.after(0, lambda: self.btn_run.config(state=state))

    def start_process_thread(self):
        self.set_run_button_state(tk.DISABLED)
        process_thread = threading.Thread(target=self.run_process, daemon=True)
        process_thread.start()

    def run_process(self):
        # ... (此函数无变化) ...
        global global_token_count
        self.master.after(0, lambda: self.txt_log.delete("1.0", tk.END))
        mode = self.mode_var.get()
        input_path = self.entry_input.get().strip()
        info_folder_path = self.entry_info.get().strip()
        api_mode = self.combo_api.get().strip()
        if not input_path or not os.path.exists(input_path):
            self.show_error_on_main_thread("错误", "请提供一个有效的输入路径！");
            self.set_run_button_state(tk.NORMAL);
            return
        if not info_folder_path or not os.path.isdir(info_folder_path):
            self.show_error_on_main_thread("错误", "请选择有效的信息文件夹！");
            self.set_run_button_state(tk.NORMAL);
            return
        if api_mode == "Gemini" and not global_gemini_client:
            self.show_error_on_main_thread("错误", "Gemini客户端未初始化。请检查配置并重启。");
            self.set_run_button_state(tk.NORMAL);
            return
        try:
            self.update_status("读取项目信息...")
            role_info_str, plot_summary_str = read_project_info(info_folder_path)
            if not role_info_str and not plot_summary_str:
                self.show_error_on_main_thread("信息缺失", "在信息文件夹中未能找到任何角色介绍或剧情简介文件。");
                self.set_run_button_state(tk.NORMAL);
                return
            global_token_count = 0
            self.update_token_count(0)
            if mode == 'Audio-Enhanced':
                self.run_folder_process(input_path, role_info_str, plot_summary_str, api_mode)
            else:
                self.run_text_only_process(input_path, role_info_str, plot_summary_str, api_mode)
        except Exception as e:
            error_msg = f"处理过程中发生严重错误: {e}\n{traceback.format_exc()}"
            self.log_message(f"[致命错误] {error_msg}");
            self.update_status("处理失败！");
            self.show_error_on_main_thread("错误", error_msg)
        finally:
            self.set_run_button_state(tk.NORMAL)

    def run_folder_process(self, folder_path, role_info_str, plot_summary_str, api_mode):
        # ... (此函数无变化，除了并发数) ...
        self.log_message(f"开始扫描媒体文件夹: {folder_path}")
        output_dir = os.path.join(folder_path, "Processed_SRTs")
        os.makedirs(output_dir, exist_ok=True)
        self.log_message(f"[信息] 输出文件将保存到: {output_dir}")
        all_files = sorted(os.listdir(folder_path))
        mp4_files = [os.path.join(folder_path, f) for f in all_files if f.lower().endswith('.mp4')]
        srt_files = [os.path.join(folder_path, f) for f in all_files if f.lower().endswith('.srt')]
        if not mp4_files or not srt_files:
            self.show_info_on_main_thread("文件缺失", "媒体文件夹中必须同时包含 .mp4 和 .srt 文件。");
            return
        if len(mp4_files) != len(srt_files):
            msg = f"文件数量不匹配！\n找到 {len(mp4_files)} 个 .mp4 文件。\n找到 {len(srt_files)} 个 .srt 文件。\n请确保两种文件的数量一致。"
            self.show_error_on_main_thread("文件数量不匹配", msg);
            return
        video_srt_pairs = list(zip(mp4_files, srt_files))
        total_files = len(video_srt_pairs)
        self.log_message(f"找到 {total_files} 个匹配的 视频/字幕 对，开始并发处理(最多5个任务)...")
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:  # 保持整体任务并发数为5
            futures = []
            for i, (current_video_path, current_srt_path) in enumerate(video_srt_pairs):
                base_name = os.path.basename(current_video_path)
                out_filename = os.path.splitext(base_name)[0] + "-speaker.srt"
                out_path = os.path.join(output_dir, out_filename)
                log_prefix = f"任务 {i + 1}/{total_files}"
                prev_video_path = video_srt_pairs[i - 1][0] if i > 0 else None
                next_video_path = video_srt_pairs[i + 1][0] if i < total_files - 1 else None
                prev_srt_path = video_srt_pairs[i - 1][1] if i > 0 else None
                next_srt_path = video_srt_pairs[i + 1][1] if i < total_files - 1 else None
                self.log_message(f"[{log_prefix}] 已加入处理队列: {base_name}")
                future = executor.submit(self.run_single_audio_file, current_video_path, current_srt_path,
                                         prev_video_path, next_video_path, prev_srt_path, next_srt_path, out_path,
                                         role_info_str, plot_summary_str, api_mode, log_prefix)
                futures.append(future)
            for future in concurrent.futures.as_completed(futures):
                try:
                    future.result()
                except Exception as exc:
                    self.log_message(f"[致命错误] 一个子任务执行失败: {exc}"); traceback.print_exc()

        print("\n所有文件处理任务已提交并完成。详细日志请查看GUI窗口。")

        self.log_message("\n" + "=" * 50 + "\n批量处理全部完成！")
        self.update_status("全部处理完成！")
        self.show_info_on_main_thread("完成", f"已完成对文件夹中 {total_files} 个文件的处理。")

    def run_text_only_process(self, srt_path, role_info_str, plot_summary_str, api_mode):
        # ... (此函数无变化) ...
        global global_token_count
        self.log_message(f"[模式] 纯文本分析模式，处理文件: {os.path.basename(srt_path)}")
        output_dir = os.path.join(os.path.dirname(srt_path), "Processed_SRTs")
        os.makedirs(output_dir, exist_ok=True)
        self.log_message(f"[信息] 输出文件将保存到: {output_dir}")
        srt_entries = parse_srt(srt_path)
        if not srt_entries: self.log_message("[错误] SRT文件为空或格式不正确。"); return
        chunk_size = int(self.entry_chunk_size.get().strip() or 200)
        results = []
        total_chunks = (len(srt_entries) + chunk_size - 1) // chunk_size
        for i in range(0, len(srt_entries), chunk_size):
            chunk = srt_entries[i:i + chunk_size]
            chunk_index = i // chunk_size + 1
            self.update_status(f"正在处理第 {chunk_index}/{total_chunks} 块...")
            prompt = build_prompt_for_chunk(chunk, role_info_str, plot_summary_str)
            current_tokens = approximate_token_count(prompt)
            with self.token_lock:
                global_token_count += current_tokens
                current_total = global_token_count
            self.update_token_count(current_total)
            result = safe_generate_content_wrapper(api_mode, prompt)
            results.append(filter_extras(result or ""))

        final_text = "\n\n".join(results)
        final_entries = parse_model_output_as_srt(final_text)
        final_srt_content = produce_standard_srt(final_entries)

        base_name = os.path.basename(srt_path)
        out_filename = os.path.splitext(base_name)[0] + "-speaker.srt"
        out_path = os.path.join(output_dir, out_filename)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(final_srt_content)
        self.log_message(f"[完成] 输出文件: {os.path.basename(out_path)}")

    # [重写] 此函数实现“5次生成+1次仲裁”逻辑
    def run_single_audio_file(self, current_video_path, current_srt_path, prev_video_path, next_video_path,
                              prev_srt_path, next_srt_path, out_path, role_info_str, plot_summary_str, api_mode,
                              log_prefix=""):
        # ======================= 在这里添加代码 =======================
        # 新增代码：在PyCharm控制台打印单行刷新进度
        # flush=True 确保立即输出，\r 让光标回到行首，实现刷新效果
        print(f"正在处理: [{log_prefix}] {os.path.basename(current_video_path)}...", end="\r", flush=True)
        # ======================= 添加代码结束 =======================

        global global_token_count
        self.update_status(f"[{log_prefix}] 处理中: {os.path.basename(current_video_path)}")
        if api_mode != "Gemini":
            self.log_message(f"[{log_prefix}][错误] 此模式仅支持 'Gemini' API。");
            return

        temp_audio_files = []
        try:
            # 准备所有素材
            current_audio_path = extract_audio_from_video(current_video_path, self, log_prefix)
            if current_audio_path: temp_audio_files.append(current_audio_path)
            prev_audio_path = extract_audio_from_video(prev_video_path, self, log_prefix) if prev_video_path else None
            if prev_audio_path: temp_audio_files.append(prev_audio_path)
            next_audio_path = extract_audio_from_video(next_video_path, self, log_prefix) if next_video_path else None
            if next_audio_path: temp_audio_files.append(next_audio_path)

            if not current_audio_path:
                self.log_message(f"[{log_prefix}][错误] 无法提取核心音频文件，跳过任务。");
                return

            with open(current_srt_path, 'r', encoding='utf-8-sig') as f:
                current_srt_content = f.read()
            prev_srt_content = ""
            if prev_srt_path:
                with open(prev_srt_path, 'r', encoding='utf-8-sig') as f: prev_srt_content = f.read()
            next_srt_content = ""
            if next_srt_path:
                with open(next_srt_path, 'r', encoding='utf-8-sig') as f: next_srt_content = f.read()

            # 1. 并行生成5个候选版本
            self.log_message(f"[{log_prefix}] 开始并行生成5个候选版本...")
            generation_prompt = build_gemini_diarization_prompt(role_info_str, plot_summary_str, current_srt_content,
                                                                prev_srt_content, next_srt_content)
            audio_paths_for_api = [current_audio_path, prev_audio_path, next_audio_path]

            candidate_srts = []
            # 使用内部线程池进行10次调用
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as inner_executor:
                futures = {
                    inner_executor.submit(
                        safe_generate_content_wrapper,
                        api_mode,
                        generation_prompt,
                        audio_paths=audio_paths_for_api,
                        temperature=0.5,  # 使用较高温度以产生多样性
                        log_prefix=f"{log_prefix}[候选 {i + 1}]"
                    ): i for i in range(5)
                }
                for future in concurrent.futures.as_completed(futures):
                    try:
                        result = future.result()
                        candidate_srts.append(result)
                        self.log_message(f"[{log_prefix}][候选 {futures[future] + 1}] 生成成功。")
                    except Exception as exc:
                        self.log_message(f"[{log_prefix}][候选 {futures[future] + 1}] 生成失败: {exc}")

            # 2. 调用仲裁模型获取最终结果
            final_result_text = run_arbitrator_model(candidate_srts, current_srt_content, role_info_str,
                                                     plot_summary_str, log_prefix)

            if not final_result_text:
                self.log_message(f"[{log_prefix}][错误] 仲裁失败，任务终止。");
                return

            # 3. 格式化并保存最终结果
            filtered_text = filter_extras(final_result_text)
            final_entries = parse_model_output_as_srt(filtered_text)
            final_srt_content = produce_standard_srt(final_entries)

            with open(out_path, "w", encoding="utf-8") as f:
                f.write(final_srt_content)
            self.log_message(f"[{log_prefix}][成功] 最终版本已生成: {os.path.basename(out_path)}")

        finally:
            # 清理所有临时音频文件
            for f_path in temp_audio_files:
                try:
                    if f_path and os.path.exists(f_path): os.remove(f_path); self.log_message(
                        f"[{log_prefix}][清理] 已删除临时文件: {os.path.basename(f_path)}")
                except Exception as e:
                    self.log_message(f"[{log_prefix}][警告] 清理临时文件 {os.path.basename(f_path)} 失败: {e}")


# ==============================================================================
#                                   程序入口
# ==============================================================================
def main():
    # ... (此函数无变化) ...
    global global_gemini_client, app_instance
    root = tk.Tk()
    app = SpeakerTaggerApp(root)
    app_instance = app
    if HAS_VERTEX_AI:
        try:
            script_dir = os.path.dirname(sys.executable if getattr(sys, 'frozen', False) else os.path.abspath(__file__))
            json_cred_path = os.path.join(script_dir, VERTEX_JSON_CRED_FILENAME)
            if not os.path.isfile(json_cred_path):
                error_msg = f"在程序目录下找不到凭证文件: {VERTEX_JSON_CRED_FILENAME}\n\n请确保该文件存在且名称正确。"
                print(f"错误：{error_msg}");
                app_instance.show_error_on_main_thread("凭证错误", error_msg);
                global_gemini_client = None
            else:
                credentials = service_account.Credentials.from_service_account_file(json_cred_path)
                vertexai.init(project=VERTEX_PROJECT_ID, location=VERTEX_LOCATION, credentials=credentials)
                global_gemini_client = GenerativeModel("gemini-2.5-pro")
                print(f"Gemini (Vertex AI) 客户端已初始化。项目: {VERTEX_PROJECT_ID}, 位置: {VERTEX_LOCATION}")
                app_instance.log_message("[成功] Gemini 客户端已成功初始化。")
        except Exception as e:
            error_msg_init = f"Gemini (Vertex AI) 初始化失败:\n\n{e}"
            print(error_msg_init);
            traceback.print_exc();
            app_instance.show_error_on_main_thread("初始化失败", error_msg_init);
            global_gemini_client = None
    else:
        app_instance.log_message("[错误] 未找到 Vertex AI SDK，Gemini 功能不可用。")
    root.mainloop()


if __name__ == "__main__":
    main()