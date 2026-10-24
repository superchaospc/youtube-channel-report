"""How much of each video is shot from a locked-off camera (tripod / set down) vs a moving one.
Global shift between frames 0.2 s apart via phase correlation on a 240p copy; a 1-second window counts as
"static" when every step moves < 0.25 px and the match is confident. Scene cuts are skipped.
Usage: python3 static_cam.py VIDEO.mp4 ...  (needs opencv-python-headless; use the 240p copies frame_sample.py keeps in OUT/video/)
Prints one JSON line per video: {"id", "seconds", "static"}."""
import sys, json, cv2, numpy as np

def run(path):
    cap = cv2.VideoCapture(path); fps = cap.get(cv2.CAP_PROP_FPS) or 30
    step = max(1, round(fps * 0.2)); win = 5
    prev = None; shifts = []; i = 0
    while True:
        ok = cap.grab()
        if not ok: break
        if i % step == 0:
            ok, f = cap.retrieve()
            if not ok: break
            g = cv2.cvtColor(cv2.resize(f, (320, 180)), cv2.COLOR_BGR2GRAY).astype(np.float32)
            g = g[18:162, 16:304]   # drop burned-in subtitles and edges
            if prev is not None:
                (dx, dy), resp = cv2.phaseCorrelate(prev, g)
                diff = float(np.mean(np.abs(g - prev)))
                shifts.append((np.hypot(dx, dy), resp, diff))
            prev = g
        i += 1
    n = len(shifts) // win; static = moving = 0
    for k in range(n):
        w = shifts[k * win:(k + 1) * win]
        if any(d > 40 for _, _, d in w):      # a cut inside this second
            continue
        if all(s < 0.25 and r > 0.3 for s, r, _ in w): static += 1
        else: moving += 1
    tot = static + moving
    return {"id": path.split("/")[-1][:-4], "seconds": tot, "static": round(static / tot, 3) if tot else None}

for p in sys.argv[1:]:
    print(json.dumps(run(p)), flush=True)
