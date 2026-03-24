from pathlib import Path

from Service.generalUtils2 import decrypt_string, encrypt_string


class ConfigManager:
    """配置文件管理器 - 使用setting.env文件"""

    def __init__(self):
        self.config_file = Path(__file__).parent / "setting.env"

    def load_config(self):
        """从setting.env加载配置"""
        config = {}
        print(f"尝试加载配置文件: {self.config_file}")
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line and '=' in line and not line.startswith('#'):
                            key, value = line.split('=', 1)
                            config[key.strip()] = decrypt_string(value.strip(), "AIDubbing")
            except IOError as e:
                print(f"读取配置文件失败: {e}")
        else:
            #如果没有文件，则创建一个setting.env文件
            self.config_file.touch()

        # 如果配置文件中没有值，使用默认值
        if 'API_KEY_GEMINI' not in config:
            config['API_KEY_GEMINI'] = ""
        if 'API_KEY_ElevenLabs' not in config:
            config['API_KEY_ElevenLabs'] = ""
        if 'API_G' not in config:
            config['API_G'] = ""

        return config

    def read_config(self):
        """从setting.env加载配置"""
        config = {}
        print(f"尝试加载配置文件: {self.config_file}")
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line and '=' in line and not line.startswith('#'):
                            key, value = line.split('=', 1)
                            config[key.strip()] = value.strip()
            except IOError as e:
                print(f"读取配置文件失败: {e}")
        else:
            #如果没有文件，则创建一个setting.env文件
            self.config_file.touch()

        # 如果配置文件中没有值，使用默认值
        if 'API_KEY_GEMINI' not in config:
            config['API_KEY_GEMINI'] = ""
        if 'API_KEY_ElevenLabs' not in config:
            config['API_KEY_ElevenLabs'] = ""
        if 'API_G' not in config:
            config['API_G'] = ""

        return config

    def save_config(self, config):
        """保存配置到setting.env"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                f.write("# AI配音工具箱配置文件\n")
                f.write("# 请妥善保管您的API密钥\n\n")

                for key, value in config.items():
                    if key.startswith('API_'):
                        value = encrypt_string(value, "AIDubbing")
                        f.write(f"{key}={value}\n")
            return True
        except IOError as e:
            print(f"保存配置文件失败: {e}")
            return False