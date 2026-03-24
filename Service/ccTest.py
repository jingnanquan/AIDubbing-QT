API_KEY_GEMINI = ""
API_KEY_DEEPSEEK = ""
API_G = ""
API_KEY_ElevenLabs = ""
API_KEY_MiniMax = ""

from Service.readConfig import ConfigManager
def read_config():
    config_manager = ConfigManager()
    config = config_manager.read_config()
    global API_KEY_GEMINI, API_KEY_ElevenLabs, API_G
    API_KEY_GEMINI = config.get("API_KEY_GEMINI", API_KEY_GEMINI)
    API_KEY_ElevenLabs = config.get("API_KEY_ElevenLabs", API_KEY_ElevenLabs)
    API_G = config.get("API_G", API_G)

    print(API_KEY_GEMINI)
    print(API_KEY_ElevenLabs)
    print(API_G)
