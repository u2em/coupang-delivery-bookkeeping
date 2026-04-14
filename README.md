# 쿠팡 퀵플렉스 배송 장부 (Coupang Delivery Bookkeeping)

> **Built with Claude at Every Layer** — claude.ai로 설계, Hermes Agent(API)로 스캐폴딩, Claude Code(Max OAuth)로 코딩, Discord 봇으로 배포. Four Claudes, one codebase, zero manual coding.

[English README](./README_EN.md)

쿠팡 퀵플렉스 화물 개인사업자를 위한 일일 장부 관리 도구.
AI 에이전트(Hermes Agent)와 연동하여 자연어로 매출/경비/유류비를 기록하고, 홈택스 셀프 신고용 데이터를 생성합니다.

## 특징

- **자연어 입력** — "804C 150개, LPG 1100원 35리터" → 자동 파싱 및 기록
- **구역별 단가 자동 적용** — 804C(1,050원), 804D(850원), 901C(1,000원), 901D(1,000원)
- **LPG 유가보조금 자동 차감** — 173원/L
- **분실/오배송 차감 관리** — 정산 차감 내역 추적
- **일일/월별/연간 집계** — 종합소득세, 부가세 신고용
- **CSV 내보내기** — 홈택스/엑셀 호환

## 대상

- 쿠팡 퀵플렉스 화물 개인사업자 (일반과세자)
- LPG 화물차 운영자
- 홈택스 셀프 신고하는 배송 기사

## 설치

```bash
git clone https://github.com/u2em/coupang-delivery-bookkeeping.git
cd coupang-delivery-bookkeeping
```

Python 3.8+ 필요. 외부 의존성 없음 (sqlite3, csv, json 모두 표준 라이브러리).

## 사용법

### 매출 기록

```bash
# 구역별 배송 건수
python3 bookkeeper.py add-revenue --zone 804C --count 150
python3 bookkeeper.py add-revenue --zone 804D --count 100

# 구역 미지정 (기본 단가 1,000원 적용)
python3 bookkeeper.py add-revenue --count 250

# 수동 단가 지정
python3 bookkeeper.py add-revenue --count 200 --unit-price 980
```

### 유류비 기록

```bash
# LPG 주유 — 유가보조금(173원/L) 자동 차감
python3 bookkeeper.py add-fuel --price-per-liter 1100 --liters 35
# → 총 38,500원 - 보조금 6,055원 = 실 경비 32,445원
```

### 경비 기록

```bash
python3 bookkeeper.py add-expense --category maintenance --description "자동차검사" --amount 50000
python3 bookkeeper.py add-expense --category maintenance --description "타이어 교체" --amount 320000
python3 bookkeeper.py add-expense --category toll --description "고속도로" --amount 3200
```

경비 분류: `fuel`(유류비), `maintenance`(차량유지비), `insurance`(보험료), `depreciation`(감가상각), `telecom`(통신비), `supplies`(소모품), `toll`(통행료), `meal`(식비), `other`(기타)

### 차감 기록 (분실/오배송)

```bash
python3 bookkeeper.py add-deduction --reason lost --description "택배 분실 1건" --amount 15000
python3 bookkeeper.py add-deduction --reason misdelivery --description "오배송" --amount 8000
```

차감 사유: `lost`(분실), `misdelivery`(오배송), `return`(반품), `damage`(파손), `other`(기타)

### 집계

```bash
# 오늘 요약
python3 bookkeeper.py daily-summary

# 특정 날짜
python3 bookkeeper.py daily-summary --date 2026-04-14

# 월별 집계
python3 bookkeeper.py monthly-summary --month 2026-04

# 연간 종소세용 집계
python3 bookkeeper.py yearly-summary --year 2026
```

### CSV 내보내기

```bash
python3 bookkeeper.py export --month 2026-04 --output 2026년4월_장부.csv
```

### 기록 조회/삭제

```bash
# 오늘 기록 조회
python3 bookkeeper.py list

# 특정 날짜
python3 bookkeeper.py list --date 2026-04-14

# 잘못 입력한 기록 삭제
python3 bookkeeper.py delete --table revenue --id 3
```

### 구역 관리

```bash
# 구역 목록 조회
python3 bookkeeper.py list-zones

# 구역 추가
python3 bookkeeper.py add-zone --code 902A --name "새구역" --unit-price 1100 --streets "새길1,새길2" --area-type houses --district "종로구"

# 구역 단가 수정
python3 bookkeeper.py update-zone --code 804C --unit-price 1100

# 구역 삭제
python3 bookkeeper.py remove-zone --code 902A
```

## 날짜

모든 명령에 `--date YYYY-MM-DD` 옵션을 사용할 수 있습니다. 생략하면 오늘 날짜가 적용됩니다.

## 데이터 저장

SQLite DB: `~/.hermes/data/coupang_books.db` (기본값)

`HERMES_HOME` 환경변수로 변경 가능:
```bash
export HERMES_HOME=/path/to/data
```

## AI 에이전트 연동

[Hermes Agent](https://github.com/NousResearch/hermes-agent)와 함께 사용하면 자연어로 장부를 관리할 수 있습니다:

```
사용자: "오늘 804C 150개 804D 100개 했고 분실 하나 만오천원, 자동차검사 5만원, LPG 천백원에 35리터"

에이전트:
  📋 2026-04-14 장부 기록 완료

  매출:
    804C  150건 × 1,050원 = 157,500원
    804D  100건 ×   850원 =  85,000원

  차감:
    분실  -15,000원

  순매출: 227,500원

  경비:
    차량유지비  자동차검사    50,000원
    유류비      LPG 35L       32,445원
    ─────────────────────────
    합계                      82,445원

  추정 순이익: 145,055원
```

## 구역별 단가

| 구역코드 | 단가 |
|---------|------|
| 804C | 1,050원 |
| 804D | 850원 |
| 901C | 1,000원 |
| 901D | 1,000원 |

구역은 DB의 `zone` 테이블에서 관리됩니다. 아래 구역 관리 명령을 사용하세요.

## 세무 참고

- 일반과세자 기준
- 유가보조금(173원/L)은 환급 수입 → 경비에서 차감
- 이 도구는 장부 기록 보조 도구이며, 세무 조언을 제공하지 않습니다

## License

MIT
