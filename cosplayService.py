import json
import os
import sys
import base64
import argparse
from typing import Optional, Dict, Any
from google import genai
from google.genai import types
import mimetypes

from Service.ccTest import API_G
from Service.generalUtils2 import decrypt_string


# from Service.dubbingMain.roleExtractAPI import RoleExtractAPI

# 检查API_KEY环境变量
# if not os.environ.get("API_KEY"):
#     raise EnvironmentError("API_KEY environment variable not set")

# 初始化AI客户端
# ai = genai.Client(api_key=os.environ.get("API_KEY"))
# ai = RoleExtractAPI.getInstance().global_gemini_client


def create_prompt(character: str) -> str:
    """创建不带参考图的提示词"""
    return f"""
**核心指令：严禁替换照片中人物的脸。** 必须在原有人物面部特征的基础上进行修改。

请将照片中的人物，通过数字艺术手法，Cosplay 成动漫角色："{character}"。最终成品应为一张**超高画质、细节丰富、风格逼真的专业级 Cosplay 写实照片**。

**改造细则：**

1.  **面部与妆容 (最重要！)**:
    *   **保留五官：** **绝对保留**照片中人物本身的核心面部特征，包括脸型、五官比例、鼻子和嘴巴的形状。
    *   **妆容再造：** 在此基础上，为他们画上"{character}"的标志性妆容。重点是眼妆，请精心再现角色的眼线、眼影风格，并改变瞳色以模拟美瞳效果。
    *   **特殊标记**: 如果角色有特殊的面部标记（如咒纹、胡须、疤痕），也请作为妆容的一部分添加上去。
    *   **严禁换脸：** 再次强调，你是一位虚拟化妆师，不是换脸师。

2.  **发型与服装**:
    *   将发型和发色完全改变，以精准匹配"{character}"的造型。
    *   将衣物完全替换为"{character}"的标志性服装、盔甲或配饰。

3.  **画质与融合**:
    *   **风格：** 追求**照片真实感 (photorealistic)**，避免产生卡通或绘画感。
    *   **光影融合：** 所有新元素（妆容、发型、服装）都需要与原图的光线、阴影、人物姿势和体型自然地融合，达到无缝效果。
    *   **背景：** **保持原始背景不变。**
    *   **输出质量：** 成品图片要求**高分辨率、细节清晰、无不自然的模糊或伪影**。
"""


def create_prompt_with_reference_image(character: str) -> str:
    """创建带参考图的提示词"""
    return f"""
**最高优先级指令：绝对禁止替换第一张（用户）照片中的人脸！** 必须在原有人物面部特征的基础上进行修改。

**任务目标：** 将第一张照片中的人物 Cosplay 成动漫角色"{character}"，并严格参考第二张图片中的角色造型。最终成品应为一张**超高画质、细节丰富、风格逼真的专业级 Cosplay 写实照片**。

**核心原则：**

*   **保留原始场景：** **必须完整保留**第一张照片的**背景、人物姿势、身体形态和光影**。
*   **参考图作用：** 第二张图片**仅作为**"{character}"的**服装、发型、妆容**的视觉参考蓝本。

**详细执行步骤：**

1.  **面部与妆容 (最重要！):**
    *   **保留五官：** 从第一张照片中**绝对保留**人物的核心面部特征，包括脸型、五官比例、鼻子和嘴巴的形状。
    *   **妆容参考：** 参考第二张图片，为用户画上"{character}"的标志性妆容。重点是眼妆，请精心再现角色的眼线、眼影风格，并改变瞳色以模拟美瞳效果。
    *   **特殊标记**: 如果参考图中的角色有特殊的面部标记（如咒纹、胡须、疤痕），也请作为妆容的一部分添加上去。
    *   **严禁换脸：** 再次强调，你是一位虚拟化妆师，不是换脸师。最终效果必须清晰地看出是同一个人（用户）。

2.  **发型与服装改造:**
    *   **造型参考：** 严格参考第二张图片，将用户的发型、发色和衣物**完全替换**为"{character}"的标志性造型。
    *   **无缝融合：** 将新的服装和发型，根据第一张照片中人物的**原始姿势和体型**进行自然地调整和匹配，确保褶皱、光影和贴合度都看起来真实可信。

3.  **画质与光影:**
    *   **风格：** 追求**照片真实感 (photorealistic)**，避免产生卡通或绘画感。
    *   **光影统一：** 所有新元素（妆容、发型、服装）都必须与第一张照片的**原始光线和阴影**自然融合。
    *   **输出质量：** 成品图片要求**高分辨率、细节清晰、无不自然的模糊或伪影**。
"""


def get_mime_type(file_path: str) -> str:
    """根据文件扩展名获取MIME类型"""
    ext = os.path.splitext(file_path)[1].lower()
    mime_types = {
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.gif': 'image/gif',
        '.webp': 'image/webp',
    }
    return mime_types.get(ext, 'image/jpeg')


def encode_image_to_base64(file_path: str) -> str:
    """将图片文件编码为base64字符串"""
    with open(file_path, 'rb') as f:
        image_data = f.read()
    return base64.b64encode(image_data).decode('utf-8')


class TransformResult:
    """转换结果类"""

    def __init__(self):
        self.image_url: str = ''
        self.text: Optional[str] = None


def save_binary_file(file_name, data):
    f = open(file_name, "wb")
    f.write(data)
    f.close()
    print(f"File saved to to: {file_name}")


async def change_outfit(
        user_image_path: str,
        character_prompt: str,
        character_image_path: Optional[str] = None
) -> TransformResult:
    """
    将用户图片中的人物Cosplay成指定动漫角色

    Args:
        user_image_path: 用户图片路径
        character_prompt: 角色名称/描述
        character_image_path: 可选的角色参考图片路径

    Returns:
        TransformResult: 包含生成图片URL和文本的结果
    """
    try:
        print("初始化")

        from google import genai, auth
        from google.genai._base_url import set_default_base_urls
        from google.auth.credentials import with_scopes_if_required
        from google.genai.types import HttpOptions
        set_default_base_urls('https://jingnanquan-cfll-gemini-64.deno.dev/', None)
        json_dict = json.loads(decrypt_string(API_G, "AIDubbing"))
        creds, project_id = auth.load_credentials_from_dict(json_dict)
        scoped_creds = with_scopes_if_required(
            creds, ["https://www.googleapis.com/auth/cloud-platform"]
        )
        ai = genai.Client(vertexai=True, project=project_id, location="global", credentials=scoped_creds, http_options = HttpOptions(timeout=300 * 1000))

        print("初始化成功")
        # 读取用户图片
        user_image_base64 = encode_image_to_base64(user_image_path)
        user_image_mime = get_mime_type(user_image_path)

        print(user_image_mime)
        # 构建parts列表
        parts = [
            types.Part.from_bytes(
                data=base64.b64decode(user_image_base64),
                mime_type=user_image_mime
            )
        ]

        # 构建提示词
        prompt = ''
        if character_image_path:
            # 读取参考图片
            character_image_base64 = encode_image_to_base64(character_image_path)
            character_image_mime = get_mime_type(character_image_path)

            parts.append(
                types.Part.from_bytes(
                    data=base64.b64decode(character_image_base64),
                    mime_type=character_image_mime
                )
            )
            prompt = create_prompt_with_reference_image(character_prompt)
        else:
            prompt = create_prompt(character_prompt)



        parts.append(types.Part.from_text(text=prompt))

        print(parts)

        contents = [
            types.Content(
                role="user",
                parts=parts,
            )
        ]

        # # 调用API生成内容
        # response = ai.models.generate_content(
        #     model='gemini-2.5-flash-image-preview',
        #     contents=parts,
        #     config=types.GenerateContentConfig(
        #         response_modalities=["IMAGE","TEXT",]
        #     )
        # )

        file_index = 0
        for chunk in ai.models.generate_content_stream(
            model='gemini-3-pro-image-preview',
            contents=contents,
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE","TEXT",]
            )
        ):
            if (
                    chunk.parts is None
            ):
                continue
            if chunk.parts[0].inline_data and chunk.parts[0].inline_data.data:
                file_name = f"ENTER_FILE_NAME_{file_index}"
                file_index += 1
                inline_data = chunk.parts[0].inline_data
                data_buffer = inline_data.data
                file_extension = mimetypes.guess_extension(inline_data.mime_type)
                save_binary_file(f"{file_name}{file_extension}", data_buffer)
            else:
                print(chunk.text)

        return TransformResult()

        # # 检查响应
        # if not response.candidates or len(response.candidates) == 0:
        #     if response.prompt_feedback and response.prompt_feedback.block_reason:
        #         print(f"Request blocked by safety filters. Reason: {response.prompt_feedback.block_reason}",
        #               file=sys.stderr)
        #         raise Exception("请求因内容安全问题被阻止。请尝试更换图片或角色名称。")
        #     raise Exception("API 未返回有效的结果。这可能是临时问题，请稍后重试。")
        #
        # # 构建结果
        # result = TransformResult()
        # image_found = False
        #
        # for part in response.candidates[0].content.parts:
        #     if part.inline_data:
        #         base64_image_bytes = part.inline_data.data
        #         mime_type = part.inline_data.mime_type
        #         result.image_url = f"data:{mime_type};base64,{base64_image_bytes}"
        #         image_found = True
        #     elif part.text:
        #         result.text = part.text
        #
        # if not image_found:
        #     raise Exception("API 响应中未找到图片，可能是由于请求被拒绝。请尝试不同的角色或图片。")
        #
        # return result

    except Exception as error:
        print(f"Gemini API Error: {error}", file=sys.stderr)
        if isinstance(error, Exception) and any(
                msg in str(error) for msg in ['安全问题', '未返回有效的结果', '未找到图片']
        ):
            raise error
        raise Exception("调用 AI 服务时出错。请检查您的网络连接或 API 密钥是否正确。")


def save_base64_image(base64_data_url: str, output_path: str) -> None:
    """将base64数据URL保存为图片文件"""
    # 解析data URL
    if ',' in base64_data_url:
        header, data = base64_data_url.split(',', 1)
    else:
        data = base64_data_url

    # 解码并保存
    image_data = base64.b64decode(data)
    with open(output_path, 'wb') as f:
        f.write(image_data)


def main():
    """主函数 - 通过控制台传参调用"""
    parser = argparse.ArgumentParser(
        description='将照片中的人物Cosplay成动漫角色',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  python script.py -u user.jpg -c "雷电将军"
  python cosplayService.py -u cosplay/3.jpg -c "爱弥斯" -r cosplay/4.jpg -o output.jpg
        """
    )

    parser.add_argument(
        '-u', '--user-image',
        required=True,
        help='用户图片路径（必需）'
    )

    parser.add_argument(
        '-c', '--character',
        required=True,
        help='目标动漫角色名称（必需）'
    )

    parser.add_argument(
        '-r', '--reference-image',
        required=False,
        help='角色参考图片路径（可选）'
    )

    parser.add_argument(
        '-o', '--output',
        required=False,
        default='output_cosplay.jpg',
        help='输出图片路径（默认：output_cosplay.jpg）'
    )

    args = parser.parse_args()

    # 验证输入文件是否存在
    if not os.path.exists(args.user_image):
        print(f"错误：用户图片不存在：{args.user_image}", file=sys.stderr)
        sys.exit(1)

    if args.reference_image and not os.path.exists(args.reference_image):
        print(f"错误：参考图片不存在：{args.reference_image}", file=sys.stderr)
        sys.exit(1)

    print(f"开始处理...")
    print(f"用户图片：{args.user_image}")
    print(f"目标角色：{args.character}")
    if args.reference_image:
        print(f"参考图片：{args.reference_image}")
    print(f"输出路径：{args.output}")
    print("-" * 50)

    try:
        # 调用转换函数
        import asyncio
        result = asyncio.run(change_outfit(
            user_image_path=args.user_image,
            character_prompt=args.character,
            character_image_path=args.reference_image
        ))

        # 保存输出图片
        if result.image_url:
            save_base64_image(result.image_url, args.output)
            print(f"\n✓ 成功！输出图片已保存至：{args.output}")

        if result.text:
            print(f"\nAI 回复：\n{result.text}")

    except Exception as e:
        print(f"\n✗ 错误：{e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()