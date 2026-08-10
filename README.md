# 회기역 열차 접근 현황

서울시 TOPIS 실시간 열차 위치정보를 이용해 **중랑역에서 회기역으로 접근하는 왕십리 방향 경의중앙선 열차**를 관측하는 Streamlit 앱입니다.

## 현재 기능

- 경의중앙선 중 회기 → 왕십리 방향 열차만 선별
- 중랑 → 회기 → 청량리 → 왕십리 구간의 현재 위치와 운행 상태 표시
- 중랑역 위치·운행 상태를 바탕으로 회기역 도착 예상 범위 표시
- 5초마다 TOPIS 정보 갱신
- 선택한 열차의 현재 상황을 1분마다 기록해 타임라인으로 표시
- 전광판처럼 선로 위에서 열차가 움직이는 시각화

출발 타이밍 판단과 지연 가능성 판정은 정확한 실측자료가 확보될 때까지 제외했습니다. 타임라인은 브라우저 세션에만 저장되며 앱을 닫으면 초기화됩니다.

## 로컬 실행

1. `.streamlit/secrets.toml`에 API 키를 입력합니다.

   ```toml
   TOPIS_API_KEY = "발급받은_실시간_지하철_API_키"
   ```

2. 실행합니다.

   ```bash
   pip install -r requirements.txt
   streamlit run streamlit_app.py
   ```

## Streamlit Community Cloud 배포

GitHub 저장소 최상단에 `streamlit_app.py`, `requirements.txt`, `README.md`, `.gitignore`를 올리고 Main file path를 `streamlit_app.py`로 지정합니다. 앱 설정의 **Secrets**에는 아래 내용을 등록합니다.

```toml
TOPIS_API_KEY = "발급받은_실시간_지하철_API_키"
```

API 키는 GitHub 저장소에 직접 올리지 마세요.
