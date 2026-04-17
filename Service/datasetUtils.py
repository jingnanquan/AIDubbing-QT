import os
import dataset

from Service.generalUtils import calculate_time


class datasetUtils:
    """
    """
    _instance = None

    @calculate_time
    def __init__(self):
        self.path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mydb.db")
        print(self.path)
        self.db = dataset.connect('sqlite:///'+self.path)
        self.voiceTable = self.db["voiceTable"]


    def save_voice_id(self, api_id:int, voice_name: str, voice_id: str):
        # table = self.db["voiceTable"]
        try:
            self.voiceTable.insert({"api_id": api_id, "voice_name":voice_name, "voice_id":voice_id})
        except Exception as e:
            print("插入失败：", e)

    def save_voice_id_withtime(self, api_id:int, voice_name: str, voice_id: str, create_time: int):
        # table = self.db["voiceTable"]
        try:
            self.voiceTable.insert({"api_id": api_id, "voice_name":voice_name, "voice_id":voice_id, "create_time": create_time})
        except Exception as e:
            print("插入失败：", e)

    def query_voice_id(self, api_id_p: int):
        # 1为elevenlab 2为minimax
        if api_id_p ==0:
            result = self.voiceTable.all()
        else:
            result = self.voiceTable.find(api_id=api_id_p)
        result_list = list(result)
        result_list.reverse()
        return {item["voice_name"]: item["voice_id"] for item in list(result_list)}

    def query_voice_id_withtime(self, api_id_p: int):
        # 1为elevenlab 2为minimax
        if api_id_p == 0:
            result = self.voiceTable.all()
        else:
            result = self.voiceTable.find(api_id=api_id_p)
        result_list = list(result)
        result_list.reverse()
        print(result_list[0:20])
        return {item["voice_name"]: [item["voice_id"],"", item["create_time"]] for item in list(result_list)}

        # table = self.db["voiceTable"]
    def sava_changer_audio_dir(self, dir_path: str):
        try:
            changerTable = self.db["changerTable"]
            changerTable.insert({"dir_path": dir_path})
        except Exception as e:
            print("插入失败：", e)

    def query_changer_audio_dir(self):
        result = self.db["changerTable"].all()
        res = [item["dir_path"] for item in result]  #最新创建的table反而在最下边，因此顺序为倒序
        # res.reverse()
        return res

    def update_voice_id(self, voice_list: list):
        # print(voice_list)
        self.voiceTable.delete()  # 删除所有声音
        self.voiceTable.insert_many(voice_list)  # 批量插入

    def delete_voice_by_id(self, voice_id_list: list):
        self.voiceTable.delete(voice_id=voice_id_list)

    @classmethod
    def getInstance(cls):
        return datasetUtils()
        # if not cls._instance:
        #     cls._instance = datasetUtils()
        # return cls._instance

if __name__ == '__main__':
    api = datasetUtils.getInstance()
    res=api.query_voice_id(1)
    print(res)


