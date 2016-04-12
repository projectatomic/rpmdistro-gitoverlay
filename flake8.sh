#!/bin/bash
set -euo pipefail
exec flake8 --ignore E501,E302,E231,W293,W291,E226 rdgo
