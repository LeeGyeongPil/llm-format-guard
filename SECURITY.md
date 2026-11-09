# 보안 정책 / Security policy

보안 취약점을 발견하셨다면 **공개 이슈 대신** 이 레포의 **Security → Report a vulnerability**(비공개 취약점 신고)로 알려 주세요. 확인 후 답변드리고, 고친 버전을 릴리스하면서 함께 안내합니다.

If you find a security issue, please **do not open a public issue**. Use **Security → Report a vulnerability** in this repository to report it privately. We will reply after checking and announce the fix with a release.

이 레포는 네트워크를 열지 않는 라이브러리이며 API 키를 다루지 않습니다(예제 `examples/with_ollama.py` 만 환경변수로 주소·키를 읽습니다). / This is a library that opens no network port and handles no keys (only the example `examples/with_ollama.py` reads its URL and key from environment variables).
