import sys, numpy as np, librosa
y, sr = librosa.load(sys.argv[1], sr=22050, mono=True)
tempo, beats = librosa.beat.beat_track(y=y, sr=sr)
print("tempo", np.round(tempo,1))
onset_env = librosa.onset.onset_strength(y=y, sr=sr)
print("tempo candidates", np.round(librosa.feature.tempo(onset_envelope=onset_env, sr=sr, aggregate=None)[:1],1))
chroma = librosa.feature.chroma_cqt(y=librosa.effects.harmonic(y), sr=sr).mean(1)
names = ['C','C#','D','D#','E','F','F#','G','G#','A','A#','B']
maj = np.array([6.35,2.23,3.48,2.33,4.38,4.09,2.52,5.19,2.39,3.66,2.29,2.88]); mi = np.array([6.33,2.68,3.52,5.38,2.60,3.53,2.54,4.75,3.98,2.69,3.34,3.17])
sc = [(np.corrcoef(np.roll(maj,k),chroma)[0,1], names[k]+' major') for k in range(12)] + [(np.corrcoef(np.roll(mi,k),chroma)[0,1], names[k]+' minor') for k in range(12)]
print("key", sorted(sc)[-3:][::-1])
S = np.abs(librosa.stft(y)); f = librosa.fft_frequencies(sr=sr)
tot = S.sum()
for a,b in [(20,60),(60,150),(150,500),(500,2000),(2000,6000),(6000,11000)]:
    print(f"band {a}-{b}Hz {S[(f>=a)&(f<b)].sum()/tot*100:.1f}%")
print("centroid Hz", int(librosa.feature.spectral_centroid(y=y, sr=sr).mean()))
print("onsets/sec", round(len(librosa.onset.onset_detect(y=y, sr=sr))/(len(y)/sr),2))
rms = librosa.feature.rms(y=y)[0]; print("crest/dynamics dB", round(20*np.log10(np.percentile(rms,95)/np.percentile(rms,10)+1e-9),1))
print("peak", round(float(np.abs(y).max()),3), "clip% ", round(float((np.abs(y)>0.98).mean()*100),3))
seg = [round(float(np.sqrt(np.mean(y[i:i+sr*4]**2))),3) for i in range(0,len(y),sr*4)]
print("rms per 4s", seg)
h, p = librosa.effects.hpss(y); print("harmonic/percussive energy", round(float((h**2).sum()/(p**2).sum()),2))
