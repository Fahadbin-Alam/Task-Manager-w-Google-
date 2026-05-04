# Docker Guide For This Project

This guide explains what we added, why we added it, and how the pieces work together.

## Big Idea First

Docker lets us package an application with its runtime and dependencies so it behaves the same on different machines.

For this project, that means:

- We do not depend on your computer already having the right Python packages installed.
- We get one repeatable startup process.
- We reduce "it works on my machine" problems.

## The 4 Main Pieces

### 1. `requirements.txt`

This file lists the Python packages the app needs.

Why Docker needs it:

- When Docker builds the image, it must know exactly what to install.
- If we skip this file, the image would not know how to get FastAPI, Uvicorn, Jinja2, and the other libraries.

In this project, it includes packages like:

- `fastapi`
- `uvicorn`
- `jinja2`
- `bcrypt`
- `requests`
- `python-jose`

### 2. `Dockerfile`

This file is the build recipe for the image.

Think of it like instructions for creating a mini-computer image for the app.

Line by line:

```dockerfile
FROM python:3.11-slim
```

- Start from an existing lightweight Python image.
- We use `python:3.11-slim` because it already contains Python, but is smaller than a full OS image.

```dockerfile
WORKDIR /app
```

- Set the working folder inside the container to `/app`.
- After this, most commands run as if `/app` is the current folder.

```dockerfile
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
```

- `PYTHONDONTWRITEBYTECODE=1` stops Python from creating extra `.pyc` cache files.
- `PYTHONUNBUFFERED=1` makes logs print immediately, which helps when reading container output.

```dockerfile
COPY requirements.txt .
```

- Copy only the dependency file first.
- This is a common Docker optimization because if your code changes but `requirements.txt` does not, Docker may reuse the old dependency-install layer.

```dockerfile
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt
```

- Upgrade `pip`.
- Install the packages from `requirements.txt`.
- `--no-cache-dir` helps keep the image smaller.

```dockerfile
COPY . .
```

- Copy the rest of the project into the image.

```dockerfile
EXPOSE 8000
```

- Documents that the app listens on port `8000`.
- This does not publish the port by itself. It is more like a note for humans and tools.

```dockerfile
CMD ["uvicorn", "Backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- This is the default command when the container starts.
- `Backend.main:app` means:
  - go to the `Backend/main.py` file
  - find the FastAPI object named `app`
- `0.0.0.0` is important inside containers because it tells the app to listen on all network interfaces, not just inside itself.

### 3. `docker-compose.yml`

This file defines how to run the container.

Think of `Dockerfile` as "how to build the app image" and `docker-compose.yml` as "how to run the app as a service."

What each section does:

```yaml
services:
  app:
```

- Defines one service named `app`.

```yaml
    build:
      context: .
      dockerfile: Dockerfile
```

- Build using the current folder as the project context.
- Use the `Dockerfile` in the project root.

```yaml
    container_name: student-guide-app
```

- Gives the running container a friendly name.

```yaml
    ports:
      - "8000:8000"
```

- Maps port `8000` on your computer to port `8000` in the container.
- Left side is your machine.
- Right side is the container.

```yaml
    environment:
      SECRET_KEY: ${SECRET_KEY:-change-me-for-real-use}
      DB_PATH: ${DB_PATH:-/app/data/app.db}
```

- Passes environment variables into the app.
- `SECRET_KEY` is used by authentication code.
- `DB_PATH` tells the app where the SQLite database should live.
- The `${VAR:-default}` format means "use the variable if provided, otherwise use this default."

```yaml
    volumes:
      - student_guide_data:/app/data
```

- This is one of the most important lines.
- It creates persistent storage for the SQLite database.
- Without this, rebuilding the container could wipe out your database.

```yaml
    restart: unless-stopped
```

- Tells Docker to restart the container automatically unless you explicitly stop it.

```yaml
volumes:
  student_guide_data:
```

- Declares the named volume used above.

### 4. `.dockerignore`

This file tells Docker what not to copy into the build context.

Why that matters:

- Smaller build context means faster builds.
- We avoid copying local virtual environments, git history, logs, and database files into the image.
- That keeps the image cleaner and avoids accidental leakage of local-only files.

## Why We Changed `Backend/main.py`

Originally, the app used fixed values in code:

- `SECRET_KEY` was hardcoded
- `DB_PATH` always pointed to a local file next to the code

That is okay for very basic local development, but not ideal for containers.

We changed it so the app can read:

- `SECRET_KEY` from an environment variable
- `DB_PATH` from an environment variable

Why this is better:

- Containers should be configurable from the outside
- Sensitive settings should not be hardcoded
- The database can be stored in a mounted volume

## Build vs Run

This is an important Docker concept.

### Build

Build means:

- read the `Dockerfile`
- create an image
- install dependencies
- copy in the code

Command:

```bash
docker compose build
```

### Run

Run means:

- start a container from that image
- open the ports
- attach the volume
- pass the environment variables

Command:

```bash
docker compose up
```

### Build and Run Together

This is the command most beginners use first:

```bash
docker compose up --build
```

That means:

- rebuild if needed
- then start the container

## What Happens When You Run `docker compose up --build`

Step by step:

1. Docker reads `docker-compose.yml`.
2. It sees there is an `app` service.
3. It sees that service must be built from `Dockerfile`.
4. Docker reads the `Dockerfile`.
5. It downloads the base Python image if it is not already present.
6. It copies `requirements.txt`.
7. It installs Python packages.
8. It copies the project files.
9. It creates and starts the container.
10. It maps port `8000` so your browser can reach the app.
11. It mounts the named volume so the database can persist.
12. It runs `uvicorn Backend.main:app --host 0.0.0.0 --port 8000`.

## Filesystem Idea: Image vs Container vs Volume

This is the part that confuses most people at first.

### Image

- A reusable blueprint
- Built from the `Dockerfile`

### Container

- A running instance of the image
- Temporary by nature

### Volume

- Persistent storage managed by Docker
- Used for data that must survive when containers are removed or rebuilt

For your app:

- code and dependencies belong in the image
- runtime process belongs in the container
- SQLite database belongs in the volume

## Environment Variables

Environment variables are settings passed in from outside the code.

That is useful because:

- you can change configuration without editing Python files
- different environments can use different values
- it is more deployment-friendly

You now have an `.env.example` file as a template.

Typical beginner workflow:

1. Copy `.env.example` to `.env`
2. Change `SECRET_KEY`
3. Run `docker compose up --build`

## Common Commands

### Start the app

```bash
docker compose up --build
```

### Start in background

```bash
docker compose up -d --build
```

### Stop the app

```bash
docker compose down
```

### See logs

```bash
docker compose logs -f
```

### Rebuild from scratch idea

If you changed dependencies or Docker instructions, rebuild:

```bash
docker compose up --build
```

## What You Should Notice in the Output

When you run Docker for the first time, look for these kinds of messages:

- base image download messages
- dependency installation messages
- container creation messages
- Uvicorn startup log

A healthy startup usually ends with something similar to:

```text
Uvicorn running on http://0.0.0.0:8000
```

Then you can open:

- `http://localhost:8000`
- `http://localhost:8000/docs`

## If Something Fails

Here is how to think about common failure types.

### "docker is not recognized"

- Docker Desktop is probably not installed, or not running.

### Package install failure during build

- Usually means a package name is wrong or a system dependency is missing.

### App starts but browser cannot connect

- Check the `ports` mapping.
- Check that Uvicorn uses `--host 0.0.0.0`.

### Data disappears after rebuild

- Check the volume mapping.
- Check that `DB_PATH` points into the mounted volume path.

## Mental Model To Remember

If you want one short summary, use this:

- `requirements.txt` says what Python must install
- `Dockerfile` says how to build the image
- `docker-compose.yml` says how to run the app
- `volume` keeps data alive
- `environment variables` let us configure the app cleanly
