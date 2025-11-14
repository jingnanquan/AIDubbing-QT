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


class LLMAPI2():
    _instance = None

    @calculate_time
    def __init__(self):
        print("LLM API初始化中")
        self.setup()

    def setup(self):
        self.connect = RoleExtractAPI.getInstance()


    def merge_subtitle_with_index(self, target_subs: list, role_match_list: list) -> tuple:
        subtitle_text = ""
        i = 0
        for subtitle in target_subs:
            subtitle_text += f"""{subtitle["index"]} | {subtitle["start"]} --> {subtitle["end"]} | {subtitle["text"]} | {role_match_list[i]}\n"""
            i += 1

        prompt = f"""**任务说明**：
你是专业的字幕处理助手, 需要对字幕文件（编号, 起始时间, 结束时间, 内容, 角色）进行智能合并，生成配音专用字幕。请严格遵循以下规
**字幕输入示例**：
1 | 00:01:02,140 --> 00:01:03,789 | 嗯？| 艾伦
2 | 00:01:03,790 --> 00:01:05,001 | (轻笑)，你在忙吗？ | 艾伦
3 | 00:01:05,500 --> 00:01:07,200 | 你看看昨天文件的这个地方\n | 艾伦
4 | 00:01:07,201 --> 00:01:09,858 | 是不是有问题？ | 艾伦
5 | 00:01:10,200 --> 00:01:12,700 | ♪ 好的，我先看一下 | 莉娜
**处理要求**：
1. **合并条件**（需同时满足）：
   - 仅合并时间连续+同一角色说话的字幕
   - 单条字幕过短语义不完整（如缺少主谓宾）或合并后更通顺
   - 相邻字幕间隔阈值<0.4秒（以结束→开始时间计算，可酌情放宽限制）
   - 建议单次合并2~5条左右的字幕，组成完整的语义即可；合并后说话总时长不超过5s或总发音字符数不超过30
**输出格式规范和示例**：
```json
{{
  "1": [1, 2],
  "2": [3, 4],
  "3": [5],
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

            subtitle_indices = result_dict
            result_subtitles = {}
            '''
            json的key默认都是字符串
            '''
            for key, value in result_dict.items():
                result_subtitles[key] = {}
                result_subtitles[key]["text"] = ""
                result_subtitles[key]["start"] = target_subs[value[0] - 1]["start"]
                result_subtitles[key]["end"] = target_subs[value[-1] - 1]["end"]
                result_subtitles[key]["role"] = role_match_list[value[0] - 1]
                # result_subtitles[key]["index"] = value
                for index in value:
                    result_subtitles[key]["text"] += target_subs[index - 1]["text"]+"|"

        except Exception as e:
            print(f"字幕合并异常")
            self.connect.gemini_status = False
            raise e
        return result_subtitles, subtitle_indices

    def correct_punctuation(self, dubbing_subs: dict) -> dict:
        '''
        dubbing_subs='1': {'text': 'You actually dared to hit me!|', 'start': '00:00:04,933', 'end': '00:00:05,933', 'role': '江浩辰'}, '2': {'text': 'Sonny!|This is what you call. business entertainment "?|', 'start': '00:00:06,133', 'end': '00:00:08,400', 'role': '童颜'},
        '''
        prompt = f"""**任务说明**：
你是专业的字幕处理助手，需要对已合并的配音字幕进行标点符号修正，使其更符合配音演绎需求。请严格遵循以下规则：
**处理要求**：
1. **标点修正原则**：
   - 删除text中的|连接符号，并修正明显标点错误（如缺少句号、问号、感叹号等）
   - 优化语气词标点（如"啊"、"哦"、"嗯"等后应使用恰当标点），需结合上下文还原出疑问、惊讶等情绪
   - 不要修改文字内容，仅修正标点符，不要中英标点混用
   - 保持原有字幕结构（编号、时间、文本、角色），返回标准JSON格式
```
**修正后输出示例**：
```json
{{
  "1": {{
    "text": "你看看昨天文件的这个地方，是不是有问题？",
    "start": "00:01:05,500",
    "end": "00:01:09,858",
    "role": "艾伦"
  }},
  "2": {{
    "text": "好的，我先看一下。",
    "start": "00:01:10,200",
    "end": "00:01:12,700",
    "role": "莉娜"
  }}
}}
**待处理字幕如下**：
{dubbing_subs}
        """
        try:
            raise Exception("我不想调用llm了")
            response = self.connect.global_gemini_client.models.generate_content_stream(
                model="gemini-2.5-pro",
                contents=prompt
            )
            response_text = ""
            for chunk in response:
                print(chunk.text, end="")
                response_text += chunk.text

            # 清理响应文本，提取JSON部分
            raw_content = re.sub(r"```(?:json)?", "", response_text)
            raw_content = raw_content.replace("```", "")

            # 用正则搜索最外层的大括号
            match = re.search(r"\{.*\}", raw_content, re.DOTALL)
            if not match:
                raise Exception("未匹配到JSON格式，gemini服务端错误")

            raw_json = match.group(0)
            result_dict = json.loads(raw_json)
            print(result_dict)
            if len(result_dict.keys()) != len(dubbing_subs.keys()):
                raise Exception("字幕返回数量异常，gemini服务端错误")

            # 这边的key都是字符串，应该没问题
            dubbing_subs2 = dubbing_subs.copy()
            for i in dubbing_subs2.keys():
                dubbing_subs2[i]["text"] = result_dict[i]["text"]
            # 返回结果与输入格式保持一致
            return dubbing_subs2

        except Exception as e:
            print(f"标点修正异常: {e}")
            self.connect.gemini_status = False
            # 如果API调用失败，返回原始字幕

            dubbing_subs2 = dubbing_subs.copy()
            for i in dubbing_subs.keys():
                dubbing_subs2[i]["text"] = dubbing_subs2[i]["text"].replace("|", " ")
            return dubbing_subs2



    def check_self(self):
        self.connect.check_self()

    @classmethod
    def getInstance(cls)-> "LLMAPI2":
        if not cls._instance:
            cls._instance = LLMAPI2()
        cls._instance.check_self()
        return cls._instance
