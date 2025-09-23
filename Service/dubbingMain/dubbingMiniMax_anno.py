# import asyncio
# import io
# import json
#
# import pypinyin
# import numpy as np
# import soundfile as sf
# import time
# from concurrent.futures import ThreadPoolExecutor
#
# import requests
# from pydub import AudioSegment
#
# from Service.dubbingMain.dubbingInterface import dubbingInterface
# from Service.subtitleUtils import match_subtitles_roles
# from Service.videoUtils import get_video_path, get_subtitle_path, calculate_time
#
#
# class dubbingMiniMax(dubbingInterface):
#     """
#     dubbingMiniMax类，继承自dubbingInterface
#     这个类是典型的配音类，可以有多个api或自定义实现。
#     主要的函数为传入音频文件和字幕文件
#     音频的文件会截取，并生成每个role的音频文件
#     通过api克隆角色语音，clone完成后。
#     根据字幕的时间戳，逐级生成语音
#     """
#     def __init__(self):
#         super().__init__()
#         self.group_id = '1924501514181677288'  # 请输入您的group_id
#         self.api_key = 'eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJHcm91cE5hbWUiOiLnh5XpkasiLCJVc2VyTmFtZSI6IueHlemRqyIsIkFjY291bnQiOiIiLCJTdWJqZWN0SUQiOiIxOTI0NTAxNTE0MTg1ODcxNTkyIiwiUGhvbmUiOiIxOTg3MTM2MDQzMCIsIkdyb3VwSUQiOiIxOTI0NTAxNTE0MTgxNjc3Mjg4IiwiUGFnZU5hbWUiOiIiLCJNYWlsIjoiIiwiQ3JlYXRlVGltZSI6IjIwMjUtMDUtMjAgMTU6MDI6NDYiLCJUb2tlblR5cGUiOjEsImlzcyI6Im1pbmltYXgifQ.OJnJsFSVutHq_jjTo9rNoohYt4DyC346f85mvMIEMSw3JpNifjt7gk3K8sUGj0fBXzcM9_8DfxrNtuJ8c28kXR-3Riogvg7X8V4A3UJezZ4bGTAKq0CLz0alFtmpBONC0j92rxWzLMZ3Eg4b3cWpBASichEBWLaTLJSImMTUcwHCnXeyWdYBK9S-HkTPJ0yXx6serGYOTaEdU7hcZpvxuhnhA5lFPCaLu-2GWLktsY7TcSGBudppv8OABqfvVRW25tZOIt6UEWl5_em8oC--eDhTc8abCpjSo4g59Me7hZylHIH3S4F4eGcyi5mLV0AN_m_r_v_kZMIvMRttVjGgow'  # 请输入您的api_key
#         self.tts_url = "https://api.minimax.chat/v1/t2a_v2?GroupId=" + self.group_id
#         self.tts_headers = {"Content-Type": "application/json", "Authorization": "Bearer " + self.api_key}
#         self.upload_url = f'https://api.minimax.chat/v1/files/upload?GroupId={self.group_id}'
#         self.upload_headers = {'authority': 'api.minimax.chat', 'Authorization': f'Bearer {self.api_key}'}
#         self.clone_url = f'https://api.minimax.chat/v1/voice_clone?GroupId={self.group_id}'
#         self.clone_headers =  { 'Authorization': f'Bearer {self.api_key}','content-type': 'application/json'}
#
#
#     # @calculate_time
#     async def dubbing(self, audio_path, subtitle_path, back_path):
#
#         """
#         处理音频和字幕
#         传入的路径必是已经处理过的
#         """
#         if not self.validate_inputs(audio_path, subtitle_path):
#             return
#         subtitles = self.parse_subtitle(subtitle_path)
#         subtitles = match_subtitles_roles(subtitles)
#         role_subtitles, origin_audio, samplerate, role_audio_path = self.parse_roles_numpy(subtitles, audio_path)
#         role_texts = {}
#         for key, sublist in role_subtitles.items():
#             text=" "
#             for sub in sublist:
#                 text += sub['text'] + ','
#             role_texts[key] = text
#         back_audio, _ = sf.read(back_path)
#         print(back_audio.shape)
#         # role_audio_path.pop('董事长')
#         # role_texts.clear()
#         # role_texts['董事长'] = "妈行了,我会把复查报告,给你带回去,你,是你,知道了,妈,儿子不孝,你想抱孙子的愿望,怕是要落空了,家财万贯又怎么样,连个继承人都没有,孤家寡人,说的就是我了吧,滚,我不想说第二遍,好热,这酒后劲怎么这么大,帮我,我会给你钱,"
#         # time1 = time.time()
#         # tasks = [self.clone_text(key, role_audio_path[key]) for key in role_audio_path.keys()]
#         # role_voice_list = await asyncio.gather(*tasks)  # 并行执行所有任务
#         # print(role_voice_list)
#         # time2 = time.time()
#         # print("耗时：", time2 - time1)
#         role_voice_list = [{'董事长': 'dongshizhang1747817909'}, {'医生': 'yisheng1747818185'}, {'陈女士': 'chennvshi1747818195'}, {'秘书男': 'mishunan1747818205'}, {'服务员': 'fuwuyuan1747818215'}]
#         role_voice_list = {k: v for d in role_voice_list for k, v in d.items()}
#         print(role_voice_list)
#         left =0
#         right=0
#
#         try:
#             while right<len(subtitles)-65:
#                 role = subtitles[left]['role']
#                 start = subtitles[left]['start']
#                 text=""
#                 while right<len(subtitles)-65:
#                     if subtitles[right]['role'] != role:
#                         break
#                     text += subtitles[right]['text'] + ','
#                     right += 1
#                 end = subtitles[right-1]['end']   # 还需要检查时间是否连续
#                 print(role, start, end, text)
#                 response = requests.request("POST", self.tts_url, headers=self.tts_headers, data=self.build_tts_body(text, voice_id=role_voice_list[role]))
#                 result = response.content
#                 result = json.loads(result)  # 由json转为dict
#
#                 # print(result)
#                 if 'data' in result:
#                     if 'audio' in result["data"]:
#                         audio = result["data"]["audio"]
#                         audio = bytes.fromhex(audio)
#
#                         dub_audio = AudioSegment.from_file(io.BytesIO(audio))
#                         dub_audio = dub_audio.set_frame_rate(44100)
#
#                         res_audio = np.array(dub_audio.get_array_of_samples())
#                         res_audio = res_audio.astype(np.float64) / 32767.0
#
#                         res_audio = np.vstack([res_audio, res_audio]).T
#                         print(back_audio.shape)
#                         print(res_audio.shape)
#                         start = int((self.time_str_to_ms(start)*samplerate)/1000)
#                         print(start)
#                         back_audio[start:start+res_audio.shape[0]] += res_audio
#                 left=right
#
#             sf.write("diyiban.mp3", back_audio, samplerate)
#         except Exception as e:
#             # 处理特定异常
#             print(f"发生错误: {e}")
#             sf.write("diyiban.mp3", back_audio, samplerate)
#         # print(role_voice_list)
#         # for key, voice_id in role_voice_list:
#         #     print(key, voice_id)
#             # role_voice_list[i] = list(role_voice_list[i].values())[0]
#
#     async def clone_text(self, key: str, audio_path: str):
#         # await asyncio.sleep(1)
#
#         response = requests.post(self.upload_url, headers=self.upload_headers, data= {'purpose': 'voice_clone'}, files= {'file': open(audio_path, 'rb')})
#         file_id = response.json().get("file").get("file_id")
#         print(file_id)
#         voice_id = ''.join([item[0] for item in pypinyin.pinyin(key, style=pypinyin.Style.NORMAL)])+str(int(time.time()))
#         print(voice_id)
#         payload = json.dumps({
#             "file_id": file_id,
#             "voice_id": voice_id,
#         })
#         response = requests.request("POST", self.clone_url, headers=self.clone_headers, data=payload)
#         print(response.text)
#         msg = json.loads(response.text)["base_resp"]["status_msg"]
#         if msg == "success":
#             return [key, voice_id]
#         else:
#             return [key, "error"]
#
#         # text = ''
#         # for i in range(30, 40):
#         #         text += subtitles[i]['text'] + ','
#         # print(text)
#         # print("接口调用中...")
#         # response = requests.request("POST", self.tts_url, headers=self.tts_headers, data=self.build_tts_body(text))
#         # result = response.content
#         # result = json.loads(result)  # 由json转为dict
#         # # print(result)
#         # audio = result["data"]["audio"]
#         # audio = bytes.fromhex(audio)
#         # print(audio)
#         #
#         # dub_audio = AudioSegment.from_file(io.BytesIO(audio))
#         # dub_audio = dub_audio.set_frame_rate(44100)
#         # # dub_audio = dub_audio.set_sample_width()
#         #
#         # res_audio = np.array(dub_audio.get_array_of_samples())
#         # res_audio = res_audio.astype(np.float64) / 32767.0
#         #
#         # print(res_audio.dtype)
#         # # res_audio = np.vstack([res_audio, res_audio]).T
#         #
#         # print(res_audio[0:30])
#         # print(res_audio.shape)
#         # sf.write("sf_hex_tts2.mp3", res_audio, samplerate)
#         # res_audio = np.column_stack([res_audio, res_audio])
#         # print(res_audio[0:30])
#         # sf.write("sf_hex_tts2_2.mp3", res_audio, samplerate)
#         #
#         # with open("byte_tts2.mp3", 'wb') as file:
#         #     file.write(audio)
#         # print(subtitles)
#
#     def build_tts_body(self, text: str, voice_id='') -> str:
#         if voice_id=='':
#             voice_id = "Chinese (Mandarin)_Mature_Woman"
#         body = json.dumps({
#             "model": "speech-02-turbo",
#             "text": text,
#             "stream": False,
#             "voice_setting": {
#                 "voice_id": voice_id,
#                 "speed": 1.0,
#                 "vol": 1.0,
#                 "pitch": 0
#             },
#             # 'subtitle_enable': True,
#             'language_boost': "Chinese",
#             "audio_setting": {
#                 "sample_rate": 32000,
#                 "bitrate": 128000,
#                 "format": "mp3",
#                 "channel": 1
#             }
#         })
#         return body
#
#
# if __name__ == '__main__':
#
#
#     # a = np.array([[1,1],[2,2],[3,3],[4,4]])
#     # b = np.array([[7,7],[8,8]])
#     # print(a)
#     # print(b)
#     # a[1:1+b.shape[0]] +=b
#     # print(a)
#     dub = dubbingMiniMax()
#     # # dub.dubbing(get_video_file("a视频2.mp3"), get_subtitle_file("a字幕.srt"))
#     asyncio.run(dub.dubbing(get_video_path("a视频2.mp3"), get_subtitle_path("a字幕.srt"), get_video_path("a视频2_instrument.wav")))
#
#
#
#     # data1, samplerate1 = sf.read("sf_hex_tts2.mp3")
#     # print(data1.dtype)
#     # print(np.max(data1))
#     # print(data1[0:30])
#     # print(data1.shape)
#     # # print(np.vstack([data1[0:30],data1[0:30]]).T)
#     # print(samplerate1)
#     # data1, samplerate1 = sf.read("sf_hex_tts2_2.mp3")
#     # print(data1.dtype)
#     # print(np.max(data1))
#     # print(data1[0:30])
#     # print(data1.shape)
#     # # print(np.vstack([data1[0:30],data1[0:30]]).T)
#     # print(samplerate1)
#     # data1, samplerate1 = sf.read("byte_tts2.mp3")
#     # print(data1.dtype)
#     # print(np.max(data1))
#     # print(data1[0:30])
#     # print(data1.shape)
#     # print(samplerate1)