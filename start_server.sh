#!/bin/bash
cd /home/saikumar/projects/fenwick-opencode
exec python3.11 -m uvicorn main:app --host 0.0.0.0 --port 8080
