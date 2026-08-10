from __future__ import annotations

from datetime import datetime
from html import escape
from zoneinfo import ZoneInfo

import requests
import streamlit as st


st.set_page_config(page_title="회기역 열차 접근 현황", page_icon="🚆", layout="wide")

SEOUL = ZoneInfo("Asia/Seoul")
LINE_NAME = "경의중앙선"
API_BASE = "https://swopenapi.seoul.go.kr/api/subway"
TRACK = ["중랑", "회기", "청량리", "왕십리"]
TARGET_UPDN_LINES = {"상행", "0"}
STATUS_LABELS = {"0": "진입", "1": "도착", "2": "출발", "3": "전역 출발"}
REFRESH_SECONDS = 5
STALL_WARNING_MINUTES = 6
MAX_SNAPSHOT_GAP_SECONDS = 150


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


def record_minute_snapshot(rows: list[dict]) -> None:
    snapshots = st.session_state.setdefault("minute_snapshots", [])
    observed_at = now()
    minute_key = observed_at.strftime("%Y-%m-%d %H:%M")
    if snapshots and snapshots[-1]["minute_key"] == minute_key:
        return
    snapshots.append({
        "minute_key": minute_key,
        "observed_at": observed_at.isoformat(),
        "time": observed_at.strftime("%H:%M"),
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


def detect_stalled_stage(selected_train_no: str) -> tuple[bool, float, str]:
    """같은 위치 단계가 끊김 없이 유지된 시간을 계산한다."""
    snapshots = st.session_state.get("minute_snapshots", [])
    consecutive: list[tuple[datetime, dict]] = []

    for snapshot in reversed(snapshots):
        train = next(
            (item for item in snapshot["trains"] if item["train_no"] == selected_train_no),
            None,
        )
        if train is None:
            break

        try:
            observed_at = datetime.fromisoformat(snapshot["observed_at"])
        except (KeyError, TypeError, ValueError):
            break

        stage = (train["station"], train["status"])
        if consecutive:
            newer_time, newer_train = consecutive[-1]
            newer_stage = (newer_train["station"], newer_train["status"])
            gap_seconds = (newer_time - observed_at).total_seconds()
            if stage != newer_stage or gap_seconds > MAX_SNAPSHOT_GAP_SECONDS:
                break

        consecutive.append((observed_at, train))

    if not consecutive:
        return False, 0.0, "관측 기록 수집 중"

    latest_time, latest_train = consecutive[0]
    earliest_time, _ = consecutive[-1]
    unchanged_minutes = max(0.0, (latest_time - earliest_time).total_seconds() / 60)
    stage_label = f'{latest_train["station"]} · {latest_train["status"]}'
    is_stalled = unchanged_minutes >= STALL_WARNING_MINUTES
    return is_stalled, unchanged_minutes, stage_label


def render_stage_warning(selected_train_no: str) -> None:
    is_stalled, unchanged_minutes, stage_label = detect_stalled_stage(selected_train_no)
    if is_stalled:
        st.error(
            f"🚨 이 열차는 약 {unchanged_minutes:.0f}분 동안 위치 단계가 "
            f"‘{stage_label}’에서 변하지 않았습니다.\n\n"
            "평상시보다 이동이 지연되고 있거나 실시간 정보 갱신에 이상이 있을 "
            "가능성이 있습니다. 현재 도착예정정보의 신뢰도가 낮습니다."
        )
    else:
        remaining = max(0, STALL_WARNING_MINUTES - unchanged_minutes)
        st.success(
            f"현재 위치 단계 이상은 감지되지 않았습니다. "
            f"‘{stage_label}’ 단계 연속 관측 약 {unchanged_minutes:.0f}분"
        )
        if 0 < unchanged_minutes < STALL_WARNING_MINUTES:
            st.caption(f"같은 단계가 약 {remaining:.0f}분 더 유지되면 확인 필요 경고를 표시합니다.")


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
    st.subheader("1분 단위 관측 타임라인")
    if not entries:
        st.info("앱을 켠 뒤 첫 1분 기록을 수집하고 있어요.")
        return
    for observed_time, item in entries[:15]:
        st.markdown(f"**{observed_time}**　`{item['station']} · {item['status']}`　→ {item['destination']}행")


st.title("🚆 회기역 열차 접근 현황")
st.caption("중랑 → 회기 → 청량리 → 왕십리 · 회기역에서 왕십리 방향 열차를 타기 위한 실시간 관측")
st.info("이 버전은 출발 시각을 판단하지 않습니다. 중랑역에서 회기역으로 접근하는 열차의 위치와 관측 기록에 집중합니다.")

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
    choice = st.selectbox("관측할 왕십리 방향 열차", labels, key="selected_train")
    train = labels[choice]
    station = normalize_station(train.get("statnNm", ""))
    train_no = str(train.get("trainNo", "-"))
    received_raw = train.get("lastRecptnDt") or train.get("recptnDt") or ""
    received = parse_api_time(str(received_raw))
    age = max(0, (now() - received).total_seconds()) if received else None
    is_stalled, unchanged_minutes, _ = detect_stalled_stage(train_no)

    render_track(train)
    st.write("")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("현재 위치", station)
    c2.metric("운행 상태", status_text(train))
    c3.metric(
        "위치 단계 상태",
        "확인 필요" if is_stalled else "정상 관측",
        f"같은 단계 {unchanged_minutes:.0f}분",
        delta_color="inverse" if is_stalled else "normal",
    )
    c4.metric("데이터 나이", f"{age:.0f}초" if age is not None else "확인 불가")
    render_stage_warning(train_no)

    left, right = st.columns([1.45, 1])
    with left:
        render_timeline(train_no)
    with right:
        st.subheader("현재 API 정보")
        st.json({
            "열차번호": train.get("trainNo"),
            "현재 역": station,
            "운행 상태": status_text(train),
            "방향/행선지": f'{train.get("updnLine", "")} / {train.get("statnTnm", "")}',
            "TOPIS 수신시각": received_raw or "확인 불가",
        })
    st.caption(f"마지막 화면 갱신 {now():%Y-%m-%d %H:%M:%S} · {REFRESH_SECONDS}초마다 자동 확인")


live_panel()

st.divider()
st.caption("서울시 TOPIS 실시간 열차 위치정보를 활용한 개인 탐구용 프로토타입입니다. 서울시 공공데이터 출처를 표시합니다.")
