"""Reader B on Kaggle: Meta's open-weight Muse Glimmer 30B reads plate photos.

Runs on Kaggle's free 2x T4 GPUs. Builds llama.cpp with CUDA, downloads Meta's
official 4-bit GGUF and vision projector, serves them with llama-server, and
reads every photo in the private dataset copyninja02/tula-plates.

Writes /kaggle/working/glimmer_reads.jsonl (one line per photo) as it goes, so a
run that stops early still keeps what it read.

LIMIT = 0 reads everything; a small number does a smoke test on the first
photos of each set. Prompt and schema match src/tula/muse.py (Reader B).
"""
import base64
import csv
import glob
import json
import os
import subprocess
import time
import urllib.request

LIMIT = 0  # per set; 0 = all
PARALLEL = 4  # photos read at once (llama-server slots)

REPO = "meta-models/Muse-Glimmer-30B-GGUF"
MODEL_FILE = "Muse-Glimmer-30B-KQuant-17GB-Q4_K_M.gguf"
MMPROJ_FILE = "mmproj-Muse-Glimmer-30B-Q4_K_M.gguf"
OUT = "/kaggle/working/glimmer_reads.jsonl"
URL = "http://127.0.0.1:8080"

PLATE_STYLES = ["single_line", "two_line", "hand_painted", "high_security", "other", "unknown"]
VEHICLE_TYPES = ["two_wheeler", "three_wheeler", "car", "suv", "van", "bus", "truck", "other", "unknown"]
SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["plate_readable", "plate_text", "plate_confidence", "plate_style",
                 "state_code", "vehicle_type", "make", "colour", "image_issues"],
    "properties": {
        "plate_readable": {"type": "boolean"},
        "plate_text": {"type": ["string", "null"]},
        "plate_confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "plate_style": {"type": "string", "enum": PLATE_STYLES},
        "state_code": {"type": ["string", "null"]},
        "vehicle_type": {"type": "string", "enum": VEHICLE_TYPES},
        "make": {"type": ["string", "null"]},
        "colour": {"type": ["string", "null"]},
        "image_issues": {"type": "array", "items": {"type": "string"}},
    },
}
# Meta's model card: Glimmer always reasons first; strength is set in the system prompt.
REASONING = "low"
SYSTEM_PROMPT = (
    f"Reasoning strength: {REASONING}\n"
    "You are Reader B in a toll-billing safety system. You read Indian number "
    "plates from camera images. A wrong read can bill an innocent person, so "
    "never guess: if a character is not clearly visible, set plate_readable to "
    "false, plate_text to null and lower plate_confidence. Write plate_text in "
    "upper case with no spaces (e.g. KA01AB1234). state_code is the first two "
    "letters of the plate. Use null for anything you cannot see. List problems "
    "such as blur, glare, night, rain, fog, occlusion or tilt in image_issues. "
    "Reply with JSON only, matching the given schema."
)
USER_PROMPT = "Read this vehicle's number plate and describe the vehicle."


def sh(cmd):
    print("$", cmd, flush=True)
    subprocess.run(cmd, shell=True, check=True)


def setup():
    sh("nvidia-smi --query-gpu=name,memory.total --format=csv")
    saved = glob.glob("/kaggle/input/**/llama_bin.tgz", recursive=True)
    if saved:
        sh(f"mkdir -p /tmp/llama.cpp/build && tar -xzf {saved[0]} -C /tmp/llama.cpp/build")
        ok = subprocess.run("cd /tmp/llama.cpp/build/bin && LD_LIBRARY_PATH=. ./llama-server --version",
                            shell=True).returncode == 0
        if not ok:
            print("saved engine does not run here; rebuilding", flush=True)
            sh("rm -rf /tmp/llama.cpp")
    if not os.path.exists("/tmp/llama.cpp/build/bin/llama-server"):
        # Kaggle images keep CUDA under /usr/local/cuda; libcuda for linking is in stubs/.
        cuda = next((p for p in sorted(glob.glob("/usr/local/cuda*"), reverse=True)
                     if os.path.exists(p + "/bin/nvcc")), "/usr/local/cuda")
        os.environ["PATH"] = cuda + "/bin:" + os.environ["PATH"]
        os.environ["CUDACXX"] = cuda + "/bin/nvcc"
        # The stubs folder is empty on Kaggle's CUDA 13 image, so link against the
        # real driver library, and turn off VMM (the only part that needs it).
        sh("mkdir -p /tmp/cudalib && L=$(ls /usr/lib/x86_64-linux-gnu/libcuda.so* /usr/local/nvidia/lib64/libcuda.so* "
           "2>/dev/null | head -1) && echo libcuda: $L && ln -sf $L /tmp/cudalib/libcuda.so || echo no libcuda found")
        sh("nvcc --version | tail -1")
        sh("git clone --depth 1 https://github.com/ggml-org/llama.cpp /tmp/llama.cpp")
        try:
            sh(f"cd /tmp/llama.cpp && cmake -B build -DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES=75 "
               f"-DGGML_CUDA_NO_VMM=ON -DCUDAToolkit_ROOT={cuda} -DCMAKE_LIBRARY_PATH=/tmp/cudalib "
               f"-DLLAMA_CURL=OFF -DLLAMA_BUILD_TESTS=OFF -DCMAKE_BUILD_TYPE=Release > /tmp/cmake.log 2>&1")
            sh("cd /tmp/llama.cpp && cmake --build build --target llama-server -j 4 > /tmp/build.log 2>&1")
        except Exception:
            sh("tail -40 /tmp/cmake.log; tail -40 /tmp/build.log 2>/dev/null || true")
            raise
        sh("cd /tmp/llama.cpp/build && tar -czf /kaggle/working/llama_bin.tgz bin")
    sh("pip install -q -U huggingface_hub")
    from huggingface_hub import hf_hub_download
    model = hf_hub_download(REPO, MODEL_FILE, local_dir="/tmp/models")
    mmproj = hf_hub_download(REPO, MMPROJ_FILE, local_dir="/tmp/models")
    log = open("/kaggle/working/llama_server.log", "w")
    subprocess.Popen(
        ["/tmp/llama.cpp/build/bin/llama-server", "-m", model, "--mmproj", mmproj,
         "-ngl", "99", "-c", "16384", "--port", "8080", "--jinja", "--split-mode", "layer"],
        stdout=log, stderr=subprocess.STDOUT,
        env={**os.environ, "LD_LIBRARY_PATH": "/tmp/llama.cpp/build/bin:" + os.environ.get("LD_LIBRARY_PATH", "")})
    for _ in range(180):
        try:
            if urllib.request.urlopen(URL + "/health", timeout=5).status == 200:
                print("server ready", flush=True)
                return
        except Exception:
            pass
        time.sleep(5)
    raise RuntimeError("llama-server did not start; see llama_server.log")


def find_photo(rel):
    hits = glob.glob(f"/kaggle/input/**/{rel}", recursive=True)
    if not hits:
        raise FileNotFoundError(rel)
    return hits[0]


def ask(path, response_format):
    mime = "image/png" if path.endswith(".png") else "image/jpeg"
    data = base64.b64encode(open(path, "rb").read()).decode()
    body = {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": [
                {"type": "text", "text": USER_PROMPT},
                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{data}"}}]},
        ],
        # Meta's recommended sampling for Glimmer, with a fixed seed so runs repeat.
        "temperature": 1.0, "top_p": 0.95, "top_k": 64, "seed": 26,
        "max_tokens": 2500,
    }
    if response_format:
        body["response_format"] = response_format
    req = urllib.request.Request(URL + "/v1/chat/completions", json.dumps(body).encode(),
                                 {"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=600))


def parse(text):
    s, e = text.find("{"), text.rfind("}")
    return json.loads(text[s:e + 1])


def main():
    setup()
    manifest = glob.glob("/kaggle/input/**/manifest.csv", recursive=True)[0]
    rows = list(csv.DictReader(open(manifest)))
    if LIMIT:
        picked = []
        for s in ("foggy", "clear", "indian"):
            picked += [r for r in rows if r["set"] == s][:LIMIT]
        rows = picked
    # Resume: reads from an earlier run attached as a dataset are kept, not redone.
    earlier = glob.glob("/kaggle/input/**/glimmer_reads.jsonl", recursive=True)
    if earlier and not os.path.exists(OUT):
        with open(OUT, "w") as out:
            for path in earlier:
                out.writelines(l for l in open(path) if l.strip())
    done = set()
    if os.path.exists(OUT):
        done = {json.loads(l)["file"] for l in open(OUT)}
    formats = [("json_schema", {"type": "json_schema",
                                "json_schema": {"name": "plate_read", "schema": SCHEMA}}),
               ("json_object", {"type": "json_object"}), ("prompt_only", None)]
    todo = [r for r in rows if r["file"] not in done]

    def read_one(r):
        rec = dict(r)
        t0 = time.time()
        for mode, fmt in formats:
            try:
                resp = ask(find_photo(r["file"]), fmt)
                msg = resp["choices"][0]["message"]
                text = msg.get("content") or ""
                rec["raw"] = text[:1500]
                rec["reasoning_chars"] = len(msg.get("reasoning_content") or "")
                rec["reasoning"] = (msg.get("reasoning_content") or "")[:800]
                rec.update(read=parse(text), format_mode=mode, usage=resp.get("usage"),
                           model=resp.get("model"), error=None)
                break
            except Exception as exc:
                rec.update(read=None, format_mode=mode, error=f"{type(exc).__name__}: {exc}"[:300])
        rec["latency_s"] = round(time.time() - t0, 2)
        return rec

    # The server has 4 slots, so 4 photos are read at once.
    from concurrent.futures import ThreadPoolExecutor
    with open(OUT, "a") as out, ThreadPoolExecutor(PARALLEL) as pool:
        for i, rec in enumerate(pool.map(read_one, todo), 1):
            out.write(json.dumps(rec) + "\n")
            out.flush()
            got = (rec["read"] or {}).get("plate_text")
            print(f"{i}/{len(todo)} {rec['file']} truth={rec['truth']} glimmer={got} "
                  f"{rec['latency_s']}s {rec['error'] or ''}", flush=True)


if __name__ == "__main__":
    main()
