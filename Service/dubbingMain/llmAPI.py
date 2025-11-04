import Config
import io
import re
import json
import time
import traceback

from pydub import AudioSegment

from Service.dubbingMain.roleExtractAPI import RoleExtractAPI
from Service.generalUtils import calculate_time


class StreamResponse:
    def __init__(self, text):
        self.text = text


class LLMAPI():
    _instance = None

    @calculate_time
    def __init__(self):
        print("LLM API初始化中")
        self.setup()

    def setup(self):
        self.connect = RoleExtractAPI.getInstance()


    def safe_generate_content_deepseek2(self, prompt, max_retries=1):
        class DeepseekResponse:
            def __init__(self, text):
                self.text = text

        for attempt in range(1, max_retries + 1):
            try:
                response = self.connect.global_deepseek_client.chat.completions.create(
                    model="deepseek-chat",
                    messages=[{"role": "user", "content": prompt}],
                    response_format={
                        'type': 'json_object'
                    },
                )
                print(json.loads(response.choices[0].message.content))

                return DeepseekResponse(response.choices[0].message.content)

            except Exception as e:
                print(f"[Deepseek] 第 {attempt} 次调用出错: {e}")
                if attempt == max_retries:
                    print("[Deepseek] 已达最大重试次数，抛出异常。")
                    self.connect.deepseek_status = False
                    raise
                print("[Deepseek] 等待 5 秒后重试...")
                time.sleep(5)

        return None

    # ------------------------------------------------------------------------------
    # Gemini 调用逻辑
    # ------------------------------------------------------------------------------
    def safe_generate_content_gemini(self, prompt, max_retries=1, stream = False, model_name=""):
        """
        Gemini 调用示例，每次失败后等待5秒重试。
        需要全局已有 client = genai.Client(...)。
        应该是不会走到return None的，
        """
        if model_name:
            for attempt in range(1, max_retries + 1):
                try:
                    if stream:
                        response = self.connect.global_gemini_client.models.generate_content_stream( model=model_name, contents=prompt)
                        result = StreamResponse("")
                        for chunk in response:
                            print(chunk.text, end="")
                            result.text+= chunk.text
                        print(result)
                        return result
                    else:
                        response = self.connect.global_gemini_client.models.generate_content(model=model_name, contents=prompt )
                        return response
                except Exception as e:
                    print(f"[Gemini] 第 {attempt} 次调用API出错: {e}")
                    if attempt == max_retries:
                        print("[Gemini] 已达最大重试次数，抛出异常。")
                        self.connect.gemini_status = False
                        raise
                    print("[Gemini] 等待 5 秒后重试...")
                    time.sleep(5)
        return None

    # ------------------------------------------------------------------------------
    # 通用包装：根据选择自动使用 Gemini 或 Deepseek
    # ------------------------------------------------------------------------------
    def safe_generate_content_wrapper(self, api_provider, prompt, max_retries=1, stream = False, model_name="gemini-2.5-pro"):
        if api_provider == "Gemini":
            return self.safe_generate_content_gemini(prompt, max_retries, stream=stream, model_name=model_name)
        else:
            return self.safe_generate_content_deepseek2(prompt, max_retries)

    '''
    以下两个函数的功能是合并字幕
    llm输出是带字幕的，这太长了，可能会导致json输出错误，最好的方式是只输出字幕的id。
    但是，我这个最初的设想就是去修正标点符号，如果标点符号不修正，那也没意义
    长期来看，可以分为两个函数，一个合并，一个修正标点符号
    '''
    def merge_subtitle(self, subtitle_text) -> dict:

        prompt = f"""**任务说明**：
你是一个专业的字幕处理助手, 你将处理字幕文件（包含编号, 起始时间, 结束时间, 内容, 角色），通过智能合并短句并优化文本生成配音专用字幕。请严格遵循以下规
**字幕输入示例**：
1 | 00:01:02,140 --> 00:01:03,789 | 嗯？| 艾伦
2 | 00:01:03,790 --> 00:01:05,001 | (轻笑) | 艾伦
3 | 00:01:05,500 --> 00:01:07,200 | 你看这个\n | 艾伦
4 | 00:01:07,201 --> 00:01:09,858 | 是不是有问题？ | 艾伦
5 | 00:01:10,200 --> 00:01:12,700 | ♪ 收到 | 莉娜
**处理要求**：
1. **合并条件**（需同时满足）：
   - 仅合并时间连续+同角色的字幕
   - 单条字幕过短语义不完整（如缺少主谓宾）或合并后更通顺
   - 相邻字幕间隔阈值<0.5秒（以结束→开始时间计算，特殊情况可放宽限制）
   *例外*：问号结尾、省略号等完整语气不强制
2. **文本处理**：
   - 删除 ♪ 换行符 (笑声) 等非发音特殊符号，(笑声转为哈哈等自然语气表达)
   - 根据语境添加/修正标点：逗号、分号分割；句号句；感叹号情绪；问号疑问；省略号、破折号表转折或长停顿
   - 不要中英标点混用
   - 合并时只修正或添加标点，不修改内容文本(text)和角色标签文本(role)，更不能翻译，否则这单你白干了
3. **时间轴规则**：
   - 新字幕时间 = 首个字幕开始时间→ 末个字幕结束时间
4. **一些小建议**：
   - 松弛的约束：如果合并，建议单次合并3条左右的字幕；合并后说话总时长不超过5s；总发音字符数不超过30
   - 松弛的约束不需要严格遵守，我相信你凭专业知识就能合并的很好
**输出格式**：
   -使用json格式输出
   ```json
    {{
      "字幕序号": {{"start":"起始时间", "end":"结束时间", "text":"优化后字幕内容", "role":"角色名称"}}
      ...
    }}
**输出示例**（基于输入示例）：
```json
    {{
      "1": {{"start":"00:01:02,140", "end":"00:01:05,001", "text":"嗯？哈哼！", "role":"艾伦"}}
      "2": {{"start":"00:01:05,500", "end":"00:01:07,200", "text":"你看这个是不是有问题？", "role":"艾伦"}}
      "3": {{"start":"00:01:10,200", "end":"00:01:12,700", "text":"收到。", "role":"莉娜"}}
      ...
    }}
```
**待处理字幕如下**：
{subtitle_text}
"""

        try:
            # print(prompt)
            response = self.connect.global_gemini_client.models.generate_content_stream(model="gemini-2.5-pro",
                                                                                        contents=prompt)
            response_text = ""
            for chunk in response:
                print(chunk.text, end="")
                response_text += chunk.text
            raw_content = re.sub(r"```(?:json)?", "", response_text)
            raw_content = raw_content.replace("```", "")
            # 用正则搜索最外层的大括号
            match = re.search(r"\{.*\}", raw_content, re.DOTALL)
            if not match:
                raise Exception("未匹配到JSON格式，gemini服务端错误")
            raw_json = match.group(0)
            result_dict = json.loads(raw_json)
            print(result_dict)

        except Exception as e:
            print(f"字幕合并异常")
            self.connect.gemini_status = False
            raise e
        return result_dict

    def merge_subtitle_with_index(self, subtitle_text) -> dict:

        prompt = f"""**任务说明**：
你是专业的字幕处理助手, 需要对字幕文件（编号, 起始时间, 结束时间, 内容, 角色）进行智能合并与标点修正，生成配音专用字幕。请严格遵循以下规
**字幕输入示例**：
1 | 00:01:02,140 --> 00:01:03,789 | 嗯？| 艾伦
2 | 00:01:03,790 --> 00:01:05,001 | (轻笑) | 艾伦
3 | 00:01:05,500 --> 00:01:07,200 | 你看这个\n | 艾伦
4 | 00:01:07,201 --> 00:01:09,858 | 是不是有问题？ | 艾伦
5 | 00:01:10,200 --> 00:01:12,700 | ♪ 收到 | 莉娜
**处理要求**：
1. **合并条件**（需同时满足）：
   - 仅合并时间连续+同角色的字幕
   - 单条字幕过短语义不完整（如缺少主谓宾）或合并后更通顺
   - 相邻字幕间隔阈值<0.5秒（以结束→开始时间计算，可酌情放宽限制）
2. **文本处理**：
   - 删除 ♪ 换行符 (笑声) 等非发音特殊符号，(笑声转为哈哈等自然语气表达)
   - 根据语境添加/修正标点：逗号、分号分割；句号句；感叹号情绪；问号疑问；省略号、破折号表转折或长停顿
   - 不要中英标点混用
   - 合并时只修正或添加标点，不修改内容文本(text)和角色标签文本(role)，更不能翻译，否则这单你白干了
3. **时间轴规则**：
   - 新字幕时间 = 首个字幕开始时间→ 末个字幕结束时间
4. **一些小建议**：
   - 松弛的约束：如果需要合并，建议单次合并2~5条左右的字幕；合并后说话总时长不超过5s或总发音字符数不超过30
   - 松弛的约束不需要严格遵守，我相信你凭专业知识就能合并的很好
**输出格式**：
   -使用json格式输出
   ```json
    {{
      "字幕序号": {{"start":"起始时间", "end":"结束时间", "text":"优化后字幕内容", "role":"角色名称","map":"原字幕序号"}}
      ...
    }}
**输出示例**（基于输入示例）：
```json
    {{
      "1": {{"start":"00:01:02,140", "end":"00:01:05,001", "text":"嗯？哈哼！", "role":"艾伦","map":[1,2]}}
      "2": {{"start":"00:01:05,500", "end":"00:01:07,200", "text":"你看这个是不是有问题？", "role":"艾伦","map":[3,4]}}
      "3": {{"start":"00:01:10,200", "end":"00:01:12,700", "text":"收到。", "role":"莉娜","map":[5]}}
      ...
    }}
```
**待处理字幕如下**：
{subtitle_text}
"""
        try:
            response = self.connect.global_gemini_client.models.generate_content_stream(model="gemini-2.5-pro",
                                                                                        contents=prompt)
            response_text = ""
            for chunk in response:
                print(chunk.text, end="")
                response_text += chunk.text
            raw_content = re.sub(r"```(?:json)?", "", response_text)
            raw_content = raw_content.replace("```", "")
            # 用正则搜索最外层的大括号
            match = re.search(r"\{.*\}", raw_content, re.DOTALL)
            if not match:
                raise Exception("未匹配到JSON格式，gemini服务端错误")
            raw_json = match.group(0)
            result_dict = json.loads(raw_json)
            print(result_dict)
        except Exception as e:
            print(f"字幕合并异常")
            self.connect.gemini_status = False
            raise e
        return result_dict




    def extract_audio_to_mp3_bytes(self, video_path):
        # 加载视频文件（pydub 依赖 ffmpeg）
        audio = AudioSegment.from_file(video_path)

        # 将音频转换为 MP3 字节流
        mp3_bytes = io.BytesIO()
        audio.export(mp3_bytes, format="mp3")
        # 获取字节数据
        mp3_bytes.seek(0)
        return mp3_bytes.read()

    def video_summary(self, subtitle_text, video_path: str, role_names=""):
        """
        步骤1：从字幕中提取需要文化翻译的专有名词。
        """

        role_name_hint = ""
        role_name_title = ""
        if role_names:
            role_name_hint = f"\n  - 主角名称严格参考以下信息：{role_names}\n  -注意！信息中不包含配角信息，配角称呼你需要自主命名"
            role_name_title = "、【主角信息】"

        result = ""
        status_text = f"步骤1：正在提取视频摘要"
        print(status_text)
        prompt = f"""你是一名专业音频后期专家和剧本监制，需对提供的【音频】{role_name_title}进行多维度情节摘要
**你需要严格遵循以下步骤**：
1.仔细聆听提供的【音频文件】，建立对角色声音的认知。
2.根据音频对话内容和角色声纹，全面建模场景剧情、角色关系和对话流
3.对音频剧情进行总结，按照场景+情节的方式进行输出

**具体输出要求如下**：
1.按时间线划分场景，标注场景切换节点（如`【场景1】：医院`）
2.角色+情节（某些角色做了什么，在讨论什么）
3.角色名需要包含至少一个信息量（性别、职业、年龄、人物关系等），如：小女孩、男警察、女孩妈妈、男主情敌
4.不要输出无关信息（比如：我已了解...;你是否需要我进一步...）

**其他注意事项**：
- 准确提取同一人物在不同场景中的活动{role_name_hint}

**输出示例**：
【场景1】警局
情节：男警察与女警察讨论连环杀人案，男警察认为女警察与案件嫌疑人有过接触，不宜参与此案
【场景2】酒吧-回忆
情节：男青年搭讪女警察，女警察凭借嗅觉决定接受并深入调查
"""

        try:
            # print(prompt)
            audio_bytes = self.extract_audio_to_mp3_bytes(video_path)
            from google.genai import types
            response = self.connect.global_gemini_client.models.generate_content_stream \
                (model="gemini-2.5-pro",
                 contents=[prompt, types.Part.from_bytes(
                     data=audio_bytes,
                     mime_type='audio/mp3',
                 )])
            response_text = ""
            for chunk in response:
                print(chunk.text, end="")
                response_text += chunk.text
            result = response_text
        except Exception as e:
            print(f"视频摘要失败：{e}")
            traceback.print_exc()
            self.connect.gemini_status = False
            raise e

        return result


    def merge_subtitle_with_audio(self, subtitle_text, video_path: str):
            """
            步骤1：从字幕中提取需要文化翻译的专有名词。
            """
            result = []
            status_text = f"步骤1：正在合并相近字幕"
            print(status_text)
            prompt = f"""你是专业的字幕处理助手, 需要根据字幕对应的【音频文件】对【字幕内容】进行智能合并与标点修正，生成配音专用字幕。
**你需要严格遵循以下步骤**：
1.仔细聆听提供的【音频文件】，建立对角色声音的认知。
2.根据音频对话内容和角色声纹，全面建模场景剧情、角色关系和对话流
3.将音频内容、音频角色声纹与字幕内容对应起来

**具体输出要求如下**：
1.你要完成的是文本转折点标记任务（即对于一段对话，准确分割出每次切换角色的位置）
2.根据音频的内容和字幕上下文关系（连续、转折），找出同一角色连续的说话内容
3.对于同一角色连续的字幕，合并为一个字幕块
4.新字幕时间 = 首个字幕开始时间→ 末个字幕结束时间
5.对输出结果中的index重新从1开始编号
6.仅输出json字符串，不要输出其他无关信息

**输出格式规范**：
```json
{{
  "index":{{
            "index": index,
            "start": start,
            "end": end,
            "text": text,
            }}
  ...
}}
```

**字幕内容如下**
{subtitle_text}
"""

            try:
                # print(prompt)
                audio_bytes = self.extract_audio_to_mp3_bytes(video_path)
                from google.genai import types
                response = self.connect.global_gemini_client.models.generate_content_stream \
                    (model="gemini-2.5-pro",
                     contents=[prompt, types.Part.from_bytes(
                         data=audio_bytes,
                         mime_type='audio/mp3',
                     )])
                response_text = ""
                for chunk in response:
                    print(chunk.text, end="")
                    response_text += chunk.text
                response_text = response_text.strip()
                # 去除可能的 ```json 或 ``` 包裹
                raw_content = re.sub(r"```(?:json)?", "", response_text)
                raw_content = raw_content.replace("```", "")

                # 用正则搜索最外层的大括号
                match = re.search(r"\{.*\}", raw_content, re.DOTALL)
                if not match:
                    print("❌ 未匹配到JSON格式，跳过该批次")
                    return result
                raw_json = match.group(0)
                result_dict = json.loads(raw_json)
                result = list(result_dict.values())

            except Exception as e:
                print(f"视频摘要失败：{e}")
                traceback.print_exc()
                self.connect.gemini_status = False
                raise e

            return result



    def video_summary_batch(self, subtitle_text, video_path: str, role_names=""):
            """
            步骤1：从字幕中提取需要文化翻译的专有名词。
            """

            role_name_hint = ""
            role_name_title = ""
            if role_names:
                role_name_hint = f"\n-如果台词明显符合某个已知角色信息（原名或别称）如：{role_names}，则写该角色名字；否则你需要自己为配角标注姓名 \n"
                role_name_title = "、【主角信息】"

            result = ""
            status_text = f"步骤1：正在提取视频摘要"
            print(status_text)
            prompt = f"""你是一名专业音频后期专家和剧本监制，需对提供的【音频】{role_name_title}进行多维度情节摘要
    **你需要严格遵循以下步骤**：
    1.仔细聆听提供的【音频文件】，建立对角色声音的认知。
    2.根据音频对话内容和角色声纹，全面建模场景剧情、角色关系和对话流
    3.对音频剧情进行总结，按照场景+情节的方式进行输出

    **具体输出要求如下**：
    1.按时间线划分场景，标注场景切换节点（如`【场景1】：医院`）
    2.角色+情节（某些角色做了什么，在讨论什么）
    3.主角名称需要严格参照角色信息表
    4.角色信息表为整部剧的主角，这一集中只涉及到其中一部分角色，你需要根据情节进行判断
    4.不要输出无关信息（比如：我已了解...;你是否需要我进一步...）

    **其他注意事项**：
    - 非主要人物的配角称呼你需要自主命名（如：卖花女、男路人、女闺蜜1、男司机等）
    - 准确提取同一人物在不同场景中的活动{role_name_hint}

    **输出示例**：
    【场景1】警局
    情节：男警察与女警察讨论连环杀人案，男警察认为女警察与案件嫌疑人有过接触，不宜参与此案
    【场景2】酒吧-回忆
    情节：男青年搭讪女警察，女警察凭借嗅觉决定接受并深入调查
    """

            try:
                # print(prompt)
                audio_bytes = self.extract_audio_to_mp3_bytes(video_path)
                from google.genai import types
                response = self.connect.global_gemini_client.models.generate_content_stream \
                    (model="gemini-2.5-pro",
                     contents=[prompt, types.Part.from_bytes(
                         data=audio_bytes,
                         mime_type='audio/mp3',
                     )])
                response_text = ""
                for chunk in response:
                    print(chunk.text, end="")
                    response_text += chunk.text
                result = response_text
            except Exception as e:
                print(f"视频摘要失败：{e}")
                traceback.print_exc()
                self.connect.gemini_status = False
                raise e

            return result

    def extract_role_info_by_hint(self, subtitle_text: str, plot_summary: str, role_names: str)-> dict:

        role_name_hint = ""
        role_name_title = ""
        if role_names:
            role_name_hint = f"\n  - 主要角色信息：{role_names}\n  - 某些配角可能不在主角信息中，你需要准确标注出该角色，并合理命名（如：'士兵甲' '随从乙' '路人丙'）\n"
            role_name_title = "、【主角信息】"

        result_dict = {}
        prompt = f"""你是一位专业的影视剧本分析助手。请根据提供的【SRT字幕内容】、【视频剧情概要】{role_name_title}，完成以下任务：
1. **角色识别要求**：
   - 将字幕对话内容与角色列表和剧情概要中的角色名称进行匹配
   - 深入理解对话上下文，全面理解场景剧情、场景转换逻辑、角色关系，确保精准匹配
   - 角色列表中的名称是固定的，不可修改
   - 注意人物对话过程中的称谓，其中的职务、姓氏、性别能够帮你更准确的匹配
   - 输出数量与字幕条数必须一致，某些开头结尾的字幕仅为提示信息，角色使用"旁白"替代
2. **输出格式规范**：
```json
{{
  "字幕序号": "角色名称",
  ...
}}
```
3. **示例输出**：
```json
{{
  "1": "张医生",
  "2": "王秘书",
  "3": "保镖1",
  ...
}}
```
4.**其他注意事项**：
   - 根据剧情概要深刻理解字幕内容的上下文关系{role_name_hint}
5.**剧情情节概要如下**：
{plot_summary}
6.**字幕内容如下**:
{subtitle_text}
"""
        try:
            # print(prompt)
            response = self.connect.global_gemini_client.models.generate_content_stream(model="gemini-2.5-pro", contents=prompt)
            response_text = ""
            for chunk in response:
                print(chunk.text, end="")
                response_text += chunk.text
            # print(response_text)
            raw_content = re.sub(r"```(?:json)?", "", response_text)
            raw_content = raw_content.replace("```", "")
            # 用正则搜索最外层的大括号
            match = re.search(r"\{.*\}", raw_content, re.DOTALL)
            if not match:
                raise Exception("未匹配到JSON格式，gemini服务端错误")
            raw_json = match.group(0)
            result_dict = json.loads(raw_json)

        except Exception as e:
            print(f"角色抽取异常")
            self.connect.gemini_status = False
            raise e
        return result_dict

    def compress_subtitles(self, texts: list[str], max_lengths: list[int]) -> list[str]:
        """
        模拟 Gemini API 调用，请根据你自己的 Gemini API 调用方式替换此函数
        输入为字幕列表 + 每条字幕的字符上限
        输出为压缩后的字幕列表
        """
        # 用 prompt 拼接
        prompts = []
        data = [{"text": text, "max_length": max_length} for text, max_length in zip(texts, max_lengths)]

        prompt = f"""你是一位专业的配音导演和字幕编辑，擅长编辑和优化冗长的字幕，从而确保配音与最终视频的质量，你的专长在于巧妙地略微缩短字幕，同时保持原有的意思和结构不变。
**包括但不限于以下几种优化方式**
1.省略不必要的修饰语或代词
2.将长词语用短词语替代
3.调整句子语序
如："Can you describe in detail your experience from yesterday?" --> "Can you describe yesterday's experience?" ; "How could you do such an outrageous thing?" --> "How could you do this?"

**输出示例**
```json
{{
  "subtitle_list": ["Please explain thought process!","We need to analyze this problem."],
}}
```
**输入格式及注意事项**
"[{{"text": 字幕1, "max_length": 18}},{{"text": 字幕2, "max_length": 10}}]"
1.text为待调整的冗长的字幕，调整前后使用的语言必须相同
2.max_length为调整预期，即调整后字幕的最大字符数
3.你的输出最好比max_length短，不要紧贴着上界
4.只返回一个json字符串，不要返回其他内容

**需要优化调整的字幕如下**
{data}
"""
        try:
            # print(prompt)
            response = self.connect.global_gemini_client.models.generate_content_stream(model="gemini-2.5-pro", contents=prompt)
            response_text = ""
            for chunk in response:
                print(chunk.text, end="")
                response_text += chunk.text
            # print(response_text)
            raw_content = re.sub(r"```(?:json)?", "", response_text)
            raw_content = raw_content.replace("```", "")
            # 用正则搜索最外层的大括号
            match = re.search(r"\{.*\}", raw_content, re.DOTALL)
            if not match:
                raise Exception("未匹配到JSON格式，gemini服务端错误")
            raw_json = match.group(0)
            result_dict = json.loads(raw_json)
            # print(raw_content)
            # print(result_dict)

        except Exception as e:
            print(f"字幕调整异常")
            self.connect.gemini_status = False
            raise e
        return result_dict["subtitle_list"]

    
    def speaker_diarization(self, video_path: str, api_provider="", label_status=None):
            prompt = f"""你是一名专业的音频分析专家，能从指定音频中进行asr，提取出对话内容。并且你最厉害的点在于能通过声纹进行聚类区分不同的说话人，能够做到Which speaker(s) spoke when?，
在面对重叠语音时，也能通过精细的检测确定某一片时间范围内是哪几个说话人在说话。
接下来你需要认真分析音频，返回说话人日志，格式如下：
[{{"start": 0:0:0,100, "end": 0:0:2,232, "speaker": "张三", "text":"你今天吃了吗"}}, {{"start": 0:0:3,156, "end": 0:0:8,345, "speaker": "李四", "text":"今天特地自己烹饪，美美饱餐一顿"}}]
"""

            try:
                print(prompt)
                audio_bytes = self.extract_audio_to_mp3_bytes(video_path)
                from google.genai import types
                response = self.connect.global_gemini_client.models.generate_content_stream\
                    (model="gemini-2.5-pro",
                     contents=[prompt, types.Part.from_bytes(
                      data=audio_bytes,
                      mime_type='audio/mp3',
                    )])
                response_text = ""
                for chunk in response:
                    print(chunk.text, end="")
                    response_text += chunk.text
                result = response_text
            except Exception as e:
                print(f"⚠️llm处理异常：{e}")
                self.connect.gemini_status = False
                raise
            time.sleep(1)  # 避免速率过快

            # 后续写入该文件到日志中
            return result

    def translate_subtitle_with_audio(self, subtitle_text, video_path: str, language: str = ""):
        """
        步骤1：从字幕中提取需要文化翻译的专有名词。
        """
        result = []
        language_text = ""
        if language:
            language_text = f",音频语言为{language}"

        status_text = f"步骤1：正在翻译字幕{language_text}"
        print(status_text)
        prompt = f"""你是专业的字幕处理助手, 需要根据字幕对应的【音频文件】对【待翻译字幕文件】对该字幕进行翻译{language_text}。
**字幕输入示例**：
**你需要严格遵循以下步骤**：
1.仔细聆听提供的【音频文件】，提取音频中的字幕对话内容。
2.初步对待翻译字幕的每条字幕进行文本翻译，翻译为与音频文件语言相同的字幕
3.结合音频字幕对话内容修正初步翻译的内容。
**注意以下要求**：
1.专业词汇、俚语、人物姓名、地点等需要结合音频内容和上下文
2.文本翻译后的主谓宾顺序需要与对应的音频内容保持一致
**输出格式规范**：
```json
{{
  "index":{{
            "index": index,
            "start": start,
            "end": end,
            "text": text,
            }}
  ...
}}
```
**待翻译字幕文件如下**
{subtitle_text}
    """

        try:
            # print(prompt)
            audio_bytes = self.extract_audio_to_mp3_bytes(video_path)
            from google.genai import types
            response = self.connect.global_gemini_client.models.generate_content_stream \
                (model="gemini-2.5-pro",
                 contents=[prompt, types.Part.from_bytes(
                     data=audio_bytes,
                     mime_type='audio/mp3',
                 )])
            response_text = ""
            for chunk in response:
                print(chunk.text, end="")
                response_text += chunk.text
            response_text = response_text.strip()
            # 去除可能的 ```json 或 ``` 包裹
            raw_content = re.sub(r"```(?:json)?", "", response_text)
            raw_content = raw_content.replace("```", "")

            # 用正则搜索最外层的大括号
            match = re.search(r"\{.*\}", raw_content, re.DOTALL)
            if not match:
                print("❌ 未匹配到JSON格式，跳过该批次")
                return result
            raw_json = match.group(0)
            result_dict = json.loads(raw_json)
            result = list(result_dict.values())

        except Exception as e:
            print(f"视频摘要失败：{e}")
            traceback.print_exc()
            self.connect.gemini_status = False
            raise e

        return result

    def merge_subtitle_with_audio_2(self, subtitle_text, video_path: str, language: str = ""):
            """
            步骤1：从字幕中提取需要文化翻译的专有名词。
            """
            result = []
            language_text = ""
            if language:
                language_text = f",音频语言为{language}"

            prompt = f"""你是专业的字幕处理助手, 需要根据字幕对应的【音频文件】对【字幕内容】进行智能合并与标点修正，生成配音专用字幕。
**你需要严格遵循以下步骤**：
1.仔细聆听提供的【音频文件】，建立对角色声音的认知{language_text}。
2.根据音频对话内容和角色声纹，全面建模场景剧情、角色关系和对话流
3.将音频内容、音频角色声纹与字幕内容对应起来

**具体输出要求如下**：
1.你要完成的是文本转折点标记任务（即对于一段对话，准确分割出每次切换角色的位置）
2.根据音频的内容和字幕上下文关系（连续、转折），找出同一角色连续的说话内容
3.对于同一角色连续的字幕，假设为a,b,c，只需合并为[id_a, id_b, id_c]
4.注意输出结果和输入字幕的编号都从1开始

**输出格式规范和示例**：
```json
{{
  "1": [1, 2, 3],
  "2": [4, 5],
  "3": [6],
  "4": [7, 8, 9],
  ...
}}
```

**字幕内容如下**
{subtitle_text}
    """

            try:
                # print(prompt)
                audio_bytes = self.extract_audio_to_mp3_bytes(video_path)
                from google.genai import types
                response = self.connect.global_gemini_client.models.generate_content_stream \
                    (model="gemini-2.5-pro",
                     contents=[prompt, types.Part.from_bytes(
                         data=audio_bytes,
                         mime_type='audio/mp3',
                     )])
                response_text = ""
                for chunk in response:
                    print(chunk.text, end="")
                    response_text += chunk.text
                response_text = response_text.strip()
                # 去除可能的 ```json 或 ``` 包裹
                raw_content = re.sub(r"```(?:json)?", "", response_text)
                raw_content = raw_content.replace("```", "")

                # 用正则搜索最外层的大括号
                match = re.search(r"\{.*\}", raw_content, re.DOTALL)
                if not match:
                    print("❌ 未匹配到JSON格式，跳过该批次")
                    return result
                raw_json = match.group(0)
                result_dict = json.loads(raw_json)
                result = list(result_dict.values())  # 我要返回跟原本字幕的对应关系，这样1是得到新的字幕列表，二是做矫正时需要返还到原本的字幕处

            except Exception as e:
                print(f"视频摘要失败：{e}")
                traceback.print_exc()
                self.connect.gemini_status = False
                raise e

            return result

    def match_role_by_hint(self, subtitle_text: str, plot_summary: str, role_names: str, video_path: str, language: str = "") -> dict:

        result_dict = {}
        language_text = ""
        if language:
            language_text = f",音频语言为{language}"
        prompt = f"""你是一位专业的影视剧本分析助手。请根据提供的【对话剧本】、【视频音频文件】、【主角信息】，完成字幕角色匹配任务：
    1. **你需要严格遵循以下步骤**：
       - 仔细聆听提供的【音频文件】，建立剧情的理解和对角色声音的认知{language_text}。
       - 根据音频对话内容和角色声纹，全面建模场景剧情、角色关系和对话流
       - 率先从主角信息中找出参与该字幕对话的主角
       - 将字幕中的每条对话与列出的主角名称进行匹配
       - 部分对话由配角参与，需要根据上下文判断其角色身份，并合理命名为'士兵甲' '随从甲' '路人甲' 等
       - 你需要深入理解对话上下文，确保精准匹配
    2. **输出格式规范**：
    ```json
    {{
      "字幕序号": "角色名称",
      ...
    }}
    ```
    3. **示例输出**：
    ```json
    {{
      "1": "张医生",
      "2": "王秘书",
      "3": "保镖1",
      ...
    }}
    ```
    4.**主角信息如下**：
    {role_names}
    5.**字幕内容如下**:
    {subtitle_text}
    """
        try:
            audio_bytes = self.extract_audio_to_mp3_bytes(video_path)
            from google.genai import types
            # print(prompt)
            # response = self.connect.global_gemini_client.models.generate_content_stream(model="gemini-2.5-pro",
            #                                                                             contents=prompt)
            response = self.connect.global_gemini_client.models.generate_content_stream \
                (model="gemini-2.5-pro",
                 contents=[prompt, types.Part.from_bytes(
                     data=audio_bytes,
                     mime_type='audio/mp3',
                 )])
            response_text = ""
            for chunk in response:
                print(chunk.text, end="")
                response_text += chunk.text
            # print(response_text)
            raw_content = re.sub(r"```(?:json)?", "", response_text)
            raw_content = raw_content.replace("```", "")
            # 用正则搜索最外层的大括号
            match = re.search(r"\{.*\}", raw_content, re.DOTALL)
            if not match:
                raise Exception("未匹配到JSON格式，gemini服务端错误")
            raw_json = match.group(0)
            result_dict = json.loads(raw_json)

        except Exception as e:
            print(f"角色抽取异常")
            self.connect.gemini_status = False
            raise e
        return result_dict


    def arbitrator_roles(self, subtitle_text: str, plot_summary: str, role_names: str, video_path: str, language: str = "") -> dict:

        result_dict = {}
        language_text = ""
        if language:
            language_text = f",音频语言为{language}"
        prompt = f"""你是一位经验丰富的总编辑和剧本监制，你的任务是从由AI标注角色SRT字幕中，找出角色标注错误，并修正成最终版本：
    1. **你需要严格遵循以下步骤**：
       - 我们会提供【音频文件】，【待校验字幕文件】，【主角信息】{language_text}。
       - 仔细聆听提供的【音频文件】，建立剧情的理解和对角色声音的认知。
       - 仔细阅读标注的【字幕文件】，逐行阅读对话内容，并于音频中相应角色比对。
       - 找出上下文对话中出现矛盾和标注错误的角色行，将剧情的前后一致性、连贯性和角色的身份作为判断标准。
       - 你需要站在全局视角，审视未出现在字幕中的主角信息中的其他主角是否与已标注的角色产生混淆。
       - 基于你的判断，生成一个全新的、完整的字幕角色表。
    2 **注意事项**
       - 角色男女声出现标注错误是非常严重的，你必须非常仔细。
       - 不要为了纠错而修改，如果没有错误，角色表保持原样（必须仔细核对）。
       - 对每一块字幕都要考虑上文和下文的角色是否冲突。
       - 确保输出的角色表与字幕序号一一对应。
       - 主角信息参考：{role_names}
       - 对于配角错误的字幕，你可以增改配角的名称。
    3. **输出格式规范**：
    ```json
    {{
      "字幕序号": "角色名称",
      ...
    }}
    ```
    4. **示例输出**：
    ```json
    {{
      "1": "张医生",
      "2": "王秘书",
      "3": "保镖1",
      ...
    }}
    ```
    5.**待校验的字幕内容如下**:
    {subtitle_text}
    """
        try:
            audio_bytes = self.extract_audio_to_mp3_bytes(video_path)
            from google.genai import types
            # print(prompt)
            # response = self.connect.global_gemini_client.models.generate_content_stream(model="gemini-2.5-pro",
            #                                                                             contents=prompt)
            response = self.connect.global_gemini_client.models.generate_content_stream \
                (model="gemini-2.5-pro",
                 contents=[prompt, types.Part.from_bytes(
                     data=audio_bytes,
                     mime_type='audio/mp3',
                 )])
            response_text = ""
            for chunk in response:
                print(chunk.text, end="")
                response_text += chunk.text
            # print(response_text)
            raw_content = re.sub(r"```(?:json)?", "", response_text)
            raw_content = raw_content.replace("```", "")
            # 用正则搜索最外层的大括号
            match = re.search(r"\{.*\}", raw_content, re.DOTALL)
            if not match:
                raise Exception("未匹配到JSON格式，gemini服务端错误")
            raw_json = match.group(0)
            result_dict = json.loads(raw_json)

        except Exception as e:
            print(f"角色抽取异常")
            self.connect.gemini_status = False
            raise e
        return result_dict


    def check_self(self):
        self.connect.check_self()

    @classmethod
    def getInstance(cls)-> "LLMAPI":
        if not cls._instance:
            cls._instance = LLMAPI()
        cls._instance.check_self()
        return cls._instance

if __name__ == '__main__':
    api = LLMAPI.getInstance()
    api.speaker_diarization("E:\\offer\\AI配音web版\\AIDubbing-QT-main\\服务器保卫战.mp3")


