# This Python file uses the following encoding: utf-8
import json
import time

import requests



print("minimax")

group_id = '1924501514181677288'    #请输入您的group_id
api_key = 'eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJHcm91cE5hbWUiOiLnh5XpkasiLCJVc2VyTmFtZSI6IueHlemRqyIsIkFjY291bnQiOiIiLCJTdWJqZWN0SUQiOiIxOTI0NTAxNTE0MTg1ODcxNTkyIiwiUGhvbmUiOiIxOTg3MTM2MDQzMCIsIkdyb3VwSUQiOiIxOTI0NTAxNTE0MTgxNjc3Mjg4IiwiUGFnZU5hbWUiOiIiLCJNYWlsIjoiIiwiQ3JlYXRlVGltZSI6IjIwMjUtMDUtMjAgMTU6MDI6NDYiLCJUb2tlblR5cGUiOjEsImlzcyI6Im1pbmltYXgifQ.OJnJsFSVutHq_jjTo9rNoohYt4DyC346f85mvMIEMSw3JpNifjt7gk3K8sUGj0fBXzcM9_8DfxrNtuJ8c28kXR-3Riogvg7X8V4A3UJezZ4bGTAKq0CLz0alFtmpBONC0j92rxWzLMZ3Eg4b3cWpBASichEBWLaTLJSImMTUcwHCnXeyWdYBK9S-HkTPJ0yXx6serGYOTaEdU7hcZpvxuhnhA5lFPCaLu-2GWLktsY7TcSGBudppv8OABqfvVRW25tZOIt6UEWl5_em8oC--eDhTc8abCpjSo4g59Me7hZylHIH3S4F4eGcyi5mLV0AN_m_r_v_kZMIvMRttVjGgow'    #请输入您的api_key

file_format = 'mp3'  # 支持 mp3/pcm/flac

url = "https://api.minimax.chat/v1/t2a_v2?GroupId=" + group_id
headers = {"Content-Type":"application/json", "Authorization":"Bearer " + api_key}


def build_tts_stream_headers() -> dict:
    headers = {
        'accept': 'application/json, text/plain, */*',
        'content-type': 'application/json',
        'authorization': "Bearer " + api_key,
    }
    return headers


def build_tts_stream_body(text: str) -> dict:
    body = json.dumps({
        "model":"speech-01-turbo",
        "text":"真正的危险不是计算机开始像人一样思考，而是人开始像计算机一样思考。计算机只是可以帮我们处理一些简单事务。",
        "stream":False,
        "voice_setting":{
            "voice_id":"male-qn-qingse",
            "speed":1.0,
            "vol":1.0,
            "pitch":0
        },
        'subtitle_enable':True,
        "pronunciation_dict":{
            "tone":[
                "处理/(chu3)(li3)", "危险/dangerous"
            ]
        },
        "audio_setting":{
            "sample_rate":32000,
            "bitrate":128000,
            "format":"mp3",
            "channel":1
        }
    })
    return body


# mpv_command = ["mpv", "--no-cache", "--no-terminal", "--", "fd://0"]
# mpv_process = subprocess.Popen(
#     mpv_command,
#     stdin=subprocess.PIPE,
#     stdout=subprocess.DEVNULL,
#     stderr=subprocess.DEVNULL,
# )

tts_url = url
tts_headers = build_tts_stream_headers()
tts_body = build_tts_stream_body('')
response = requests.request("POST", tts_url, stream=True, headers=tts_headers, data=tts_body)
result = response.content
# result2 = response.raw
# result = result[5:]
print(result)
result = json.loads(result)
print(result)
audio = result["data"]["audio"]
audio = bytes.fromhex(audio)

# 结果保存至文件
timestamp = int(time.time())
file_name = f'output_total_{timestamp}.{file_format}'
with open(file_name, 'wb') as file:
    file.write(audio)




# print(response)
# print(response.raw)
# print(response.content)
# print(response.text)
# print(response.content)
# print(json.load(response.raw))
# if "data" in response:
#     print(response["data"])
# for chunk in (response.raw):
#     print(chunk["data"])



# def call_tts_stream(text: str) -> Iterator[bytes]:
#     tts_url = url
#     tts_headers = build_tts_stream_headers()
#     tts_body = build_tts_stream_body(text)
#
#     response = requests.request("POST", tts_url, stream=True, headers=tts_headers, data=tts_body)
#     for chunk in (response.raw):
#         if chunk:
#             if chunk[:5] == b'data:':
#                 data = json.loads(chunk[5:])
#                 print(data)
#
#                 if "data" in data and "extra_info" not in data:
#                     if "audio" in data["data"]:
#                         if 'subtitle_file' in data["data"]:
#                             print(data["data"]['subtitle_file'])
#                         audio = data["data"]['audio']
#                         yield audio
#
#
# def audio_play(audio_stream: Iterator[bytes]) -> bytes:
#     audio = b""
#     p = pyaudio.PyAudio()
#     stream = p.open(format=pyaudio.paInt16,
#                     channels=1,
#                     rate=44100,  # 根据实际音频参数调整
#                     output=True)
#     for chunk in audio_stream:
#         if chunk is not None and chunk != '\n':
#             # stream.write(binascii.unhexlify(chunk))
#             decoded_hex = bytes.fromhex(chunk)
#             # mpv_process.stdin.write(decoded_hex)  # type: ignore
#             # mpv_process.stdin.flush()
#             audio += decoded_hex
#
#     return audio
#
#
# audio_chunk_iterator = call_tts_stream('')
# audio = audio_play(audio_chunk_iterator)

# 结果保存至文件
# timestamp = int(time.time())
# file_name = f'output_total_{timestamp}.{file_format}'
# with open(file_name, 'wb') as file:
#     file.write(audio)