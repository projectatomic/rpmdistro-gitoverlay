#!/bin/bash
set -euo pipefail
IFS=$'\n\t'

# Initial test for rpmdistro-gitoverlay
export PYTHON=${PYTHON:-"/usr/bin/python"}
export PYTHON3=${PYTHON3:-"/usr/bin/python3"}
export PYTHONPATH=${PYTHONPATH:-$(pwd)}
export WORK_DIR=$(mktemp -p $(pwd) -d -t .tmp.XXXXXXXXXX)

LOG=${LOG:-"$(pwd)/tests.log"}

cleanup () {
    rm -rf ${WORK_DIR}
}

get_coverage_bin() {
    COVERAGE_BIN=${COVERAGE_BIN-"/usr/bin/coverage"}

    if [[ ! -x "${COVERAGE_BIN}" ]]; then
        # Check to see if it is in local instead.
        COVERAGE_BIN="/usr/local/bin/coverage"
    fi

    if [[ ! -x "${COVERAGE_BIN}" ]]; then
        # The executable is "coverage2" on systems with default python3 and no
        # python3 install.
        COVERAGE_BIN="/usr/bin/coverage2"
    fi

    if [[ ! -x "${COVERAGE_BIN}" ]]; then
        COVERAGE_BIN="/usr/bin/coverage3"
    fi
    echo ${COVERAGE_BIN}
}

load_coverage() {
    COVERAGE_BIN=$1;

    if [[ -x "${COVERAGE_BIN}" ]]; then
        COVERAGE="${COVERAGE_BIN}
        run
        --source=./rdgo/
        --branch"
    else
        COVERAGE="${PYTHON3:-/usr/bin/python3}"
    fi
    echo ${COVERAGE}
}

execute_unittest() {
    # Load variables
    COVERAGE_BIN=$1; shift
    COVERAGE=$1;

    # Execute Unit tests
    set +e
    ${COVERAGE} -m unittest discover ./tests/unit/ | tee -a ${LOG}
    _UNIT_FAIL="$?"
    set -e

    if [[ -x "${COVERAGE_BIN}" ]]; then
        echo "Coverage report:" | tee -a ${LOG}
        ${COVERAGE_BIN} report | tee -a ${LOG}
    fi

    if [[ $_UNIT_FAIL -eq 0 ]]; then
            echo "ALL TESTS PASSED"
            exit 0
        else
            echo "Unit tests failed."
    fi
}

trap cleanup EXIT

echo "UNIT TESTS:"

# Get Coverage and Coverage bin
COVERAGE_BIN=$(get_coverage_bin)
COVERAGE=$(load_coverage "${COVERAGE_BIN}")

execute_unittest ${COVERAGE_BIN} ${COVERAGE}
exit 1
