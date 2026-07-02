@echo off
REM Windows equivalent of run.sh — replicates make setup + make run directly,
REM since make is not guaranteed on Windows.

where docker >nul 2>nul || (echo ERROR: docker is required & exit /b 1)
if not exist .env (
    copy .env.example .env
    echo Created .env from .env.example - edit to add EIA_API_KEY
)
docker compose build || exit /b 1
docker compose up -d --wait || exit /b 1
echo Services healthy. Executing full pipeline...
docker compose exec dagster dagster job execute -m orchestration.definitions -j full_pipeline || exit /b 1
echo.
echo Pipeline complete.
echo   Report:     see reports\output\
echo   Dagster UI: http://localhost:3000
echo   API docs:   http://localhost:8001/docs
