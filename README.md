# Drexel Student Success App

## Project Overview

The Drexel Student Success App is a student-focused platform designed to improve campus engagement, academic planning, and peer networking.

This sprint focuses on implementing the backend API using FastAPI to support:

- Clubs discovery
- Club events
- Peer availability
- Networking features

---

## User Story Implemented (Sprint Feature)

> As a person that participates in clubs and wants to be involved more,  
> I would like to know what clubs and which of my peers are available  
> so I can network and make friends.

This is supported through:

- `/clubs`
- `/clubs/{club_id}/events`
- `/availability`
- `/networking`

---

## Architecture

Backend: FastAPI  
API Documentation: Swagger UI (`/docs`)  
Data Models: Pydantic  

The backend currently runs as a local development server.

---

## Features Implemented

- GET `/clubs`
- GET `/clubs/{club_id}/events`
- GET `/availability`
- GET `/networking`

---

## How to Run Locally

```bash
cd backend
python -m venv .venv
source .venv/Scripts/activate
pip install fastapi uvicorn
uvicorn main:app --reload
```

## Docker Setup

This project now includes a basic Docker setup so the app can run in a container instead of depending on your machine's Python environment.

### Why these files exist

- `requirements.txt`: gives Docker an exact package install list.
- `Dockerfile`: tells Docker how to build the app image.
- `.dockerignore`: keeps unnecessary files out of the build context so builds stay smaller and faster.
- `docker-compose.yml`: gives us one simple command to build and run the app.

### Important Docker idea

Containers are meant to be replaceable. Your app uses SQLite, so the database needs a persistent location outside the temporary container filesystem.  
That is why the app now supports a `DB_PATH` environment variable, and `docker-compose.yml` mounts a named Docker volume at `/app/data`.

### Build and run with Docker Compose

```bash
docker compose up --build
```

Then open:

- App/API: `http://localhost:8000`
- Swagger docs: `http://localhost:8000/docs`

### Stop the container

```bash
docker compose down
```

### Rebuild after code changes

```bash
docker compose up --build
```

### Notes

- `SECRET_KEY` is read from an environment variable now, which is better for Docker and deployment.
- `DB_PATH` defaults to the original local file path, so running without Docker still works.
- The named Docker volume keeps your SQLite data even if the container is recreated.
- For a beginner-friendly walkthrough of every Docker file, read `DOCKER_GUIDE.md`.
