FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy requirements file
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt
RUN python -m spacy download en_core_web_sm

# Copy the entire backend application
# We copy it into a "backend" directory because main.py is in backend/app/main.py
COPY backend/ ./backend/

# Expose port (Render sets the PORT environment variable)
EXPOSE 8080

# Command to run the application
# We use $PORT so Render can bind to the correct port dynamically
CMD uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT:-8080}
