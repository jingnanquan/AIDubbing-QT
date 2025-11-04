import datetime
import os
from Config import AUDIO_SEPARATION_FOLDER

#
import librosa
import numpy as np
from Service.uvrMain.uvr5_pack.lib_v5 import spec_utils
from Service.uvrMain.uvr5_pack.utils import inference
from Service.uvrMain.uvr5_pack.lib_v5.model_param_init import ModelParameters
from Service.uvrMain.uvr5_pack.lib_v5.nets_123812KB import *
import soundfile as sf

class AudioPre():
    _instance = None
    _model_loaded = False
    _model = None
    _mp = None
    
    def __init__(self, device, is_half, model_path='uvr5_weights/2_HP-UVR.pth'):
        self.device = device
        self.is_half = is_half
        self.model_path = model_path
        self.data = {
            # Processing Options
            'postprocess': False,
            'tta': False,
            # Constants
            'window_size': 512,
            'agg': 10,
            'high_end_process': 'mirroring',
        }
        
        # 延迟加载模型
        self._load_model_if_needed()

    def _load_model_if_needed(self):
        """延迟加载模型，只在第一次使用时加载"""
        if not AudioPre._model_loaded:
            self._load_model()
            AudioPre._model_loaded = True

    def _load_model(self):
        """实际加载模型的函数"""
        from torch import load

        prefix_path = os.path.dirname(os.path.abspath(__file__))
        model_path = os.path.join(prefix_path, self.model_path)
        print(f"正在加载UVR模型: {model_path}")
        
        self.model_path = model_path
        model_params_d = os.path.join(prefix_path, "uvr5_pack/lib_v5/modelparams/4band_v2.json")
        print(f"模型参数文件: {model_params_d}")

        # 加载模型参数
        AudioPre._mp = ModelParameters(model_params_d)

        # 创建模型
        AudioPre._model = CascadedASPPNet(AudioPre._mp.param['bins'] * 2)
        cpk = load(model_path, map_location='cpu')
        AudioPre._model.load_state_dict(cpk)
        AudioPre._model.eval()
        
        if self.is_half:
            AudioPre._model = AudioPre._model.half().to(self.device)
        else:
            AudioPre._model = AudioPre._model.to(self.device)

        self.mp = AudioPre._mp
        self.model = AudioPre._model
        print("人声去除模型初始化完毕！")

    @property
    def mp(self):
        """获取模型参数"""
        if not AudioPre._model_loaded:
            self._load_model_if_needed()
        return AudioPre._mp

    @mp.setter
    def mp(self, value):
        self._mp = value

    @property
    def model(self):
        """获取模型"""
        if not AudioPre._model_loaded:
            self._load_model_if_needed()
        return AudioPre._model

    @model.setter
    def model(self, value):
        self._model = value

    def _path_audio_(self, music_file, on_progress=None, output_path=AUDIO_SEPARATION_FOLDER):
        from torch import no_grad
        name=os.path.basename(music_file)
        name= os.path.splitext(name)[0]
        print(name)
        X_wave, y_wave, X_spec_s, y_spec_s = {}, {}, {}, {}
        bands_n = len(self.mp.param['band'])
        # print(bands_n)
        for d in range(bands_n, 0, -1):
            if on_progress:
                on_progress(10 - d, "")
            bp = self.mp.param['band'][d]
            if d == bands_n: # high-end band
                X_wave[d], _ = librosa.load(music_file, sr=bp['sr'], mono=False, dtype=np.float32, res_type=bp['res_type'])
                if X_wave[d].ndim == 1:
                    X_wave[d] = np.asfortranarray([X_wave[d], X_wave[d]])
            else: # lower bands
                X_wave[d] = librosa.core.resample(X_wave[d+1], orig_sr=self.mp.param['band'][d+1]['sr'], target_sr=bp['sr'], res_type=bp['res_type'])
            # Stft of wave source
            X_spec_s[d] = spec_utils.wave_to_spectrogram_mt(X_wave[d], bp['hl'], bp['n_fft'], self.mp.param['mid_side'], self.mp.param['mid_side_b2'], self.mp.param['reverse'])
            # pdb.set_trace()
            if d == bands_n and self.data['high_end_process'] != 'none':
                input_high_end_h = (bp['n_fft']//2 - bp['crop_stop']) + ( self.mp.param['pre_filter_stop'] - self.mp.param['pre_filter_start'])
                input_high_end = X_spec_s[d][:, bp['n_fft']//2-input_high_end_h:bp['n_fft']//2, :]
        X_spec_m = spec_utils.combine_spectrograms(X_spec_s, self.mp)
        aggresive_set = float(self.data['agg']/100)
        aggressiveness = {'value': aggresive_set, 'split_bin': self.mp.param['band'][1]['crop_stop']}
        with no_grad():
            pred, X_mag, X_phase = inference(X_spec_m,self.device,self.model, aggressiveness,self.data)
        # Postprocess
        if self.data['postprocess']:
            pred_inv = np.clip(X_mag - pred, 0, np.inf)
            pred = spec_utils.mask_silence(pred, pred_inv)
        y_spec_m = pred * X_phase
        v_spec_m = X_spec_m - y_spec_m
        if on_progress:
            on_progress(12, "")

        print("结束推理")
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        back_filename = os.path.join(output_path, 'background-{}-{}.wav'.format(name,timestamp))
        vocal_filename = os.path.join(output_path, 'vocal-{}-{}.wav'.format(name,timestamp))

        if on_progress:
            on_progress(14, "")
        # if (ins_root is not None):
        if self.data['high_end_process'].startswith('mirroring'):
            input_high_end_ = spec_utils.mirroring(self.data['high_end_process'], y_spec_m, input_high_end, self.mp)
            wav_instrument = spec_utils.cmb_spectrogram_to_wave(y_spec_m, self.mp,input_high_end_h, input_high_end_)
        else:
            wav_instrument = spec_utils.cmb_spectrogram_to_wave(y_spec_m, self.mp)
        # print(wav_instrument)
        # print(type(wav_instrument))
        print("采样率", self.mp.param['sr'])
        print ('%s instruments done'%name)


        sf.write(back_filename, wav_instrument, self.mp.param['sr'])
        if on_progress:
            on_progress(16, "")
        # wavfile.write(back_filename, self.mp.param['sr'], (np.array(wav_instrument)*32768).astype("int16"))  #
        # if (vocal_root is not None):
        if self.data['high_end_process'].startswith('mirroring'):
            input_high_end_ = spec_utils.mirroring(self.data['high_end_process'],  v_spec_m, input_high_end, self.mp)
            wav_vocals = spec_utils.cmb_spectrogram_to_wave(v_spec_m, self.mp, input_high_end_h, input_high_end_)
        else:
            wav_vocals = spec_utils.cmb_spectrogram_to_wave(v_spec_m, self.mp)
        print ('%s vocals done'%name)
        sf.write(vocal_filename, wav_vocals, self.mp.param['sr'])
        if on_progress:
            on_progress(18, "")
        return back_filename, vocal_filename

    @classmethod
    def getInstance(cls)-> 'AudioPre':
        if not cls._instance:
            from torch import cuda
            # cuda.is_available()
            device = "cuda" if cuda.is_available() else "cpu"
            if device=="cuda":
                cls._instance = AudioPre(device=device, is_half=True)
            elif device=="cpu":
                cls._instance = AudioPre(device=device, is_half=False)
        return cls._instance



# uvr5的模型，虽然只是2，效果已经非常牛了
if __name__ == '__main__':
    pre_fun = AudioPre.getInstance()
    audio_path = r"E:\offer\AI配音web版\8.28\AIDubbing-QT-main\a视频_test.mp4"
    # save_path = 'opt3'
    pre_fun._path_audio_(audio_path)
