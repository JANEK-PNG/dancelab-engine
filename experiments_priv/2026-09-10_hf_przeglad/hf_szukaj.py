import json, urllib.parse, sys, time, subprocess
def api(kind, q, limit=30, extra=""):
    url = f"https://huggingface.co/api/{kind}?search={urllib.parse.quote(q)}&sort=downloads&direction=-1&limit={limit}{extra}"
    out = subprocess.run(["curl","-s","--max-time","40",url],capture_output=True,text=True).stdout
    return json.loads(out)
def lic(tags):
    return ",".join(t[8:] for t in tags if t.startswith("license:")) or "?"
seen=set()
print("=== MODELE ===")
for q in ["music", "clap", "mert", "muq", "music tagging", "beat tracking", "key detection", "demucs", "source separation", "music embedding", "audio embedding", "music genre", "bpm", "music2latent", "musicfm", "encodec", "dj"]:
    try: rows = api("models", q, 25)
    except Exception as e: print("!!", q, e); continue
    for m in rows:
        i = m["id"]
        if i in seen: continue
        seen.add(i)
        print(f"{m.get('downloads',0):>9} | {lic(m.get('tags',[])):<22} | {m.get('pipeline_tag','-'):<22} | {i}")
    time.sleep(0.3)
print("=== ZBIORY ===")
seen=set()
for q in ["music", "musiccaps", "fma", "jamendo", "gtzan", "musdb", "song describer", "electronic music", "techno", "dj mix", "beatport", "music genre", "million song", "discogs", "music tags", "audioset", "music4all", "disco-10m", "harmonic", "chords", "beat", "key"]:
    try: rows = api("datasets", q, 25)
    except Exception as e: print("!!", q, e); continue
    for d in rows:
        i = d["id"]
        if i in seen: continue
        seen.add(i)
        tags = d.get("tags",[])
        size = ",".join(t[15:] for t in tags if t.startswith("size_categories:"))
        print(f"{d.get('downloads',0):>8} | {lic(tags):<22} | {size:<10} | {i}")
    time.sleep(0.3)
