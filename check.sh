#!/usr/bin/env bash
# one command: the planted case test, exit 1 on any failure
cd "$(dirname "$0")" && bash tests/test.sh
