# 역사 자료와 사용 범위

선정 기간은 **1206~1259년**이다. 같은 ‘Mongol Empire’ 레코드에서 초기 영역과 대규모 서방 확장을 8개 원본 상태로 추적할 수 있어 선택했다. 이는 최종 승인된 영상 타임라인이 아니다. 각 구간은 해당 데이터셋이 제시한 재구성 영역의 유효 연도 범위이며, 첫 연도를 모든 정복이 일어난 날짜로 해석하지 않는다.

| 원본 FromYear | 원본 ToYear | 원본 Area(km², 반올림) |
|---:|---:|---:|
| 1206 | 1209 | 2,464,171 |
| 1210 | 1215 | 2,821,825 |
| 1216 | 1219 | 4,121,744 |
| 1220 | 1226 | 8,584,614 |
| 1227 | 1235 | 14,120,008 |
| 1236 | 1240 | 18,805,059 |
| 1241 | 1249 | 20,934,701 |
| 1250 | 1259 | 23,974,433 |

## 원본·학술 근거

- 데이터: Seshat Global History Databank, **Cliopatria v0.2.1**. https://github.com/Seshat-Global-History-Databank/cliopatria/tree/v0.2.1
- 고정 커밋: `5f433377139a6eeaeacbdc894b70f8805b72c8b5`.
- 원본 ZIP SHA256: `e10a4e429fca708788ff9e7572a95fce801fae55852d217cffabc1c59cd4eed4`.
- 파일: `cliopatria.geojson.zip` 내부 `cliopatria_polities_only_v021.geojson`. EPSG:4326. 이름과 연도로 8개 Feature를 추출했으며 좌표·속성은 수정하지 않았다.
- 논문: Bennett et al. (2025), *Cliopatria – A geospatial database of world-wide political entities from 3400BCE to 2024CE*, Scientific Data 12:247. DOI https://doi.org/10.1038/s41597-025-04516-9 ; 공개 본문 https://pmc.ncbi.nlm.nih.gov/articles/PMC11822181/
- 라이선스: CC BY 4.0, https://creativecommons.org/licenses/by/4.0/ . 출처·저자·변경 사항 표기 필요. 복사한 라이선스 파일 포함.
- 보조 연대 검토: Encyclopaedia Iranica, ‘Mongols’, https://www.iranicaonline.org/articles/mongols-2/ . 1209 서하 복속, 1211 이후 금과 전쟁, 1218~1224 서방 원정, 1227 서하 멸망, 1234 금 정복 등의 설명을 참고했다. 이 문헌의 연대를 폴리곤 전체의 정복 날짜로 자동 대응시키지 않았다. 해당 URL은 현재 색인 페이지로 리디렉션될 수 있다.

## 정확성 한계

이 연구 데이터는 역사학적 재구성이다. 경계·통제 범위·시기에는 불확실성이 있고, 원본 제공자도 다른 해석 가능성을 명시한다. 본 작업은 원본 출처와 좌표 복사·유효성만 검증했으며 모든 국지 경계를 독립적인 역사 사료로 재확정하지 않았다. 논문에 표시된 과거 버전의 1250년 면적과 현재 v0.2.1 값도 같다고 가정하지 않는다.

군사 진군 경로와 전투 전선은 이 데이터에 없다. 이를 임의로 만들지 않았다. 위 표의 면적은 출처 값이며 현대 국경이나 현재 국가 영토 주장으로 해석하지 않는다. ‘연도별 원본 지도를 충실하게 보여주는 것’과 ‘일자별 실제 정복 순서를 재현하는 것’은 별개다.
