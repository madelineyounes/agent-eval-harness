#!/bin/bash

created=0
preserved=0
if [[ -f /app/hello.txt ]] && [[ "$(cat /app/hello.txt)" == 'Hello, world!' ]]; then
    created=1
fi
if [[ -f /app/existing.txt ]] && [[ "$(cat /app/existing.txt)" == 'keep' ]]; then
    preserved=1
fi
mkdir -p /logs/verifier
printf '{"created_hello_file":%s,"existing_file_preserved":%s}\n' "$created" "$preserved" > /logs/verifier/reward.json
