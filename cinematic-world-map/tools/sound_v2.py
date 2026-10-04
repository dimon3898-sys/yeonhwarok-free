"""MASTER v2 original score. Inherits the preserved v1 synthesis primitives.
Generated waveforms are CC0-1.0; no external samples or reference audio.
"""
from pathlib import Path
import json
import numpy as np
from scipy.io import wavfile
from sound import SoundEngine as BaseSoundEngine, SR, ROOT

class SoundEngine(BaseSoundEngine):
    def music(self):
        t=np.arange(len(self.audio))/SR
        energy=np.interp(t,[0,.65,3,4,7.5,9.3,10.5,13.5,15.8,17.8,19.25,20],
                         [.7,1,.72,.45,.55,1,.75,.85,1.08,.98,1.24,.25])
        envelope=(1-np.exp(-t*7))*np.clip((20-t)/.3,0,1)*energy
        for k,(f,amp) in enumerate([(36.708,.027),(55,.012),(73.416,.018),(110,.009),
                                    (146.832,.007),(174.614,.0038),(220,.0025),(293.665,.0012)]):
            phase=2*np.pi*f*t+.16*np.sin(t*(.13+k*.018))
            tone=amp*np.sin(phase)*envelope*(.88+.12*np.sin(t*.37+k))
            self.audio[:,0]+=tone*(.72+.06*np.sin(t*.19+k))
            self.audio[:,1]+=np.roll(tone,round(11+k*7))*(.72-.06*np.sin(t*.19+k))
        bed=self.filtered(self.rng.normal(size=len(t)),60,290)*.010*envelope
        self.audio[:,0]+=bed;self.audio[:,1]+=np.roll(bed,613)*.83
        # Quiet breath around scale changes, leaving 500 Hz–4 kHz mostly open.
        breath=self.filtered(self.rng.normal(size=len(t)),220,620)*.0023
        self.audio[:,0]+=breath*energy
        self.audio[:,1]+=np.roll(breath,307)*energy

    def pulse(self,start,amp=.055,pan=0):
        t=np.arange(round(.7*SR))/SR
        env=(1-np.exp(-t*160))*np.exp(-t*12)
        body=np.sin(2*np.pi*(242*t+12*(1-np.exp(-t*5))))*.55
        air=self.filtered(self.rng.normal(size=len(t)),320,1350)*.22
        self.add((body+air)*env*amp,start,pan,'soft electronic route sweep')
        self.add((body+air)*env*amp*.11,start+.14,-pan,'diffuse route reflection')

    def impact(self,start,amp=.28,deep=False,pan=0):
        self.hit(start,amp,deep,pan)
        t=np.arange(round((1.8 if deep else .7)*SR))/SR
        phone_body=np.sin(2*np.pi*104*t)*np.exp(-t/(.3 if deep else .14))*(1-np.exp(-t*180))
        self.add(phone_body*amp*.19,start,pan,'restrained impact body')

    def build(self):
        self.music()
        self.impact(0,.30,True)
        self.whoosh(0,1.6,.23,-.10)
        self.impact(.4,.095,False,-.09)
        self.pulse(1.15,.050,-.08)
        self.passby(1.65,1.7)
        self.pulse(2.75,.032,.13)
        self.whoosh(4.0,1.1,.11,.08)
        self.impact(5.9,.09,False,.10)
        self.impact(7.1,.15,False,.10)
        self.whoosh(7.9,1.65,.24,-.1)
        self.impact(8.4,.11,False)
        self.pulse(8.7,.028,-.08)
        self.whoosh(9.7,1.5,.17,.08)
        self.pulse(10.15,.062,.06)
        self.passby(11.55,1.65)
        self.whoosh(12.75,2.0,.14,-.1)
        self.impact(14.25,.13,True,-.06)
        self.whoosh(14.1,1.8,.13,-.06)
        self.impact(16.3,.10,False,-.1)
        self.impact(17.2,.18,False,-.08)
        self.whoosh(18.0,1.45,.23)
        self.impact(19.3,.36,True)
        t=np.arange(len(self.audio))/SR
        self.audio*=np.clip((20-t)/.18,0,1)[:,None]**1.4
        peak=np.max(np.abs(self.audio));self.audio*=min(1,.86/peak)
        dest=ROOT/'assets/audio/v2';dest.mkdir(exist_ok=True)
        wavfile.write(dest/'score_raw.wav',SR,np.float32(self.audio))
        (dest/'cue_sheet.json').write_text(json.dumps(sorted(self.cues,key=lambda x:x['time']),indent=2))
        rms=[20*np.log10(max(np.sqrt(np.mean(self.audio[i*SR:(i+1)*SR]**2)),1e-12)) for i in range(20)]
        (dest/'waveform_analysis.json').write_text(json.dumps({'sample_rate':SR,'channels':2,'duration':20,'peak_dbfs':float(20*np.log10(np.max(np.abs(self.audio)))),'rms_dbfs_by_second':rms,'direct_listening':False},indent=2))
        print('Original v2 score generated; peak dBFS',20*np.log10(np.max(np.abs(self.audio))))

if __name__=='__main__':SoundEngine().build()
