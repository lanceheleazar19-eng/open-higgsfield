import sys, time, os
sys.path.insert(0, "/home/user/acestep/src")
import torch
torch.set_num_threads(4)
from acestep.handler import AceStepHandler
from acestep.llm_inference import LLMHandler
from acestep.inference import GenerationParams, GenerationConfig, generate_music

DUR = float(sys.argv[1]) if len(sys.argv) > 1 else 30
LYRICS_FILE = sys.argv[2] if len(sys.argv) > 2 else "/home/user/acestep/lyrics_test.txt"
OUT = sys.argv[3] if len(sys.argv) > 3 else "/home/user/acestep/out"

t0 = time.time()
dit = AceStepHandler()
msg, ok = dit.initialize_service(project_root="/home/user/acestep", config_path="acestep-v15-turbo", device="cpu")
print(msg, ok, f"init {time.time()-t0:.0f}s", flush=True)
_orig = dit.tiled_decode
def _small_decode(latents, chunk_size=128, overlap=16, offload_wav_to_cpu=True):
    import gc
    dit.model = None; dit.text_encoder = None
    gc.collect()
    with torch.inference_mode():
        return _orig(latents, chunk_size=128, overlap=16, offload_wav_to_cpu=True)
dit.tiled_decode = _small_decode
llm = LLMHandler()  # not initialized: skip the language model planner on CPU

params = GenerationParams(
    caption=("tropical house pop, dancehall pop, chopped vocal synth hooks, plucky marimba synths, "
             "snappy claps, offbeat rhythm, warm deep bass, airy young male tenor vocals, smooth "
             "falsetto chorus, upbeat, catchy, radio pop 2016, Spanish lyrics"),
    lyrics=open(LYRICS_FILE).read(),
    vocal_language="es",
    bpm=100,
    keyscale="C minor",
    timesignature="4",
    duration=DUR,
    inference_steps=8,
    thinking=False,
    use_cot_metas=False, use_cot_caption=False, use_cot_language=False,
)
cfg = GenerationConfig(batch_size=1, audio_format="wav", use_random_seed=False, seeds=[42])
t1 = time.time()
res = generate_music(dit, llm, params, cfg, save_dir=OUT)
print("gen", f"{time.time()-t1:.0f}s", res.success, res.error, flush=True)
for a in res.audios:
    print("AUDIO", a["path"])
