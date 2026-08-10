from __future__ import annotations

from datetime import datetime
from html import escape
from zoneinfo import ZoneInfo

import requests
import streamlit as st


st.set_page_config(page_title="경의중앙선 실시간 위치", page_icon="🚆", layout="wide")

SEOUL = ZoneInfo("Asia/Seoul")
LINE_NAME = "경의중앙선"
API_BASE = "http://swopenapi.seoul.go.kr/api/subway"
TRACK = ["중랑", "회기", "청량리", "왕십리"]
TARGET_UPDN_LINES = {"상행", "0"}
STATUS_LABELS = {"0": "진입", "1": "도착", "2": "출발", "3": "전역 출발"}
REFRESH_SECONDS = 5


def now() -> datetime:
    return datetime.now(SEOUL)


def secret_key() -> str:
    try:
        return str(st.secrets["TOPIS_API_KEY"])
    except (KeyError, FileNotFoundError):
        return ""


@st.cache_data(ttl=4, show_spinner=False)
def fetch_positions(api_key: str) -> tuple[list[dict], str | None]:
    url = f"{API_BASE}/{api_key}/json/realtimePosition/0/200/{LINE_NAME}"
    try:
        response = requests.get(url, timeout=8)
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError) as exc:
        return [], f"TOPIS 연결 실패: {exc}"

    error = payload.get("errorMessage", {})
    if error.get("status") and int(error.get("status")) != 200:
        return [], error.get("message", "API 오류가 발생했습니다.")
    return payload.get("realtimePositionList", []), None


def normalize_station(value: str) -> str:
    return (value or "").replace("역", "").strip()


def parse_api_time(value: str) -> datetime | None:
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y%m%d%H%M%S"):
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=SEOUL)
        except (TypeError, ValueError):
            pass
    return None


def is_wangsimni_bound(row: dict) -> bool:
    """중랑→회기→청량리→왕십리 방향인 상행 열차만 고른다."""
    direction = str(row.get("updnLine", "")).strip()
    return direction in TARGET_UPDN_LINES


def status_text(row: dict) -> str:
    raw = str(row.get("trainSttus", ""))
    return STATUS_LABELS.get(raw, raw or "상태 미상")


def train_label(row: dict) -> str:
    station = normalize_station(row.get("statnNm", "위치 미상"))
    return f'{row.get("trainNo", "번호 미상")}열차 · {station} {status_text(row)} · {row.get("statnTnm", "행선지 미상")}행'


def arrival_estimate(row: dict) -> tuple[str, str]:
    """실측 학습 전까지는 역 단계와 운행상태에 따른 범위만 보여준다."""
    station = normalize_station(row.get("statnNm", ""))
    state = str(row.get("trainSttus", ""))
    if station == "중랑":
        ranges = {"0": "약 3~5분", "1": "약 3~4분", "2": "약 2~3분", "3": "약 4~6분"}
        return ranges.get(state, "약 3~5분"), "중랑역 위치·운행상태 기반 임시 범위"
    if station == "회기":
        if state in {"0", "3"}:
            return "곧 도착", "회기역 진입 단계"
        if state == "1":
            return "현재 도착", "회기역 도착 단계"
        return "회기역 출발", "이미 회기역을 지난 열차"
    if station in {"청량리", "왕십리"}:
        return "이미 통과", f"현재 {station}역"
    return "계산 불가", "관측 구간 밖"


def record_minute_snapshot(rows: list[dict]) -> None:
    snapshots = st.session_state.setdefault("minute_snapshots", [])
    minute_key = now().strftime("%Y-%m-%d %H:%M")
    if snapshots and snapshots[-1]["minute_key"] == minute_key:
        return
    snapshots.append({
        "minute_key": minute_key,
        "time": now().strftime("%H:%M"),
        "trains": [
            {
                "train_no": str(row.get("trainNo", "-")),
                "station": normalize_station(row.get("statnNm", "위치 미상")),
                "status": status_text(row),
                "destination": str(row.get("statnTnm", "-")),
            }
            for row in rows
        ],
    })
    del snapshots[:-30]


def render_track(train: dict) -> None:
    station = normalize_station(train.get("statnNm", ""))
    index = TRACK.index(station) if station in TRACK else 0
    state = str(train.get("trainSttus", ""))
    offset = {"3": -0.20, "0": -0.08, "1": 0.0, "2": 0.16}.get(state, 0.0)
    position = min(100, max(0, ((index + offset) / (len(TRACK) - 1)) * 100))
    nodes = "".join(f'<div class="station"><span class="dot"></span><b>{escape(name)}</b></div>' for name in TRACK)
    st.markdown(
        f"""
        <style>
        .board {{background:#101722;border:1px solid #2c394a;border-radius:18px;padding:26px 24px 20px;color:#f4f7fb;box-shadow:0 12px 30px rgba(0,0,0,.18)}}
        .board-title {{font-size:.9rem;color:#9fb2c8;margin-bottom:28px;letter-spacing:.04em}}
        .track-wrap {{position:relative;margin:0 3% 10px;height:92px}}
        .rail {{position:absolute;top:37px;left:0;right:0;height:6px;border-radius:9px;background:repeating-linear-gradient(90deg,#728196 0 18px,#394759 18px 27px)}}
        .stations {{position:absolute;inset:25px 0 auto;display:flex;justify-content:space-between}}
        .station {{width:70px;text-align:center;font-size:.82rem;color:#d8e2ed;transform:translateX(0)}}
        .dot {{display:block;width:18px;height:18px;margin:4px auto 12px;border:4px solid #eef5fb;background:#182231;border-radius:50%;box-sizing:border-box}}
        .train {{position:absolute;top:0;left:calc({position:.2f}% - 25px);width:50px;height:29px;border-radius:8px 8px 5px 5px;background:#f7fafc;border-bottom:6px solid #52a96b;box-shadow:0 0 18px rgba(255,255,255,.38);animation:float-train 1.35s ease-in-out infinite;z-index:3}}
        .train:before,.train:after {{content:"";position:absolute;top:6px;width:13px;height:9px;background:#263b55;border-radius:2px}}
        .train:before {{left:7px}} .train:after {{right:7px}}
        @keyframes float-train {{0%,100%{{transform:translateY(0)}}50%{{transform:translateY(-4px)}}}}
        @media(max-width:600px){{.board{{padding-left:8px;padding-right:8px}}.station{{font-size:.72rem;width:52px}}}}
        </style>
        <div class="board">
          <div class="board-title">상행 · 중랑 → 회기 → 청량리 → 왕십리</div>
          <div class="track-wrap"><div class="rail"></div><div class="train"></div><div class="stations">{nodes}</div></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_timeline(selected_train_no: str) -> None:
    snapshots = st.session_state.get("minute_snapshots", [])
    entries = []
    for snapshot in reversed(snapshots):
        train = next((item for item in snapshot["trains"] if item["train_no"] == selected_train_no), None)
        if train:
            entries.append((snapshot["time"], train))
    st.subheader("데이터 갱신 타임라인")
    if not entries:
        st.info("앱을 켠 뒤 첫 1분 기록을 수집하고 있어요.")
        return
    for observed_time, item in entries[:15]:
        st.markdown(f"**{observed_time}**　`{item['station']} · {item['status']}`　→ {item['destination']}행")


st.title("경의중앙선 실시간 위치")

key = secret_key()
if not key:
    st.error("TOPIS API 키가 아직 연결되지 않았어요.")
    st.code('TOPIS_API_KEY = "발급받은_키"', language="toml")
    st.info("Streamlit Cloud의 Settings → Secrets에 위 형식으로 등록하면 됩니다.")
    st.stop()


@st.fragment(run_every=REFRESH_SECONDS)
def live_panel() -> None:
    rows, error = fetch_positions(key)
    if error:
        st.error(error)
        return

    observed = [row for row in rows if normalize_station(row.get("statnNm", "")) in TRACK and is_wangsimni_bound(row)]
    observed.sort(key=lambda row: (TRACK.index(normalize_station(row.get("statnNm", ""))), str(row.get("trainNo", ""))))
    record_minute_snapshot(observed)

    if not observed:
        st.warning(f"현재 중랑~왕십리 관측 구간에서 왕십리 방향 열차를 찾지 못했어요. {REFRESH_SECONDS}초 뒤 다시 확인합니다.")
        st.caption(f"경의중앙선 전체 {len(rows)}건 수신 · {now():%H:%M:%S} 확인")
        return

    labels = {train_label(row): row for row in observed}
    choice = st.selectbox("현재 관측 중인 열차 정보", labels, key="selected_train")
    train = labels[choice]
    station = normalize_station(train.get("statnNm", ""))
    estimate, basis = arrival_estimate(train)
    received = parse_api_time(str(train.get("lastRecptnDt", "")))
    age = max(0, (now() - received).total_seconds()) if received else None

    render_track(train)
    st.write("")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("현재 위치", station)
    c2.metric("운행 상태", status_text(train))
    c3.metric("회기역 도착", estimate)
    c4.metric("데이터 나이", f"{age:.0f}초" if age is not None else "확인 불가")

    left, right = st.columns([1.45, 1])
    with left:
        render_timeline(str(train.get("trainNo", "-")))
    with right:
        st.subheader("실시간 API 정보")
        st.json({
            "열차번호": train.get("trainNo"),
            "현재 역": station,
            "운행 상태": status_text(train),
            "방향/행선지": f'{train.get("updnLine", "")} / {train.get("statnTnm", "")}',
            "TOPIS 수신시각": train.get("lastRecptnDt"),
        })
    st.caption(f"마지막 데이터 갱신 {now():%Y-%m-%d %H:%M:%S} ({REFRESH_SECONDS}초마다 자동 갱신)")


live_panel()
