#!/bin/zsh
set -e
which python

projectDir=`pwd`


generate_rc_files() {
  pushd "$projectDir/$1"
  for f in *.qrc
  do
    pyside6-rcc "$f" -o "${f%.*}_rc.py"
    print "qrc generate for $f"
  done
  popd
}

find . -name "*_rc.py" -exec rm {} +
for DIR in $(find . -name '*.qrc' -exec dirname {} + | sort | uniq)
do
  generate_rc_files $DIR
done

generate_uic_files() {
  pushd "$projectDir/$1"
  for f in *.ui
  do
    pyside6-uic "$f" -o "${f%.*}"_uic.py
    print  "uic generate for $1/$f"
  done
  popd
}

find . -name "*_uic.py" -exec rm {} +
for DIR in $(find . -name '*.ui' -exec dirname {} + | sort | uniq)
do
  generate_uic_files $DIR
done
find . -depth 2 -name '*_uic.py' -exec sed -E -i -e 's/import ([a-zA-Z]+_rc)/from . import \1/g' {} +
find . -depth 3 -name '*_uic.py' -exec sed -E -i -e 's/import ([a-zA-Z]+_rc)/from .. import \1/g' {} +
find . -name '*.py-e' -exec rm {} +


cd "$projectDir"
rm -rf dist/* || TRUE
rm -rf build
python setup.py py2app -A
open dist
