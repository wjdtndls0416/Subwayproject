# 회기역 열차 접근 현황

서울시 TOPIS 실시간 열차 위치정보의 `updnLine` 값을 이용해 **중랑역에서 회기역으로 접근하는 상행 경의중앙선 열차**를 관측하는 Streamlit 앱입니다.

## 현재 기능

- `updnLine`이 `"상행"` 또는 공식 코드 `"0"`인 경의중앙선 열차만 선별
- 중랑 → 회기 → 청량리 → 왕십리 구간의 현재 위치와 운행 상태 표시
- 5초마다 TOPIS 정보 갱신
- 선택한 열차의 현재 상황을 1분마다 기록해 타임라인으로 표시
- 같은 열차의 `현재 역 + 운행 상태`가 앱 관측상 몇 분 동안 지속됐는지 표시
- `lastRecptnDt` 또는 `recptnDt`를 이용한 TOPIS 데이터 나이 표시
- 전광판처럼 선로 위에서 열차가 움직이는 시각화

고정 도착 예상시간, 출발 타이밍 판단, 지연 경고는 제공하지 않습니다. 현재 단계 지속시간은 5초마다 갱신되며 단계가 바뀌면 다시 계산됩니다. 앱을 켜기 전부터 지속된 시간은 포함하지 않으며, 타임라인과 지속시간 기록은 브라우저 세션에만 저장되어 앱이 재시작되면 초기화됩니다.

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
