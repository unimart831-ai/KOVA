FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js (for Tailwind CSS CLI)
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY requirements/ requirements/
RUN pip install --no-cache-dir -r requirements/development.txt

# Tailwind
COPY package.json package-lock.json* tailwind.config.js ./
RUN npm install

# Copy app source
COPY . .

# Build Tailwind CSS
RUN npx tailwindcss -i ./static/css/input.css -o ./static/css/output.css --minify

EXPOSE 8000

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
