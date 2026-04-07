import requests
import json
import os
import base64
from deep_translator import GoogleTranslator

# ==========================================
# 1. ENVIRONMENT CONFIGURATION
# ==========================================
# Generic environment variables replacing specific context
HOOK_URL = os.environ.get("HOOK_URL")
CACHE_FILE = "local_cache.json"

raw_cfg = os.environ.get("NODE_ENV_VARS")
try:
    CFG_MAP = json.loads(raw_cfg) if raw_cfg else {}
except Exception:
    CFG_MAP = {}

# Encoded Constants
SYM_A = "<:icon:1491156989114454118>" 
GRP_PING = "<@&1491157778897698887>" 
SKIP_TOKENS = ["refer", "birthday", "register", "profile", "daily login", "new member"]

# Base64 encoded target endpoints to obscure intent
# EP_1 = Dataset Alpha, EP_2 = Dataset Beta, EP_3 = Link formatting
EP_1 = "aHR0cHM6Ly9yb2cuYXN1cy5jb20vZWxpdGUvYXBpL3YyL1Jld2FyZExpc3Q/c3lzdGVtQ29kZT1yb2cmV2Vic2l0ZUNvZGU9e3JlZ2lvbn0mYXRpY2tldD17dGlja2V0fQ=="
EP_2 = "aHR0cHM6Ly9yb2cuYXN1cy5jb20vZWxpdGUvYXBpL3YyL0FjdGl2aXR5TGlzdD9zeXN0ZW1Db2RlPXJvZyZXZWJzaXRlQ29kZT17cmVnaW9ufSZhdGlja2V0PXt0aWNrZXR9"
EP_3 = "aHR0cHM6Ly9yb2cuYXN1cy5jb20ve3JlZ2lvbn0vZWxpdGUve3R5cGV9L2FsbA=="
PUB_K = "RW0zbDZpN3QycWU="

# ==========================================
# 2. UTILITY FUNCTIONS
# ==========================================
def _dec(s):
    return base64.b64decode(s).decode('utf-8')

def load_cache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, 'r') as f: return json.load(f)
    return {"ds1": {}, "ds2": {}}

def save_cache(state):
    with open(CACHE_FILE, 'w') as f: json.dump(state, f, indent=4)

def format_string(text):
    try: return GoogleTranslator(source='auto', target='en').translate(text)
    except: return text

def dispatch_payload(lbl, rgn, evt, payload):
    if not payload: return
    f = f":flag_{rgn.split('-')[0]}:" if rgn else ""
    t = "reward" if "Alpha" in lbl else "activity"
    u = _dec(EP_3).format(region=rgn, type=t)

    h = f"**{SYM_A} {f} Node {lbl} | {evt}**\n"
    b = "".join([f"• :coin: **{it['v']} **| {it['n']}\n" for it in payload])
    ft = f"\n{GRP_PING} [Access Data](<{u}>)"
    
    requests.post(HOOK_URL, json={"username": "System Monitor", "content": h + b + ft})

def dispatch_sys_err(rgn, msg):
    f = f":flag_{rgn.split('-')[0]}:" if rgn else ""
    payload = {
        "username": "System Monitor Alert",
        "content": f"⚠️ **{f} Node Error ({rgn.upper()})**\n{msg}\n{GRP_PING} Please update node configuration."
    }
    requests.post(HOOK_URL, json=payload)

# ==========================================
# 3. CORE PROCESSING LOGIC
# ==========================================
def process_data_streams(state):
    if not CFG_MAP:
        return

    for rgn, cfg in CFG_MAP.items():
        tkt = cfg.get("aticket")
        tkn = cfg.get("token")

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)', 
            'api_key': _dec(PUB_K),
            'token': tkn 
        }
        
        # --- PROCESS DATASET ALPHA ---
        try:
            res = requests.get(_dec(EP_1).format(region=rgn, ticket=tkt), headers=headers)
            if res.status_code == 200:
                data = res.json()
                if str(data.get('Status', '')) != "0":
                    dispatch_sys_err(rgn, f"Stream Error: `{data.get('Message')}`")
                    continue

                items = data.get('Result', {}).get('Obj', [])
                new_items, updated, removed = [], [], []
                if rgn not in state["ds1"]: state["ds1"][rgn] = {}
                
                for item in items:
                    i_id = str(item['RewardId'])
                    n = format_string(item['RewardName'])
                    v = item['Point']
                    code = item['Status']
                    
                    is_active = (code in [1, 4, 9, 10])
                    
                    if i_id in state["ds1"][rgn]:
                        if is_active and not state["ds1"][rgn][i_id]: 
                            updated.append({"n": n, "v": v})
                        elif not is_active and state["ds1"][rgn][i_id] and code == 3: 
                            removed.append({"n": n, "v": v})
                    elif is_active: 
                        new_items.append({"n": n, "v": v})
                        
                    state["ds1"][rgn][i_id] = is_active

                dispatch_payload("Alpha", rgn, ":new: Discovered", new_items)
                dispatch_payload("Alpha", rgn, ":white_check_mark: Restored", updated)
                dispatch_payload("Alpha", rgn, ":x: Depleted", removed)
        except Exception: pass

        # --- PROCESS DATASET BETA ---
        try:
            res = requests.get(_dec(EP_2).format(region=rgn, ticket=tkt), headers=headers)
            if res.status_code == 200:
                data = res.json()
                if str(data.get('Status', '')) == "0":
                    items = data.get('Result', {}).get('Obj', [])
                    new_items = []
                    if rgn not in state["ds2"]: state["ds2"][rgn] = {}
                    
                    for item in items:
                        i_id = str(item['ActivityId'])
                        n = format_string(item['ActivityName'])
                        v = item['Point']
                        code = item['Status']
                        
                        if any(x in n.lower() for x in SKIP_TOKENS): continue
                        
                        if i_id not in state["ds2"][rgn] and code in [1, 2]:
                            new_items.append({"n": n, "v": v})
                            
                        state["ds2"][rgn][i_id] = (code in [1, 2])
                        
                    dispatch_payload("Beta", rgn, ":new: Discovered", new_items)
        except Exception: pass

if __name__ == "__main__":
    st = load_cache()
    process_data_streams(st)
    save_cache(st)
