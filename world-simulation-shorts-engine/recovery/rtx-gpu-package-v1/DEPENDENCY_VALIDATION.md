# 의존성 검증 범위

정확한 구성·pin·출처는 `DEPENDENCIES.md`, `dependency_contract.json`, `native-packages.lock`, `evidence/DEPENDENCY_SOURCES.json`을 따릅니다.

현재 CPU 실행환경의 5개 native probe는 실제 GDAL/NumPy/Pillow/libnetcdf로 원본 ASTRA parser를 호출하여 Float32 bit·nodata·PixelIsPoint·signed elevation·NetCDF4·PNG·neutral 값을 보존했습니다. 작은 합성 fixture를 사용하는 native 실행 검사이며, 이미 완료된 ASTRA 원본 데이터 감사 24개를 반복한 것이 아닙니다. 해당 테스트와 strict contract/bootstrap 검사는 모두 실행 증거에 기록합니다.

고정된 공식 GDAL 3.10.3 이미지의 layer SHA/size/diff ID를 검증해 별도 sysroot로 추출했습니다. 해당 image의 loader/Python/native libraries를 CPU로 직접 실행하여 Python 3.12.3, NumPy 1.26.4, Pillow 10.2.0, GDAL 3.10.3과 요구되는 GDAL/osr context API를 확인했습니다. Docker container나 하드웨어 GPU 실행으로 보고하지 않습니다.

이 실행환경의 dependency 관측은 `CURRENT_CPU_DEPENDENCIES.json`에 구분해 기록합니다. 현재 checkout에는 `node_modules/playwright`가 설치되어 있지 않습니다. 새 이미지 구성은 변경하지 않은 package-lock으로 Playwright dev dependency를 설치하며 strict dependency verifier가 실제 설치 누락을 실패 처리합니다. 현재 환경의 Chrome 154/ Python 3.13 관측을 새 이미지의 Chrome 155/Python 3.12 PASS로 바꾸어 기록하지 않습니다.

Docker daemon의 기존 vfs 저장 공간 부족으로 dependency container를 시작하지 못했습니다. OS의 chroot 권한도 허용되지 않아 sysroot loader 방식으로 필요한 native 확인을 수행했습니다. 기존 파일 삭제, daemon prune, proxy/TLS 우회는 수행하지 않았습니다. MCR image access는 proxy 403으로 확인되어 공식 고정 Chrome DEB를 사용하는 구성을 준비했습니다.

새 이미지가 아직 build되지 않았으므로 최종 APT transitive closure, 전체 이미지 ABI/browser 실행, 실제 이미지 크기·manifest digest는 미검증입니다. Docker build와 startup 모두 source 및 dependency verifier를 실행하도록 구성합니다. actual image 검사 실패 시 GPU admission을 시작할 수 없습니다.

Chrome DEB와 base component의 공개 hash/digest는 새 통합 이미지의 digest와 구분합니다. GPU hardware draw·NVIDIA driver injection·영상 품질은 이 CPU 의존성 결과에 포함되지 않습니다.

고정 Ubuntu NetCDF 4.9.2/HDF5 라이브러리도 SHA가 검증된 sysroot에서 실행했습니다. 실제 기존 ASTRA parser의 CF signed Int16·좌표축·nodata·원본 SHA 검사가 통과했고, 공유 라이브러리의 host 혼입이 없음을 확인했습니다. Chrome DEB의 실제 bytes·SHA·control metadata는 확인했으며 browser 실행은 하지 않았습니다. 이 component 검사도 아직 빌드되지 않은 전체 이미지의 runtime PASS와 구분합니다.
