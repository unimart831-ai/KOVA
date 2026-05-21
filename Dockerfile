FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# System dependencies (libcairo2-dev + pkg-config needed by pycairo/xhtml2pdf)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    fonts-dejavu-core \
    pkg-config \
    libcairo2-dev \
    libpango1.0-dev \
    libgdk-pixbuf-2.0-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js (for Tailwind CSS CLI)
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies — install BOTH production and development requirements
COPY requirements/ requirements/
RUN pip install --no-cache-dir -r requirements/production.txt -r requirements/development.txt

# Tailwind
COPY package.json package-lock.json* tailwind.config.js ./
RUN npm install

# Copy app source
COPY . .

# Build Tailwind CSS
RUN npx tailwindcss -i ./static/css/input.css -o ./static/css/output.css --minify

# Collect static files (whitenoise serves them in production)
RUN DJANGO_SETTINGS_MODULE=config.settings.base python manage.py collectstatic --noinput 2>/dev/null || true

EXPOSE 8000

CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "config.asgi:application"]
