#!/bin/zsh
set -e

projectDir=`pwd`


if [ -n "$VIRTUAL_ENV" ]; then
    # 在虚拟环境中
    echo "当前处于虚拟环境中，无法正常打包"
    exit 1
fi

generate_rc_py() {
  RC_FILE=$1
  RC_PY_FILE=${RC_FILE%.*}_rc.py
  pipenv run pyside6-rcc "$RC_FILE" -o "$RC_PY_FILE"
  echo "qrc generate for $RC_FILE"
}

generate_uic_py() {
  UI_FILE=$1
  UI_PY_FILE=${UI_FILE%.*}_uic.py
  pipenv run pyside6-uic "$UI_FILE" -o "$UI_PY_FILE"
  echo "uic generate for $UI_FILE"
}

regenerate_qt_files() {
  cd "$projectDir"

  find . -name "*_rc.py" -exec rm {} +
  for FILE in $(find . -name '*.qrc' -exec sh -c 'echo "$0"' {} \;); do
    generate_rc_py "$FILE"
  done

  find . -name "*_uic.py" -exec rm {} +
  for FILE in $(find . -name '*.ui' -exec sh -c 'echo "$0"' {} \;)
  do
    generate_uic_py "$FILE"
  done
  find . -depth 2 -name '*_uic.py' -exec sed -E -i -e 's/import ([a-zA-Z]+_rc)/from . import \1/g' {} +
  find . -depth 3 -name '*_uic.py' -exec sed -E -i -e 's/import ([a-zA-Z]+_rc)/from .. import \1/g' {} +
  find . -name '*.py-e' -exec rm {} +
}

package_with_setup() {
  cd "$projectDir"
  SETUP_PY=$(find . -name 'setup.py' | head -n 1)
  if [ -z "$SETUP_PY" ]; then
      echo "setup.py not found"
      exit 1
  fi
  echo "Package with $SETUP_PY"
  pipenv clean
  echo "Install requirements"
  python3 -m pip install -r requirements.txt > /dev/null
  python3 "$SETUP_PY" py2app > py2app.log || true
  rm -rf  build || ture
  echo "Uninstall requirements"
  python3 -m pip uninstall -y -r requirements.txt > /dev/null

  if [ -f after_package.sh ]; then
      echo "Run after_package.sh"
      source ./after_package.sh || ture
  fi
}


regenerate_qt_files
package_with_setup
