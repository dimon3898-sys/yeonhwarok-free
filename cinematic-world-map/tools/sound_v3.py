"""Original CC0 score: preserved V2 synthesis, newly synchronized V3 cues."""
from pathlib import Path
import json
import numpy as np
from scipy.io import wavfile
from sound_v2 import SoundEngine as V2SoundEngine, SR, ROOT

class SoundEngine(V2SoundEngine):
    def build(self):
        dest=ROOT/'assets/audio/v3';dest.mkdir(exist_ok=True)
        for name in ['score_raw.wav','cue_sheet.json','waveform_analysis.json']:
            if (dest/name).exists():raise RuntimeError('Refusing to overwrite '+str(dest/name))
        self.music()
        self.impact(0,.30,True)
        self.whoosh(0,1.6,.22,-.08)
        self.impact(.6,.075,False,-.07)
        self.pulse(.9,.035,-.08)
        self.pulse(1.2,.050,-.06)
        self.passby(1.5,1.65)
        self.whoosh(3.45,1.1,.10,.08)
        self.impact(5.6,.07,False,.10)
        self.impact(7.1,.15,False,.10)
        self.whoosh(7.8,1.65,.23,-.08)
        self.impact(8.3,.095,False)
        self.pulse(8.8,.025,-.06)
        self.whoosh(9.7,1.4,.15,.08)
        self.pulse(10.2,.058,.06)
        self.passby(11.6,1.65)
        self.whoosh(12.4,1.9,.13,-.08)
        self.impact(14,.12,True,-.06)
        self.whoosh(14.1,1.8,.11,-.06)
        self.impact(16.5,.075,False,-.08)
        self.impact(17.25,.17,False,-.08)
        self.whoosh(18.1,1.25,.21)
        self.impact(19.2,.34,True)
        t=np.arange(len(self.audio))/SR
        self.audio*=np.clip((20-t)/.18,0,1)[:,None]**1.4
        peak=np.max(np.abs(self.audio));self.audio*=min(1,.83/peak)
        dest=ROOT/'assets/audio/v3';dest.mkdir(exist_ok=True)
        path=dest/'score_raw.wav'
        if path.exists():raise RuntimeError('Refusing to overwrite '+str(path))
        wavfile.write(path,SR,np.float32(self.audio))
        with (dest/'cue_sheet.json').open('x') as file:json.dump(sorted(self.cues,key=lambda x:x['time']),file,indent=2)
        rms=[20*np.log10(max(np.sqrt(np.mean(self.audio[i*SR:(i+1)*SR]**2)),1e-12)) for i in range(20)]
        with (dest/'waveform_analysis.json').open('x') as file:json.dump({'sample_rate':SR,'channels':2,'duration':20,'peak_dbfs':float(20*np.log10(np.max(np.abs(self.audio)))),'rms_dbfs_by_second':rms,'direct_listening':False,'license':'CC0-1.0'},file,indent=2)
        print('V3 score generated',path)
if __name__=='__main__':SoundEngine().build()
