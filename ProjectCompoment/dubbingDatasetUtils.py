import os
import dataset
from sqlalchemy.pool import QueuePool

from ProjectCompoment.dubbingEntity import Project, Subtitle

class dubbingDatasetUtils:
    _instance = None

    def __init__(self):
        self.path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Service", "mydb.db")
        print(self.path)
        self.db = dataset.connect('sqlite:///' + self.path,
                                 engine_kwargs={
                                     "connect_args": {"check_same_thread": False},
                                     "poolclass": QueuePool,
                                     "pool_size": 5,
                                     "max_overflow": 10,
                                     "pool_timeout": 30,
                                 })
        self.projectTable = self.db["projectTable"]
        self.subtitleTable = self.db["subtitleTable"]

    @classmethod
    def getInstance(cls) -> 'dubbingDatasetUtils':
        if cls._instance is None:
            cls._instance = dubbingDatasetUtils()
        return cls._instance

    # 插入项目
    def insert_project(self, project: Project):
        data = project.__dict__.copy()
        try:
            project_id = self.projectTable.insert(data)
            last_row = self.projectTable.find_one(order_by='-id')
            return last_row['id'] if last_row and 'id' in last_row else -1
        except Exception:
            return -1

    # 插入字幕
    def insert_subtitle(self, subtitle: Subtitle):
        data = subtitle.__dict__.copy()
        return self.subtitleTable.insert(data)
    
    def insert_subtitle_many(self, subtitles: list[Subtitle]):
        data_list = [subtitle.__dict__ for subtitle in subtitles]
        return self.subtitleTable.insert_many(data_list)

    # 查找所有项目，返回 Project 实例列表
    def get_all_projects(self):
        return [Project(**item) for item in self.projectTable.all()]

    def get_project_by_id(self, id: int):
        return Project(**self.projectTable.find_one(id=id))

    # 根据项目id查找字幕，返回 Subtitle 实例列表
    def get_subtitles_by_project_id(self, project_id: int):
        return [Subtitle(**item) for item in self.subtitleTable.find(project_id=project_id)]
    
    def clear_all_data(self):
        self.projectTable.delete()
        self.subtitleTable.delete()

# 示例用法
if __name__ == '__main__':
    api = dubbingDatasetUtils.getInstance()
    print(api.get_all_projects())
    project = Project(projectname="测试项目", original_video_path="", original_bgm_audio_path="", original_voice_audio_path="", target_dubbing_audio_path="", target_video_path="")
    print(api.insert_project(project))
    
    
    # api.clear_all_data()
    subtitle = Subtitle(project_id=1, original_subtitle="Hello2", target_subtitle="你好呀", start_time="00:00:01:000", end_time="00:00:03:000", role_name="角色A")
    # subtitle2 = Subtitle(project_id=1, original_subtitle="QQQ", target_subtitle="你好呀", start_time="00:00:01:000", end_time="00:00:03:000", role_name="角色C")
    # print(api.insert_subtitle_many([subtitle, subtitle2]))
    # res = api.get_subtitles_by_project_id(1)
    # print(res)
    # for item in res:
    #     print(item.__dict__)

