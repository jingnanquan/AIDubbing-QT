import os
import re
import json
import time

# import vertexai
from google.auth.credentials import with_scopes_if_required
from google.genai.types import HttpOptions
# from vertexai.generative_models import GenerativeModel

from Service.ccTest import API_KEY_DEEPSEEK, API_G
from Service.generalUtils import calculate_time
from Service.generalUtils2 import decrypt_string



class RoleExtractAPI():
    # ------------------------------------------------------------------------------
    # 全局 Gemini Client (在 GUI 初始化阶段进行实例化)
    # ------------------------------------------------------------------------------
    # global_gemini_client = None
    # http_options = HttpOptions(timeout=40 * 1000)
    _instance = None

    @calculate_time
    def __init__(self):
        print("gemini and deepseek初始化中")
        self.setup()

    def setup(self, g_status=False, d_status=False):
        from openai import OpenAI
        from google import genai,auth
        from google.genai._base_url import set_default_base_urls
        set_default_base_urls('https://jingnanquan-cfll-gemini-64.deno.dev/', None)
        json_dict = json.loads(decrypt_string(API_G, "AIDubbing"))
        creds, project_id = auth.load_credentials_from_dict(json_dict)
        scoped_creds = with_scopes_if_required(
            creds, ["https://www.googleapis.com/auth/cloud-platform"]
        )

        if not g_status:
            print("==gemini==")
            # vertexai.init(project=project_id, location="us-central1", credentials=creds)
            # self.global_gemini_client = GenerativeModel("gemini-2.5-pro")
            self.global_gemini_client = genai.Client(vertexai=True, project=project_id, location="global", credentials=scoped_creds, http_options = HttpOptions(timeout=300 * 1000))  # 通过企业用户凭证
            # self.global_gemini_client = genai.Client(api_key = API_KEY_GEMINI, http_options = HttpOptions(timeout=300 * 1000))  # 通过中转服务器，调用gemini
        if not d_status:
            print("==deepseek==")
            # self.global_deepseek_client = OpenAI(
            #     api_key=decrypt_string(API_KEY_DEEPSEEK, "AIDubbing"),
            #     base_url="https://api.deepseek.com",
            # )

            self.global_deepseek_client = None
        self.gemini_status = True
        self.deepseek_status = True

    # ------------------------------------------------------------------------------
    # Deepseek 调用逻辑
    # ------------------------------------------------------------------------------
    def safe_generate_content_deepseek2(self, prompt, max_retries=1):
        """
        使用 Deepseek 的 REST API 进行调用（伪代码示例），
        需要安装 requests 库: pip install requests

        如果 Deepseek 的实际返回格式 / 参数名 / 接口地址 不同，
        请根据官方文档调整。
        """
        class DeepseekResponse:
            def __init__(self, text):
                self.text = text

        for attempt in range(1, max_retries + 1):
            try:
                response = self.global_deepseek_client.chat.completions.create(
                    model="deepseek-chat",
                    messages=[{"role": "user", "content": prompt}],
                    response_format={
                        'type': 'json_object'
                    }
                )
                print(json.loads(response.choices[0].message.content))

                return DeepseekResponse(response.choices[0].message.content)

            except Exception as e:
                print(f"[Deepseek] 第 {attempt} 次调用出错: {e}")
                if attempt == max_retries:
                    print("[Deepseek] 已达最大重试次数，抛出异常。")
                    self.deepseek_status = False
                    raise
                print("[Deepseek] 等待 5 秒后重试...")
                time.sleep(5)

        return None

    # ------------------------------------------------------------------------------
    # Gemini 调用逻辑
    # ------------------------------------------------------------------------------
    def safe_generate_content_gemini(self, prompt, max_retries=1, model_name=""):
        """
        Gemini 调用示例，每次失败后等待5秒重试。
        需要全局已有 client = genai.Client(...)。
        应该是不会走到return None的，
        """
        if model_name:
            for attempt in range(1, max_retries + 1):
                try:
                    # 使用全局 client
                    response = self.global_gemini_client.models.generate_content(model=model_name, contents=prompt )
                    return response
                except Exception as e:
                    print(f"[Gemini] 第 {attempt} 次调用API出错: {e}")
                    if attempt == max_retries:
                        print("[Gemini] 已达最大重试次数，抛出异常。")
                        self.gemini_status = False
                        raise
                    print("[Gemini] 等待 5 秒后重试...")
                    time.sleep(5)
        return None

    # ------------------------------------------------------------------------------
    # 通用包装：根据选择自动使用 Gemini 或 Deepseek
    # ------------------------------------------------------------------------------
    def safe_generate_content_wrapper(self, api_provider, prompt, max_retries=1, model_name="gemini-2.5-pro"):
        """
        - api_provider: 'Gemini' or 'Deepseek'
        - prompt: 要发送的提示词
        - max_retries: 失败重试次数
        - model_name: 仅对 Gemini 有效，默认 'gemini-2.0-pro-exp-02-05'
        """
        if api_provider == "Gemini":
            return self.safe_generate_content_gemini(prompt, max_retries, model_name)
        else:
            return self.safe_generate_content_deepseek2(prompt, max_retries)



    def extract_role_info(self, original_text, api_provider="", label_status=None):
        """
        步骤1：从字幕中提取需要文化翻译的专有名词。
        """
        # print(original_text)
        # chunks = split_into_chunks(original_text)
        # total_chunks = len(chunks)
        # print(chunks)
        # print(total_chunks)
        chunks = [original_text]
        total_chunks = 1
        # chunks = chunk_text(original_text, chunk_size=4000)
        # total_chunks = len(chunks)

        extraction_results = []
        result_dict = {}
        for idx, chunk in enumerate(chunks, start=1):
            status_text = f"步骤1：正在处理 {idx}/{total_chunks}..."
            print(status_text)
            if label_status:
                label_status.config(text=status_text)
                label_status.update()

            prompt = f"""你是一位专业的影视剧本分析助手。请根据提供的SRT字幕内容，完成以下任务：
                    1. **角色识别要求**：
                       - 通过对话上下文推断说话人身份
                       - 优先提取「姓氏+身份」格式（例：张医生、王秘书）
                       - 无明确姓氏时使用「身份+编号」（例：保镖1、记者2）
                       - 你要完全理解字幕对话的逻辑, 角色数量尽可能少
                       - 牢记：角色数量总数不超过6个
                       - 不要编造新角色，下文的角色很有可能在上文出现过
                       - 同一角色在不同语句中必须保持相同命名
                       - 不要犯低级错误，说出“角色A”这句话的一定不是角色A
                    2. **输出格式规范**：
                    ```json
                    {{
                      "字幕序号": "角色名称（使用中文）",
                      ...
                    }}
                    3. **示例输出**：
                    ```json
                    {{
                      "1": "张医生",
                      "2": "王秘书",
                      "3": "保镖1",
                      ...
                    }}
                    ```
                    以下为输入的字幕文本:
                    {chunk}
                    """

            try:
                print(prompt)
                response = self.safe_generate_content_wrapper(api_provider, prompt)
                if response is None or response.text is None:
                    print(f"⚠️ 第 {idx}/{total_chunks} 分块提取失败，跳过该分块")
                    continue

                response_text = response.text.strip()
                extraction_results.append(response_text)
                # 去除可能的 ```json 或 ``` 包裹
                raw_content = re.sub(r"```(?:json)?", "", response_text)
                raw_content = raw_content.replace("```", "")

                # 用正则搜索最外层的大括号
                match = re.search(r"\{.*\}", raw_content, re.DOTALL)
                if not match:
                    print("❌ 未匹配到JSON格式，跳过该批次")
                    # 这里为了演示，不会终止流程，只是跳过这一批
                    continue
                raw_json = match.group(0)
                batch_dict = json.loads(raw_json)
                result_dict.update(batch_dict)
                # print(result_dict)

            except Exception as e:
                print(f"⚠️ 第 {idx}/{total_chunks} 分块处理异常：{e}，跳过该分块")
                raise

            time.sleep(1)  # 避免速率过快

        # 后续写入该文件到日志中
        print(result_dict)
        return result_dict


    def extract_role_info_by_hint(self, original_text, hint_roles, api_provider="", label_status=None):
        """
        步骤1：从字幕中提取需要文化翻译的专有名词。
        """
        chunks = [original_text]
        total_chunks = 1

        extraction_results = []
        result_dict = {}
        for idx, chunk in enumerate(chunks, start=1):
            status_text = f"步骤1：正在处理 {idx}/{total_chunks}..."
            print(status_text)
            if label_status:
                label_status.config(text=status_text)
                label_status.update()

            prompt = f"""你是一位专业的影视剧本分析助手。请根据提供的SRT字幕内容和角色列表，完成以下任务：
                    1. **角色识别要求**：
                       - 将对话内容与角色列表中的角色名称进行匹配
                       - 深入理解对话上下文，确保精准匹配
                       - 角色列表中的名称是固定的，不可增改
                       - 不要犯低级错误，说出“角色A”这句话的一定不是角色A
                    2. **输出格式规范**：
                    ```json
                    {{
                      "字幕序号": "角色名称",
                      ...
                    }}
                    3. **示例输出**：
                    ```json
                    {{
                      "1": "张医生",
                      "2": "王秘书",
                      "3": "保镖1",
                      ...
                    }}
                    ```
                    4.接下来是角色列表:{hint_roles}
                    5.以下为输入的字幕内容:
                    {chunk}
                    """

            try:
                print(prompt)
                response = self.safe_generate_content_wrapper(api_provider, prompt)
                if response is None or response.text is None:
                    print(f"⚠️ 第 {idx}/{total_chunks} 分块提取失败，跳过该分块")
                    continue

                response_text = response.text.strip()
                extraction_results.append(response_text)
                # 去除可能的 ```json 或 ``` 包裹
                raw_content = re.sub(r"```(?:json)?", "", response_text)
                raw_content = raw_content.replace("```", "")

                # 用正则搜索最外层的大括号
                match = re.search(r"\{.*\}", raw_content, re.DOTALL)
                if not match:
                    print("❌ 未匹配到JSON格式，跳过该批次")
                    # 这里为了演示，不会终止流程，只是跳过这一批
                    continue
                raw_json = match.group(0)
                batch_dict = json.loads(raw_json)
                result_dict.update(batch_dict)
                # print(result_dict)

            except Exception as e:
                print(f"⚠️ 第 {idx}/{total_chunks} 分块处理异常：{e}，跳过该分块")
                raise

            time.sleep(1)  # 避免速率过快

        # 后续写入该文件到日志中
        print(result_dict)
        return result_dict

    def check_self(self):
        # self.gemini_status = False
        self.setup(self.gemini_status, self.deepseek_status)



    @classmethod
    def getInstance(cls)-> "RoleExtractAPI":
        if not cls._instance:
            cls._instance = RoleExtractAPI()
        cls._instance.check_self()
        return cls._instance
