#!/bin/sh
# 메뉴찾기 봇 실행: 키가 없으면 물어봐서 .env 에 저장한 뒤 서버를 띄운다.
cd "$(dirname "$0")" || exit 1

PY=
for c in python3 python py; do
  # Windows 의 Microsoft Store 가짜 python 은 command -v 에는 잡히지만 실행은 안 되므로 직접 실행해 본다
  if "$c" -c "import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)" >/dev/null 2>&1; then PY=$c; break; fi
done
[ -n "$PY" ] || { echo "Python 3.8 이상이 필요합니다."; exit 1; }

if [ -z "$AXROUTER_API_KEY" ] && ! grep -q '^AXROUTER_API_KEY=.' .env 2>/dev/null; then
  printf "AXROUTER_API_KEY 를 입력하세요(화면에 보이지 않습니다): "
  stty -echo 2>/dev/null; read -r KEY; stty echo 2>/dev/null; echo
  [ -n "$KEY" ] || { echo "키가 비어 있습니다."; exit 1; }
  printf 'AXROUTER_API_KEY=%s\n' "$KEY" > .env
  echo ".env 에 저장했습니다(git 에는 올라가지 않습니다)."
fi

exec "$PY" tools/server.py
