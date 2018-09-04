#!/bin/sh
set -e

progs="autoconf autoreconf automake libtoolize pkg-config"

for p in ${progs}; do
	if ! test -x "$(command -v ${p})"; then
		echo "*** Please install ${p}"
		result=1
	fi
done

[ -z ${result} ] || exit 1

test -n "$srcdir" || srcdir=`dirname "$0"`
test -n "$srcdir" || srcdir=.

olddir=`pwd`
cd $srcdir

mkdir -p m4

autoreconf --force --install --verbose

cd $olddir
test -n "$NOCONFIGURE" || "$srcdir/configure" "$@"
