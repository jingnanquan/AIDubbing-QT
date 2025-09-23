# This Python file uses the following encoding: utf-8

import requests



print("minimax_clone")

group_id = '1924501514181677288'    #请输入您的group_id
api_key = 'eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJHcm91cE5hbWUiOiLnh5XpkasiLCJVc2VyTmFtZSI6IueHlemRqyIsIkFjY291bnQiOiIiLCJTdWJqZWN0SUQiOiIxOTI0NTAxNTE0MTg1ODcxNTkyIiwiUGhvbmUiOiIxOTg3MTM2MDQzMCIsIkdyb3VwSUQiOiIxOTI0NTAxNTE0MTgxNjc3Mjg4IiwiUGFnZU5hbWUiOiIiLCJNYWlsIjoiIiwiQ3JlYXRlVGltZSI6IjIwMjUtMDUtMjAgMTU6MDI6NDYiLCJUb2tlblR5cGUiOjEsImlzcyI6Im1pbmltYXgifQ.OJnJsFSVutHq_jjTo9rNoohYt4DyC346f85mvMIEMSw3JpNifjt7gk3K8sUGj0fBXzcM9_8DfxrNtuJ8c28kXR-3Riogvg7X8V4A3UJezZ4bGTAKq0CLz0alFtmpBONC0j92rxWzLMZ3Eg4b3cWpBASichEBWLaTLJSImMTUcwHCnXeyWdYBK9S-HkTPJ0yXx6serGYOTaEdU7hcZpvxuhnhA5lFPCaLu-2GWLktsY7TcSGBudppv8OABqfvVRW25tZOIt6UEWl5_em8oC--eDhTc8abCpjSo4g59Me7hZylHIH3S4F4eGcyi5mLV0AN_m_r_v_kZMIvMRttVjGgow'    #请输入您的api_key

file_format = 'mp3'  # 支持 mp3/pcm/flac


clone_url = f'https://api.minimax.chat/v1/files/upload?GroupId={group_id}'
clone_headers = {
    'authority': 'api.minimax.chat',
    'Authorization': f'Bearer {api_key}'
}

data = {
    'purpose': 'voice_clone'
}

files = {
    'file': open('output.mp3', 'rb')
}
response = requests.post(clone_url, headers=clone_headers, data=data, files=files)

