"""
타임캡슐 — 교실용 편지 앱
편지를 팻말에 걸어두면 나무가 자라고, 마지막 수업에 하나씩 열립니다.
반마다 날짜·코드·편지가 완전히 따로 굴러갑니다.
"""
import base64
import json
import random
from datetime import date, datetime
from pathlib import Path

import streamlit as st

# ─────────────────────────────────────────────────────────────
# 반 설정 — 여기만 바꾸면 됩니다
#
#   code  : 아이들이 입력하는 코드. 이 코드가 반을 알아서 찾아갑니다.
#           8개가 서로 겹치지 않게 하세요.
#   start : 편지 쓰는 날 (0주차)
#   open  : 마지막 수업 (개봉일)
#   cuts  : 그림이 바뀌는 주차. 생략하면 DEFAULT_CUTS 를 씁니다.
#           예) "6-1": {..., "cuts": (2, 4, 7)}
# ─────────────────────────────────────────────────────────────
DEFAULT_CUTS = (2, 5, 9)   # 0~1주 팻말만 / 2~4주 묘목 / 5~8주 자라는 중 / 9주~ 큰 나무

CLASSES = {
    "5-1": {"name": "5학년 1반", "code": "namu51", "start": date(2026, 9, 1), "open": date(2026, 12, 15)},
    "5-2": {"name": "5학년 2반", "code": "namu52", "start": date(2026, 9, 1), "open": date(2026, 12, 16)},
    "5-3": {"name": "5학년 3반", "code": "namu53", "start": date(2026, 9, 2), "open": date(2026, 12, 17)},
    "5-4": {"name": "5학년 4반", "code": "namu54", "start": date(2026, 9, 2), "open": date(2026, 12, 18)},
    "6-1": {"name": "6학년 1반", "code": "namu61", "start": date(2026, 9, 3), "open": date(2026, 12, 15)},
    "6-2": {"name": "6학년 2반", "code": "namu62", "start": date(2026, 9, 3), "open": date(2026, 12, 16)},
    "6-3": {"name": "6학년 3반", "code": "namu63", "start": date(2026, 9, 4), "open": date(2026, 12, 17)},
    "6-4": {"name": "6학년 4반", "code": "namu64", "start": date(2026, 9, 4), "open": date(2026, 12, 18)},
}

TEACHER_PIN = "0000"   # 배포 전에 반드시 바꾸세요. 이 코드로 들어가면 개봉 화면입니다.
MUSIC_FILE  = "music.mp3"

DATA_DIR = Path("data")
STATIC   = Path("static")

BG_FILE     = "base_wide.jpg"   # 나무 없는 하늘·언덕·팻말

# 나무는 배경에서 떼어낸 별도 레이어입니다. 그래야 바람에 흔들 수 있습니다.
# 값은 배경 그림 안에서의 위치(%)로, 원래 그려져 있던 자리 그대로입니다.
TREES = [
    None,
    {"f": "tree_s.webp", "left": 47.20, "top": 57.91, "w": 5.21,  "sway": 1.6, "dur": 4.5},
    {"f": "tree_m.webp", "left": 32.08, "top": 31.80, "w": 38.93, "sway": 0.9, "dur": 6.5},
    {"f": "tree_l.webp", "left": 29.02, "top": 19.25, "w": 42.00, "sway": 0.6, "dur": 8.0},
]
STAGE_LABEL = ["아직 아무것도", "묘목", "자라는 중", "큰 나무"]

# 꾸미기 아이템 — sky=하늘에 뜨는 것, ground=땅에 놓는 것
ITEMS = {
    "delphinium": {"label": "파란 꽃",  "zone": "ground", "w": 9},
    "poppy":      {"label": "주황 꽃",  "zone": "ground", "w": 11},
    "daisy":      {"label": "노란 꽃",  "zone": "ground", "w": 9},
    "clover":     {"label": "클로버",   "zone": "ground", "w": 6},
    "grass":      {"label": "풀과 돌",  "zone": "ground", "w": 20},
    "bush":       {"label": "덤불",     "zone": "ground", "w": 20},
    "butterfly":  {"label": "나비",     "zone": "sky",    "w": 8},
    "bird":       {"label": "새",       "zone": "sky",    "w": 11},
}

MAX_PER_STUDENT = 3   # 한 사람이 놓을 수 있는 개수


# ─────────────────────────────────────────────────────────────
# 반 조회
# ─────────────────────────────────────────────────────────────
def find_class_by_code(code):
    code = code.strip()
    for key, c in CLASSES.items():
        if code and code == c["code"]:
            return key
    return None


def cfg(key):
    return CLASSES[key]


def cuts(key):
    return cfg(key).get("cuts", DEFAULT_CUTS)


# ─────────────────────────────────────────────────────────────
# 저장소 — 반마다 별도 파일. 한 줄에 편지 하나씩 append.
# ─────────────────────────────────────────────────────────────
def data_file(key):
    return DATA_DIR / f"letters_{key}.jsonl"


def load_letters(key):
    path = data_file(key)
    if not path.exists():
        return []
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return out


def save_letter(key, record):
    DATA_DIR.mkdir(exist_ok=True)
    with open(data_file(key), "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def find_letter(key, number):
    for r in load_letters(key):
        if r["number"] == number:
            return r
    return None


# ─────────────────────────────────────────────────────────────
# 농장 꾸미기 — 추가만 하는 기록장(append-only)
#
# 지우기는 아이들도 할 수 있지만, 파일에서 줄이 사라지지는 않습니다.
# 지움도 하나의 기록으로 덧붙습니다. 그래서 언제든 되돌릴 수 있습니다.
# ─────────────────────────────────────────────────────────────
def garden_file(key):
    return DATA_DIR / f"garden_{key}.jsonl"


def garden_log(key):
    path = garden_file(key)
    if not path.exists():
        return []
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return out


def garden_append(key, event):
    DATA_DIR.mkdir(exist_ok=True)
    with open(garden_file(key), "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def garden_state(key, log=None):
    """기록을 처음부터 재생해서 지금 화면에 보일 것만 남깁니다."""
    placed = {}
    for e in (garden_log(key) if log is None else log):
        if e.get("op") == "add":
            placed[e["id"]] = e
        elif e.get("op") == "remove":
            placed.pop(e.get("id"), None)
    return list(placed.values())


def garden_place(key, number, item, x, y):
    # 같은 밀리초에 두 개를 놓으면 id가 겹쳐 하나가 사라집니다. 난수를 붙입니다.
    eid = f"{number}-{int(datetime.now().timestamp()*1000)}-{random.randrange(1<<24):06x}"
    garden_append(key, {
        "op": "add", "id": eid, "number": number, "item": item,
        "x": round(x, 1), "y": round(y, 1),
        "at": datetime.now().isoformat(timespec="seconds"),
    })
    return eid


def garden_remove(key, eid, by):
    garden_append(key, {
        "op": "remove", "id": eid, "by": by,
        "at": datetime.now().isoformat(timespec="seconds"),
    })


def garden_count(key, number):
    return sum(1 for e in garden_state(key) if e["number"] == number)


# ─────────────────────────────────────────────────────────────
# 성장 — 시작일로부터 몇 주가 지났는지로만 결정
# ─────────────────────────────────────────────────────────────
def weeks_elapsed(key):
    return max(0, (date.today() - cfg(key)["start"]).days // 7)


def stage_index(key):
    w = weeks_elapsed(key)
    for i, cut in enumerate(cuts(key)):
        if w < cut:
            return i
    return 3


def days_left(key):
    return max(0, (cfg(key)["open"] - date.today()).days)


@st.cache_data(show_spinner=False)
def asset_url(name):
    """그림을 data URI 로 직접 실어 보냅니다.

    Streamlit 정적 서빙(app/static/...)은 배포 환경에 따라 동작하지 않는
    경우가 있어, 설정에 의존하지 않는 이 방식을 씁니다.
    캐시가 걸려 있어 인코딩은 최초 1회만 일어납니다.
    """
    path = STATIC / name
    if not path.exists():
        return ""
    mime = {"jpg": "image/jpeg", "png": "image/png", "webp": "image/webp"}[name.rsplit(".", 1)[1]]
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode()


# ─────────────────────────────────────────────────────────────
# 스타일
# ─────────────────────────────────────────────────────────────
def inject_css(stage_file, intro=False):
    """intro=True 면 아이콘이 먼저 뜨고 배경이 뒤따라 번집니다."""
    bg = asset_url(stage_file)
    bg_anim = "animation: veilOut 2.0s ease-out 1.15s both;" if intro else "opacity: 0; display: none;"
    css = f"""
@import url('https://fonts.googleapis.com/css2?family=Gaegu:wght@400;700&family=Gowun+Dodum&display=swap');
  #MainMenu, footer, header {{visibility: hidden;}}
  .stApp {{
    --scene-bg: url("{bg}");
    background-image: var(--scene-bg);
    background-size: cover;
    background-position: center center;
    background-attachment: fixed;
    background-color: #f3ece2;
  }}
  [data-testid="stAppViewContainer"],
  [data-testid="stMain"],
  [data-testid="stHeader"],
  [data-testid="stBottomBlockContainer"],
  section.main,
  .main {{background: transparent !important;}}
  /* 시작 화면에서 배경을 잠시 덮었다가 걷히는 막 */
  .stApp::after {{
    content: "";
    position: fixed;
    inset: 0;
    background: #f3ece2;
    pointer-events: none;
    z-index: 0;
    {bg_anim}
  }}
  .block-container {{position: relative; z-index: 1;}}
  @keyframes veilOut {{from {{opacity: 1;}} to {{opacity: 0;}}}}

  /* 시작 화면 아이콘 */
  .icon-wrap {{text-align: center; margin: 0.4rem 0 1.2rem;}}
  .icon-wrap img {{
    width: 190px; max-width: 52vw; height: auto;
    filter: drop-shadow(0 10px 26px rgba(90,70,40,0.22));
    animation: iconIn 1.15s cubic-bezier(.2,.7,.3,1) both;
  }}
  @keyframes iconIn {{
    from {{opacity: 0; transform: scale(0.86) translateY(10px);}}
    to   {{opacity: 1; transform: scale(1) translateY(0);}}
  }}
  .intro-late {{animation: lateIn 1.4s ease-out 1.5s both;}}
  @keyframes lateIn {{from {{opacity: 0;}} to {{opacity: 1;}}}}

  @media (prefers-reduced-motion: reduce) {{
    .stApp::after {{animation: none !important; opacity: 0 !important;}}
    .icon-wrap img, .intro-late {{animation: none !important; opacity: 1 !important;}}
  }}

  .block-container {{max-width: 620px; padding-top: 2.2rem; padding-bottom: 4rem;}}

  html, body, [class*="css"], .stMarkdown, p, div, label, input, textarea {{
    font-family: 'Gowun Dodum', sans-serif;
  }}

  .sky-title {{
    font-family: 'Gaegu', cursive; font-size: 2.5rem; font-weight: 700;
    color: #4a6b3f; text-align: center; letter-spacing: 0.04em;
    text-shadow: 0 2px 12px rgba(255,255,255,0.9); margin-bottom: 0.1rem;
  }}
  .sky-sub {{
    text-align: center; color: #6e7f6a; font-size: 0.95rem;
    text-shadow: 0 1px 8px rgba(255,255,255,0.9); margin-bottom: 1.6rem;
  }}

  .paper {{
    background: rgba(253, 249, 240, 0.93);
    border: 1px solid rgba(139,111,78,0.28); border-radius: 3px;
    padding: 1.5rem 1.6rem; box-shadow: 0 8px 28px rgba(90,70,40,0.16);
    animation: rise 0.7s ease-out;
  }}
  @keyframes rise {{
    from {{opacity: 0; transform: translateY(14px);}}
    to   {{opacity: 1; transform: translateY(0);}}
  }}
  @media (prefers-reduced-motion: reduce) {{ .paper {{animation: none;}} }}

  .letter-body {{
    font-family: 'Gaegu', cursive; font-size: 1.35rem; line-height: 1.95;
    color: #3f3a33; white-space: pre-wrap; word-break: break-word;
  }}
  .letter-from {{
    font-family: 'Gaegu', cursive; font-size: 1.15rem;
    color: #8b6f4e; text-align: right; margin-top: 1.2rem;
  }}
  .meta {{
    font-size: 0.82rem; color: #9a9184;
    border-top: 1px dashed rgba(139,111,78,0.3);
    padding-top: 0.7rem; margin-top: 1.1rem;
  }}
  .badge {{
    display: inline-block; background: rgba(253,249,240,0.9);
    border: 1px solid rgba(139,111,78,0.25); border-radius: 999px;
    padding: 0.35rem 1rem; font-size: 0.9rem; color: #5c6b4f;
  }}
  .center {{text-align: center;}}

  .stButton > button {{
    background: #7d9b5e; color: #fff; border: none; border-radius: 4px;
    padding: 0.55rem 1.4rem; font-family: 'Gowun Dodum', sans-serif;
  }}
  .stButton > button:hover {{background: #6b8850; color: #fff;}}
  .stButton > button:focus-visible {{outline: 3px solid #f2c25c; outline-offset: 2px;}}

  .stTextInput input, .stTextArea textarea {{
    background: rgba(253,249,240,0.95); border: 1px solid rgba(139,111,78,0.3);
  }}
  .stTextArea textarea {{font-family: 'Gaegu', cursive; font-size: 1.25rem; line-height: 1.9;}}
  /* 농장 배경 — 화면 전체 */
  .backdrop {{
    position: fixed; inset: 0; z-index: 0;
    pointer-events: none; overflow: hidden;
  }}
  .backdrop img {{position: absolute;}}
  .tree {{
    transform-origin: 50% 100%;
    filter: drop-shadow(0 4px 8px rgba(90,70,40,0.10));
    animation-name: treeSway;
    animation-iteration-count: infinite;
    animation-timing-function: ease-in-out;
  }}
  @keyframes treeSway {{
    0%, 100% {{transform: rotate(calc(var(--sway) * -1));}}
    50%      {{transform: rotate(var(--sway));}}
  }}
  .deco {{
    transform-origin: 50% 100%;
    transform: translate(-50%, -100%);
    filter: drop-shadow(0 3px 5px rgba(90,70,40,0.18));
    animation-iteration-count: infinite;
    animation-timing-function: ease-in-out;
  }}
  .deco.swayA {{animation-name: swayA;}}
  .deco.flyA {{animation-name: flyA; transform-origin: 50% 50%;}}
  @keyframes swayA {{
    0%, 100% {{transform: translate(-50%, -100%) rotate(-2.2deg);}}
    50%      {{transform: translate(-50%, -100%) rotate(2.2deg);}}
  }}
  @keyframes flyA {{
    0%, 100% {{transform: translate(-50%, -50%) translate(0, 0) rotate(-3deg);}}
    50%      {{transform: translate(-50%, -50%) translate(16px, -12px) rotate(3deg);}}
  }}
  .ghost {{opacity: 0.55;}}
  @media (prefers-reduced-motion: reduce) {{
    .deco, .tree {{animation: none !important;}}
  }}
"""
    # 빈 줄이 하나라도 있으면 Streamlit 마크다운이 HTML 블록을 끊어버려
    # 나머지 CSS가 화면에 글자로 찍힙니다. 반드시 전부 제거합니다.
    css = "".join(line.strip() + " " for line in css.splitlines() if line.strip())
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def play_music():
    """음악을 자동 재생하고 재생기는 화면에서 감춥니다.

    브라우저는 사용자가 한 번이라도 클릭한 뒤에야 소리를 허용합니다.
    시작 화면에서 '들어가기'를 누르는 순간 그 조건이 충족되므로,
    그 이후 화면에서는 자동 재생이 걸립니다.
    시작 화면에는 음악을 넣지 않습니다.
    """
    music = STATIC / MUSIC_FILE
    if not music.exists():
        return
    st.markdown(
        '<style>[data-testid="stAudio"]{position:absolute;width:1px;height:1px;'
        'opacity:0;pointer-events:none;}</style>',
        unsafe_allow_html=True,
    )
    try:
        st.audio(str(music), loop=True, autoplay=True)
    except TypeError:
        st.audio(str(music))   # 구버전 Streamlit


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render_backdrop(key, extra=None, stage=None):
    """화면 전체를 그 반의 농장으로 만듭니다.

    배경 그림(나무 없음) 위에 나무 레이어와 꾸민 것들을 얹습니다.
    나무를 따로 떼어냈기 때문에 바람에 흔들 수 있습니다.
    """
    layers = []

    idx = stage if stage is not None else stage_index(key)
    t = TREES[idx]
    if t:
        layers.append(
            f'<img class="tree" src="{asset_url(t["f"])}" '
            f'style="left:{t["left"]}%;top:{t["top"]}%;width:{t["w"]}%;'
            f'--sway:{t["sway"]}deg;animation-duration:{t["dur"]}s;" alt="">'
        )

    items = garden_state(key)
    if extra:
        items = items + [extra]
    for i, e in enumerate(items):
        meta = ITEMS.get(e["item"])
        if not meta:
            continue
        scale = 0.75 + (e["y"] / 100) * 0.55          # 아래쪽일수록 가깝게 = 크게
        w = meta["w"] * scale
        cls = "flyA" if meta["zone"] == "sky" else "swayA"
        ghost = " ghost" if e.get("id") == "_preview" else ""
        layers.append(
            f'<img class="deco {cls}{ghost}" src="{asset_url("items/" + e["item"] + ".webp")}" '
            f'style="left:{e["x"]}%;top:{e["y"]}%;width:{w:.1f}%;'
            f'animation-duration:{3.2 + (i % 5) * 0.7:.1f}s;'
            f'animation-delay:{(i % 7) * 0.4:.1f}s;" alt="">'
        )

    st.markdown(f'<div class="backdrop">{"".join(layers)}</div>', unsafe_allow_html=True)
    return items


def printable_html(key, letters):
    """서버가 사라져도 남는 사본. 브라우저에서 열어 PDF로 인쇄하세요."""
    c = cfg(key)
    parts = []
    for r in sorted(letters, key=lambda x: int(x["number"])):
        w = datetime.fromisoformat(r["written_at"]).date()
        parts.append(
            f"<article><h2>{r['number']}번 {esc(r['nickname'])}</h2>"
            f"<p>{esc(r['body'])}</p>"
            f"<small>{w.year}. {w.month}. {w.day}</small></article>"
        )
    return f"""<!doctype html><html lang="ko"><meta charset="utf-8">
<title>타임캡슐 — {c['name']}</title>
<style>
 body{{font-family:sans-serif;max-width:640px;margin:3rem auto;padding:0 1.5rem;color:#333;}}
 h1{{font-size:1.6rem;border-bottom:2px solid #7d9b5e;padding-bottom:.6rem;}}
 article{{page-break-inside:avoid;margin:2.4rem 0;border-left:3px solid #d8ddc9;padding-left:1.2rem;}}
 h2{{font-size:1.1rem;color:#5c6b4f;margin-bottom:.6rem;}}
 p{{white-space:pre-wrap;line-height:1.9;}}
 small{{color:#999;}}
</style>
<h1>타임캡슐 — {c['name']}</h1>
<p>{c['start']} 에 맡기고 {c['open']} 에 열었습니다. 모두 {len(letters)}통.</p>
{''.join(parts)}
</html>"""


# ─────────────────────────────────────────────────────────────
# 화면 1 — 편지 쓰기
# ─────────────────────────────────────────────────────────────
def page_write(key):
    c = cfg(key)
    st.markdown('<div class="sky-title">타임캡슐</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="sky-sub">{c["name"]} · {c["open"].month}월 {c["open"].day}일에 열립니다</div>',
        unsafe_allow_html=True,
    )

    if date.today() > c["open"]:
        st.markdown('<div class="paper center">편지 쓰는 기간이 끝났어요.</div>', unsafe_allow_html=True)
        return

    number = st.text_input("번호", max_chars=2, placeholder="예: 7", key=f"w_num_{key}")
    nickname = st.text_input("이름 또는 별명", max_chars=12, placeholder="편지 아래에 적힐 이름", key=f"w_nick_{key}")
    body = st.text_area(
        "그날의 나에게",
        height=260, max_chars=1200,
        placeholder="지금 무슨 생각을 하고 있는지, 그때는 어떤 사람이 되어 있길 바라는지 써 보세요.",
        key=f"w_body_{key}",
    )

    st.caption("한 번 넣으면 개봉일까지 열 수 없어요. 선생님은 관리를 위해 내용을 볼 수 있습니다.")

    if st.button("팻말에 걸기", key=f"w_btn_{key}"):
        num = number.strip()
        if not num.isdigit():
            st.error("번호는 숫자로 적어 주세요.")
            return
        if not nickname.strip():
            st.error("이름 또는 별명을 적어 주세요.")
            return
        if len(body.strip()) < 20:
            st.error("편지가 너무 짧아요. 20자 이상 써 주세요.")
            return
        if find_letter(key, num):
            st.error(f"{num}번은 이미 편지를 넣었어요. '내 나무 보기'에서 확인할 수 있어요.")
            return

        save_letter(key, {
            "number": num,
            "nickname": nickname.strip(),
            "body": body.strip(),
            "written_at": datetime.now().isoformat(timespec="seconds"),
        })
        st.session_state.just_saved = num
        st.rerun()


# ─────────────────────────────────────────────────────────────
# 화면 2 — 내 나무 보기
# ─────────────────────────────────────────────────────────────
def page_tree(key):
    """우리 농장 — 배경을 보고, 꽃을 놓고, 자기가 놓은 것은 치울 수 있습니다."""
    c = cfg(key)
    st.markdown(
        f'<div class="sky-sub">{c["name"]} · {weeks_elapsed(key)}주차 · '
        f'{STAGE_LABEL[stage_index(key)]} · 개봉까지 {days_left(key)}일</div>',
        unsafe_allow_html=True,
    )

    number = st.text_input("번호", max_chars=2, placeholder="예: 7", key=f"t_num_{key}").strip()

    # 미리보기용 임시 배치 — 배경에 흐리게 얹힙니다
    preview = None
    if number.isdigit():
        item = st.session_state.get(f"g_item_{key}")
        if item:
            preview = {
                "id": "_preview", "number": number, "item": item,
                "x": st.session_state.get(f"g_x_{key}", 50),
                "y": st.session_state.get(f"g_y_{key}", 80),
            }
    st.session_state["_preview"] = preview

    if not number.isdigit():
        st.caption("번호를 넣으면 꽃을 놓을 수 있어요.")
        return

    rec = find_letter(key, number)
    if rec:
        written = datetime.fromisoformat(rec["written_at"]).date()
        st.markdown(
            f'<div class="center" style="margin:0.8rem 0;"><span class="badge">'
            f'{esc(rec["nickname"])}의 편지는 잘 있어요 · {(date.today()-written).days}일째'
            f'</span></div>',
            unsafe_allow_html=True,
        )

    mine = garden_count(key, number)
    st.markdown(f"**꾸미기** — {mine}/{MAX_PER_STUDENT}개 놓았어요")

    if mine < MAX_PER_STUDENT:
        names = list(ITEMS.keys())
        labels = [ITEMS[i]["label"] for i in names]
        picked = st.selectbox("무엇을 놓을까요", labels, key=f"g_sel_{key}")
        st.session_state[f"g_item_{key}"] = names[labels.index(picked)]

        zone = ITEMS[st.session_state[f"g_item_{key}"]]["zone"]
        st.slider("왼쪽 ↔ 오른쪽", 5, 95, key=f"g_x_{key}",
                  value=st.session_state.get(f"g_x_{key}", 50))
        if zone == "ground":
            st.slider("뒤쪽 ↔ 앞쪽", 68, 96, key=f"g_y_{key}",
                      value=st.session_state.get(f"g_y_{key}", 82))
        else:
            st.slider("낮게 ↔ 높게", 20, 60, key=f"g_y_{key}",
                      value=st.session_state.get(f"g_y_{key}", 42))

        if st.button("여기에 놓기", key=f"g_put_{key}"):
            garden_place(key, number,
                         st.session_state[f"g_item_{key}"],
                         st.session_state[f"g_x_{key}"],
                         st.session_state[f"g_y_{key}"])
            st.rerun()
    else:
        st.caption(f"한 사람이 {MAX_PER_STUDENT}개까지 놓을 수 있어요. 하나를 치우면 다시 놓을 수 있어요.")

    # 자기가 놓은 것만 치울 수 있습니다
    own = [e for e in garden_state(key) if e["number"] == number]
    if own:
        st.markdown("**내가 놓은 것**")
        for e in own:
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown(f'<span class="badge">{ITEMS[e["item"]]["label"]}</span>',
                            unsafe_allow_html=True)
            with col2:
                if st.button("치우기", key=f"g_del_{e['id']}"):
                    garden_remove(key, e["id"], by=number)
                    st.rerun()
        st.caption("치워도 기록은 남아서 선생님이 되돌릴 수 있어요.")

    st.markdown(
        f'<div class="center" style="margin-top:1.2rem;"><span class="badge">'
        f'{c["name"]} 편지 {len(load_letters(key))}통 · 꾸민 것 {len(garden_state(key))}개'
        f'</span></div>',
        unsafe_allow_html=True,
    )


# ─────────────────────────────────────────────────────────────
# 화면 3 — 개봉 (교사용)
# ─────────────────────────────────────────────────────────────
def page_open():
    keys = list(CLASSES.keys())
    labels = [CLASSES[k]["name"] for k in keys]
    picked = st.selectbox("반", labels, key="open_class")
    key = keys[labels.index(picked)]

    # 반을 바꾸면 진행 상태 초기화
    if st.session_state.get("open_key") != key:
        st.session_state.open_key = key
        st.session_state.pop("order", None)
        st.session_state.idx = -1

    c = cfg(key)
    # 개봉 화면 배경 = 그 반이 꾸민 농장. 나무는 다 자란 모습으로 고정합니다.
    render_backdrop(key, stage=3)

    letters = load_letters(key)
    if not letters:
        st.markdown(f'<div class="paper center">{c["name"]}은 아직 편지가 없어요.</div>', unsafe_allow_html=True)
        return

    if "order" not in st.session_state:
        order = list(range(len(letters)))
        random.shuffle(order)
        st.session_state.order = order

    order = st.session_state.order
    idx = st.session_state.get("idx", -1)

    play_music()

    if idx < 0:
        st.markdown('<div class="sky-title">타임캡슐이 열립니다</div>', unsafe_allow_html=True)
        st.markdown(
            f'<div class="sky-sub">{c["name"]} · {len(letters)}통의 편지 · {weeks_elapsed(key)}주 만에</div>',
            unsafe_allow_html=True,
        )
        if st.button("첫 번째 편지 열기"):
            st.session_state.idx = 0
            st.rerun()
        st.download_button(
            "인쇄용으로 내려받기",
            data=printable_html(key, letters),
            file_name=f"타임캡슐_{c['name']}_{c['open']}.html",
            mime="text/html",
        )

        # 치운 것 되돌리기 — 기록이 전부 남아 있어 복구할 수 있습니다
        removed = [e for e in garden_log(key) if e.get("op") == "remove"]
        if removed:
            with st.expander(f"치워진 것 되돌리기 ({len(removed)}개 기록)"):
                state_ids = {e["id"] for e in garden_state(key)}
                adds = {e["id"]: e for e in garden_log(key) if e.get("op") == "add"}
                for r in reversed(removed[-20:]):
                    a = adds.get(r["id"])
                    if not a or a["id"] in state_ids:
                        continue
                    lbl = ITEMS.get(a["item"], {}).get("label", a["item"])
                    if st.button(f"{a['number']}번의 {lbl} 되돌리기", key=f"undo_{r['id']}"):
                        garden_append(key, dict(a, at=datetime.now().isoformat(timespec="seconds")))
                        st.rerun()
        return

    if idx >= len(order):
        st.markdown('<div class="sky-title">여기까지</div>', unsafe_allow_html=True)
        st.markdown('<div class="paper center letter-body">모두 잘 자랐습니다.</div>', unsafe_allow_html=True)
        return

    rec = letters[order[idx]]
    written = datetime.fromisoformat(rec["written_at"]).date()
    st.markdown(f'<div class="sky-sub">{idx+1} / {len(order)}</div>', unsafe_allow_html=True)
    st.markdown(
        f"""
<div class="paper">
  <div class="letter-body">{esc(rec['body'])}</div>
  <div class="letter-from">— {esc(rec['nickname'])}</div>
  <div class="meta">{written.year}. {written.month}. {written.day}에 쓴 편지</div>
</div>
""",
        unsafe_allow_html=True,
    )

    if st.button("다음 편지" if idx + 1 < len(order) else "마치기"):
        st.session_state.idx = idx + 1
        st.rerun()


# ─────────────────────────────────────────────────────────────
# 메인
# ─────────────────────────────────────────────────────────────
def main():
    st.set_page_config(page_title="타임캡슐", page_icon="🌳", layout="centered")

    key = st.session_state.get("cls")
    teacher = st.session_state.get("teacher", False)

    at_start = not key and not teacher

    inject_css(BG_FILE, intro=at_start)

    # 시작 화면 — 아이콘이 먼저 뜨고 배경이 뒤따릅니다
    if at_start:
        st.markdown(
            f'<div class="icon-wrap"><img src="{asset_url("icon.webp")}" alt=""></div>',
            unsafe_allow_html=True,
        )
        st.markdown('<div class="sky-title intro-late">타임캡슐</div>', unsafe_allow_html=True)
        st.markdown('<div class="sky-sub intro-late">선생님이 알려준 코드를 넣어 주세요</div>', unsafe_allow_html=True)
        code = st.text_input("반 코드", type="password")
        if st.button("들어가기"):
            found = find_class_by_code(code)
            if found:
                st.session_state.cls = found
                st.rerun()
            elif code.strip() == TEACHER_PIN:
                st.session_state.teacher = True
                st.rerun()
            else:
                st.error("코드가 맞지 않아요.")
        return

    if teacher:
        page_open()
        return

    render_backdrop(key, extra=st.session_state.get("_preview"))

    if st.session_state.get("just_saved"):
        num = st.session_state.pop("just_saved")
        c = cfg(key)
        st.markdown('<div class="sky-title">잘 걸었어요</div>', unsafe_allow_html=True)
        st.markdown(
            f"""
<div class="paper center">
  <div class="letter-body">{num}번의 편지를 팻말에 걸었습니다.<br>
  나무가 자라는 동안 가끔 보러 오세요.</div>
  <div class="meta">{c['open'].year}. {c['open'].month}. {c['open'].day}에 열립니다 · {days_left(key)}일 남음</div>
</div>
""",
            unsafe_allow_html=True,
        )
        return

    play_music()
    tab1, tab2 = st.tabs(["편지 쓰기", "우리 농장"])
    with tab1:
        page_write(key)
    with tab2:
        page_tree(key)


if __name__ == "__main__":
    main()
