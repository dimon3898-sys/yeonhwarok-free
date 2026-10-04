"""Original deterministic 48 kHz stereo score and effects. No sampled audio.
The composition and generated waveforms are released under CC0-1.0.
"""
from pathlib import Path
import json
import numpy as np
from scipy.signal import butter, sosfilt
from scipy.io import wavfile

SR=48000
ROOT=Path(__file__).resolve().parents[1]

class SoundEngine:
    def __init__(self,seconds=20):
        self.seconds=seconds
        self.audio=np.zeros((int(SR*seconds),2),np.float64)
        self.rng=np.random.default_rng(1947)
        self.cues=[]

    def filtered(self,noise,low,high):
        return sosfilt(butter(3,[low,high],btype='bandpass',fs=SR,output='sos'),noise)

    def add(self,signal,start,pan=0,kind='fx'):
        i=round(start*SR)
        if i<0:
            signal=signal[-i:];i=0
        n=min(len(signal),len(self.audio)-i)
        if n<=0:return
        gains=np.array([np.sqrt((1-pan)/2),np.sqrt((1+pan)/2)])
        self.audio[i:i+n]+=signal[:n,None]*gains[None,:]
        self.cues.append(dict(time=start,kind=kind,duration=len(signal)/SR,pan=pan))

    def music(self):
        t=np.arange(len(self.audio))/SR
        attack=np.minimum(t/1.4,1)
        end=np.minimum((20-t)/1.8,1)
        env=np.clip(attack*end,0,1)
        # D minor suspended harmonics; intentionally no loud midrange lead.
        for k,f in enumerate([36.7081,55.0,73.4162,110.0,146.8324,174.6141,220.0]):
            phase=2*np.pi*f*t+.1*np.sin(t*(.16+k*.015))
            amp=[.052,.018,.026,.012,.009,.006,.003][k]
            swell=.70+.30*np.sin(t*.28+k*.7)
            tone=amp*np.sin(phase)*swell*env
            self.audio[:,0]+=tone*np.cos(.34+k*.17)
            self.audio[:,1]+=tone*np.sin(.34+k*.17)
        air=self.filtered(self.rng.normal(size=len(t)),80,350)*.018*env
        self.audio[:,0]+=air
        self.audio[:,1]+=np.roll(air,517)*.8
        # Very soft bowed halo; slow harmonic evolution, no narration masking.
        halo=(np.sin(2*np.pi*293.665*t+.12*np.sin(t*.45))+np.sin(2*np.pi*349.228*t+.17*np.sin(t*.38)))*.0028
        self.audio[:,0]+=halo*env*(.6+.4*np.sin(t*.2)**2)
        self.audio[:,1]+=np.roll(halo,133)*env*.8

    def whoosh(self,start,duration=1.2,amp=.22,pan=0):
        t=np.arange(int(SR*duration))/SR
        env=np.sin(np.pi*t/duration)**2.4
        noise=self.filtered(self.rng.normal(size=len(t)),50,900)
        sig=noise*env*amp
        self.add(sig,start,pan,'low whoosh')
        self.add(np.roll(sig,1709)*.16,start+.10,-pan,'whoosh reflection')

    def hit(self,start,amp=.20,deep=False,pan=0):
        duration=2.15 if deep else 1.0
        t=np.arange(int(SR*duration))/SR
        f0,f1=(62,31) if deep else (99,54)
        phase=2*np.pi*(f1*t+(f0-f1)*.09*(1-np.exp(-t/.09)))
        onset=1-np.exp(-t*180)
        sub=np.sin(phase)*np.exp(-t/(.65 if deep else .27))*onset
        air=self.filtered(self.rng.normal(size=len(t)),100,1600)*np.exp(-t/.075)*.29*onset
        sig=(sub+air)*amp
        self.add(sig,start,pan,'deep impact' if deep else 'soft arrival hit')
        self.add(sig*.10,start+.19,-pan,'hit reflection')

    def pulse(self,start,amp=.06,pan=0):
        t=np.arange(int(SR*.65))/SR
        freq=680*np.exp(-t*2.2)+210
        phase=2*np.pi*np.cumsum(freq)/SR
        sig=np.sin(phase)*np.exp(-t*14)*(1-np.exp(-t*130))*amp
        self.add(sig,start,pan,'route pulse')
        self.add(sig*.17,start+.16,-pan,'pulse reflection')

    def passby(self,start,duration=1.6):
        t=np.arange(int(duration*SR))/SR
        env=np.sin(np.pi*t/duration)**3
        n=self.filtered(self.rng.normal(size=len(t)),100,1300)*env*.17
        for j in range(2):
            gains=np.sqrt(np.clip((1+(-1 if j==0 else 1)*(t/duration*2-1))/2,0,1))
            i=round(start*SR);size=min(len(n),len(self.audio)-i)
            self.audio[i:i+size,j]+=n[:size]*gains[:size]
        self.cues.append(dict(time=start,kind='stereo pass-by',duration=duration))

    def build(self):
        self.music()
        self.whoosh(0,1.5,.24,-.12)
        self.hit(1.6,.10)
        self.pulse(2.8,.085,-.15)
        self.whoosh(3.45,1.3,.14,-.15)
        self.passby(5.15,1.6)
        self.whoosh(7.35,1.5,.18,.08)
        self.hit(9.15,.16,.0)
        self.pulse(10.4,.072,.1)
        self.whoosh(10.25,1.1,.10,.1)
        self.passby(12.2,1.9)
        self.whoosh(13.5,1.7,.17,-.1)
        self.hit(16.05,.19,False,.12)
        self.pulse(17.2,.05)
        self.whoosh(17.5,1.5,.18)
        self.hit(18.60,.33,True)
        t=np.arange(len(self.audio))/SR
        fade=np.clip((20-t)/.28,0,1)**1.3
        self.audio*=fade[:,None]
        peak=np.max(np.abs(self.audio));self.audio*=min(1,.82/peak)
        dest=ROOT/'assets/audio';dest.mkdir(parents=True,exist_ok=True)
        wavfile.write(dest/'score_raw.wav',SR,np.float32(self.audio))
        (dest/'cue_sheet.json').write_text(json.dumps(sorted(self.cues,key=lambda x:x['time']),indent=2))
        print('Generated original 20 s stereo composition; peak',20*np.log10(np.max(np.abs(self.audio))))

if __name__=='__main__':SoundEngine().build()
